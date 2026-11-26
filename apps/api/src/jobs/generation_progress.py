"""
Live progress for studio generations (/v1/studio/generate).

The generate call runs synchronously (or in async background mode), so the studio
passes a job id with the request and polls GET /v1/studio/jobs/{job_id} while it
is in flight. Each state below is recorded at the moment the router actually
reaches that step, and every move is checked against the canonical job state
machine (Bible §19).

Backed by Redis when REDIS_URL is configured (and the redis client is installed),
with a thread-safe in-memory fallback store for single-process local/test runs
when REDIS_URL is unset.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, Optional

from apps.api.src.jobs.state_machine import TERMINAL_STATES, transition

# Finished records are dropped after this long so the registry can't grow unbounded.
_FINISHED_TTL_SECONDS = 3600
_ACTIVE_TTL_SECONDS = 86400


class JobIdConflict(ValueError):
    pass


def _now() -> float:
    return time.time()


class RedisBackedProgressStore:
    """
    Redis-backed job progress store with thread-safe local fallback when
    REDIS_URL is unset or the redis library is unavailable.
    """

    def __init__(self, key_prefix: str = "keystone:job_progress:") -> None:
        self._key_prefix = key_prefix
        self._lock = threading.Lock()
        self._fallback_records: Dict[str, Dict[str, Any]] = {}
        self._redis_client: Any = None
        self._redis_url: Optional[str] = None

    def _get_redis(self) -> Any:
        redis_url = os.getenv("REDIS_URL", "").strip()
        if not redis_url:
            return None
        if self._redis_client is not None and self._redis_url == redis_url:
            return self._redis_client
        try:
            import redis  # type: ignore

            self._redis_client = redis.from_url(redis_url, decode_responses=True)
            self._redis_url = redis_url
            return self._redis_client
        except ImportError:
            return None

    def _key(self, job_id: str) -> str:
        return f"{self._key_prefix}{job_id}"

    def _prune_locked(self, now: float) -> None:
        stale = [
            jid
            for jid, rec in self._fallback_records.items()
            if rec["state"] in TERMINAL_STATES and now - rec["updated_at"] > _FINISHED_TTL_SECONDS
        ]
        for jid in stale:
            self._fallback_records.pop(jid, None)

    def create(self, job_id: str, record: Dict[str, Any]) -> None:
        client = self._get_redis()
        if client is not None:
            created = client.set(
                self._key(job_id),
                json.dumps(record),
                nx=True,
                ex=_ACTIVE_TTL_SECONDS,
            )
            if not created:
                raise JobIdConflict(f"job_id {job_id} is already in use")
            return

        now = _now()
        with self._lock:
            self._prune_locked(now)
            if job_id in self._fallback_records:
                raise JobIdConflict(f"job_id {job_id} is already in use")
            self._fallback_records[job_id] = record

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        client = self._get_redis()
        if client is not None:
            raw = client.get(self._key(job_id))
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)

        with self._lock:
            rec = self._fallback_records.get(job_id)
            if rec is None:
                return None
            return {
                **rec,
                "events": [dict(e) for e in rec["events"]],
            }

    def update_transition(self, job_id: str, next_state: str, reason: str) -> str:
        client = self._get_redis()
        if client is not None:
            raw = client.get(self._key(job_id))
            if not raw:
                raise KeyError(f"Unknown job_id {job_id}")
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            rec = json.loads(raw)
            rec["state"] = transition(rec["state"], next_state)
            rec["updated_at"] = _now()
            rec["events"].append({"state": next_state, "at": rec["updated_at"], "reason": reason})
            ttl = _FINISHED_TTL_SECONDS if rec["state"] in TERMINAL_STATES else _ACTIVE_TTL_SECONDS
            client.set(self._key(job_id), json.dumps(rec), ex=ttl)
            return rec["state"]

        with self._lock:
            rec = self._fallback_records[job_id]
            rec["state"] = transition(rec["state"], next_state)
            rec["updated_at"] = _now()
            rec["events"].append({"state": next_state, "at": rec["updated_at"], "reason": reason})
            return rec["state"]

    def mark_failed(self, job_id: str, detail: str) -> None:
        client = self._get_redis()
        if client is not None:
            raw = client.get(self._key(job_id))
            if not raw:
                return
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            rec = json.loads(raw)
            if rec["state"] in TERMINAL_STATES:
                return
            rec["state"] = "FAILED"
            rec["error"] = detail
            rec["updated_at"] = _now()
            rec["events"].append({"state": "FAILED", "at": rec["updated_at"], "reason": detail})
            client.set(self._key(job_id), json.dumps(rec), ex=_FINISHED_TTL_SECONDS)
            return

        with self._lock:
            rec = self._fallback_records[job_id]
            if rec["state"] in TERMINAL_STATES:
                return
            rec["state"] = "FAILED"
            rec["error"] = detail
            rec["updated_at"] = _now()
            rec["events"].append({"state": "FAILED", "at": rec["updated_at"], "reason": detail})

    def set_result(self, job_id: str, result: Dict[str, Any]) -> None:
        client = self._get_redis()
        if client is not None:
            raw = client.get(self._key(job_id))
            if not raw:
                return
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            rec = json.loads(raw)
            rec["result"] = result
            rec["updated_at"] = _now()
            ttl = _FINISHED_TTL_SECONDS if rec["state"] in TERMINAL_STATES else _ACTIVE_TTL_SECONDS
            client.set(self._key(job_id), json.dumps(rec), ex=ttl)
            return

        with self._lock:
            rec = self._fallback_records.get(job_id)
            if rec is None:
                return
            rec["result"] = result
            rec["updated_at"] = _now()


_progress_store = RedisBackedProgressStore()


def normalize_job_id(raw: Optional[str]) -> str:
    """Accept a client-supplied UUID or mint one. Anything else is rejected."""
    if raw is None or str(raw).strip() == "":
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(str(raw).strip()))
    except ValueError as exc:
        raise ValueError("job_id must be a UUID") from exc


class GenerationProgress:
    """Records real state transitions for one generation."""

    def __init__(self, job_id: str, tool: str) -> None:
        now = _now()
        record = {
            "job_id": job_id,
            "tool": tool,
            "state": "CREATED",
            "created_at": now,
            "updated_at": now,
            "error": None,
            "result": None,
            "events": [{"state": "CREATED", "at": now, "reason": f"Generation request received for {tool}"}],
        }
        _progress_store.create(job_id, record)
        self.job_id = job_id

    @property
    def state(self) -> str:
        rec = _progress_store.get(self.job_id)
        if rec is None:
            raise KeyError(self.job_id)
        return str(rec["state"])

    def advance(self, next_state: str, reason: str) -> None:
        _progress_store.update_transition(self.job_id, next_state, reason)

    def fail(self, detail: str) -> None:
        _progress_store.mark_failed(self.job_id, detail)

    def set_result(self, result: Dict[str, Any]) -> None:
        _progress_store.set_result(self.job_id, result)


def snapshot(job_id: str) -> Optional[Dict[str, Any]]:
    rec = _progress_store.get(job_id)
    if rec is None:
        return None
    return {
        "job_id": rec["job_id"],
        "tool": rec["tool"],
        "current_state": rec["state"],
        "terminal": rec["state"] in TERMINAL_STATES,
        "error": rec["error"],
        "result": rec.get("result"),
        "created_at": rec["created_at"],
        "updated_at": rec["updated_at"],
        "events": [dict(e) for e in rec["events"]],
    }
