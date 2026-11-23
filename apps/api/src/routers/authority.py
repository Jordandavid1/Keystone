"""
KEYSTONE Authority Engine REST Endpoints (Bible §12, §13).
Mounts /v1/authority/evaluate, /v1/authority/policies, /v1/authority/envelope/issue,
and /v1/authority/envelope/verify.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_user
from apps.api.src.auth.security import verify_service_token
from apps.api.src.db.session import get_db
from packages.contracts.src.models import ProposedAction, AuthorityDecision, ExecutionEnvelope
from services.authority.src.engine import authority_engine
from services.authority.src.rules import (
    ASPECT_RATIO_WHITELIST,
    IMAGE_MAX_WIDTH,
    IMAGE_MAX_HEIGHT,
    VIDEO_MAX_RESOLUTION,
    VIDEO_MAX_DURATION_SECONDS,
    BASE_CREDIT_TABLE,
    CONFIRMATION_CREDIT_THRESHOLD,
    ACTION_TYPES,
    CAPABILITY_NAMESPACES
)
from services.harness.src.envelope import EnvelopeEngine

router = APIRouter(prefix="/v1/authority", tags=["Authority"])


async def require_admin_or_service_token(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Allow either a valid internal service token or an authenticated admin user."""
    if x_service_token and verify_service_token(x_service_token):
        return
    user = await get_current_user(
        request=request,
        authorization=authorization,
        x_api_key=x_api_key,
        db=db,
    )
    if getattr(user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role or valid service token required",
        )


class AuthorityEvaluateRequest(BaseModel):
    action: ProposedAction
    user_id: Optional[str] = Field("usr_system", description="Requesting user UUID")
    credit_balance: Optional[int] = Field(100, ge=0, description="Available credit balance")
    held_balance: Optional[int] = Field(0, ge=0, description="Currently held credits")
    untrusted_content: Optional[str] = Field(None, description="Raw untrusted input for Aikido quarantine check")
    request_id: Optional[str] = Field(None, description="Optional caller request identifier")


class EnvelopeIssueRequest(BaseModel):
    decision: AuthorityDecision
    job_id: str
    user_id: str
    workflow_id: Optional[str] = "wf_default"
    workflow_version: Optional[str] = "1.0.0"
    compiled_prompt_id: Optional[str] = "cp_default"
    arguments: Optional[Dict[str, Any]] = None
    input_asset_ids: Optional[List[str]] = None


class EnvelopeVerifyRequest(BaseModel):
    envelope: Dict[str, Any]
    secret: Optional[str] = None


@router.post(
    "/evaluate",
    response_model=AuthorityDecision,
    dependencies=[Depends(get_current_user)],
    summary="Evaluate Proposed Action",
    description="Evaluates a ProposedAction against safety policies, parameter boundaries, and credit balance."
)
def evaluate_action(req: AuthorityEvaluateRequest) -> AuthorityDecision:
    decision = authority_engine.evaluate(
        action=req.action,
        user_id=req.user_id or "usr_system",
        credit_balance=req.credit_balance if req.credit_balance is not None else 100,
        held_balance=req.held_balance or 0,
        untrusted_content=req.untrusted_content,
        request_id=req.request_id
    )
    return decision


@router.get(
    "/policies",
    summary="Get Active Authority Policies",
    description="Returns boundary limits, whitelists, and credit cost tables."
)
def get_policies() -> Dict[str, Any]:
    return {
        "policy_bundle_version": authority_engine.POLICY_BUNDLE_VERSION,
        "action_types": list(ACTION_TYPES),
        "capabilities": list(CAPABILITY_NAMESPACES),
        "aspect_ratio_whitelist": list(ASPECT_RATIO_WHITELIST),
        "resolution_limits": {
            "image_max_width": IMAGE_MAX_WIDTH,
            "image_max_height": IMAGE_MAX_HEIGHT,
            "video_max_resolution": VIDEO_MAX_RESOLUTION,
            "video_max_duration_seconds": VIDEO_MAX_DURATION_SECONDS
        },
        "base_credits": BASE_CREDIT_TABLE,
        "confirmation_threshold": CONFIRMATION_CREDIT_THRESHOLD
    }


@router.post(
    "/envelope/issue",
    response_model=ExecutionEnvelope,
    dependencies=[Depends(require_admin_or_service_token)],
    summary="Issue Signed Execution Envelope",
    description="Cryptographically signs and issues an ExecutionEnvelope for an approved AuthorityDecision."
)
def issue_envelope(req: EnvelopeIssueRequest) -> ExecutionEnvelope:
    if req.decision.decision not in ("ALLOW", "approve"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CANNOT_ISSUE_ENVELOPE: AuthorityDecision verdict is '{req.decision.decision}', requires 'ALLOW' or 'approve'"
        )

    envelope = EnvelopeEngine.create_envelope(
        decision=req.decision,
        job_id=req.job_id,
        user_id=req.user_id,
        workflow_id=req.workflow_id or "wf_default",
        workflow_version=req.workflow_version or "1.0.0",
        compiled_prompt_id=req.compiled_prompt_id or "cp_default",
        arguments=req.arguments,
        input_asset_ids=req.input_asset_ids
    )
    return envelope


@router.post(
    "/envelope/verify",
    dependencies=[Depends(get_current_user)],
    summary="Verify Execution Envelope",
    description="Verifies HMAC-SHA256 signature, expiration, clock skew, and single-use nonce."
)
def verify_envelope(req: EnvelopeVerifyRequest) -> Dict[str, Any]:
    try:
        result = EnvelopeEngine.verify_envelope(req.envelope, secret=req.secret)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
