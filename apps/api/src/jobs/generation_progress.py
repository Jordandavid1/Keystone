"""
Live progress for studio generations (/v1/zencreator/generate).

The generate call runs synchronously, so the studio passes a job id with the
request and polls GET /v1/zencreator/jobs/{job_id} while it is in flight. Each
state below is recorded at the moment the router actually reaches that step,
and every move is checked against the canonical job state machine (Bible §19).

The registry is in-process memory, like /v1/jobs event history: it survives
for the life of the API process, not across restarts.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from apps.api.src.jobs.state_machine import TERMINAL_STATES, transition

# Finished records are dropped after this long so the registry can't grow unbounded.
_FINISHED_TTL_SECONDS = 3600

_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}


class JobIdConflict(ValueError):
    pass


def _now() -> float:
    return time.time()


def _prune(now: float) -> None:
    stale = [
        jid for jid, rec in _jobs.items()
        if rec["state"] in TERMINAL_STATES and now - rec["updated_at"] > _FINISHED_TTL_SECONDS
    ]
    for jid in stale:
        _jobs.pop(jid, None)


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
        with _lock:
            _prune(now)
            if job_id in _jobs:
                raise JobIdConflict(f"job_id {job_id} is already in use")
            _jobs[job_id] = {
                "job_id": job_id,
                "tool": tool,
                "state": "CREATED",
                "created_at": now,
                "updated_at": now,
                "error": None,
                "events": [{"state": "CREATED", "at": now, "reason": f"Generation request received for {tool}"}],
            }
        self.job_id = job_id

    @property
    def state(self) -> str:
        with _lock:
            return _jobs[self.job_id]["state"]

    def advance(self, next_state: str, reason: str) -> None:
        with _lock:
            rec = _jobs[self.job_id]
            rec["state"] = transition(rec["state"], next_state)
            rec["updated_at"] = _now()
            rec["events"].append({"state": next_state, "at": rec["updated_at"], "reason": reason})

    def fail(self, detail: str) -> None:
        with _lock:
            rec = _jobs[self.job_id]
            if rec["state"] in TERMINAL_STATES:
                return
            rec["state"] = "FAILED"
            rec["error"] = detail
            rec["updated_at"] = _now()
            rec["events"].append({"state": "FAILED", "at": rec["updated_at"], "reason": detail})


def snapshot(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        rec = _jobs.get(job_id)
        if rec is None:
            return None
        return {
            "job_id": rec["job_id"],
            "tool": rec["tool"],
            "current_state": rec["state"],
            "terminal": rec["state"] in TERMINAL_STATES,
            "error": rec["error"],
            "created_at": rec["created_at"],
            "updated_at": rec["updated_at"],
            "events": [dict(e) for e in rec["events"]],
        }

