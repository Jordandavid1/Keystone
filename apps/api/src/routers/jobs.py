"""
KEYSTONE Job Lifecycle Router (/v1/jobs)
Job creation, deterministic state machine transitions, and event tracking.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.session import get_db
from apps.api.src.jobs.state_machine import (
    STATES,
    JobStateMachine,
    normalize_state,
    transition,
)
from apps.api.src.repositories.jobs import JobRepository

router = APIRouter(prefix="/v1/jobs", tags=["Jobs"])

# Global in-memory job event history for tracking lifecycle transitions
_JOB_EVENTS: Dict[str, List[Dict[str, Any]]] = {}


class CreateJobRequest(BaseModel):
    request_id: Optional[str] = None
    authority_decision_id: Optional[str] = None
    capability_id: Optional[str] = "image_gen"
    provider_id: Optional[str] = "kaggle_comfyui"
    workflow_id: Optional[str] = "wf_default"
    workflow_version: Optional[str] = "1.0.0"
    initial_state: Optional[str] = "CREATED"
    priority: Optional[int] = 100


class TransitionJobRequest(BaseModel):
    next_state: str
    reason: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[Dict[str, Any]] = None


@router.post("", summary="Create a new job record")
async def create_job(
    req: CreateJobRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    job_repo = JobRepository(db, tenant_id=tenant_id)
    job_id = str(uuid.uuid4())
    req_id = req.request_id or str(uuid.uuid4())
    auth_dec_id = req.authority_decision_id or str(uuid.uuid4())
    state = normalize_state(req.initial_state or "CREATED")

    job = await job_repo.create_job(
        id=job_id,
        request_id=req_id,
        authority_decision_id=auth_dec_id,
        capability_id=req.capability_id or "image_gen",
        provider_id=req.provider_id or "kaggle_comfyui",
        workflow_id=req.workflow_id or "wf_default",
        workflow_version=req.workflow_version or "1.0.0",
        state=state,
        priority=req.priority or 100
    )

    _JOB_EVENTS[job.id] = [
        {
            "job_id": job.id,
            "state": job.state,
            "reason": "Job created",
            "timestamp": job.created_at.isoformat() if job.created_at else None
        }
    ]

    return {
        "status": "ok",
        "id": job.id,
        "request_id": job.request_id,
        "authority_decision_id": job.authority_decision_id,
        "user_id": job.user_id,
        "capability_id": job.capability_id,
        "provider_id": job.provider_id,
        "state": job.state,
        "priority": job.priority,
        "created_at": job.created_at.isoformat() if job.created_at else None
    }


@router.get("", summary="List jobs for current tenant")
async def list_jobs(
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    job_repo = JobRepository(db, tenant_id=tenant_id)
    jobs = await job_repo.list_jobs()
    return {
        "jobs": [
            {
                "id": j.id,
                "request_id": j.request_id,
                "capability_id": j.capability_id,
                "provider_id": j.provider_id,
                "state": j.state,
                "priority": j.priority,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "updated_at": j.updated_at.isoformat() if j.updated_at else None
            }
            for j in jobs
        ]
    }


@router.get("/{job_id}", summary="Get job by ID")
async def get_job(
    job_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    job_repo = JobRepository(db, tenant_id=tenant_id)
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or forbidden"
        )
    return {
        "id": job.id,
        "request_id": job.request_id,
        "capability_id": job.capability_id,
        "provider_id": job.provider_id,
        "workflow_id": job.workflow_id,
        "workflow_version": job.workflow_version,
        "state": job.state,
        "priority": job.priority,
        "error_code": job.error_code,
        "error_detail": job.error_detail,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None
    }


@router.post("/{job_id}/transition", summary="Execute deterministic state transition")
async def transition_job(
    job_id: str,
    req: TransitionJobRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    job_repo = JobRepository(db, tenant_id=tenant_id)
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or forbidden"
        )

    target_state = normalize_state(req.next_state)
    try:
        new_state = transition(job.state, target_state)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err)
        )

    await job_repo.update_job_state(
        job_id=job.id,
        next_state=new_state,
        error_code=req.error_code,
        error_detail=req.error_detail
    )

    if job.id not in _JOB_EVENTS:
        _JOB_EVENTS[job.id] = []
    _JOB_EVENTS[job.id].append({
        "job_id": job.id,
        "previous_state": job.state,
        "state": new_state,
        "reason": req.reason or "Transition executed",
        "error_code": req.error_code
    })

    return {
        "status": "ok",
        "id": job.id,
        "previous_state": job.state,
        "current_state": new_state
    }


@router.get("/{job_id}/events", summary="Stream or list state machine transition events")
async def get_job_events(
    job_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    job_repo = JobRepository(db, tenant_id=tenant_id)
    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or forbidden"
        )

    events = _JOB_EVENTS.get(job.id, [
        {
            "job_id": job.id,
            "state": job.state,
            "reason": "Current state snapshot"
        }
    ])
    return {
        "job_id": job.id,
        "current_state": job.state,
        "events": events
    }
