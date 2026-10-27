"""
KEYSTONE Kaggle Worker Bridge REST Endpoints (Bible §24).
Mounts /internal/workers/register, /internal/workers/heartbeat, /internal/workers,
and /internal/workers/drain.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.harness.src.worker_bridge import worker_bridge

router = APIRouter(prefix="/internal/workers", tags=["Workers"])


class WorkerRegisterRequest(BaseModel):
    worker_id: str = Field(..., description="Unique worker node identifier")
    worker_type: str = Field("cognition", description="Worker category: cognition, creative, comfyui")
    tunnel_url: str = Field(..., description="Ephemeral tunnel URL (Cloudflare/ngrok)")
    capabilities: List[str] = Field(..., min_length=1, description="Supported capability namespaces")
    hardware: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Hardware metrics: GPUs, VRAM, RAM")
    auth_token: Optional[str] = Field(None, description="Worker authorization token")


class WorkerHeartbeatRequest(BaseModel):
    worker_id: str = Field(..., description="Worker node identifier")
    metrics: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Heartbeat telemetry")
    timestamp: Optional[float] = Field(None, description="Local worker Unix timestamp")


class WorkerDrainRequest(BaseModel):
    worker_id: str = Field(..., description="Worker node identifier to drain")


@router.post(
    "/register",
    summary="Register Ephemeral Worker",
    description="Registers an ephemeral worker with dynamic tunnel URL and capabilities."
)
def register_worker(req: WorkerRegisterRequest) -> Dict[str, Any]:
    try:
        res = worker_bridge.register_worker(
            worker_id=req.worker_id,
            worker_type=req.worker_type,
            tunnel_url=req.tunnel_url,
            capabilities=req.capabilities,
            hardware=req.hardware,
            auth_token=req.auth_token
        )
        return res
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/heartbeat",
    summary="Worker Heartbeat",
    description="Updates worker last heartbeat timestamp and telemetry."
)
def heartbeat(req: WorkerHeartbeatRequest) -> Dict[str, Any]:
    try:
        res = worker_bridge.heartbeat(
            worker_id=req.worker_id,
            metrics=req.metrics,
            timestamp=req.timestamp
        )
        return res
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "",
    summary="List Registered Workers",
    description="Lists registered ephemeral workers and current health/status."
)
def list_workers(active_only: bool = False) -> Dict[str, Any]:
    workers = worker_bridge.list_workers(active_only=active_only)
    return {
        "count": len(workers),
        "workers": workers
    }


@router.post(
    "/drain",
    summary="Drain Worker",
    description="Marks worker as DRAINING before session shutdown."
)
def drain_worker(req: WorkerDrainRequest) -> Dict[str, Any]:
    try:
        res = worker_bridge.drain_worker(req.worker_id)
        return res
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
