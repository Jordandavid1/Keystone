"""
KEYSTONE Job Lifecycle Router (/v1/jobs)
Job creation, deterministic state machine transitions, and event tracking.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.models import (
    AuthorityDecision as AuthorityDecisionRecord,
    CreditAccount,
    Request,
)
from apps.api.src.db.session import get_db
from apps.api.src.jobs.state_machine import (
    STATES,
    JobStateMachine,
    normalize_state,
    transition,
)
from apps.api.src.repositories.jobs import JobRepository
from packages.contracts.src.models import ProposedAction
from services.authority.src.engine import authority_engine

router = APIRouter(prefix="/v1/jobs", tags=["Jobs"])

# Global in-memory job event history for tracking lifecycle transitions
_JOB_EVENTS: Dict[str, List[Dict[str, Any]]] = {}


class CreateJobRequest(BaseModel):
    request_id: Optional[str] = None
    authority_decision_id: Optional[str] = None
    request_text: Optional[str] = None
    action: Optional[ProposedAction] = None
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
    req_id = req.request_id
    auth_dec_id = req.authority_decision_id
    authority_decision = None
    authorized_arguments = None
    state = normalize_state(req.initial_state or "CREATED")

    # The live creative path submits the compiled action here. Persist its
    # request and authority decision using the authenticated tenant and actual
    # credit account before creating a job with those foreign keys.
    if req.action is not None:
        if req.request_id or req.authority_decision_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Do not supply request or decision IDs when submitting an action; KEYSTONE persists them.",
            )
        if state != "CREATED":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Action-backed jobs must begin in CREATED state.",
            )
        if req.action.action_type != "generate" or req.action.capability != "image.generation":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The integrated generation path currently accepts text-to-image create actions only.",
            )
        req_id = str(uuid.uuid4())
        request_record = Request(
            id=req_id,
            user_id=tenant_id,
            request_text=req.request_text or str(req.action.parameters.get("prompt", "")),
            preferences={
                "action_type": req.action.action_type,
                "capability_id": req.action.capability,
            },
            state="created",
        )
        db.add(request_record)
        await db.flush()

        account_result = await db.execute(
            select(CreditAccount)
            .where(CreditAccount.user_id == tenant_id)
            .where(CreditAccount.status == "active")
        )
        credit_account = account_result.scalar_one_or_none()
        authority_decision = authority_engine.evaluate(
            action=req.action,
            user_id=tenant_id,
            credit_balance=credit_account.balance if credit_account else 0,
            held_balance=credit_account.held_balance if credit_account else 0,
            request_id=req_id,
        )
        auth_dec_id = str(uuid.uuid4())
        if authority_decision.decision not in ("ALLOW", "approve"):
            request_record.state = "rejected"
            auth_dec_id = str(uuid.uuid4())
            decision_record = AuthorityDecisionRecord(
                id=auth_dec_id,
                request_id=req_id,
                decision=authority_decision.decision_enum or "deny",
                capability_id=authority_decision.capability_id,
                provider_id=req.provider_id or "comfyui",
                sanitized_arguments=authority_decision.sanitized_arguments,
                reason_codes=authority_decision.reason_codes,
                policy_bundle_version=authority_decision.policy_bundle_version,
                capability_registry_version=authority_decision.capability_registry_version,
                harness_bundle_version=authority_decision.harness_bundle_version,
            )
            db.add(decision_record)
            await db.flush()
            job = await job_repo.create_job(
                id=job_id,
                request_id=req_id,
                authority_decision_id=auth_dec_id,
                capability_id=req.action.capability,
                provider_id=req.provider_id or "comfyui",
                workflow_id=req.workflow_id or "wf_default",
                workflow_version=req.workflow_version or "1.0.0",
                state="REJECTED",
                priority=req.priority or 100,
            )
            _JOB_EVENTS[job.id] = [{
                "job_id": job.id,
                "state": job.state,
                "reason": "Authority denied generation",
                "timestamp": job.created_at.isoformat() if job.created_at else None,
            }]
            return {
                "status": "rejected",
                "id": job.id,
                "request_id": req_id,
                "authority_decision_id": auth_dec_id,
                "user_id": job.user_id,
                "capability_id": job.capability_id,
                "provider_id": job.provider_id,
                "state": job.state,
                "authority_decision": {
                    **authority_decision.model_dump(mode="json"),
                    "decision_id": auth_dec_id,
                    "request_id": req_id,
                },
                "authorized_arguments": authority_decision.sanitized_arguments,
            }

        decision_record = AuthorityDecisionRecord(
            id=auth_dec_id,
            request_id=req_id,
            decision=authority_decision.decision_enum or "deny",
            capability_id=authority_decision.capability_id,
            provider_id=req.provider_id or "comfyui",
            sanitized_arguments=authority_decision.sanitized_arguments,
            reason_codes=authority_decision.reason_codes,
            policy_bundle_version=authority_decision.policy_bundle_version,
            capability_registry_version=authority_decision.capability_registry_version,
            harness_bundle_version=authority_decision.harness_bundle_version,
        )
        db.add(decision_record)
        await db.flush()
        authorized_arguments = authority_decision.sanitized_arguments

    if not req_id:
        req_id = str(uuid.uuid4())
        request_record = Request(
            id=req_id,
            user_id=tenant_id,
            request_text=req.request_text or f"Job creation request for {req.capability_id or 'generation'}",
            preferences={
                "action_type": "generate",
                "capability_id": req.capability_id or "image.generation",
            },
            state="created",
        )
        db.add(request_record)
        await db.flush()

    if not auth_dec_id:
        auth_dec_id = str(uuid.uuid4())
        decision_record = AuthorityDecisionRecord(
            id=auth_dec_id,
            request_id=req_id,
            decision="approve",
            capability_id=req.capability_id or "image.generation",
            provider_id=req.provider_id or "kaggle_comfyui",
            sanitized_arguments={},
            reason_codes=["auto_approved_shell"],
            policy_bundle_version="1.0.0",
            capability_registry_version="1.0.0",
            harness_bundle_version="1.0.0",
        )
        db.add(decision_record)
        await db.flush()
    elif req.action is None:
        request_result = await db.execute(
            select(Request)
            .where(Request.id == req_id)
            .where(Request.user_id == tenant_id)
        )
        request_record = request_result.scalar_one_or_none()
        decision_result = await db.execute(
            select(AuthorityDecisionRecord)
            .where(AuthorityDecisionRecord.id == auth_dec_id)
            .where(AuthorityDecisionRecord.request_id == req_id)
            .where(AuthorityDecisionRecord.decision == "approve")
        )
        if request_record is None or decision_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A persisted request and matching approved authority decision are required.",
            )

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
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "authority_decision": (
            {
                **authority_decision.model_dump(mode="json"),
                "decision_id": auth_dec_id,
                "request_id": req_id,
            }
            if authority_decision is not None else None
        ),
        "authorized_arguments": authorized_arguments,
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
