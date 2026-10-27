"""
KEYSTONE Provider Routing Engine (Bible §8, §23).
Discovers registered ephemeral workers via WorkerBridge, matches capabilities,
and handles routing and fallbacks for creative tool execution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from services.harness.src.worker_bridge import worker_bridge, WorkerRecord


class ProviderRouter:
    """
    Routes execution requests to capable, active workers.
    """

    @classmethod
    def select_worker(cls, capability_id: str) -> Optional[WorkerRecord]:
        """
        Selects an active worker capable of handling capability_id.
        Prefers active workers with lowest queue or best metrics.
        """
        candidates = worker_bridge.route_for_capability(capability_id)
        if not candidates:
            return None

        # Sort by active job count in metrics if available
        def worker_load(w: WorkerRecord) -> int:
            return int(w.metrics.get("active_jobs", 0))

        sorted_candidates = sorted(candidates, key=worker_load)
        return sorted_candidates[0]

    @classmethod
    def dispatch_envelope(
        cls,
        envelope_data: Dict[str, Any],
        worker_record: Optional[WorkerRecord] = None
    ) -> Dict[str, Any]:
        """
        Dispatches execution envelope to the assigned worker endpoint.
        """
        cap = envelope_data.get("capability_id", "")
        worker = worker_record or cls.select_worker(cap)
        if not worker:
            return {
                "status": "QUEUED_NO_WORKER",
                "message": f"No active worker currently advertising capability '{cap}'",
                "capability_id": cap
            }

        return {
            "status": "DISPATCHED",
            "worker_id": worker.worker_id,
            "tunnel_url": worker.tunnel_url,
            "job_id": envelope_data.get("job_id"),
            "envelope_id": envelope_data.get("envelope_id")
        }


# Global provider router instance
provider_router = ProviderRouter()
