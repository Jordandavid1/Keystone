"""
KEYSTONE Creative Tool Fabric & Quality API Router (Milestone M4, Bible §8, §13, §14, §23).
Provides endpoints for capability discovery, adapter request execution with execution envelopes,
KHF quality evaluation, and bounded retry decisions.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from services.comfy.src.adapters import (
    ADAPTER_REGISTRY,
    get_adapter,
    list_capabilities,
    validate_adapter_request
)
from services.comfy.src.routing import provider_router
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.khf_quality import KHFQualityHarness
from services.harness.src.retry_loop import BoundedRetryManager
from packages.contracts.src.models import (
    CapabilityManifest,
    ExecutionEnvelope,
    HarnessResult,
    QualityScore,
    RetryPolicy
)

router = APIRouter(prefix="/v1/creative", tags=["Creative Tool Fabric"])


class CreativeExecuteRequest(BaseModel):
    adapter: str = Field(..., description="Target adapter (comfyui, image_gen, image_edit, wan_i2v, wan_t2v, facefusion, upscale)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Execution parameters")
    envelope: Optional[Dict[str, Any]] = Field(None, description="Optional signed ExecutionEnvelope")


class QualityEvaluateRequest(BaseModel):
    prompt: str = Field(..., description="Prompt that generated output")
    output_data: Dict[str, Any] = Field(..., description="Output metrics and properties")
    phase: str = Field("post-execution", description="Execution phase")


class RetryEvaluateRequest(BaseModel):
    policy: Optional[RetryPolicy] = None
    attempt_count: int = Field(default=1, ge=0)
    cumulative_cost: float = Field(default=1.0, ge=0.0)
    latest_success: bool = Field(default=False)
    failure_code: Optional[str] = None


@router.get(
    "/capabilities",
    response_model=List[CapabilityManifest],
    summary="List Creative Tool Capabilities",
    description="Returns all registered creative capability manifests per Bible §8."
)
def get_creative_capabilities() -> List[CapabilityManifest]:
    return list_capabilities()


@router.post(
    "/execute",
    summary="Execute Creative Adapter Request",
    description="Validates parameters, enforces execution envelope integrity if provided, builds workflow graph."
)
def execute_creative_job(request: CreativeExecuteRequest) -> Dict[str, Any]:
    # 1. If envelope is provided, verify it first
    if request.envelope:
        try:
            EnvelopeEngine.verify_envelope(request.envelope)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_ENVELOPE: {exc}"
            )

    # 2. Execute adapter
    try:
        result = validate_adapter_request(request.adapter, request.parameters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        )

    # 3. Route to active worker if capability available
    dispatch = provider_router.dispatch_envelope(
        {
            "capability_id": result.get("capability_id", ""),
            "job_id": request.parameters.get("job_id", f"job_{uuid.uuid4().hex[:12]}"),
            "envelope_id": request.envelope.get("envelope_id") if request.envelope else None
        }
    )
    result["dispatch"] = dispatch

    return result


@router.post(
    "/quality/evaluate",
    response_model=HarnessResult,
    summary="Evaluate Generation Output with KHF",
    description="Runs KHF quality assessment against generated output across 8 dimensions."
)
def evaluate_quality(request: QualityEvaluateRequest) -> HarnessResult:
    return KHFQualityHarness.evaluate_output(
        output_data=request.output_data,
        prompt=request.prompt,
        phase=request.phase
    )


@router.post(
    "/retry/evaluate",
    summary="Evaluate Bounded Retry Policy",
    description="Checks if an attempt should be retried, replanned, or aborted based on budgets."
)
def evaluate_retry_decision(request: RetryEvaluateRequest) -> Dict[str, Any]:
    manager = BoundedRetryManager(policy=request.policy)
    computed_hash = hashlib.sha256(
        f"{request.attempt_count}:{request.cumulative_cost}:{request.failure_code or 'NONE'}".encode("utf-8")
    ).hexdigest()
    # Reconstruct attempts
    for i in range(request.attempt_count):
        is_last = (i == request.attempt_count - 1)
        manager.record_attempt(
            job_id="job_retry_eval",
            provider_id="comfy.eval",
            capability_id="creative.eval",
            prompt_hash=computed_hash,
            success=request.latest_success if is_last else False,
            cost=request.cumulative_cost / max(1, request.attempt_count),
            failure_code=request.failure_code if is_last else "PREVIOUS_ATTEMPT_FAILED"
        )

    decision = manager.evaluate_retry()
    return decision.to_dict()
