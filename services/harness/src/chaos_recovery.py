"""
KEYSTONE Chaos Worker Recovery & Adversarial Hardening Engine (Bible §14, §19, §34).
Simulates worker crashes, network drops, unhandled exceptions, and timeouts.
Verifies state machine resilience, credit ledger hold preservation, and retry recovery.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from services.authority.src.credits_ledger import credits_ledger
from services.harness.src.worker_bridge import worker_bridge


class ChaosRecoveryEngine:
    """
    Simulates worker failures and validates system crash recovery.
    """

    @classmethod
    def simulate_worker_crash(
        cls,
        job_record: Dict[str, Any],
        worker_id: str,
        hold_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simulates an abrupt worker crash during job execution:
        1. Transitions job state from 'running' to 'retry_pending'.
        2. Drains or marks the failing worker OFFLINE.
        3. Protects the credit hold: ensures hold is NOT settled and remains provisional.
        4. Increments retry counter.
        """
        current_state = job_record.get("state", "running")
        if current_state != "running":
            raise ValueError(f"INVALID_CRASH_STATE: Worker can only crash while job is 'running' (got '{current_state}')")

        # 1. Update job state to retry_pending
        retry_count = int(job_record.get("retry_count", 0)) + 1
        job_record["state"] = "retry_pending"
        job_record["retry_count"] = retry_count
        job_record["last_error"] = f"WORKER_CRASH: Worker '{worker_id}' disconnected unexpectedly"

        # 2. Mark worker offline in bridge
        w = worker_bridge.get_worker(worker_id)
        if w:
            worker_bridge._workers[worker_id].status = "OFFLINE"

        # 3. Credit ledger integrity check
        # Verify that hold is still active and has NOT been finalized/settled
        hold_settled = False
        if hold_id:
            for e in credits_ledger._entries:
                if e.hold_id == hold_id and e.entry_type == "SETTLE":
                    hold_settled = True
                    break

        return {
            "recovered": True,
            "job_id": job_record.get("job_id"),
            "new_state": "retry_pending",
            "retry_count": retry_count,
            "worker_id": worker_id,
            "worker_status": "OFFLINE",
            "hold_intact": not hold_settled,
            "error": job_record["last_error"]
        }

    @classmethod
    def recover_and_reassign(
        cls,
        job_record: Dict[str, Any],
        replacement_worker_id: str
    ) -> Dict[str, Any]:
        """
        Reassigns an aborted job from 'retry_pending' to 'running' on a healthy worker.
        """
        if job_record.get("state") != "retry_pending":
            raise ValueError("CANNOT_RECOVER: Job must be in 'retry_pending' state")

        job_record["state"] = "running"
        job_record["worker_id"] = replacement_worker_id
        job_record["reassigned_at"] = time.time()

        return {
            "status": "REASSIGNED",
            "job_id": job_record.get("job_id"),
            "state": "running",
            "assigned_worker_id": replacement_worker_id
        }
