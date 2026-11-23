"""
KEYSTONE Creative Tool Fabric & Quality API Router (Milestone M4, Bible §8, §13, §14, §23).
Provides endpoints for capability discovery, adapter request execution with execution envelopes,
KHF quality evaluation, and bounded retry decisions.
"""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from apps.api.src.auth.dependencies import get_current_user, require_admin

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


def _validate_worker_url(url: str) -> None:
    if "\r" in url or "\n" in url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_INPUT: Newline characters are not allowed in URL"
        )
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_URL: Only http and https URLs with a valid host are allowed"
        )
    host = parsed.hostname.lower()
    if host in ("169.254.169.254", "metadata.google.internal", "metadata"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSRF_BLOCKED: Metadata endpoints are forbidden"
        )
    allow_private = os.getenv("KEYSTONE_ALLOW_PRIVATE_WORKERS", "0") == "1"
    try:
        ip_obj = ipaddress.ip_address(host)
        ips = [ip_obj]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
            ips = [ipaddress.ip_address(info[4][0]) for info in infos]
        except OSError:
            ips = []
    for ip in ips:
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSRF_BLOCKED: Link-local, multicast, or unspecified IP is forbidden"
            )
        if not allow_private and (ip.is_private or ip.is_loopback or ip.is_reserved):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SSRF_BLOCKED: Private or loopback IP is forbidden unless KEYSTONE_ALLOW_PRIVATE_WORKERS=1"
            )


def _reject_newlines(val: Optional[str], field_name: str) -> None:
    if val is not None and ("\r" in val or "\n" in val):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"INVALID_INPUT: Newline characters are not allowed in {field_name}"
        )


@router.post(
    "/execute",
    summary="Execute Creative Adapter Request",
    description="Validates parameters, enforces execution envelope integrity, builds workflow graph."
)
def execute_creative_job(
    request: CreativeExecuteRequest,
    _current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    # 1. Require and verify execution envelope
    if request.envelope is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MISSING_ENVELOPE: ExecutionEnvelope v2 is required"
        )
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


class ComfyConfigUpdateRequest(BaseModel):
    comfy_base_url: Optional[str] = Field(None, description="Live ComfyUI base or Cloudflare tunnel URL")
    base_url: Optional[str] = Field(None, description="Alias for comfy_base_url")
    comfy_api_key: Optional[str] = Field(None, description="Optional Bearer/API key for ComfyUI")
    comfy_auth_token: Optional[str] = Field(None, description="Optional auth token alias for ComfyUI")
    openai_base_url: Optional[str] = Field(None, description="Live OpenAI-compatible Qwen cognition tunnel URL")
    openai_api_key: Optional[str] = Field(None, description="Optional API key for Qwen cognition endpoint")
    openai_model: Optional[str] = Field(None, description="Optional served model alias for Qwen cognition endpoint")


@router.get(
    "/comfy/status",
    summary="ComfyUI & MiniMax H3 Live Runtime Status",
    description="Returns live ComfyUI wiring status, workflow graph readiness, H3 health check, and registered creative adapters."
)
def get_comfy_runtime_status() -> Dict[str, Any]:
    import os
    import urllib.request
    from services.comfy.src.client import comfy_client
    from apps.api.src.creative import h3

    comfy_url = comfy_client.base_url()
    h3_info = h3.describe()
    h3_health = h3.health() if comfy_url else {"configured": False, "reachable": False, "detail": "COMFY_BASE_URL is not set"}
    online = bool(h3_health.get("reachable"))
    cognition_endpoint = (os.getenv("OPENAI_BASE_URL") or os.getenv("COGNITION_BASE_URL") or "").strip().rstrip("/")
    cognition_online = False
    if cognition_endpoint:
        try:
            models_url = f"{cognition_endpoint}/models" if cognition_endpoint.endswith("/v1") else f"{cognition_endpoint}/v1/models"
            api_key = os.getenv("OPENAI_API_KEY", "")
            req = urllib.request.Request(
                models_url,
                headers={"Authorization": f"Bearer {api_key}", "User-Agent": "KEYSTONE-RuntimeProbe/2.0"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                cognition_online = (resp.status == 200)
        except Exception:
            cognition_online = False

    return {
        "status": "ok",
        "online": online,
        "base_url": comfy_url or None,
        "comfy_configured": comfy_client.is_configured(),
        "comfy_base_url": comfy_url or None,
        "cognition_endpoint": cognition_endpoint or None,
        "cognition_online": cognition_online,
        "openai_base_url": cognition_endpoint or None,
        "openai_model": os.getenv("OPENAI_MODEL", "OBLITERATUS/Qwen3.8-27B-OBLITERATED"),
        "h3": h3_info,
        "h3_health": h3_health,
        "adapters": list(ADAPTER_REGISTRY.keys()),
        "workflows": {
            "sdxl_txt2img": "ready",
            "sdxl_img2img": "ready",
            "upscale_4x": "ready",
            "minimax_h3_ref2va": "ready" if h3.workflow_path() else "missing"
        }
    }


@router.post(
    "/comfy/configure",
    summary="Dynamically Configure ComfyUI & Cognition Tunnel URLs",
    description="Updates COMFY_BASE_URL / KEYSTONE_COMFY_URL and OPENAI_BASE_URL in memory, .env, and WorkerBridge."
)
def configure_comfy_runtime(
    req: ComfyConfigUpdateRequest,
    _admin: Any = Depends(require_admin),
) -> Dict[str, Any]:
    from pathlib import Path
    from services.harness.src.worker_bridge import worker_bridge

    _reject_newlines(req.comfy_api_key, "comfy_api_key")
    _reject_newlines(req.comfy_auth_token, "comfy_auth_token")
    _reject_newlines(req.openai_api_key, "openai_api_key")

    updates: Dict[str, str] = {}
    effective_comfy_url = req.comfy_base_url if req.comfy_base_url is not None else req.base_url
    if effective_comfy_url is not None:
        clean_comfy = effective_comfy_url.strip().rstrip("/")
        _validate_worker_url(clean_comfy)
        if clean_comfy.endswith("/v1"):
            clean_comfy = clean_comfy[:-3].rstrip("/")
        os.environ["COMFY_BASE_URL"] = clean_comfy
        os.environ["KEYSTONE_COMFY_URL"] = clean_comfy
        os.environ["KAGGLE_COMFYUI_TUNNEL"] = clean_comfy
        updates["COMFY_BASE_URL"] = clean_comfy
        updates["KEYSTONE_COMFY_URL"] = clean_comfy
        updates["KAGGLE_COMFYUI_TUNNEL"] = clean_comfy
        if clean_comfy:
            worker_bridge.register_worker(
                worker_id="kaggle-creative-comfyui",
                worker_type="creative_worker",
                tunnel_url=clean_comfy,
                capabilities=[
                    "creative.comfyui",
                    "image.generation",
                    "image.editing",
                    "video.i2v",
                    "video.t2v",
                    "video.minimax_h3_ref2va",
                    "identity.facefusion",
                    "upscale.clarity",
                ],
                hardware={"gpu": "NVIDIA T4 x2", "vram_total_gib": 30.0},
            )

    effective_comfy_key = req.comfy_api_key if req.comfy_api_key is not None else req.comfy_auth_token
    if effective_comfy_key is not None:
        clean_key = effective_comfy_key.strip()
        os.environ["KEYSTONE_COMFY_API_KEY"] = clean_key
        os.environ["COMFY_BEARER_TOKEN"] = clean_key
        updates["KEYSTONE_COMFY_API_KEY"] = clean_key

    if req.openai_base_url is not None:
        clean_oai = req.openai_base_url.strip().rstrip("/")
        _validate_worker_url(clean_oai)
        if clean_oai and not clean_oai.endswith("/v1"):
            clean_oai = f"{clean_oai}/v1"
        os.environ["OPENAI_BASE_URL"] = clean_oai
        os.environ["COGNITION_BASE_URL"] = clean_oai
        os.environ["KAGGLE_COGNITION_TUNNEL"] = clean_oai[:-3] if clean_oai.endswith("/v1") else clean_oai
        updates["OPENAI_BASE_URL"] = clean_oai
        updates["COGNITION_BASE_URL"] = clean_oai
        if clean_oai:
            worker_bridge.register_worker(
                worker_id="kaggle-cognition-t4x2",
                worker_type="cognition_worker",
                tunnel_url=clean_oai,
                capabilities=["cognition.qwen_27b", "cognition.reasoning", "planning.propose"],
                hardware={"gpu": "NVIDIA T4 x2", "vram_total_gib": 30.0},
            )

    if req.openai_api_key is not None:
        clean_okey = req.openai_api_key.strip()
        os.environ["OPENAI_API_KEY"] = clean_okey
        updates["OPENAI_API_KEY"] = clean_okey

    if req.openai_model is not None and req.openai_model.strip():
        clean_omodel = req.openai_model.strip()
        os.environ["OPENAI_MODEL"] = clean_omodel
        updates["OPENAI_MODEL"] = clean_omodel

    # Persist to .env if writable
    if updates:
        repo_root = Path(__file__).resolve().parents[4]
        for env_path in (repo_root / ".env", repo_root / "dist" / ".env"):
            if env_path.parent.exists():
                try:
                    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
                    written_keys = set()
                    new_lines = []
                    for line in lines:
                        stripped = line.strip()
                        if "=" in stripped and not stripped.startswith("#"):
                            k = stripped.split("=", 1)[0].strip()
                            if k in updates:
                                new_lines.append(f"{k}={updates[k]}")
                                written_keys.add(k)
                                continue
                        new_lines.append(line)
                    for k, v in updates.items():
                        if k not in written_keys:
                            new_lines.append(f"{k}={v}")
                    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                except Exception:
                    pass

    return get_comfy_runtime_status()
