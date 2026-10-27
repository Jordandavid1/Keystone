"""
KEYSTONE Ephemeral Kaggle Worker Bridge & Registry (Bible §24).
Provides dynamic tunnel registration, 30s heartbeat loop tracking, 90s offline detection,
and capability-based worker job routing.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


HEARTBEAT_INTERVAL_SECONDS = 30
OFFLINE_TIMEOUT_SECONDS = 90


class WorkerRecord:
    def __init__(
        self,
        worker_id: str,
        worker_type: str,
        tunnel_url: str,
        capabilities: List[str],
        hardware: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None
    ):
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.tunnel_url = tunnel_url.rstrip("/")
        self.capabilities = list(capabilities)
        self.hardware = hardware or {}
        self.auth_token = auth_token
        self.status = "ACTIVE"
        self.registered_at = time.time()
        self.last_heartbeat_at = self.registered_at
        self.metrics: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_type": self.worker_type,
            "tunnel_url": self.tunnel_url,
            "capabilities": self.capabilities,
            "hardware": self.hardware,
            "status": self.status,
            "registered_at": self.registered_at,
            "last_heartbeat_at": self.last_heartbeat_at,
            "metrics": self.metrics
        }


class WorkerBridge:
    """
    Manages ephemeral Kaggle worker registrations, heartbeats,
    and capability routing.
    """

    def __init__(self):
        self._workers: Dict[str, WorkerRecord] = {}

    def register_worker(
        self,
        worker_id: str,
        worker_type: str,
        tunnel_url: str,
        capabilities: List[str],
        hardware: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registers or updates an ephemeral worker with dynamic tunnel endpoint.
        """
        if not worker_id or not str(worker_id).strip():
            raise ValueError("INVALID_WORKER_ID: worker_id is required")
        if not tunnel_url or not str(tunnel_url).strip():
            raise ValueError("INVALID_TUNNEL_URL: tunnel_url is required")
        if not capabilities or len(capabilities) == 0:
            raise ValueError("INVALID_CAPABILITIES: At least one capability must be declared")

        record = WorkerRecord(
            worker_id=worker_id,
            worker_type=worker_type,
            tunnel_url=tunnel_url,
            capabilities=capabilities,
            hardware=hardware,
            auth_token=auth_token
        )
        self._workers[worker_id] = record
        return {
            "status": "registered",
            "worker": record.to_dict()
        }

    def heartbeat(
        self,
        worker_id: str,
        metrics: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Processes worker heartbeat and updates telemetry.
        """
        if worker_id not in self._workers:
            raise ValueError(f"UNKNOWN_WORKER: Worker '{worker_id}' is not registered")

        worker = self._workers[worker_id]
        worker.last_heartbeat_at = timestamp if timestamp is not None else time.time()
        if worker.status == "OFFLINE":
            worker.status = "ACTIVE"
        if metrics:
            worker.metrics.update(metrics)

        return {
            "status": "ok",
            "worker_id": worker_id,
            "state": worker.status,
            "last_heartbeat_at": worker.last_heartbeat_at
        }

    def detect_offline_workers(self, now: Optional[float] = None) -> List[str]:
        """
        Scans workers and transitions any with missed heartbeats (> 90s) to OFFLINE.
        """
        current_time = now if now is not None else time.time()
        offline_worker_ids = []

        for w_id, worker in self._workers.items():
            if worker.status != "DRAINING" and (current_time - worker.last_heartbeat_at) > OFFLINE_TIMEOUT_SECONDS:
                worker.status = "OFFLINE"
                offline_worker_ids.append(w_id)

        return offline_worker_ids

    def route_for_capability(self, capability: str) -> List[WorkerRecord]:
        """
        Finds all healthy, active workers advertising the requested capability.
        """
        self.detect_offline_workers()
        matched = []
        for worker in self._workers.values():
            if worker.status == "ACTIVE" and capability in worker.capabilities:
                matched.append(worker)
        return matched

    def drain_worker(self, worker_id: str) -> Dict[str, Any]:
        """Sets worker state to DRAINING to prevent new jobs prior to session teardown."""
        if worker_id not in self._workers:
            raise ValueError(f"UNKNOWN_WORKER: Worker '{worker_id}' not found")
        self._workers[worker_id].status = "DRAINING"
        return {"status": "draining", "worker_id": worker_id}

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        self.detect_offline_workers()
        w = self._workers.get(worker_id)
        return w.to_dict() if w else None

    def list_workers(self, active_only: bool = False) -> List[Dict[str, Any]]:
        self.detect_offline_workers()
        workers = list(self._workers.values())
        if active_only:
            workers = [w for w in workers if w.status == "ACTIVE"]
        return [w.to_dict() for w in workers]

    def clear(self) -> None:
        self._workers.clear()


# Global worker bridge instance
worker_bridge = WorkerBridge()
