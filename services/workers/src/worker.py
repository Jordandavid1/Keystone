"""
KEYSTONE Async Job Queue Worker (Bible v2 §12, §19, §23.4, §40.7; ADR-005 PR5).

Consumes queued creative/video jobs from Redis (falling back to in-process
asyncio.Queue when REDIS_URL is unset or the redis client library is unavailable),
cryptographically verifies ExecutionEnvelope v2 signature, expiry, nonce, and
content_mode before invoking ComfyUI or any video/image execution fabric, and
persists deterministic Job state-machine transitions and AuditEvent rows to DB.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

from sqlalchemy import select

from apps.api.src.db.models import AuditEvent, Job, User
from apps.api.src.jobs.state_machine import TERMINAL_STATES, normalize_state, transition
from packages.contracts.src.models import ExecutionEnvelope
from services.comfy.src.client import ComfyUIClient, comfy_client
from services.harness.src.envelope import CLOCK_SKEW_TOLERANCE_SECONDS, ENVELOPE_TTL_SECONDS, EnvelopeEngine, nonce_cache

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
        }


def _as_uuid_or_none(value: Optional[str]) -> Optional[str]:
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
            "RETRY_PENDING": ["QUEUED", "RUNNING"],
            "REPLAN_REQUIRED": ["PLANNING", "AUTHORIZING", "QUEUED", "RUNNING"],
        }
        return paths.get(cur, [tgt])

    if tgt == "COMPLETED":
        paths = {
            "RUNNING": ["VALIDATING_OUTPUT", "COMPLETED"],
            "VALIDATING_OUTPUT": ["COMPLETED"],
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


class KeystoneWorker:
    """
    Async worker consuming job payloads, enforcing ExecutionEnvelope v2 verification,
    driving DB Job state-machine transitions, and persisting durable AuditEvent rows.
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
    ) -> None:
        self.queue = queue or AsyncJobQueue()
        self.session_factory = session_factory
        self.comfy_client = comfy_client_instance or comfy_client
        self.executor = executor
        self.expected_mode = expected_mode
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.post_execute_hook = post_execute_hook
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
            evt_payload: Dict[str, Any] = {
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

    async def process_job(
        self,
        raw_payload: Union[Dict[str, Any], ExecutionEnvelope, str],
        *,
        db: Optional[Any] = None,
        expected_mode: Optional[str] = None,
        raise_on_reject: bool = False,
    ) -> WorkerResult:
        """
        Verify ExecutionEnvelope v2 before running any ComfyUI/video job, transition
        the DB Job row through the canonical state machine, and persist AuditEvents.
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
                            capability_id=payload.get("capability_id") or (env_dict or {}).get("capability_id") or "video.generation",
                            provider_id=payload.get("provider_id") or (env_dict or {}).get("provider_id") or "comfyui",
                            workflow_id=payload.get("workflow_id") or (env_dict or {}).get("workflow_id") or "wf_default",
                            workflow_version=payload.get("workflow_version") or (env_dict or {}).get("workflow_version") or "1.0.0",
                            status="QUEUED",
                            content_mode=req_mode or (env_dict or {}).get("content_mode"),
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

                # First validate signature, version, expiry, floor, age_verified, and mode without
                # mutating the nonce cache if invalid; then consume nonce unless real ComfyUIClient
                # will consume it right before HTTP submission.
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

            # 3. Execute verified workflow / job
            try:
                if self.executor is not None:
                    exec_output = await _maybe_await(self.executor(envelope_obj, payload, verified))
                else:
                    workflow_name = payload.get("workflow_name") or (env_dict or {}).get("workflow_id")
                    graph = payload.get("graph") or payload.get("workflow")
                    exec_output = await asyncio.to_thread(
                        client.execute_workflow,
                        envelope_obj,
                        workflow_name=workflow_name if graph is None else None,
                        graph=graph,
                        expected_mode=verified.get("content_mode"),
                    )
                    # Guarantee nonce consumption if an injected client didn't consume it
                    if check_nonce and not nonce_cache.has(verified["nonce"]):
                        nonce_cache.consume(verified["nonce"], ttl=ENVELOPE_TTL_SECONDS + CLOCK_SKEW_TOLERANCE_SECONDS)

                if self.post_execute_hook is not None:
                    await _maybe_await(self.post_execute_hook(job, envelope_obj, exec_output, session))

            except Exception as exec_exc:
                fail_code = _extract_failure_code(exec_exc, default="WORKER_EXECUTION_FAILED")
                fail_reason = f"{type(exec_exc).__name__}: {exec_exc}"
                audit_id = await self._advance_job(
                    session,
                    job=job,
                    raw_job_id=job_id,
                    raw_user_id=user_id,
                    target_state="FAILED",
                    reason=fail_reason,
                    event_type="worker.job_failed",
                    failure_code=fail_code,
                    extra_payload={"envelope_id": verified.get("envelope_id")},
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
                )

            # 4. Execution succeeded -> VALIDATING_OUTPUT -> COMPLETED
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
                extra_payload={"envelope_id": verified.get("envelope_id")},
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
