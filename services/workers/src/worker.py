"""
KEYSTONE Async Job Queue Worker (Bible v2 §12, §13.5, §14, §19, §23.4, §40.7; ADR-005 PR5 & PR7).

Consumes queued creative/video jobs from Redis (falling back to in-process
asyncio.Queue when REDIS_URL is unset or the redis client library is unavailable),
cryptographically verifies ExecutionEnvelope v2 signature, expiry, nonce, and
content_mode before invoking ComfyUI or any video/image execution fabric, runs the
post-execution KHF 5-family evaluator tank with bounded retries (`retry_loop.py`,
`KEYSTONE_EVAL_RETRY_MAX` default 3), persists `GenerationAttempt` + `HarnessRun`
rows to PostgreSQL/SQLite, and flags assets for operator review (`Asset.status = "needs_review"`,
`Asset.metadata_["review_required"] = True`) on retry budget exhaustion.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Union

from sqlalchemy import select

from apps.api.src.db.models import (
    Asset,
    AttemptAsset,
    AuditEvent,
    GenerationAttempt as DbGenerationAttempt,
    HarnessRun,
    Job,
    User,
)
from apps.api.src.jobs.state_machine import TERMINAL_STATES, normalize_state, transition
from packages.contracts.src.models import ExecutionEnvelope, HarnessResult, RetryPolicy
from services.comfy.src.client import ComfyUIClient, comfy_client
from services.harness.src.envelope import (
    CLOCK_SKEW_TOLERANCE_SECONDS,
    ENVELOPE_TTL_SECONDS,
    EnvelopeEngine,
    nonce_cache,
)
from services.harness.src.khf_quality import KHFQualityHarness
from services.harness.src.retry_loop import (
    BoundedRetryManager,
    RetryDecision,
    flag_asset_for_operator_review,
    get_eval_retry_max,
)

logger = logging.getLogger("keystone.workers")

DEFAULT_WORKER_QUEUE_KEY = "keystone:jobs:queue"


class WorkerEnvelopeRejected(ValueError):
    """Raised when a worker refuses an unsigned, invalid, or mode-mismatched envelope."""

    def __init__(self, code: str, reason: str, *, job_id: Optional[str] = None) -> None:
        self.code = code
        self.reason = reason
        self.job_id = job_id
        super().__init__(reason)


@dataclass
class WorkerResult:
    """Outcome returned by KeystoneWorker for a single consumed job payload."""

    job_id: str
    status: str
    accepted: bool
    reason_code: Optional[str] = None
    reason: Optional[str] = None
    envelope_id: Optional[str] = None
    content_mode: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    audit_event_id: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    attempt_count: int = 0
    review_required: bool = False
    asset_id: Optional[str] = None
    asset_status: Optional[str] = None
    retry_decision: Optional[Dict[str, Any]] = None
    harness_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "accepted": self.accepted,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "envelope_id": self.envelope_id,
            "content_mode": self.content_mode,
            "output": self.output,
            "audit_event_id": self.audit_event_id,
            "events": self.events,
            "attempt_count": self.attempt_count,
            "review_required": self.review_required,
            "asset_id": self.asset_id,
            "asset_status": self.asset_status,
            "retry_decision": self.retry_decision,
            "harness_results": self.harness_results,
        }


def _as_uuid_or_none(value: Optional[Any]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _extract_failure_code(exc: BaseException, default: str = "INVALID_ENVELOPE") -> str:
    msg = str(exc).strip()
    if ":" in msg:
        prefix = msg.split(":", 1)[0].strip()
        if prefix and " " not in prefix and len(prefix) <= 64:
            return prefix
    if msg and " " not in msg and len(msg) <= 64:
        return msg
    return default


def _parse_job_payload(
    raw_payload: Union[Dict[str, Any], ExecutionEnvelope, str],
) -> tuple[Dict[str, Any], Optional[Union[ExecutionEnvelope, Dict[str, Any]]], Optional[str]]:
    """
    Normalize raw queue item into (payload_dict, envelope_obj_or_none, parse_error).
    Supports wrapped payloads {"job_id": ..., "envelope": ...}, bare ExecutionEnvelope
    models/dicts, and serialized JSON strings.
    """
    if isinstance(raw_payload, ExecutionEnvelope):
        data = raw_payload.model_dump()
        return {"job_id": data.get("job_id"), "user_id": data.get("user_id"), "envelope": data}, raw_payload, None

    if isinstance(raw_payload, str):
        try:
            decoded = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            return {}, None, f"INVALID_JSON_PAYLOAD: {exc}"
        if not isinstance(decoded, dict):
            return {}, None, "INVALID_PAYLOAD_TYPE: Expected JSON object"
        raw_payload = decoded

    if not isinstance(raw_payload, dict):
        return {}, None, f"INVALID_PAYLOAD_TYPE: Expected dict or ExecutionEnvelope, got {type(raw_payload).__name__}"

    payload = dict(raw_payload)
    if "envelope" in payload:
        envelope_obj = payload.get("envelope")
    elif any(k in payload for k in ("signature", "envelope_id", "envelope_version", "nonce")):
        envelope_obj = payload
    else:
        envelope_obj = None

    return payload, envelope_obj, None


def _path_to_state(current_state: str, target_state: str) -> List[str]:
    """Compute a deterministic valid state-machine transition sequence."""
    cur = normalize_state(current_state)
    tgt = normalize_state(target_state)
    if cur == tgt:
        return []
    if cur in TERMINAL_STATES:
        transition(cur, tgt)  # Raises canonical ILLEGAL_TRANSITION

    if tgt == "REJECTED":
        paths = {
            "CREATED": ["REJECTED"],
            "VALIDATING": ["REJECTED"],
            "PLANNING": ["AUTHORIZING", "REJECTED"],
            "AUTHORIZING": ["REJECTED"],
            "QUEUED": ["REJECTED"],
            "RETRY_PENDING": ["QUEUED", "REJECTED"],
            "REPLAN_REQUIRED": ["PLANNING", "AUTHORIZING", "REJECTED"],
        }
        return paths.get(cur, [tgt])

    if tgt == "RUNNING":
        paths = {
            "CREATED": ["VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED", "RUNNING"],
            "VALIDATING": ["PLANNING", "AUTHORIZING", "QUEUED", "RUNNING"],
            "PLANNING": ["AUTHORIZING", "QUEUED", "RUNNING"],
            "AUTHORIZING": ["QUEUED", "RUNNING"],
            "QUEUED": ["RUNNING"],
            "VALIDATING_OUTPUT": ["RETRY_PENDING", "QUEUED", "RUNNING"],
            "RETRY_PENDING": ["QUEUED", "RUNNING"],
            "REPLAN_REQUIRED": ["PLANNING", "AUTHORIZING", "QUEUED", "RUNNING"],
        }
        return paths.get(cur, [tgt])

    if tgt == "VALIDATING_OUTPUT":
        paths = {
            "QUEUED": ["RUNNING", "VALIDATING_OUTPUT"],
            "RUNNING": ["VALIDATING_OUTPUT"],
            "RETRY_PENDING": ["QUEUED", "RUNNING", "VALIDATING_OUTPUT"],
        }
        return paths.get(cur, [tgt])

    if tgt == "RETRY_PENDING":
        paths = {
            "RUNNING": ["VALIDATING_OUTPUT", "RETRY_PENDING"],
            "VALIDATING_OUTPUT": ["RETRY_PENDING"],
        }
        return paths.get(cur, [tgt])

    if tgt == "REPLAN_REQUIRED":
        paths = {
            "RUNNING": ["VALIDATING_OUTPUT", "REPLAN_REQUIRED"],
            "VALIDATING_OUTPUT": ["REPLAN_REQUIRED"],
        }
        return paths.get(cur, [tgt])

    if tgt == "COMPLETED":
        paths = {
            "RUNNING": ["VALIDATING_OUTPUT", "COMPLETED"],
            "VALIDATING_OUTPUT": ["COMPLETED"],
            "RETRY_PENDING": ["QUEUED", "RUNNING", "VALIDATING_OUTPUT", "COMPLETED"],
            "REPLAN_REQUIRED": ["PLANNING", "AUTHORIZING", "QUEUED", "RUNNING", "VALIDATING_OUTPUT", "COMPLETED"],
        }
        return paths.get(cur, [tgt])

    if tgt == "FAILED":
        paths = {
            "CREATED": ["VALIDATING", "FAILED"],
            "VALIDATING": ["FAILED"],
            "PLANNING": ["FAILED"],
            "AUTHORIZING": ["PLANNING", "FAILED"],
            "QUEUED": ["FAILED"],
            "RUNNING": ["FAILED"],
            "VALIDATING_OUTPUT": ["FAILED"],
            "RETRY_PENDING": ["FAILED"],
            "REPLAN_REQUIRED": ["FAILED"],
        }
        return paths.get(cur, [tgt])

    return [tgt]


class AsyncJobQueue:
    """
    Redis-backed async FIFO job queue with an in-process asyncio.Queue fallback
    when REDIS_URL is unset or the redis async package is unavailable.
    """

    def __init__(
        self,
        queue_key: Optional[str] = None,
        *,
        redis_url: Optional[str] = None,
        redis_client: Optional[Any] = None,
    ) -> None:
        self.queue_key = queue_key or os.getenv("KEYSTONE_WORKER_QUEUE", DEFAULT_WORKER_QUEUE_KEY)
        self._explicit_redis_url = redis_url
        self._injected_redis = redis_client
        self._cached_redis: Any = None
        self._cached_redis_url: Optional[str] = None
        self._local_queue: Optional[asyncio.Queue[Dict[str, Any]]] = None
        self._local_loop: Optional[asyncio.AbstractEventLoop] = None

    def _resolve_redis_url(self) -> str:
        if self._explicit_redis_url is not None:
            return self._explicit_redis_url.strip()
        return os.getenv("REDIS_URL", "").strip()

    def _get_redis(self) -> Any:
        if self._injected_redis is not None:
            return self._injected_redis
        url = self._resolve_redis_url()
        if not url:
            return None
        if self._cached_redis is not None and self._cached_redis_url == url:
            return self._cached_redis
        try:
            import redis.asyncio as aioredis  # type: ignore

            self._cached_redis = aioredis.from_url(url, decode_responses=True)
            self._cached_redis_url = url
            return self._cached_redis
        except ImportError:
            return None

    def _get_local_queue(self) -> asyncio.Queue[Dict[str, Any]]:
        loop = asyncio.get_running_loop()
        if self._local_queue is None or self._local_loop is not loop:
            self._local_queue = asyncio.Queue()
            self._local_loop = loop
        return self._local_queue

    @property
    def backend(self) -> str:
        return "redis" if self._get_redis() is not None else "asyncio.Queue"

    async def enqueue(self, payload: Union[Dict[str, Any], ExecutionEnvelope, str]) -> str:
        """Push a job payload onto the Redis list or in-process asyncio.Queue fallback."""
        normalized, env_obj, parse_err = _parse_job_payload(payload)
        if parse_err:
            raise ValueError(parse_err)
        if isinstance(env_obj, ExecutionEnvelope):
            normalized["envelope"] = env_obj.model_dump()
        job_id = str(
            normalized.get("job_id")
            or (normalized.get("envelope") or {}).get("job_id", "")
            or ""
        ).strip()
        if job_id and not normalized.get("job_id"):
            normalized["job_id"] = job_id

        client = self._get_redis()
        if client is not None:
            serialized = json.dumps(normalized, default=str)
            await _maybe_await(client.rpush(self.queue_key, serialized))
            return job_id

        await self._get_local_queue().put(normalized)
        return job_id

    async def dequeue(self, timeout: float = 0.25) -> Optional[Dict[str, Any]]:
        """Pop the next job payload from Redis or asyncio.Queue fallback."""
        client = self._get_redis()
        if client is not None:
            deadline = time.monotonic() + max(0.0, float(timeout))
            if timeout >= 1.0 and hasattr(client, "blpop"):
                res = await _maybe_await(client.blpop(self.queue_key, timeout=max(1, int(timeout))))
                if not res:
                    return None
                raw = res[1] if isinstance(res, (list, tuple)) and len(res) >= 2 else res
                return _decode_queue_item(raw)
            while True:
                raw = await _maybe_await(client.lpop(self.queue_key))
                if raw is not None:
                    return _decode_queue_item(raw)
                if time.monotonic() >= deadline:
                    return None
                await asyncio.sleep(min(0.05, max(0.005, deadline - time.monotonic())))

        queue = self._get_local_queue()
        if timeout <= 0:
            try:
                return queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def size(self) -> int:
        client = self._get_redis()
        if client is not None:
            return int(await _maybe_await(client.llen(self.queue_key)))
        return self._get_local_queue().qsize()

    async def clear(self) -> None:
        client = self._get_redis()
        if client is not None:
            await _maybe_await(client.delete(self.queue_key))
            return
        queue = self._get_local_queue()
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break


def _decode_queue_item(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("INVALID_QUEUE_ITEM: Expected JSON object")
        return parsed
    if isinstance(raw, dict):
        return dict(raw)
    raise ValueError(f"INVALID_QUEUE_ITEM: Unsupported type {type(raw).__name__}")


@asynccontextmanager
async def _open_session(
    session_factory: Optional[Any],
    explicit_db: Optional[Any],
) -> AsyncGenerator[Any, None]:
    if explicit_db is not None:
        yield explicit_db
        return

    if session_factory is None:
        from apps.api.src.db.session import async_session_factory

        session_factory = async_session_factory

    sess = session_factory()
    if hasattr(sess, "__aenter__"):
        async with sess as s:
            yield s
    elif hasattr(sess, "__enter__"):
        with sess as s:
            yield s
    else:
        try:
            yield sess
        finally:
            close_fn = getattr(sess, "close", None)
            if callable(close_fn):
                await _maybe_await(close_fn())


def _is_bare_envelope_spy_output(
    exec_output: Any,
    payload: Dict[str, Any],
    has_existing_assets: bool,
    enforce_khf: bool,
) -> bool:
    """
    Detect the bare PR5 envelope-verification spy return `{"prompt_id": ..., "outputs": []}`
    where no artifact bytes, no asset rows, and no quality evaluation parameters were supplied.
    """
    if enforce_khf or has_existing_assets:
        return False
    if any(
        k in payload
        for k in (
            "asset_id",
            "asset",
            "evaluate",
            "enable_khf",
            "retry_policy",
            "max_attempts",
            "retry_max",
            "requested_text",
            "expected_text",
            "reference_assets",
        )
    ):
        return False
    if not isinstance(exec_output, dict):
        return False
    allowed_spy_keys = {"prompt_id", "outputs", "envelope_id", "job_id", "status"}
    if not set(exec_output.keys()).issubset(allowed_spy_keys):
        return False
    outputs_val = exec_output.get("outputs")
    if isinstance(outputs_val, list) and len(outputs_val) == 0 and "prompt_id" in exec_output:
        return True
    return False


def _coerce_to_harness_result(
    raw: Any,
    *,
    default_phase: str = "post-execution",
) -> Optional[HarnessResult]:
    if isinstance(raw, HarnessResult):
        return raw
    if isinstance(raw, dict) and ("verdict" in raw or "harness_id" in raw):
        v = str(raw.get("verdict") or "fail").lower()
        if v not in ("pass", "warn", "fail"):
            v = "fail"
        score_val = raw.get("score")
        if score_val is None:
            score_val = 1.0 if v == "pass" else 0.0
        return HarnessResult(
            harness_id=str(raw.get("harness_id") or KHFQualityHarness.HARNESS_ID),
            harness_version=str(raw.get("harness_version") or KHFQualityHarness.VERSION),
            phase=str(raw.get("phase") or default_phase),  # type: ignore[arg-type]
            verdict=v,  # type: ignore[arg-type]
            score=max(0.0, min(1.0, float(score_val))),
            reason_codes=list(raw.get("reason_codes") or raw.get("defects") or ([] if v == "pass" else ["EVALUATION_FAILED"])),
            evidence=dict(raw.get("evidence") or {}),
            runtime_ms=float(raw.get("runtime_ms") or 0.0),
        )
    if isinstance(raw, bool):
        return HarnessResult(
            harness_id=KHFQualityHarness.HARNESS_ID,
            harness_version=KHFQualityHarness.VERSION,
            phase=default_phase,  # type: ignore[arg-type]
            verdict="pass" if raw else "fail",
            score=1.0 if raw else 0.0,
            reason_codes=[] if raw else ["POST_EXECUTE_HOOK_FAILED"],
            evidence={},
            runtime_ms=0.0,
        )
    return None


class KeystoneWorker:
    """
    Async worker consuming job payloads, enforcing ExecutionEnvelope v2 verification,
    running post-execution KHF 5-family evaluation with bounded retries (`BoundedRetryManager`),
    driving DB Job state-machine transitions, and persisting durable `HarnessRun` & `AuditEvent` rows.
    """

    def __init__(
        self,
        *,
        queue: Optional[AsyncJobQueue] = None,
        session_factory: Optional[Any] = None,
        comfy_client_instance: Optional[Any] = None,
        executor: Optional[Callable[..., Any]] = None,
        expected_mode: Optional[str] = None,
        worker_id: Optional[str] = None,
        post_execute_hook: Optional[Callable[..., Any]] = None,
        evaluator: Optional[Callable[..., Any]] = None,
        retry_policy: Optional[RetryPolicy] = None,
        max_retries: Optional[int] = None,
        pass_threshold: float = KHFQualityHarness.PASS_THRESHOLD,
        enforce_khf: bool = False,
    ) -> None:
        self.queue = queue or AsyncJobQueue()
        self.session_factory = session_factory
        self.comfy_client = comfy_client_instance or comfy_client
        self.executor = executor
        self.expected_mode = expected_mode
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.post_execute_hook = post_execute_hook
        self.evaluator = evaluator
        self.retry_policy = retry_policy
        self.max_retries = max_retries
        self.pass_threshold = float(pass_threshold)
        self.enforce_khf = bool(enforce_khf)
        self._stop_requested = False

    async def enqueue_job(self, payload: Union[Dict[str, Any], ExecutionEnvelope, str]) -> str:
        return await self.queue.enqueue(payload)

    async def _record_event(
        self,
        db: Any,
        *,
        event_type: str,
        job: Optional[Job],
        raw_job_id: Optional[str],
        raw_user_id: Optional[str],
        payload: Dict[str, Any],
    ) -> str:
        event_id = str(uuid.uuid4())
        resolved_job_id = job.id if job is not None else _as_uuid_or_none(raw_job_id)
        resolved_user_id = job.user_id if job is not None else _as_uuid_or_none(raw_user_id)
        evt = AuditEvent(
            id=event_id,
            user_id=resolved_user_id,
            job_id=resolved_job_id,
            event_type=event_type,
            payload=payload,
        )
        db.add(evt)
        return event_id

    async def _advance_job(
        self,
        db: Any,
        *,
        job: Optional[Job],
        raw_job_id: str,
        raw_user_id: Optional[str],
        target_state: str,
        reason: str,
        event_type: str = "job.state_transition",
        failure_code: Optional[str] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
        recorded_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        now = datetime.now(timezone.utc)
        last_event_id: Optional[str] = None

        if job is None:
            evt_payload: Dict[str, Any] = {
                "job_id": raw_job_id or None,
                "state": target_state,
                "reason": reason,
                "worker_id": self.worker_id,
                "timestamp": now.isoformat(),
            }
            if failure_code:
                evt_payload["failure_code"] = failure_code
            if extra_payload:
                evt_payload.update(extra_payload)
            last_event_id = await self._record_event(
                db,
                event_type=event_type,
                job=None,
                raw_job_id=raw_job_id,
                raw_user_id=raw_user_id,
                payload=evt_payload,
            )
            if recorded_events is not None:
                recorded_events.append(evt_payload)
            return last_event_id

        if job is not None and target_state == "REJECTED" and job.status in TERMINAL_STATES:
            evt_payload = {
                "job_id": job.id,
                "previous_state": job.status,
                "state": "REJECTED",
                "reason": reason,
                "worker_id": self.worker_id,
                "timestamp": now.isoformat(),
                "terminal_state_preserved": job.status,
            }
            if failure_code:
                evt_payload["failure_code"] = failure_code
            if extra_payload:
                evt_payload.update(extra_payload)
            last_event_id = await self._record_event(
                db,
                event_type=event_type,
                job=job,
                raw_job_id=job.id,
                raw_user_id=job.user_id,
                payload=evt_payload,
            )
            if recorded_events is not None:
                recorded_events.append(evt_payload)
            return last_event_id

        steps = _path_to_state(job.status, target_state)
        if not steps:
            if failure_code and job.failure_code != failure_code:
                job.failure_code = failure_code
            job.updated_at = now
            return None

        for step in steps:
            prev = job.status
            new_state = transition(prev, step)
            job.status = new_state
            job.updated_at = now
            if new_state == "QUEUED" and job.queued_at is None:
                job.queued_at = now
            elif new_state == "RUNNING" and job.started_at is None:
                job.started_at = now
            elif new_state in TERMINAL_STATES:
                job.completed_at = now
                if failure_code and new_state in ("FAILED", "REJECTED"):
                    job.failure_code = failure_code

            is_final_step = step == steps[-1]
            step_event_type = event_type if is_final_step else "job.state_transition"
            evt_payload = {
                "job_id": job.id,
                "previous_state": prev,
                "state": new_state,
                "reason": reason if is_final_step else f"Advancing job to {new_state}",
                "worker_id": self.worker_id,
                "timestamp": now.isoformat(),
            }
            if is_final_step and failure_code:
                evt_payload["failure_code"] = failure_code
            if is_final_step and extra_payload:
                evt_payload.update(extra_payload)

            last_event_id = await self._record_event(
                db,
                event_type=step_event_type,
                job=job,
                raw_job_id=job.id,
                raw_user_id=job.user_id,
                payload=evt_payload,
            )
            if recorded_events is not None:
                recorded_events.append(evt_payload)

        return last_event_id

    async def _resolve_or_create_target_assets(
        self,
        session: Any,
        *,
        job: Optional[Job],
        user_id: Optional[str],
        payload: Dict[str, Any],
        exec_output: Any,
        verified: Dict[str, Any],
        create_if_missing: bool = False,
    ) -> List[Asset]:
        """Locate any `Asset` ORM rows associated with this job/attempt, or create one if needed."""
        assets: List[Asset] = []
        seen_ids: set[str] = set()

        def _add_asset(a: Optional[Asset]) -> None:
            if a is not None and isinstance(a, Asset):
                aid = str(a.id)
                if aid not in seen_ids:
                    seen_ids.add(aid)
                    assets.append(a)

        # 1. Direct Asset object in payload or exec_output
        if isinstance(payload.get("asset"), Asset):
            _add_asset(payload["asset"])
        if isinstance(exec_output, dict) and isinstance(exec_output.get("asset"), Asset):
            _add_asset(exec_output["asset"])

        # 2. Explicit asset_id in exec_output, payload, or outputs list
        candidate_ids: List[str] = []
        for src in (exec_output if isinstance(exec_output, dict) else {}, payload):
            aid = src.get("asset_id")
            if aid and str(aid) not in candidate_ids:
                candidate_ids.append(str(aid))
            out_list = src.get("outputs")
            if isinstance(out_list, list):
                for item in out_list:
                    if isinstance(item, dict) and item.get("asset_id"):
                        cid = str(item["asset_id"])
                        if cid not in candidate_ids:
                            candidate_ids.append(cid)

        for cid in candidate_ids:
            res = await _maybe_await(session.execute(select(Asset).where(Asset.id == cid)))
            found = res.scalar_one_or_none()
            _add_asset(found)

        # 3. Any Asset rows belonging to user_id if none matched explicit asset_id
        eff_user_id = user_id or (job.user_id if job is not None else None)
        if not assets and eff_user_id:
            stmt = select(Asset).where(Asset.user_id == eff_user_id, Asset.deleted_at.is_(None))
            if job is not None and job.project_id:
                stmt = stmt.where(Asset.project_id == job.project_id)
            res = await _maybe_await(session.execute(stmt))
            for row in res.scalars().all():
                _add_asset(row)

        # 4. Create an Asset row if requested and none existed in DB yet
        if not assets and create_if_missing and eff_user_id:
            user_check = await _maybe_await(session.execute(select(User).where(User.id == eff_user_id)))
            if user_check.scalar_one_or_none() is not None:
                new_aid = candidate_ids[0] if candidate_ids else str(uuid.uuid4())
                out_dict = exec_output if isinstance(exec_output, dict) else {}
                mime = str(out_dict.get("mime_type") or payload.get("mime_type") or "image/png")
                media_type = "video" if mime.startswith("video/") else ("audio" if mime.startswith("audio/") else "image")
                ext = ".mp4" if media_type == "video" else (".wav" if media_type == "audio" else ".png")
                filename = str(out_dict.get("filename") or payload.get("filename") or f"output_{new_aid[:8]}{ext}")
                storage_key = str(
                    out_dict.get("storage_key")
                    or payload.get("storage_key")
                    or f"tenants/{eff_user_id}/assets/{new_aid}/{filename}"
                )
                raw_bytes = out_dict.get("bytes") or out_dict.get("data") or out_dict.get("asset_bytes")
                size_bytes = len(raw_bytes) if isinstance(raw_bytes, (bytes, bytearray)) else int(out_dict.get("byte_size") or 0)

                new_asset = Asset(
                    id=new_aid,
                    user_id=eff_user_id,
                    project_id=job.project_id if job is not None else payload.get("project_id"),
                    asset_type=media_type,
                    storage_key=storage_key,
                    filename=filename,
                    mime_type=mime,
                    size_bytes=size_bytes,
                    status="ready",
                    metadata_={
                        "job_id": job.id if job is not None else verified.get("job_id"),
                        "envelope_id": verified.get("envelope_id"),
                    },
                    mature=(verified.get("content_mode") == "unrestricted"),
                )
                session.add(new_asset)
                await _maybe_await(session.flush())
                _add_asset(new_asset)

        return assets

    async def _invoke_hook_or_evaluator(
        self,
        fn: Callable[..., Any],
        *,
        job: Optional[Job],
        envelope_obj: Any,
        exec_output: Any,
        session: Any,
        attempt_number: int,
        payload: Dict[str, Any],
    ) -> Any:
        """Invoke a custom `post_execute_hook` or `evaluator` regardless of its parameter arity."""
        try:
            sig = inspect.signature(fn)
            params = list(sig.parameters.values())
            has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
            pos_params = [
                p
                for p in params
                if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]
            arity = len(pos_params)
        except (ValueError, TypeError):
            has_varargs = True
            arity = 4

        if has_varargs or arity >= 4:
            return await _maybe_await(fn(job, envelope_obj, exec_output, session))
        if arity == 3:
            return await _maybe_await(fn(job, envelope_obj, exec_output))
        if arity == 2:
            return await _maybe_await(fn(exec_output, session))
        if arity == 1:
            return await _maybe_await(fn(exec_output))
        return await _maybe_await(fn())

    async def _evaluate_attempt_output(
        self,
        session: Any,
        *,
        job: Optional[Job],
        envelope_obj: Any,
        env_dict: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
        verified: Dict[str, Any],
        exec_output: Any,
        attempt_number: int,
        attempt_id: str,
    ) -> HarnessResult:
        """
        Execute the worker post-execution evaluation hook for a single attempt and
        ensure a durable `HarnessRun` row is persisted in `session`.
        """
        eff_job_id = job.id if job is not None else _as_uuid_or_none(verified.get("job_id"))

        # Check how many HarnessRun rows exist for this job/attempt before hook execution
        before_count = 0
        if eff_job_id:
            cnt_res = await _maybe_await(
                session.execute(select(HarnessRun).where(HarnessRun.job_id == eff_job_id))
            )
            before_count = len(cnt_res.scalars().all())

        harness_res: Optional[HarnessResult] = None

        # 1. Custom post_execute_hook if configured
        if self.post_execute_hook is not None:
            hook_out = await self._invoke_hook_or_evaluator(
                self.post_execute_hook,
                job=job,
                envelope_obj=envelope_obj,
                exec_output=exec_output,
                session=session,
                attempt_number=attempt_number,
                payload=payload,
            )
            harness_res = _coerce_to_harness_result(hook_out)

        # 2. Custom evaluator if configured and post_execute_hook did not return a HarnessResult
        if harness_res is None and self.evaluator is not None:
            eval_out = await self._invoke_hook_or_evaluator(
                self.evaluator,
                job=job,
                envelope_obj=envelope_obj,
                exec_output=exec_output,
                session=session,
                attempt_number=attempt_number,
                payload=payload,
            )
            harness_res = _coerce_to_harness_result(eval_out)

        # 3. Direct HarnessResult or verdict dict returned by executor
        if harness_res is None:
            if isinstance(exec_output, HarnessResult):
                harness_res = exec_output
            elif isinstance(exec_output, dict) and isinstance(exec_output.get("harness_result"), (HarnessResult, dict)):
                harness_res = _coerce_to_harness_result(exec_output["harness_result"])
            elif isinstance(exec_output, dict) and "verdict" in exec_output and not any(
                k in exec_output for k in ("bytes", "asset_bytes", "data", "image_bytes", "video_bytes")
            ):
                harness_res = _coerce_to_harness_result(exec_output)

        # 4. Canonical 5-family KHFQualityHarness.evaluate_output
        if harness_res is None:
            args_dict = (env_dict or {}).get("arguments") or {}
            prompt_text = str(
                payload.get("prompt")
                or (exec_output.get("prompt") if isinstance(exec_output, dict) else None)
                or args_dict.get("prompt")
                or args_dict.get("positive_prompt")
                or ""
            )
            eval_input: Any = exec_output
            if isinstance(exec_output, dict):
                merged_input = dict(args_dict)
                merged_input.update(
                    {
                        k: v
                        for k, v in payload.items()
                        if k not in ("envelope",)
                    }
                )
                merged_input.update(exec_output)
                eval_input = merged_input

            harness_res = KHFQualityHarness.evaluate_output(
                eval_input,
                prompt=prompt_text,
                phase="post-execution",
                persona_id=(
                    payload.get("persona_id")
                    or (job.persona_id if job is not None else None)
                    or args_dict.get("persona_id")
                ),
                persona_sheet=payload.get("persona_sheet") or args_dict.get("persona_sheet"),
                reference_assets=(
                    payload.get("reference_assets")
                    or payload.get("reference_asset_ids")
                    or args_dict.get("reference_assets")
                ),
                content_mode=verified.get("content_mode") or "sfw",
                requested_text=payload.get("requested_text") or args_dict.get("requested_text"),
                expected_text=payload.get("expected_text") or args_dict.get("expected_text"),
                media_type=payload.get("media_type") or args_dict.get("media_type"),
                mime_type=payload.get("mime_type") or args_dict.get("mime_type"),
                is_retry=(attempt_number > 1),
                attempt_number=attempt_number,
                vlm_budget_pct=payload.get("vlm_budget_pct"),
                service_tier=payload.get("service_tier") or args_dict.get("service_tier"),
                vlm_provider=payload.get("vlm_provider"),
                ocr_hook=payload.get("ocr_hook"),
                run_ocr=payload.get("run_ocr"),
                run_vlm=payload.get("run_vlm"),
                run_temporal=payload.get("run_temporal"),
                run_identity=payload.get("run_identity"),
                db=None,  # We persist below with attempt_id & job_id
                job_id=eff_job_id,
                attempt_id=attempt_id,
            )

        # 5. Guarantee durable HarnessRun row persistence for this attempt
        after_count = before_count
        if eff_job_id:
            cnt_res2 = await _maybe_await(
                session.execute(select(HarnessRun).where(HarnessRun.job_id == eff_job_id))
            )
            after_count = len(cnt_res2.scalars().all())

        if after_count <= before_count:
            await KHFQualityHarness.persist_harness_run_async(
                session,
                harness_res,
                job_id=eff_job_id,
                attempt_id=attempt_id if job is not None else None,
                flush=True,
            )

        return harness_res

    async def process_job(
        self,
        raw_payload: Union[Dict[str, Any], ExecutionEnvelope, str],
        *,
        db: Optional[Any] = None,
        expected_mode: Optional[str] = None,
        raise_on_reject: bool = False,
    ) -> WorkerResult:
        """
        Verify ExecutionEnvelope v2 before running any ComfyUI/video job, execute
        bounded quality retry loop (`BoundedRetryManager`, up to `KEYSTONE_EVAL_RETRY_MAX`),
        persist `GenerationAttempt` + `HarnessRun` rows in DB, and flag `Asset` with
        `status="needs_review"` & `metadata_["review_required"] = True` on budget exhaustion.
        """
        payload, envelope_obj, parse_error = _parse_job_payload(raw_payload)
        env_dict: Optional[Dict[str, Any]] = None
        if isinstance(envelope_obj, ExecutionEnvelope):
            env_dict = envelope_obj.model_dump()
        elif isinstance(envelope_obj, dict):
            env_dict = dict(envelope_obj)

        job_id = str(
            payload.get("job_id")
            or (env_dict.get("job_id") if env_dict else "")
            or ""
        ).strip()
        user_id = str(
            payload.get("user_id")
            or payload.get("tenant_id")
            or (env_dict.get("user_id") if env_dict else "")
            or ""
        ).strip() or None

        req_mode = (
            expected_mode
            or payload.get("expected_mode")
            or payload.get("content_mode")
            or self.expected_mode
        )
        check_nonce = bool(payload.get("check_nonce", True))
        recorded_events: List[Dict[str, Any]] = []

        async with _open_session(self.session_factory, db) as session:
            job: Optional[Job] = None
            if job_id:
                res = await _maybe_await(session.execute(select(Job).where(Job.id == job_id)))
                job = res.scalar_one_or_none()
                if job is None and user_id:
                    user_res = await _maybe_await(session.execute(select(User).where(User.id == user_id)))
                    if user_res.scalar_one_or_none() is not None:
                        job = Job(
                            id=job_id,
                            user_id=user_id,
                            project_id=payload.get("project_id"),
                            capability_id=payload.get("capability_id") or (env_dict or {}).get("capability_id") or "video.generation",
                            provider_id=payload.get("provider_id") or (env_dict or {}).get("provider_id") or "comfyui",
                            workflow_id=payload.get("workflow_id") or (env_dict or {}).get("workflow_id") or "wf_default",
                            workflow_version=payload.get("workflow_version") or (env_dict or {}).get("workflow_version") or "1.0.0",
                            status="QUEUED",
                            content_mode=req_mode or (env_dict or {}).get("content_mode"),
                            persona_id=_as_uuid_or_none(payload.get("persona_id")),
                            queued_at=datetime.now(timezone.utc),
                        )
                        session.add(job)
                        await _maybe_await(session.flush())

            if job is not None:
                user_id = user_id or job.user_id

            job_mode = getattr(job, "content_mode", None) if job is not None else None
            resolved_expected_mode = req_mode or job_mode

            client = self.comfy_client
            is_real_comfy_exec = (
                self.executor is None
                and getattr(getattr(client, "execute_workflow", None), "__func__", None)
                is ComfyUIClient.execute_workflow
            )

            # 1. Verify ExecutionEnvelope v2 BEFORE any execution
            verified: Optional[Dict[str, Any]] = None
            rejection_code: Optional[str] = None
            rejection_reason: Optional[str] = None

            try:
                if parse_error:
                    raise ValueError(parse_error)
                if envelope_obj is None:
                    raise ValueError("MISSING_ENVELOPE: Signed ExecutionEnvelope v2 is required")
                if req_mode and job_mode and req_mode != job_mode:
                    raise ValueError(
                        f"ENVELOPE_MODE_MISMATCH: Job content_mode={job_mode} conflicts with expected_mode={req_mode}"
                    )
                if payload.get("job_id") and env_dict and env_dict.get("job_id") and str(payload["job_id"]) != str(env_dict["job_id"]):
                    raise ValueError(
                        f"ENVELOPE_JOB_MISMATCH: Payload job_id '{payload['job_id']}' != envelope job_id '{env_dict['job_id']}'"
                    )
                if payload.get("user_id") and env_dict and env_dict.get("user_id") and str(payload["user_id"]) != str(env_dict["user_id"]):
                    raise ValueError(
                        f"ENVELOPE_USER_MISMATCH: Payload user_id '{payload['user_id']}' != envelope user_id '{env_dict['user_id']}'"
                    )

                verified = EnvelopeEngine.verify_envelope(
                    envelope_obj,
                    expected_mode=resolved_expected_mode,
                    check_nonce=False,
                )
                if check_nonce and nonce_cache.has(verified["nonce"]):
                    raise ValueError(f"REPLAY_ATTACK_DETECTED: Nonce {verified['nonce']} has already been consumed")
                if check_nonce and not is_real_comfy_exec:
                    verified = EnvelopeEngine.verify_envelope(
                        envelope_obj,
                        expected_mode=resolved_expected_mode,
                        check_nonce=True,
                    )
            except (ValueError, RuntimeError) as exc:
                rejection_code = _extract_failure_code(exc, default="INVALID_ENVELOPE")
                rejection_reason = str(exc)

            if rejection_code is not None:
                logger.warning("Worker %s rejected job %s: %s", self.worker_id, job_id or "<unknown>", rejection_reason)
                audit_id = await self._advance_job(
                    session,
                    job=job,
                    raw_job_id=job_id,
                    raw_user_id=user_id,
                    target_state="REJECTED",
                    reason=rejection_reason or rejection_code,
                    event_type="worker.envelope_rejected",
                    failure_code=rejection_code,
                    extra_payload={
                        "expected_mode": resolved_expected_mode,
                        "envelope_mode": env_dict.get("content_mode") if env_dict else None,
                        "envelope_id": env_dict.get("envelope_id") if env_dict else None,
                    },
                    recorded_events=recorded_events,
                )
                await _maybe_await(session.commit())

                if raise_on_reject:
                    raise WorkerEnvelopeRejected(rejection_code, rejection_reason or rejection_code, job_id=job_id or None)

                return WorkerResult(
                    job_id=job.id if job is not None else job_id,
                    status="REJECTED",
                    accepted=False,
                    reason_code=rejection_code,
                    reason=rejection_reason,
                    envelope_id=env_dict.get("envelope_id") if env_dict else None,
                    content_mode=env_dict.get("content_mode") if env_dict else None,
                    audit_event_id=audit_id,
                    events=recorded_events,
                )

            assert verified is not None

            # 2. Envelope verified -> bind envelope metadata & advance Job to RUNNING
            if job is not None and env_dict is not None:
                job.envelope = env_dict
                parsed_env_uuid = _as_uuid_or_none(env_dict.get("envelope_id"))
                if parsed_env_uuid:
                    job.envelope_id = parsed_env_uuid
                job.content_mode = verified.get("content_mode")

            job_t0 = time.perf_counter()
            total_eval_ms = 0
            raw_credit_cost = payload.get("credit_cost") or payload.get("hold_credits")
            credit_held_amount = 0
            if raw_credit_cost and int(raw_credit_cost) > 0 and job is not None and user_id:
                from apps.api.src.services.credits import hold_for_job_async

                try:
                    await hold_for_job_async(
                        session,
                        user_id=user_id,
                        job_id=job.id,
                        amount=int(raw_credit_cost),
                        content_mode=verified.get("content_mode") or "sfw",
                        idempotency_key=f"hold:{job.id}",
                    )
                    credit_held_amount = int(raw_credit_cost)
                except ValueError as cred_exc:
                    fail_code = _extract_failure_code(cred_exc, default="INSUFFICIENT_CREDITS")
                    fail_reason = str(cred_exc)
                    audit_id = await self._advance_job(
                        session,
                        job=job,
                        raw_job_id=job_id,
                        raw_user_id=user_id,
                        target_state="FAILED",
                        reason=fail_reason,
                        event_type="worker.credit_hold_failed",
                        failure_code=fail_code,
                        extra_payload={"envelope_id": verified.get("envelope_id")},
                        recorded_events=recorded_events,
                    )
                    await _maybe_await(session.commit())
                    return WorkerResult(
                        job_id=job.id,
                        status="FAILED",
                        accepted=False,
                        reason_code=fail_code,
                        reason=fail_reason,
                        envelope_id=verified.get("envelope_id"),
                        content_mode=verified.get("content_mode"),
                        audit_event_id=audit_id,
                        events=recorded_events,
                    )

            await self._advance_job(
                session,
                job=job,
                raw_job_id=job_id,
                raw_user_id=user_id,
                target_state="RUNNING",
                reason=f"Verified ExecutionEnvelope v2 ({verified.get('envelope_id')}); starting execution",
                event_type="job.state_transition",
                extra_payload={"envelope_id": verified.get("envelope_id"), "content_mode": verified.get("content_mode")},
                recorded_events=recorded_events,
            )
            await _maybe_await(session.commit())

            # 3. Configure BoundedRetryManager (`KEYSTONE_EVAL_RETRY_MAX`, default 3)
            raw_policy = payload.get("retry_policy") or self.retry_policy
            if isinstance(raw_policy, dict):
                active_policy = RetryPolicy(**raw_policy)
            elif isinstance(raw_policy, RetryPolicy):
                active_policy = raw_policy
            else:
                max_att = (
                    payload.get("max_attempts")
                    or payload.get("retry_max")
                    or self.max_retries
                )
                resolved_max = get_eval_retry_max(int(max_att) if max_att is not None else None)
                active_policy = RetryPolicy(
                    max_attempts=min(10, max(1, resolved_max)),
                    max_total_runtime_seconds=int(payload.get("max_total_runtime_seconds") or 300),
                    max_estimated_cost=float(payload.get("max_estimated_cost") or 10.0),
                )

            eff_threshold = float(payload.get("pass_threshold") or self.pass_threshold)
            retry_manager = BoundedRetryManager(policy=active_policy, pass_threshold=eff_threshold)

            existing_assets = await self._resolve_or_create_target_assets(
                session,
                job=job,
                user_id=user_id,
                payload=payload,
                exec_output=None,
                verified=verified,
                create_if_missing=False,
            )

            exec_output: Any = None
            latest_harness_result: Optional[HarnessResult] = None
            latest_decision: Optional[RetryDecision] = None
            collected_harness_dicts: List[Dict[str, Any]] = []
            current_payload = dict(payload)

            # 4. Execute workflow + post-execution KHF evaluation + bounded retry loop
            while True:
                attempt_idx = len(retry_manager.attempts) + 1
                attempt_id = str(uuid.uuid4())
                attempt_started = datetime.now(timezone.utc)
                attempt_t0 = time.perf_counter()

                try:
                    if self.executor is not None:
                        exec_output = await _maybe_await(self.executor(envelope_obj, current_payload, verified))
                    else:
                        workflow_name = current_payload.get("workflow_name") or (env_dict or {}).get("workflow_id")
                        graph = current_payload.get("graph") or current_payload.get("workflow")
                        exec_output = await asyncio.to_thread(
                            client.execute_workflow,
                            envelope_obj,
                            workflow_name=workflow_name if graph is None else None,
                            graph=graph,
                            expected_mode=verified.get("content_mode"),
                        )
                        if check_nonce and not nonce_cache.has(verified["nonce"]):
                            nonce_cache.consume(verified["nonce"], ttl=ENVELOPE_TTL_SECONDS + CLOCK_SKEW_TOLERANCE_SECONDS)
                except Exception as exec_exc:
                    fail_code = _extract_failure_code(exec_exc, default="WORKER_EXECUTION_FAILED")
                    fail_reason = f"{type(exec_exc).__name__}: {exec_exc}"
                    if credit_held_amount > 0 and job is not None and user_id:
                        from apps.api.src.services.credits import release_hold_async

                        await release_hold_async(
                            session,
                            user_id=user_id,
                            job_id=job.id,
                            reason=fail_code,
                        )
                    audit_id = await self._advance_job(
                        session,
                        job=job,
                        raw_job_id=job_id,
                        raw_user_id=user_id,
                        target_state="FAILED",
                        reason=fail_reason,
                        event_type="worker.job_failed",
                        failure_code=fail_code,
                        extra_payload={"envelope_id": verified.get("envelope_id"), "attempt": attempt_idx},
                        recorded_events=recorded_events,
                    )
                    await _maybe_await(session.commit())
                    return WorkerResult(
                        job_id=job.id if job is not None else job_id,
                        status="FAILED",
                        accepted=True,
                        reason_code=fail_code,
                        reason=fail_reason,
                        envelope_id=verified.get("envelope_id"),
                        content_mode=verified.get("content_mode"),
                        audit_event_id=audit_id,
                        events=recorded_events,
                        attempt_count=attempt_idx,
                    )

                attempt_runtime_s = max(0.001, time.perf_counter() - attempt_t0)
                attempt_cost = float(
                    (exec_output.get("cost") if isinstance(exec_output, dict) else None)
                    or current_payload.get("attempt_cost")
                    or 1.0
                )

                # If this is a bare PR5 envelope-only spy with no outputs/bytes/assets/hooks, complete immediately
                if (
                    self.post_execute_hook is None
                    and self.evaluator is None
                    and _is_bare_envelope_spy_output(exec_output, current_payload, bool(existing_assets), self.enforce_khf)
                ):
                    break

                # Persist GenerationAttempt row in DB when Job row exists (so HarnessRun.attempt_id FK is satisfied)
                prompt_hash_val = str(
                    (env_dict or {}).get("compiled_prompt_id")
                    or current_payload.get("prompt_hash")
                    or hashlib.sha256(str(job_id or attempt_id).encode("utf-8")).hexdigest()
                )
                cap_id_val = str(
                    (job.capability_id if job is not None else None)
                    or (env_dict or {}).get("capability_id")
                    or current_payload.get("capability_id")
                    or "image.generation"
                )
                prov_id_val = str(
                    (job.provider_id if job is not None else None)
                    or (env_dict or {}).get("provider_id")
                    or current_payload.get("provider_id")
                    or "comfyui"
                )
                wf_ver_val = str(
                    (job.workflow_version if job is not None else None)
                    or (env_dict or {}).get("workflow_version")
                    or "1.0.0"
                )

                db_attempt: Optional[DbGenerationAttempt] = None
                if job is not None:
                    db_attempt = DbGenerationAttempt(
                        attempt_id=attempt_id,
                        job_id=job.id,
                        provider_id=prov_id_val,
                        capability_id=cap_id_val,
                        prompt_hash=prompt_hash_val,
                        workflow_version=wf_ver_val,
                        seed=int(current_payload["seed"]) if isinstance(current_payload.get("seed"), int) else None,
                        started_at=attempt_started,
                        completed_at=datetime.now(timezone.utc),
                        success=True,
                        output_asset_ids=[],
                        metrics={"runtime_seconds": round(attempt_runtime_s, 4), "cost": attempt_cost},
                        resource_cost={"credits": attempt_cost},
                    )
                    session.add(db_attempt)
                    await _maybe_await(session.flush())

                # Advance Job to VALIDATING_OUTPUT before running KHF evaluation
                await self._advance_job(
                    session,
                    job=job,
                    raw_job_id=job_id,
                    raw_user_id=user_id,
                    target_state="VALIDATING_OUTPUT",
                    reason=f"Evaluating attempt {attempt_idx} output via KHF evaluator tank",
                    event_type="job.state_transition",
                    extra_payload={"attempt_number": attempt_idx, "attempt_id": attempt_id},
                    recorded_events=recorded_events,
                )

                # Run KHF post-execution evaluation and persist HarnessRun row in DB
                eval_t0 = time.perf_counter()
                latest_harness_result = await self._evaluate_attempt_output(
                    session,
                    job=job,
                    envelope_obj=envelope_obj,
                    env_dict=env_dict,
                    payload=current_payload,
                    verified=verified,
                    exec_output=exec_output,
                    attempt_number=attempt_idx,
                    attempt_id=attempt_id,
                )
                total_eval_ms += max(1, int((time.perf_counter() - eval_t0) * 1000))
                collected_harness_dicts.append(latest_harness_result.model_dump())

                attempt_passed = (
                    latest_harness_result.verdict == "pass"
                    and (latest_harness_result.score is None or float(latest_harness_result.score) >= eff_threshold)
                )
                fail_code_att = (
                    latest_harness_result.reason_codes[0]
                    if (not attempt_passed and latest_harness_result.reason_codes)
                    else (None if attempt_passed else "QUALITY_BELOW_THRESHOLD")
                )

                if db_attempt is not None:
                    db_attempt.success = attempt_passed
                    db_attempt.failure_code = fail_code_att

                retry_manager.record_attempt(
                    job_id=job.id if job is not None else (job_id or "job_unknown"),
                    provider_id=prov_id_val,
                    capability_id=cap_id_val,
                    prompt_hash=prompt_hash_val,
                    success=attempt_passed,
                    cost=attempt_cost,
                    runtime_seconds=attempt_runtime_s,
                    failure_code=fail_code_att,
                    attempt_id=attempt_id,
                    workflow_version=wf_ver_val,
                )

                latest_decision = retry_manager.evaluate_retry(
                    latest_harness_result=latest_harness_result,
                    pass_threshold=eff_threshold,
                )

                if latest_decision.action == "PASS":
                    break

                if latest_decision.action == "RETRY":
                    # Bounded retry permitted: advance VALIDATING_OUTPUT -> RETRY_PENDING -> QUEUED -> RUNNING
                    await self._advance_job(
                        session,
                        job=job,
                        raw_job_id=job_id,
                        raw_user_id=user_id,
                        target_state="RETRY_PENDING",
                        reason=latest_decision.reason,
                        event_type="worker.retry_scheduled",
                        failure_code=fail_code_att,
                        extra_payload={
                            "attempt_number": attempt_idx,
                            "next_attempt": latest_decision.attempt_number,
                            "recommended_adjustments": latest_decision.recommended_adjustments,
                        },
                        recorded_events=recorded_events,
                    )
                    await self._advance_job(
                        session,
                        job=job,
                        raw_job_id=job_id,
                        raw_user_id=user_id,
                        target_state="RUNNING",
                        reason=f"Starting bounded retry attempt {latest_decision.attempt_number}",
                        event_type="job.state_transition",
                        extra_payload={"attempt_number": latest_decision.attempt_number},
                        recorded_events=recorded_events,
                    )
                    await _maybe_await(session.flush())

                    # Apply recommended adjustments for next attempt
                    current_payload = dict(current_payload)
                    current_payload.update(latest_decision.recommended_adjustments)
                    current_payload["is_retry"] = True
                    current_payload["attempt_number"] = latest_decision.attempt_number
                    continue

                # Budget exhausted (action in ("REPLAN", "ABORT")) -> escalate asset to operator review!
                target_assets = await self._resolve_or_create_target_assets(
                    session,
                    job=job,
                    user_id=user_id,
                    payload=current_payload,
                    exec_output=exec_output,
                    verified=verified,
                    create_if_missing=True,
                )
                primary_asset_id: Optional[str] = None
                for target_asset in target_assets:
                    flag_asset_for_operator_review(
                        target_asset,
                        reason=latest_decision.reason,
                        reason_codes=list(latest_harness_result.reason_codes),
                        attempt_count=len(retry_manager.attempts),
                    )
                    if primary_asset_id is None:
                        primary_asset_id = str(target_asset.id)
                    if db_attempt is not None:
                        if str(target_asset.id) not in (db_attempt.output_asset_ids or []):
                            db_attempt.output_asset_ids = [*(db_attempt.output_asset_ids or []), str(target_asset.id)]

                exhausted_code = (
                    latest_harness_result.reason_codes[0]
                    if latest_harness_result.reason_codes
                    else "EVAL_RETRY_BUDGET_EXHAUSTED"
                )
                if job is not None:
                    job.failure_code = exhausted_code
                    job.outputs = [
                        {
                            "asset_id": str(a.id),
                            "status": a.status,
                            "review_required": bool((a.metadata_ or {}).get("review_required", True)),
                            "reason": latest_decision.reason,
                        }
                        for a in target_assets
                    ]

                audit_id = await self._advance_job(
                    session,
                    job=job,
                    raw_job_id=job_id,
                    raw_user_id=user_id,
                    target_state="REPLAN_REQUIRED" if latest_decision.action == "REPLAN" else "FAILED",
                    reason=f"Operator review required after {len(retry_manager.attempts)} attempts: {latest_decision.reason}",
                    event_type="worker.operator_review_required",
                    failure_code=exhausted_code,
                    extra_payload={
                        "envelope_id": verified.get("envelope_id"),
                        "attempt_count": len(retry_manager.attempts),
                        "review_required": True,
                        "asset_id": primary_asset_id,
                        "asset_status": "needs_review",
                        "retry_decision": latest_decision.to_dict(),
                    },
                    recorded_events=recorded_events,
                )
                await _maybe_await(session.commit())

                out_dict: Dict[str, Any] = (
                    dict(exec_output)
                    if isinstance(exec_output, dict)
                    else {"result": exec_output}
                )
                out_dict.update(
                    {
                        "review_required": True,
                        "asset_id": primary_asset_id,
                        "asset_status": "needs_review",
                        "status": "needs_review",
                        "attempt_count": len(retry_manager.attempts),
                        "retry_decision": latest_decision.to_dict(),
                    }
                )

                return WorkerResult(
                    job_id=job.id if job is not None else job_id,
                    status="needs_review",
                    accepted=True,
                    reason_code=exhausted_code,
                    reason=latest_decision.reason,
                    envelope_id=verified.get("envelope_id"),
                    content_mode=verified.get("content_mode"),
                    output=out_dict,
                    audit_event_id=audit_id,
                    events=recorded_events,
                    attempt_count=len(retry_manager.attempts),
                    review_required=True,
                    asset_id=primary_asset_id,
                    asset_status="needs_review",
                    retry_decision=latest_decision.to_dict(),
                    harness_results=collected_harness_dicts,
                )

            # 5. Execution & KHF quality evaluation succeeded -> VALIDATING_OUTPUT -> COMPLETED
            passing_assets = await self._resolve_or_create_target_assets(
                session,
                job=job,
                user_id=user_id,
                payload=current_payload,
                exec_output=exec_output,
                verified=verified,
                create_if_missing=False,
            )
            primary_pass_asset_id = str(passing_assets[0].id) if passing_assets else None

            if passing_assets:
                from apps.api.src.services.c2pa_credentials import sign_c2pa_manifest

                raw_out_bytes = (
                    exec_output.get("bytes") or exec_output.get("data")
                    if isinstance(exec_output, dict)
                    else None
                )
                for asset_row in passing_assets:
                    if getattr(asset_row, "c2pa_manifest", None) is None:
                        if isinstance(raw_out_bytes, (bytes, bytearray)) and not getattr(asset_row, "checksum", None):
                            asset_row.checksum = hashlib.sha256(bytes(raw_out_bytes)).hexdigest()
                        asset_row.c2pa_manifest = sign_c2pa_manifest(
                            asset_id=str(asset_row.id),
                            job_id=str(job.id if job is not None else verified.get("job_id") or asset_row.id),
                            user_id=str(asset_row.user_id),
                            asset_bytes=bytes(raw_out_bytes) if isinstance(raw_out_bytes, (bytes, bytearray)) else None,
                            asset_sha256=getattr(asset_row, "checksum", None),
                            fabric=str((job.provider_id if job is not None else None) or "comfyui"),
                            content_mode=str(verified.get("content_mode") or "sfw"),
                            title=getattr(asset_row, "filename", None) or f"Keystone Asset {asset_row.id}",
                        )

            total_runtime_s = max(0.001, time.perf_counter() - job_t0)
            if credit_held_amount > 0 and job is not None and user_id:
                from apps.api.src.services.credits import settle_hold_async

                actual_cost = int(payload.get("actual_credit_cost") or credit_held_amount)
                await settle_hold_async(
                    session,
                    user_id=user_id,
                    job_id=job.id,
                    actual_amount=actual_cost,
                    capability_id=(job.capability_id if job is not None else None) or "image.generation",
                    vram_minutes=round(total_runtime_s / 60.0, 4),
                    gpu_seconds=round(total_runtime_s, 3),
                    evaluator_ms=max(1, total_eval_ms),
                )

            if job is not None and isinstance(exec_output, dict):
                outputs_list = exec_output.get("outputs")
                if isinstance(outputs_list, list):
                    job.outputs = outputs_list
                else:
                    job.outputs = [
                        {
                            k: v
                            for k, v in exec_output.items()
                            if k in ("prompt_id", "envelope_id", "job_id", "asset_id", "mime_type", "url")
                        }
                    ]

            audit_id = await self._advance_job(
                session,
                job=job,
                raw_job_id=job_id,
                raw_user_id=user_id,
                target_state="COMPLETED",
                reason="Worker execution validated and completed",
                event_type="worker.job_completed",
                extra_payload={
                    "envelope_id": verified.get("envelope_id"),
                    "attempt_count": max(1, len(retry_manager.attempts)),
                },
                recorded_events=recorded_events,
            )
            await _maybe_await(session.commit())

            return WorkerResult(
                job_id=job.id if job is not None else job_id,
                status="COMPLETED",
                accepted=True,
                envelope_id=verified.get("envelope_id"),
                content_mode=verified.get("content_mode"),
                output=exec_output if isinstance(exec_output, dict) else {"result": exec_output},
                audit_event_id=audit_id,
                events=recorded_events,
                attempt_count=max(1, len(retry_manager.attempts)),
                review_required=False,
                asset_id=primary_pass_asset_id,
                asset_status="ready" if primary_pass_asset_id else None,
                retry_decision=latest_decision.to_dict() if latest_decision else None,
                harness_results=collected_harness_dicts,
            )

    async def run_once(
        self,
        *,
        timeout: float = 0.25,
        db: Optional[Any] = None,
        expected_mode: Optional[str] = None,
    ) -> Optional[WorkerResult]:
        """Dequeue and process a single job if available."""
        item = await self.queue.dequeue(timeout=timeout)
        if item is None:
            return None
        return await self.process_job(item, db=db, expected_mode=expected_mode)

    async def run_until_empty(
        self,
        *,
        db: Optional[Any] = None,
        expected_mode: Optional[str] = None,
        max_jobs: Optional[int] = None,
    ) -> List[WorkerResult]:
        """Drain all currently queued jobs and return their WorkerResults."""
        results: List[WorkerResult] = []
        while max_jobs is None or len(results) < max_jobs:
            res = await self.run_once(timeout=0.0, db=db, expected_mode=expected_mode)
            if res is None:
                break
            results.append(res)
        return results

    async def run_forever(self, *, poll_timeout: float = 0.5) -> None:
        """Continuously consume jobs until stop() is called."""
        self._stop_requested = False
        while not self._stop_requested:
            try:
                await self.run_once(timeout=poll_timeout)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Unhandled error in worker loop: %s", exc)
                await asyncio.sleep(0.1)

    def stop(self) -> None:
        self._stop_requested = True


__all__ = [
    "DEFAULT_WORKER_QUEUE_KEY",
    "AsyncJobQueue",
    "KeystoneWorker",
    "WorkerEnvelopeRejected",
    "WorkerResult",
]
