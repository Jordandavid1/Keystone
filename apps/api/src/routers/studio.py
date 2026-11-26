"""
KEYSTONE studio generative router.

Keeps the /v1/studio request/response contract used by the Next.js studio UX,
routes all image & video intents through the Gate (ExecutionEnvelope v2) and ComfyUI
workflow fabric, and never returns mock or placeholder media.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_optional_user
from services.comfy.src.client import (
    ComfyUIError,
    ComfyUINotConfigured,
    H3Error,
    build_video_workflow_graph,
    comfy_client,
    compile_video_prompt,
    h3_describe,
    is_non_neutral_grade,
    normalize_grade_params,
    resolve_aspect_dimensions,
    upload_image_to_comfy,
)
from services.comfy.src.grade import apply_grade
from services.comfy.src.video_ops import (
    VIDEO_DEFAULT_FPS,
    VideoOpsError,
    extract_last_frame,
    probe_video_metadata,
    resolve_target_fps,
    stitch_video_segments,
)
from apps.api.src.db.models import Asset, User
from apps.api.src.db.session import async_session_factory, get_db
from apps.api.src.jobs import generation_progress
from apps.api.src.jobs.generation_progress import GenerationProgress, JobIdConflict
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.routers.assets import content_url
from apps.api.src.storage.service import AssetStorageService, generate_storage_key
from packages.prompt_engine.playbooks import PlaybookRegistry
from services.cognition.src.client import CognitionConnector, load_keystone_dotenv

router = APIRouter(prefix="/v1/studio", tags=["Studio Generative Pipeline"])

STUDIO_USER_ID = "00000000-0000-4000-8000-000000000001"
STUDIO_EMAIL = "studio@local.keystone"

LLM_TOOLS = {"run_any_llm"}
H3_VIDEO_TOOLS = {
    "minimax_h3",
    "videogen",
    "text_to_video",
    "image_to_video",
    "video2video",
    "extend",
    "video_upscaler",
    "couplegen",
    "lipsync",
}
VIDEO_POST_TOOLS = {"video_merger"}

# canonical_tool -> (intent, workflow_name, capability_id, relationship_type)
IMAGE_TOOL_SPECS: Dict[str, Tuple[str, str, str, str]] = {
    "by_prompt": ("generate", "sdxl_create", "image.generation", "reference"),
    "by_ref": ("generate", "sdxl_create", "image.generation", "reference"),
    "image_editor": ("edit", "sdxl_edit", "image.editing", "edit"),
    "variation": ("variate", "sdxl_vary", "image.generation", "variation"),
    "upscaler": ("upscale", "esrgan_upscale", "upscale.clarity", "upscale"),
    "faceswap": ("edit", "sdxl_edit", "image.editing", "edit"),
    "photoshoot": ("generate", "sdxl_create", "image.generation", "reference"),
    "facegen": ("generate", "sdxl_create", "image.generation", "reference"),
    "carousel": ("variate", "sdxl_vary", "image.generation", "variation"),
    "collaber": ("generate", "sdxl_create", "image.generation", "reference"),
}

# canonical_tool -> (intent, variant, capability_id, relationship_type)
VIDEO_TOOL_SPECS: Dict[str, Tuple[str, str, str, str]] = {
    "minimax_h3": ("animate", "ref2v", "video.minimax_h3_ref2va", "animation"),
    "text_to_video": ("animate", "t2v", "video.t2v", "animation"),
    "image_to_video": ("animate", "i2v", "video.i2v", "animation"),
    "videogen": ("animate", "ref2v", "video.minimax_h3_ref2va", "animation"),
    "video2video": ("animate", "v2v", "video.minimax_h3_ref2va", "animation"),
    "extend": ("animate", "i2v", "video.i2v", "animation"),
    "video_upscaler": ("upscale", "video_upscale", "upscale.clarity", "upscale"),
    "couplegen": ("animate", "ref2v", "video.minimax_h3_ref2va", "animation"),
    "lipsync": ("animate", "ref2v", "video.minimax_h3_ref2va", "animation"),
}

TOOL_ALIASES: Dict[str, str] = {
    "h3": "minimax_h3",
    "pinkcherry": "minimax_h3",
    "t2v": "text_to_video",
    "i2v": "image_to_video",
    "ref2v": "videogen",
    "v2v": "video2video",
    "re-render": "video2video",
    "rerender": "video2video",
    "video_extend": "extend",
    "video_upscale": "video_upscaler",
}

ALL_TOOLS = {
    "minimax_h3",
    "by_prompt",
    "by_ref",
    "image_editor",
    "variation",
    "faceswap",
    "photoshoot",
    "facegen",
    "carousel",
    "collaber",
    "couplegen",
    "upscaler",
    "videogen",
    "text_to_video",
    "image_to_video",
    "video2video",
    "extend",
    "lipsync",
    "video_upscaler",
    "video_merger",
    "run_any_llm",
}


class ToolGenerationRequest(BaseModel):
    tool: str = Field(..., description="Tool name from the generative pipeline catalog")
    input: Dict[str, Any] = Field(default_factory=dict, description="Tool input matching input_schema")
    async_mode: bool = Field(
        default=False,
        description="When true, executes generation in a background task and returns HTTP 202 with job_id for polling",
    )
    job_id: Optional[str] = Field(
        default=None,
        description="Optional client-chosen UUID. Poll GET /v1/studio/jobs/{job_id} for live progress while this request runs.",
    )


def _no_engine_message(tool: str) -> str:
    return (
        f"NO_ENGINE_CONFIGURED: tool '{tool}' has no engine or model available on the runtime. "
        "No placeholder output was returned."
    )


async def _ensure_studio_user(db: AsyncSession) -> str:
    result = await db.execute(select(User).where(User.id == STUDIO_USER_ID))
    user = result.scalar_one_or_none()
    if user is not None:
        return str(user.id)
    result = await db.execute(select(User).where(User.email == STUDIO_EMAIL))
    user = result.scalar_one_or_none()
    if user is not None:
        return str(user.id)
    db.add(
        User(
            id=STUDIO_USER_ID,
            email=STUDIO_EMAIL,
            role="user",
            content_mode="sfw",
            is_active=True,
        )
    )
    await db.flush()
    return STUDIO_USER_ID


async def _persist_bytes(
    db: AsyncSession,
    payload: bytes,
    mime_type: str,
    filename: str,
    media_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    owner_id: Optional[str] = None,
    project_id: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    mature: bool = False,
) -> Dict[str, Any]:
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ENGINE_EMPTY_OUTPUT: the engine returned no bytes",
        )
    # Signed-in callers own what they upload or generate; signed-out studio use
    # keeps the shared studio account it always had.
    tenant_id = owner_id or await _ensure_studio_user(db)
    asset_id = str(uuid.uuid4())
    storage_key = generate_storage_key(tenant_id, asset_id, filename)
    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, payload, mime_type)
    repo = AssetRepository(db, tenant_id=tenant_id)
    asset = await repo.create_asset(
        id=asset_id,
        filename=filename,
        mime_type=mime_type,
        byte_size=len(payload),
        storage_key=storage_key,
        project_id=project_id,
        media_type=media_type,
        storage_provider=storage.provider.__class__.__name__,
        metadata=metadata or {},
        mature=bool(mature),
        asset_bytes=payload,
        content_mode="unrestricted" if mature else "sfw",
        fabric="comfyui",
        job_id=(metadata or {}).get("job_id"),
    )
    asset.filename = filename
    if width is not None:
        asset.width = int(width)
    if height is not None:
        asset.height = int(height)
    if duration_seconds is not None:
        asset.duration_seconds = float(duration_seconds)
    asset.mature = bool(mature)
    await db.flush()
    url = content_url(asset)
    return {
        "asset_id": str(asset.id),
        "url": url,
        "download_url": url,
        "preview_url": url,
        "type": media_type,
        "mime_type": mime_type,
        "byte_size": len(payload),
        "width": width,
        "height": height,
        "duration_seconds": duration_seconds,
        "mature": bool(mature),
        "created_at": time.time(),
    }


async def _load_asset_with_bytes(
    db: AsyncSession, asset_id: str, tenant_id: str
) -> Optional[Tuple[Asset, str, str, bytes]]:
    result = await db.execute(
        select(Asset).where(
            Asset.id == str(asset_id),
            Asset.user_id == tenant_id,
            Asset.deleted_at.is_(None),
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        return None
    storage = AssetStorageService()
    try:
        payload = await storage.provider.get_object(asset.storage_key)
    except FileNotFoundError:
        return None
    meta = getattr(asset, "metadata_", None) or {}
    filename = meta.get("original_filename") or asset.filename or asset.storage_key.split("/")[-1] or f"{asset_id}.bin"
    return asset, filename, asset.mime_type or "application/octet-stream", payload


async def _load_reference_bytes(
    db: AsyncSession, asset_id: str, tenant_id: str
) -> Optional[Tuple[str, str, bytes]]:
    loaded = await _load_asset_with_bytes(db, asset_id, tenant_id)
    if loaded is None:
        return None
    _asset, filename, mime_type, payload = loaded
    return filename, mime_type, payload


def _collect_ref_ids(tool_input: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in (
        "ref_asset_id",
        "reference_asset_id",
        "image_asset_id",
        "source_image_asset_id",
        "video_asset_id",
        "source_video_asset_id",
        "source_asset_id",
        "input_asset_id",
        "parent_asset_id",
        "asset_id",
        "audio_asset_id",
        "face_ref_id",
        "body_ref_id",
    ):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            ids.append(value.strip())
    for key in ("character_assets", "reference_asset_ids", "clips", "ref_asset_ids"):
        value = tool_input.get(key)
        if isinstance(value, list):
            ids.extend(str(item).strip() for item in value if str(item).strip())
    seen = set()
    unique: List[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _playbook_context(tool_input: Dict[str, Any]) -> str:
    explicit = str(tool_input.get("playbook_context") or "").strip()
    if explicit:
        return explicit
    playbook_id = str(tool_input.get("playbook_id") or "").strip()
    if not playbook_id or not PlaybookRegistry.exists(playbook_id):
        return ""
    playbook = PlaybookRegistry.get(playbook_id)
    ctx = playbook.domain_context or {}
    skill_lines = [
        f"- {item.get('name')}: {item.get('description')}"
        for item in (playbook.skills or [])
        if isinstance(item, dict)
    ]
    parts = [
        f"Playbook: {playbook.label} ({playbook.id})",
        f"Intended outcome: {playbook.outcome}",
        f"System framing: {ctx.get('system_framing') or ''}".strip(),
        f"Domain brief: {ctx.get('domain_brief') or ''}".strip(),
        f"Default visual style: {ctx.get('default_visual_style') or ''}".strip(),
        f"Default environment: {ctx.get('default_environment') or ''}".strip(),
        f"Quality standard: {ctx.get('quality_standard') or ''}".strip(),
    ]
    if skill_lines:
        parts.append("Bound skills and workflows:\n" + "\n".join(skill_lines))
    return "\n".join(part for part in parts if part and not part.endswith(": "))


def _user_prompt(tool_input: Dict[str, Any]) -> str:
    return str(
        tool_input.get("positive_prompt")
        or tool_input.get("prompt")
        or tool_input.get("text")
        or ""
    ).strip()


def _llm_endpoint() -> Tuple[bool, str, str, str]:
    load_keystone_dotenv()
    explicit = (
        os.getenv("COGNITION_BASE_URL", "").strip()
        or os.getenv("OPENAI_BASE_URL", "").strip()
    )
    connector = CognitionConnector()
    endpoint = connector.resolve_active_endpoint().rstrip("/")
    default = "http://localhost:8000/v1"
    if not explicit and endpoint == default:
        return False, "", "", ""
    model = os.getenv("OPENAI_MODEL", "").strip() or connector.resolve_served_model()
    return True, endpoint, connector.resolve_api_key(), model


def _call_llm(prompt: str, system_prompt: str, max_tokens: int, tool_input: Dict[str, Any]) -> str:
    configured, endpoint, api_key, model = _llm_endpoint()
    if not configured or not endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "NO_ENGINE_CONFIGURED: no OpenAI-compatible LLM endpoint is set. "
                "Set OPENAI_BASE_URL (and optionally OPENAI_API_KEY / OPENAI_MODEL) "
                "to the Colab llama-server address."
            ),
        )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": float(tool_input.get("temperature", 0.7) or 0.7),
        "max_tokens": int(max_tokens or 2048),
    }
    request = urllib.request.Request(
        f"{endpoint}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Keystone/2.0",
        },
    )
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read()[:2000].decode("utf-8", "replace")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ENGINE_UNREACHABLE: LLM HTTP {exc.code}: {body or exc.reason}",
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ENGINE_UNREACHABLE: LLM at {endpoint} could not be reached: {exc.reason}",
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="ENGINE_UNREACHABLE: LLM request timed out",
        ) from exc

    choices = raw.get("choices") or []
    if not choices:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ENGINE_EMPTY_OUTPUT: the LLM returned no choices",
        )
    message = choices[0].get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ENGINE_EMPTY_OUTPUT: the LLM returned empty text",
        )
    return text


@router.get("/tools", summary="List All 17 Generative Pipeline Tools")
def list_tools() -> Dict[str, Any]:
    return {
        "source": "builtin_catalog",
        "tools": {name: {"metadata": {"description": name}} for name in sorted(ALL_TOOLS)},
    }


@router.get("/playbooks", summary="List canonical prompt-engine playbooks")
def list_playbooks() -> Dict[str, Any]:
    playbooks = [item.to_dict() for item in PlaybookRegistry.list_playbooks()]
    return {"count": len(playbooks), "playbooks": playbooks}


class StudioEngineConfigureRequest(BaseModel):
    comfy_base_url: Optional[str] = Field(None, description="ComfyUI server or GPU worker URL (e.g. http://127.0.0.1:8188)")
    comfy_api_key: Optional[str] = Field(None, description="Optional Bearer token / API key for ComfyUI")
    openai_base_url: Optional[str] = Field(None, description="OpenAI-compatible LLM endpoint (Together.ai, Fireworks.ai, HuggingFace, llama.cpp)")
    openai_api_key: Optional[str] = Field(None, description="API key for OpenAI-compatible cognition provider")
    openai_model: Optional[str] = Field(None, description="Served open-weight model identifier")


class StudioComfyLaunchRequest(BaseModel):
    host: str = Field(default="127.0.0.1", description="Bind host for local ComfyUI server")
    port: int = Field(default=8188, ge=1024, le=65535, description="Bind port for local ComfyUI server")
    wait_seconds: float = Field(default=45.0, ge=5.0, le=180.0, description="Startup readiness timeout in seconds")


def _build_full_engine_status() -> Dict[str, Any]:
    from services.comfy.src.client import ADAPTER_REGISTRY, h3_health, h3_workflow_path
    from services.comfy.src.runtime_manager import (
        discover_local_comfy_dir,
        get_last_boot_error,
        probe_comfy_endpoint,
    )

    llm_configured, endpoint, _api_key, model = _llm_endpoint()
    comfy = h3_describe()
    comfy_url = comfy_client.base_url()
    comfy_probe = probe_comfy_endpoint(comfy_url, timeout=2.5) if comfy_url else {"reachable": False, "system_stats": None, "latency_ms": None, "error": None}
    h3_health_info = h3_health() if comfy_url else {"configured": False, "reachable": False, "detail": "COMFY_BASE_URL is not set"}
    local_comfy_dir = discover_local_comfy_dir()
    wired = LLM_TOOLS | set(IMAGE_TOOL_SPECS) | set(VIDEO_TOOL_SPECS) | VIDEO_POST_TOOLS
    comfy_live = bool(comfy_probe.get("reachable") or h3_health_info.get("reachable"))
    return {
        "online": bool(llm_configured or comfy_live or comfy.get("configured")),
        "comfy_online": comfy_live,
        "comfy_base_url": comfy_url or None,
        "cognition_endpoint": endpoint or None,
        "local_comfy_available": local_comfy_dir is not None,
        "local_comfy_path": str(local_comfy_dir) if local_comfy_dir else None,
        "boot_error": get_last_boot_error(),
        "llm": {
            "configured": llm_configured,
            "endpoint_present": bool(endpoint),
            "endpoint": endpoint or None,
            "model": model if llm_configured else os.getenv("OPENAI_MODEL", "OBLITERATUS/Qwen3.8-27B-OBLITERATED"),
        },
        "comfy": {
            **comfy,
            "reachable": comfy_live,
            "latency_ms": comfy_probe.get("latency_ms"),
            "error": comfy_probe.get("error"),
        },
        "h3": comfy,
        "h3_health": h3_health_info,
        "system_stats": comfy_probe.get("system_stats"),
        "adapters": list(ADAPTER_REGISTRY.keys()),
        "workflows": {
            "sdxl_txt2img": "ready",
            "sdxl_img2img": "ready",
            "upscale_4x": "ready",
            "minimax_h3_ref2va": "ready" if h3_workflow_path() else "missing",
        },
        "supported_video_fps": [30, 60, 100, 120],
        "wired_tools": sorted(wired),
        "unwired_tools": sorted(ALL_TOOLS - wired),
    }


@router.get("/engine", summary="Describe the configured ComfyUI, MiniMax-H3, and Cognition engines")
def engine_status() -> Dict[str, Any]:
    return _build_full_engine_status()


@router.get("/engine/status", summary="Live ComfyUI, MiniMax-H3, and Cognition Runtime Telemetry")
def detailed_engine_status() -> Dict[str, Any]:
    return _build_full_engine_status()


@router.post("/engine/configure", summary="Configure Studio ComfyUI & Open-Weight Cognition Endpoints")
def configure_studio_engine(req: StudioEngineConfigureRequest) -> Dict[str, Any]:
    from services.comfy.src.runtime_manager import configure_studio_runtime

    try:
        configure_studio_runtime(
            comfy_base_url=req.comfy_base_url,
            comfy_api_key=req.comfy_api_key,
            openai_base_url=req.openai_base_url,
            openai_api_key=req.openai_api_key,
            openai_model=req.openai_model,
            persist=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _build_full_engine_status()


@router.post("/engine/launch", summary="Launch & Wire Local ComfyUI Server with MiniMax-H3 Capabilities")
def launch_studio_comfy(req: StudioComfyLaunchRequest = StudioComfyLaunchRequest()) -> Dict[str, Any]:
    from services.comfy.src.runtime_manager import launch_local_comfy_daemon

    ok, detail, _probe = launch_local_comfy_daemon(
        host=req.host,
        port=req.port,
        wait_seconds=req.wait_seconds,
    )
    snap = _build_full_engine_status()
    snap["launch_ok"] = ok
    snap["launch_message"] = detail
    if not ok and not snap.get("comfy_online"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return snap


@router.post("/engine/stop", summary="Stop Managed Local ComfyUI Subprocess")
def stop_studio_comfy() -> Dict[str, Any]:
    from services.comfy.src.runtime_manager import stop_local_comfy_daemon

    stopped, detail = stop_local_comfy_daemon()
    snap = _build_full_engine_status()
    snap["stopped"] = stopped
    snap["stop_message"] = detail
    return snap


@router.get("/balance", summary="Get Credit Balance")
def get_balance() -> Dict[str, Any]:
    return {
        "balance": None,
        "currency": "credits",
        "status": "local_engine",
        "note": "Studio billing is disabled. Generation uses the configured engine and is not charged per tool.",
    }


@router.post("/upload", summary="Upload Media Asset (Image, Video, Audio)")
async def upload_asset(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    owner: Optional[User] = Depends(get_optional_user),
) -> Dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
    filename = file.filename or "upload.bin"
    mime_type = file.content_type or "application/octet-stream"
    if mime_type.startswith("video/") or filename.lower().endswith((".mp4", ".webm", ".mov", ".mkv", ".avi")):
        media_type = "video"
    elif mime_type.startswith("audio/") or filename.lower().endswith((".mp3", ".wav", ".ogg", ".m4a", ".flac")):
        media_type = "audio"
    else:
        media_type = "image"
    stored = await _persist_bytes(
        db,
        content,
        mime_type,
        filename,
        media_type,
        metadata={"source": "studio_upload", "original_filename": filename},
        owner_id=str(owner.id) if owner else None,
    )
    return {
        "asset_id": stored["asset_id"],
        "id": stored["asset_id"],
        "filename": filename,
        "byte_size": stored["byte_size"],
        "mime_type": mime_type,
        "url": stored["url"],
        "download_url": stored["download_url"],
        "preview_url": stored["preview_url"],
        "media_type": media_type,
    }


@router.get("/jobs/{job_id}", summary="Live progress for a studio generation")
async def generation_job(job_id: str) -> Dict[str, Any]:
    try:
        normalized = generation_progress.normalize_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    snap = generation_progress.snapshot(normalized)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No generation job '{normalized}' on this server")
    return snap


_BACKGROUND_TASKS: set[asyncio.Task] = set()


async def _run_generation_background(
    request: ToolGenerationRequest,
    progress: GenerationProgress,
    owner_id: Optional[str],
) -> None:
    async with async_session_factory() as db:
        try:
            result = await _run_generation(request, db, progress, owner_id)
            result["job_id"] = progress.job_id
            result["job_state"] = progress.state
            await db.commit()
            progress.set_result(result)
        except HTTPException as exc:
            await db.rollback()
            progress.fail(str(exc.detail))
        except Exception as exc:
            await db.rollback()
            progress.fail(f"ENGINE_ERROR: {exc}")


@router.post("/generate", summary="Execute Any Generative Pipeline Tool")
async def generate_tool(
    request: ToolGenerationRequest,
    db: AsyncSession = Depends(get_db),
    owner: Optional[User] = Depends(get_optional_user),
) -> Any:
    tool = (request.tool or "").strip()
    try:
        job_id = generation_progress.normalize_job_id(request.job_id)
        progress = GenerationProgress(job_id, tool or "unknown")
    except JobIdConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    owner_id = str(owner.id) if owner else None
    if request.async_mode:
        task = asyncio.create_task(_run_generation_background(request, progress, owner_id))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
        return JSONResponse(
            status_code=202,
            content={
                "generation_id": job_id,
                "job_id": job_id,
                "job_state": progress.state,
                "status": "accepted",
                "outputs": [],
            },
            headers={"X-Keystone-Job-Id": job_id},
        )

    try:
        result = await _run_generation(request, db, progress, owner_id)
    except HTTPException as exc:
        progress.fail(str(exc.detail))
        headers = dict(exc.headers or {})
        headers["X-Keystone-Job-Id"] = job_id
        raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers) from exc
    except Exception as exc:
        progress.fail(f"ENGINE_ERROR: {exc}")
        raise
    result["job_id"] = job_id
    result["job_state"] = progress.state
    progress.set_result(result)
    return result


async def _dispatch(progress: GenerationProgress, playbook_ctx: str, engine: str) -> None:
    """Record the planning → authorizing → queued → running steps as they happen."""
    progress.advance(
        "PLANNING",
        "Compiled the prompt with the attached playbook" if playbook_ctx else "Compiled the prompt (no playbook attached)",
    )
    progress.advance("AUTHORIZING", "Local engine: billing is off, so no credit hold was placed")
    progress.advance("QUEUED", f"Dispatching to {engine}")
    progress.advance("RUNNING", f"Generating with {engine}")


def _build_gate_arguments(
    tool_input: Dict[str, Any],
    capability_id: str,
    primary_asset_id: Optional[str],
    aspect_ratio: str,
    duration: float,
    scale_factor: int,
) -> Dict[str, Any]:
    """Build AuthorityEngine-compliant argument dict while preserving caller params."""
    args = dict(tool_input)
    if primary_asset_id and not args.get("input_asset_id"):
        args["input_asset_id"] = primary_asset_id
    args["aspect_ratio"] = aspect_ratio
    raw_fps = (
        args.get("fps")
        or args.get("frame_rate")
        or args.get("framerate")
        or args.get("hz")
        or (args.get("output_prefs") or {}).get("framerate")
    )
    if capability_id.startswith("video.") or capability_id == "creative.video_wan":
        args["duration_seconds"] = max(1, min(15, int(round(duration))))
        args["fps"] = resolve_target_fps(raw_fps, default=VIDEO_DEFAULT_FPS)
        res = str(args.get("resolution") or "720p").lower()
        if res not in ("480p", "720p", "1080p"):
            args["resolution"] = "1080p" if res in ("2k", "4k") else "720p"
    if capability_id == "upscale.clarity":
        args["scale_factor"] = 4 if int(scale_factor) >= 4 else 2
        if raw_fps is not None:
            resolved_up_fps = resolve_target_fps(raw_fps, default=None)
            if resolved_up_fps is not None:
                args["fps"] = resolved_up_fps
    return args


async def _authorize_through_gate(
    db: AsyncSession,
    effective_user_id: str,
    *,
    intent: str,
    prompt_text: str,
    capability_id: str,
    arguments: Dict[str, Any],
    input_asset_ids: List[str],
    project_id: Optional[str],
    persona_id: Optional[str],
    playbook: Any,
    session_id: Optional[str] = None,
):
    from apps.api.src.services.gate import GateService

    return await GateService.authorize_async(
        db,
        user_id=effective_user_id,
        intent=intent,
        prompt_text=prompt_text,
        capability_id=capability_id,
        arguments=arguments,
        project_id=project_id,
        session_id=session_id,
        persona_id=persona_id,
        input_asset_ids=input_asset_ids,
        playbook=playbook,
    )


def _as_uuid_or_none(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


async def _persist_gate_audit_rows(
    db: AsyncSession,
    *,
    receipt: Any,
    effective_user_id: str,
    project_id: Optional[str],
    capability_id: str,
    workflow_name: str,
    compiled_prompt: str,
    output_asset_id: str,
    harness_res: Any,
    parent_asset_ids: List[str],
    relationship_type: str,
    started_at: datetime,
    seed: Optional[int] = None,
    metrics: Optional[Dict[str, Any]] = None,
    mature: bool = False,
) -> None:
    from apps.api.src.db.models import (
        AssetRelationship,
        AttemptAsset,
        GenerationAttempt,
        HarnessRun,
        Job,
    )
    from apps.api.src.lineage.dag import LineageDAG

    safe_project_id = _as_uuid_or_none(project_id)
    safe_env_uuid = _as_uuid_or_none(receipt.envelope.envelope_id)

    existing_job = await db.execute(select(Job).where(Job.id == receipt.job_id))
    if existing_job.scalar_one_or_none() is None:
        db.add(
            Job(
                id=receipt.job_id,
                user_id=effective_user_id,
                project_id=safe_project_id,
                request_id=receipt.request_id,
                capability_id=capability_id,
                provider_id="comfyui",
                workflow_id=workflow_name,
                workflow_version="1.0.0",
                status="COMPLETED" if harness_res.verdict == "pass" else "FAILED",
                envelope_id=safe_env_uuid,
                envelope=receipt.envelope.model_dump(mode="json"),
                content_mode=receipt.content_mode,
                persona_id=getattr(receipt, "persona_id", None),
                outputs=[output_asset_id],
            )
        )
        await db.flush()

    attempt_id = str(uuid.uuid4())
    prompt_hash = hashlib.sha256(compiled_prompt.encode("utf-8")).hexdigest()
    db.add(
        GenerationAttempt(
            attempt_id=attempt_id,
            job_id=receipt.job_id,
            provider_id="comfyui",
            capability_id=capability_id,
            prompt_hash=prompt_hash,
            workflow_version="1.0.0",
            seed=seed,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            success=(harness_res.verdict == "pass"),
            output_asset_ids=[output_asset_id],
            metrics=metrics,
        )
    )
    await db.flush()

    db.add(AttemptAsset(attempt_id=attempt_id, asset_id=output_asset_id))
    db.add(
        HarnessRun(
            id=str(uuid.uuid4()),
            job_id=receipt.job_id,
            attempt_id=attempt_id,
            harness_id=harness_res.harness_id,
            harness_version=harness_res.harness_version,
            phase=harness_res.phase,
            verdict=harness_res.verdict,
            score=harness_res.score,
            reason_codes=harness_res.reason_codes,
            evidence=harness_res.evidence,
            runtime_ms=int(round(harness_res.runtime_ms or 0)),
        )
    )
    effective_mature = bool(mature or getattr(receipt, "mature", False))
    seen_parents = set()
    for ref_id in parent_asset_ids:
        if ref_id and ref_id != output_asset_id and ref_id not in seen_parents:
            seen_parents.add(ref_id)
            db.add(
                AssetRelationship(
                    id=str(uuid.uuid4()),
                    parent_asset_id=ref_id,
                    child_asset_id=output_asset_id,
                    relationship_type=relationship_type,
                    job_id=receipt.job_id,
                    mature=effective_mature,
                )
            )
    if getattr(receipt, "persona_id", None):
        dag = LineageDAG(session=db)
        await dag.persist_depicts_edge(
            child_asset_id=output_asset_id,
            persona_id=receipt.persona_id,
            persona_version=getattr(receipt, "persona_version", None) or 1,
            job_id=receipt.job_id,
            mature=effective_mature,
        )
    await db.commit()


def _raise_comfy_http_error(exc: Exception) -> None:
    message = str(exc)
    if isinstance(exc, ComfyUINotConfigured) or message.startswith(("COMFY_NOT_CONFIGURED", "H3_NOT_CONFIGURED")):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"NO_ENGINE_CONFIGURED: {message}",
        ) from exc
    if "UNREACHABLE" in message:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ENGINE_UNREACHABLE: {message}",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"ENGINE_ERROR: {message}",
    ) from exc


async def _run_video_generation(
    *,
    tool: str,
    canonical_tool: str,
    tool_input: Dict[str, Any],
    prompt: str,
    playbook_ctx: str,
    gen_id: str,
    db: AsyncSession,
    progress: GenerationProgress,
    effective_user_id: str,
) -> Dict[str, Any]:
    from services.harness.src.evaluators.deterministic import validate_asset_bytes

    intent, variant, capability_id, relationship_type = VIDEO_TOOL_SPECS[canonical_tool]
    camera_motion = tool_input.get("camera_motion") or tool_input.get("motion")
    raw_speed = tool_input.get("motion_speed")
    motion_speed = float(raw_speed) if raw_speed is not None else None
    duration = float(tool_input.get("duration") or tool_input.get("duration_seconds") or 5.0)
    raw_fps = (
        tool_input.get("fps")
        or tool_input.get("frame_rate")
        or tool_input.get("framerate")
        or tool_input.get("hz")
        or (tool_input.get("output_prefs") or {}).get("framerate")
    )
    target_fps = resolve_target_fps(
        raw_fps,
        default=None if canonical_tool == "video_upscaler" else VIDEO_DEFAULT_FPS,
    )
    aspect_ratio = str(tool_input.get("aspect_ratio") or tool_input.get("ratio") or "16:9").strip().split()[0]
    grade = normalize_grade_params(tool_input)
    lut = tool_input.get("lut")
    raw_scale = tool_input.get("scale_factor") or tool_input.get("scale")
    if raw_scale is None and str(tool_input.get("resolution") or "").lower() == "4k":
        scale_factor = 4
    else:
        scale_factor = 4 if int(raw_scale or 2) >= 4 else 2

    from apps.api.src.services.gate import load_persona_reference_media

    if canonical_tool in ("lipsync", "couplegen") and not comfy_client.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_no_engine_message(tool),
        )

    if canonical_tool in ("text_to_video", "image_to_video", "videogen", "video2video", "minimax_h3") and not prompt:
        detail_map = {
            "minimax_h3": "minimax_h3 requires a prompt describing the video scene and motion",
            "text_to_video": "text_to_video requires a prompt",
            "image_to_video": "image_to_video requires a motion prompt",
            "videogen": "videogen requires a prompt describing the motion and scene",
            "video2video": "video2video requires a prompt describing the style or motion transfer",
        }
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail_map[canonical_tool],
        )

    ref_ids = _collect_ref_ids(tool_input)
    loaded_refs: List[Tuple[str, Asset, str, str, bytes]] = []
    for ref_id in ref_ids:
        loaded = await _load_asset_with_bytes(db, ref_id, effective_user_id)
        if loaded is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reference asset '{ref_id}' was not found in studio storage",
            )
        asset_obj, fname, mtype, payload = loaded
        loaded_refs.append((ref_id, asset_obj, fname, mtype, payload))

    effective_prompt = prompt
    if not effective_prompt and canonical_tool == "extend":
        effective_prompt = "Continue the shot seamlessly with natural motion"
    elif not effective_prompt and canonical_tool == "video_upscaler":
        effective_prompt = "Neural ESRGAN video super-resolution upscale"
    elif not effective_prompt and canonical_tool == "couplegen":
        effective_prompt = "Two characters together in a cohesive cinematic shot with smooth natural motion"
    elif not effective_prompt and canonical_tool == "lipsync":
        effective_prompt = "Natural expressive speaking portrait synchronized to audio track"

    initial_primary_id = ref_ids[0] if ref_ids else None
    pre_compiled_prompt = compile_video_prompt(
        effective_prompt,
        camera_motion=camera_motion,
        motion_speed=motion_speed,
        duration=duration,
        fps=target_fps,
        aspect_ratio=aspect_ratio,
        grade=grade,
        lut=lut,
    )
    gate_args = _build_gate_arguments(
        tool_input,
        capability_id,
        initial_primary_id,
        aspect_ratio,
        duration,
        scale_factor,
    )

    await _dispatch(progress, playbook_ctx, f"ComfyUI ({variant})")
    started_at = datetime.now(timezone.utc)

    persona_param = tool_input.get("as") or tool_input.get("persona_id")
    # If i2v requires input_asset_id at AuthorityEngine and persona has refs, attach persona ref ID first if needed
    receipt = await _authorize_through_gate(
        db,
        effective_user_id,
        intent=intent,
        prompt_text=effective_prompt,
        capability_id=capability_id,
        arguments=gate_args,
        input_asset_ids=ref_ids,
        project_id=tool_input.get("project_id"),
        session_id=tool_input.get("session_id"),
        persona_id=persona_param,
        playbook=tool_input.get("playbook_id"),
    )

    persona_img_refs: List[Tuple[str, Asset, str, str, bytes]] = []
    if receipt.persona_reference_assets:
        persona_loaded = await load_persona_reference_media(
            db,
            effective_user_id,
            receipt.persona_reference_assets,
            media_kind="image",
        )
        existing_ref_set = set(ref_ids)
        for p_asset, p_fname, p_mime, p_bytes in persona_loaded:
            p_id = str(p_asset.id)
            item = (p_id, p_asset, p_fname, p_mime, p_bytes)
            persona_img_refs.append(item)
            if p_id not in existing_ref_set:
                existing_ref_set.add(p_id)
                ref_ids.append(p_id)
                loaded_refs.append(item)

    image_refs = [item for item in loaded_refs if (item[1].asset_type == "image" or item[3].startswith("image/"))]
    video_refs = [item for item in loaded_refs if (item[1].asset_type == "video" or item[3].startswith("video/"))]
    audio_refs = [item for item in loaded_refs if (item[1].asset_type == "audio" or item[3].startswith("audio/"))]

    if canonical_tool == "image_to_video" and not image_refs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="image_to_video requires a reference image asset",
        )
    if canonical_tool in ("videogen", "couplegen") and not loaded_refs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{canonical_tool} requires a reference image. Upload or attach one before running.",
        )
    if canonical_tool == "lipsync" and (not image_refs or not audio_refs):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="lipsync requires both a portrait reference image and an audio asset.",
        )
    if canonical_tool == "video2video" and not video_refs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="video2video requires a source video asset",
        )
    if canonical_tool in ("extend", "video_upscaler") and not video_refs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{canonical_tool} requires a source video asset",
        )
    if canonical_tool == "minimax_h3":
        if video_refs:
            variant = "v2v"
        elif image_refs or audio_refs:
            variant = "ref2v"
        else:
            variant = "t2v"

    compiled_prompt = compile_video_prompt(
        receipt.compiled_prompt or effective_prompt,
        camera_motion=camera_motion,
        motion_speed=motion_speed,
        duration=duration,
        fps=target_fps,
        aspect_ratio=aspect_ratio,
        grade=grade,
        lut=lut,
    ) or pre_compiled_prompt

    effective_mature = bool(
        receipt.mature
        or receipt.persona_mature
        or any(getattr(item[1], "mature", False) for item in loaded_refs)
    )

    try:
        if canonical_tool == "extend":
            source_video_bytes = video_refs[0][4]
            with tempfile.TemporaryDirectory(prefix="ks_extend_") as tmpdir:
                tmp_root = Path(tmpdir)
                src_path = tmp_root / "source.mp4"
                ext_path = tmp_root / "extension.mp4"
                stitched_path = tmp_root / "stitched.mp4"
                src_path.write_bytes(source_video_bytes)

                last_frame_bytes = await asyncio.to_thread(extract_last_frame, src_path)
                persona_second = persona_img_refs[0] if persona_img_refs else None
                exec_res = await asyncio.to_thread(
                    comfy_client.execute_video_workflow,
                    receipt.envelope,
                    "i2v",
                    compiled_prompt,
                    expected_mode=receipt.content_mode,
                    ref_image_bytes=last_frame_bytes,
                    ref_image_filename="last_frame.png",
                    second_image_bytes=persona_second[4] if persona_second else None,
                    second_image_filename=persona_second[2] if persona_second else None,
                    camera_motion=camera_motion,
                    motion_speed=motion_speed,
                    duration=duration,
                    fps=target_fps,
                    aspect_ratio=aspect_ratio,
                    width=tool_input.get("width"),
                    height=tool_input.get("height"),
                    seed=tool_input.get("seed"),
                    steps=tool_input.get("steps"),
                    grade=grade,
                    lut=lut,
                )
                ext_path.write_bytes(exec_res["bytes"])
                await asyncio.to_thread(stitch_video_segments, [src_path, ext_path], stitched_path, target_fps=target_fps)
                video_bytes = stitched_path.read_bytes()
                mime_type = "video/mp4"
        else:
            ref_img_1 = image_refs[0] if len(image_refs) >= 1 else None
            ref_img_2 = image_refs[1] if len(image_refs) >= 2 else None
            ref_vid_1 = video_refs[0] if len(video_refs) >= 1 else None
            ref_aud_1 = audio_refs[0] if len(audio_refs) >= 1 else None

            exec_res = await asyncio.to_thread(
                comfy_client.execute_video_workflow,
                receipt.envelope,
                variant,
                compiled_prompt,
                expected_mode=receipt.content_mode,
                ref_image_bytes=ref_img_1[4] if ref_img_1 else None,
                ref_image_filename=ref_img_1[2] if ref_img_1 else None,
                second_image_bytes=ref_img_2[4] if ref_img_2 else None,
                second_image_filename=ref_img_2[2] if ref_img_2 else None,
                ref_video_bytes=ref_vid_1[4] if ref_vid_1 else None,
                ref_video_filename=ref_vid_1[2] if ref_vid_1 else None,
                ref_audio_bytes=ref_aud_1[4] if ref_aud_1 else None,
                ref_audio_filename=ref_aud_1[2] if ref_aud_1 else None,
                camera_motion=camera_motion,
                motion_speed=motion_speed,
                duration=duration,
                fps=target_fps,
                aspect_ratio=aspect_ratio,
                width=tool_input.get("width"),
                height=tool_input.get("height"),
                denoise=tool_input.get("denoise") if tool_input.get("denoise") is not None else tool_input.get("strength"),
                seed=tool_input.get("seed"),
                steps=tool_input.get("steps"),
                grade=grade,
                lut=lut,
                scale_factor=scale_factor,
            )
            video_bytes = exec_res["bytes"]
            mime_type = exec_res.get("mime_type") or "video/mp4"
    except VideoOpsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"VIDEO_PROCESSING_ERROR: {exc}",
        ) from exc
    except ComfyUIError as exc:
        _raise_comfy_http_error(exc)

    progress.advance("VALIDATING_OUTPUT", "Running Tier-A deterministic video validation")
    harness_res = validate_asset_bytes(video_bytes, "video", mime_type)

    out_w, out_h = resolve_aspect_dimensions(aspect_ratio, tool_input.get("width"), tool_input.get("height"))
    out_dur = duration
    out_fps = float(exec_res.get("fps") or target_fps or VIDEO_DEFAULT_FPS)
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = Path(tmp.name)
        try:
            probed = probe_video_metadata(tmp_path)
            out_w = int(probed.get("width") or out_w)
            out_h = int(probed.get("height") or out_h)
            if probed.get("duration"):
                out_dur = float(probed["duration"])
            if probed.get("fps"):
                out_fps = float(probed["fps"])
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    except Exception:
        pass

    stored = await _persist_bytes(
        db,
        video_bytes,
        mime_type,
        f"{variant}_{gen_id[:8]}.mp4",
        "video",
        metadata={
            "source": "comfy_video_workflow",
            "tool": tool,
            "canonical_tool": canonical_tool,
            "variant": variant,
            "prompt": compiled_prompt,
            "camera_motion": camera_motion,
            "motion_speed": motion_speed,
            "duration": out_dur,
            "fps": out_fps,
            "target_fps": target_fps,
            "aspect_ratio": aspect_ratio,
            "grade": grade,
            "comfy_prompt_id": exec_res.get("prompt_id"),
            "envelope_id": receipt.envelope.envelope_id,
            "playbook_id": tool_input.get("playbook_id"),
            "persona_id": receipt.persona_id,
            "persona_version": receipt.persona_version,
        },
        owner_id=effective_user_id,
        project_id=tool_input.get("project_id"),
        width=out_w,
        height=out_h,
        duration_seconds=out_dur,
        mature=effective_mature,
    )

    await _persist_gate_audit_rows(
        db,
        receipt=receipt,
        effective_user_id=effective_user_id,
        project_id=tool_input.get("project_id"),
        capability_id=capability_id,
        workflow_name=variant,
        compiled_prompt=compiled_prompt,
        output_asset_id=stored["asset_id"],
        harness_res=harness_res,
        parent_asset_ids=ref_ids,
        relationship_type=relationship_type,
        started_at=started_at,
        seed=tool_input.get("seed"),
        metrics={
            "camera_motion": camera_motion,
            "motion_speed": motion_speed,
            "aspect_ratio": aspect_ratio,
            "duration": out_dur,
            "fps": out_fps,
            "target_fps": target_fps,
            "grade_applied": exec_res.get("grade_applied", False),
        },
        mature=effective_mature,
    )

    progress.advance("COMPLETED", "Video stored")
    return {
        "generation_id": gen_id,
        "status": "succeeded",
        "tool": tool,
        "input": tool_input,
        "outputs": [stored],
        "envelope_id": receipt.envelope.envelope_id,
        "comfy_prompt_id": exec_res.get("prompt_id"),
        "persona_id": receipt.persona_id,
        "persona_version": receipt.persona_version,
        "mature": effective_mature,
    }


async def _run_generation(
    request: ToolGenerationRequest,
    db: AsyncSession,
    progress: GenerationProgress,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    tool = (request.tool or "").strip()
    canonical_tool = TOOL_ALIASES.get(tool, tool)
    tool_input = request.input or {}
    progress.advance("VALIDATING", "Checking the tool and its inputs")
    if canonical_tool not in ALL_TOOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tool '{tool}'. Expected one of: {', '.join(sorted(ALL_TOOLS))}",
        )

    gen_id = str(uuid.uuid4())
    playbook_ctx = _playbook_context(tool_input)
    prompt = _user_prompt(tool_input)
    if playbook_ctx and canonical_tool != "run_any_llm" and playbook_ctx not in prompt:
        prompt = f"{playbook_ctx}\n\nUser request:\n{prompt}".strip()

    if canonical_tool in LLM_TOOLS:
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="run_any_llm requires a prompt",
            )
        effective_user_id = owner_id or await _ensure_studio_user(db)
        receipt = await _authorize_through_gate(
            db,
            effective_user_id,
            intent="analyze",
            prompt_text=prompt,
            capability_id="cognition.reasoning",
            arguments={"max_tokens": int(tool_input.get("max_tokens") or 2048)},
            input_asset_ids=[],
            project_id=tool_input.get("project_id"),
            session_id=tool_input.get("session_id"),
            persona_id=tool_input.get("as") or tool_input.get("persona_id"),
            playbook=tool_input.get("playbook_id"),
        )
        default_system = (
            "You are KEYSTONE Creative Prompt Cognition. Expand user ideas into rich cinematic "
            "details with camera, lighting, and composition specifics."
        )
        system_prompt = str(tool_input.get("system_prompt") or default_system)
        if playbook_ctx:
            system_prompt = f"{system_prompt}\n\nAttached playbook context:\n{playbook_ctx}"
        if receipt.persona_sheet:
            system_prompt = f"{system_prompt}\n\n[PERSONA SHEET]\n{receipt.persona_sheet}"
        await _dispatch(progress, playbook_ctx, "the language model")
        text = await asyncio.to_thread(
            _call_llm,
            prompt,
            system_prompt,
            int(tool_input.get("max_tokens") or 2048),
            tool_input,
        )
        progress.advance("VALIDATING_OUTPUT", "Checking the model's answer")
        if not (text or "").strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="ENGINE_EMPTY_OUTPUT: the LLM returned an empty answer",
            )
        progress.advance("COMPLETED", "Answer ready")
        return {
            "generation_id": gen_id,
            "status": "succeeded",
            "tool": tool,
            "input": tool_input,
            "outputs": [],
            "text": text,
            "envelope_id": receipt.envelope.envelope_id,
            "persona_id": receipt.persona_id,
            "persona_version": receipt.persona_version,
        }

    if (
        canonical_tool not in VIDEO_TOOL_SPECS
        and canonical_tool not in IMAGE_TOOL_SPECS
        and canonical_tool not in VIDEO_POST_TOOLS
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_no_engine_message(tool),
        )

    if (
        canonical_tool in ("lipsync", "couplegen", "faceswap", "photoshoot", "facegen", "carousel", "collaber")
        and not comfy_client.is_configured()
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_no_engine_message(tool),
        )

    effective_user_id = owner_id or await _ensure_studio_user(db)

    if canonical_tool == "video_merger":
        from services.comfy.src.video_ops import convert_video_bytes_fps
        from services.harness.src.evaluators.deterministic import validate_asset_bytes

        ref_ids = _collect_ref_ids(tool_input)
        if len(ref_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="video_merger requires at least 2 video clips attached.",
            )
        clip_blobs: List[Tuple[str, Asset, bytes]] = []
        for cid in ref_ids:
            loaded_clip = await _load_asset_with_bytes(db, cid, effective_user_id)
            if loaded_clip is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Clip asset '{cid}' was not found in studio storage",
                )
            c_asset, _c_fname, c_mime, c_bytes = loaded_clip
            if c_asset.asset_type != "video" and not c_mime.startswith("video/"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Asset '{cid}' is not a video clip.",
                )
            clip_blobs.append((cid, c_asset, c_bytes))

        raw_fps = (
            tool_input.get("fps")
            or tool_input.get("frame_rate")
            or tool_input.get("framerate")
            or (tool_input.get("output_prefs") or {}).get("framerate")
        )
        target_fps = resolve_target_fps(raw_fps, default=VIDEO_DEFAULT_FPS)
        started_at = datetime.now(timezone.utc)
        gate_args = _build_gate_arguments(tool_input, "video.i2v", ref_ids[0], "16:9", 5.0, 2)
        receipt = await _authorize_through_gate(
            db,
            effective_user_id,
            intent="animate",
            prompt_text=prompt or "Multi-clip timeline sequence merge",
            capability_id="video.i2v",
            arguments=gate_args,
            input_asset_ids=ref_ids,
            project_id=tool_input.get("project_id"),
            session_id=tool_input.get("session_id"),
            persona_id=tool_input.get("as") or tool_input.get("persona_id"),
            playbook=tool_input.get("playbook_id"),
        )
        await _dispatch(progress, playbook_ctx, "FFmpeg Video Sequencer")
        with tempfile.TemporaryDirectory(prefix="ks_merge_") as tmpdir:
            tmp_root = Path(tmpdir)
            seg_paths: List[Path] = []
            for idx, (_cid, _ca, cbytes) in enumerate(clip_blobs):
                seg = tmp_root / f"clip_{idx:03d}.mp4"
                seg.write_bytes(cbytes)
                seg_paths.append(seg)
            merged_out = tmp_root / "merged.mp4"
            await asyncio.to_thread(stitch_video_segments, seg_paths, merged_out, target_fps=target_fps)
            merged_bytes = merged_out.read_bytes()
            if target_fps:
                merged_bytes = await asyncio.to_thread(convert_video_bytes_fps, merged_bytes, target_fps)
            probed = probe_video_metadata(merged_out)

        progress.advance("VALIDATING_OUTPUT", "Running Tier-A deterministic video validation")
        harness_res = validate_asset_bytes(merged_bytes, "video", "video/mp4")
        effective_mature = bool(
            receipt.mature
            or receipt.persona_mature
            or any(getattr(item[1], "mature", False) for item in clip_blobs)
        )
        stored = await _persist_bytes(
            db,
            merged_bytes,
            "video/mp4",
            f"merged_{gen_id[:8]}.mp4",
            "video",
            metadata={
                "source": "ffmpeg_video_merger",
                "tool": tool,
                "fps": float(probed.get("fps") or target_fps),
                "clips": ref_ids,
                "envelope_id": receipt.envelope.envelope_id,
            },
            owner_id=effective_user_id,
            project_id=tool_input.get("project_id"),
            width=int(probed.get("width") or 1280),
            height=int(probed.get("height") or 720),
            duration_seconds=float(probed.get("duration") or 5.0),
            mature=effective_mature,
        )
        await _persist_gate_audit_rows(
            db,
            receipt=receipt,
            effective_user_id=effective_user_id,
            project_id=tool_input.get("project_id"),
            capability_id="video.i2v",
            workflow_name="video_merger",
            compiled_prompt=receipt.compiled_prompt or (prompt or "Multi-clip sequence"),
            output_asset_id=stored["asset_id"],
            harness_res=harness_res,
            parent_asset_ids=ref_ids,
            relationship_type="sequence",
            started_at=started_at,
            mature=effective_mature,
        )
        progress.advance("COMPLETED", "Merged sequence stored")
        return {
            "generation_id": gen_id,
            "status": "succeeded",
            "tool": tool,
            "input": tool_input,
            "outputs": [stored],
            "envelope_id": receipt.envelope.envelope_id,
            "mature": effective_mature,
        }

    if canonical_tool in VIDEO_TOOL_SPECS:
        return await _run_video_generation(
            tool=tool,
            canonical_tool=canonical_tool,
            tool_input=tool_input,
            prompt=prompt,
            playbook_ctx=playbook_ctx,
            gen_id=gen_id,
            db=db,
            progress=progress,
            effective_user_id=effective_user_id,
        )

    if canonical_tool in IMAGE_TOOL_SPECS:
        from apps.api.src.services.gate import load_persona_reference_media

        intent, workflow_name, capability_id, relationship_type = IMAGE_TOOL_SPECS[canonical_tool]
        ref_ids = _collect_ref_ids(tool_input)
        ref_bytes: Optional[bytes] = None
        ref_filename: Optional[str] = None
        ref_mature = False
        if ref_ids:
            loaded_ref_asset = await _load_asset_with_bytes(db, ref_ids[0], effective_user_id)
            if loaded_ref_asset is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reference asset '{ref_ids[0]}' was not found in studio storage",
                )
            ref_asset_obj, ref_filename, _ref_mime, ref_bytes = loaded_ref_asset
            ref_mature = bool(getattr(ref_asset_obj, "mature", False))

        if canonical_tool == "facegen":
            dna_bits = [
                f"{k}: {tool_input[k]}"
                for k in ("gender", "age", "origin", "body_type", "eye_color", "hair_color", "hair_style", "makeup")
                if tool_input.get(k)
            ]
            dna_summary = ", ".join(dna_bits)
            prompt = f"Portrait identity sheet ({dna_summary}). {prompt}".strip()
        elif canonical_tool == "photoshoot" and not prompt:
            prompt = f"Editorial studio portrait session ({tool_input.get('category_id', 'studio_editorial')}), natural lighting and sharp detail"
        elif canonical_tool == "carousel" and not prompt:
            prompt = "Consistent multi-angle turnaround view preserving exact subject identity, clothing, and lighting"
        elif canonical_tool == "faceswap" and not prompt:
            prompt = "Preserve facial likeness and identity seamlessly matched to scene lighting and camera angle"
        elif canonical_tool == "collaber" and not prompt:
            prompt = "Two character personas composed naturally into one cohesive scene with preserved likeness"

        if canonical_tool in ("image_editor", "upscaler", "faceswap", "carousel") and not ref_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{canonical_tool} requires a source image asset",
            )

        grade = normalize_grade_params(tool_input)
        aspect_ratio = str(tool_input.get("aspect_ratio") or tool_input.get("ratio") or "1:1").strip().split()[0]
        raw_scale = tool_input.get("scale_factor") or tool_input.get("scale") or 2
        scale_factor = 4 if int(raw_scale) >= 4 else 2

        await _dispatch(progress, playbook_ctx, f"ComfyUI ({workflow_name})")

        from services.comfy.src.client import decode_png_rgba
        from services.harness.src.evaluators.deterministic import (
            _parse_image_dimensions_fallback,
            validate_asset_bytes,
        )

        gate_args = _build_gate_arguments(
            tool_input,
            capability_id,
            ref_ids[0] if ref_ids else None,
            aspect_ratio,
            5.0,
            scale_factor,
        )
        started_at = datetime.now(timezone.utc)
        receipt = await _authorize_through_gate(
            db,
            effective_user_id,
            intent=intent,
            prompt_text=prompt or f"{tool} generation",
            capability_id=capability_id,
            arguments=gate_args,
            input_asset_ids=ref_ids,
            project_id=tool_input.get("project_id"),
            session_id=tool_input.get("session_id"),
            persona_id=tool_input.get("as") or tool_input.get("persona_id"),
            playbook=tool_input.get("playbook_id"),
        )

        if ref_bytes is None and receipt.persona_reference_assets:
            persona_loaded = await load_persona_reference_media(
                db,
                effective_user_id,
                receipt.persona_reference_assets,
                media_kind="image",
            )
            if persona_loaded:
                p_asset, p_fname, _p_mime, p_bytes = persona_loaded[0]
                ref_bytes = p_bytes
                ref_filename = p_fname
                ref_mature = ref_mature or bool(getattr(p_asset, "mature", False))
                if str(p_asset.id) not in ref_ids:
                    ref_ids.append(str(p_asset.id))

        effective_mature = bool(receipt.mature or receipt.persona_mature or ref_mature)
        compiled_image_prompt = receipt.compiled_prompt or (prompt or f"{tool} generation")

        src_dims: Optional[Tuple[int, int]] = None
        if ref_bytes:
            try:
                w, h, _ = decode_png_rgba(ref_bytes)
                src_dims = (w, h)
            except Exception:
                src_dims = _parse_image_dimensions_fallback(ref_bytes)

        uploaded_name = None
        if ref_bytes:
            input_img_bytes = ref_bytes
            if canonical_tool == "upscaler" and is_non_neutral_grade(grade):
                input_img_bytes = apply_grade(
                    ref_bytes,
                    exposure=grade["exposure"],
                    contrast=grade["contrast"],
                    saturation=grade["saturation"],
                    warmth=grade["warmth"],
                )
            try:
                uploaded_name = await asyncio.to_thread(
                    upload_image_to_comfy,
                    input_img_bytes,
                    ref_filename or f"ref_{gen_id[:8]}.png",
                )
            except ComfyUIError as exc:
                _raise_comfy_http_error(exc)

        effective_wf = (
            "sdxl_edit"
            if (canonical_tool in ("by_ref", "by_prompt") and uploaded_name)
            else workflow_name
        )
        out_w, out_h = resolve_aspect_dimensions(aspect_ratio, tool_input.get("width"), tool_input.get("height"))

        selected_ckpt = str(tool_input.get("checkpoint") or tool_input.get("model") or tool_input.get("selected_model") or "").strip()
        explicit_safetensor = selected_ckpt if selected_ckpt.endswith((".safetensors", ".ckpt", ".pth")) else None

        try:
            exec_res = await asyncio.to_thread(
                comfy_client.execute_workflow,
                receipt.envelope,
                workflow_name=effective_wf,
                expected_mode=receipt.content_mode,
                parameters={
                    "prompt": compiled_image_prompt,
                    "negative_prompt": tool_input.get("negative_prompt"),
                    "image_name": uploaded_name,
                    "checkpoint": explicit_safetensor,
                    "model_name": explicit_safetensor if effective_wf == "esrgan_upscale" else None,
                    "width": out_w,
                    "height": out_h,
                    "steps": tool_input.get("steps"),
                    "cfg": tool_input.get("cfg") or tool_input.get("guidance"),
                    "denoise": tool_input.get("denoise") or tool_input.get("strength"),
                    "seed": tool_input.get("seed"),
                    "scale_factor": scale_factor,
                    "grade": grade,
                },
            )
        except ComfyUIError as exc:
            _raise_comfy_http_error(exc)

        image_bytes = exec_res.get("bytes") or b""
        mime_type = exec_res.get("mime_type") or "image/png"

        progress.advance("VALIDATING_OUTPUT", "Running Tier-A deterministic validation")
        harness_res = validate_asset_bytes(
            image_bytes,
            "image",
            mime_type,
            source_dimensions=src_dims,
            require_upscale_delta=(intent == "upscale" and src_dims is not None),
        )

        stored = await _persist_bytes(
            db,
            image_bytes,
            mime_type,
            f"{effective_wf}_{gen_id[:8]}.png",
            "image",
            metadata={
                "source": "comfy_workflow",
                "tool": tool,
                "intent": intent,
                "workflow": effective_wf,
                "prompt": compiled_image_prompt,
                "comfy_prompt_id": exec_res.get("prompt_id"),
                "playbook_id": tool_input.get("playbook_id"),
                "persona_id": receipt.persona_id,
                "persona_version": receipt.persona_version,
            },
            owner_id=effective_user_id,
            project_id=tool_input.get("project_id"),
            width=out_w,
            height=out_h,
            mature=effective_mature,
        )

        await _persist_gate_audit_rows(
            db,
            receipt=receipt,
            effective_user_id=effective_user_id,
            project_id=tool_input.get("project_id"),
            capability_id=capability_id,
            workflow_name=effective_wf,
            compiled_prompt=compiled_image_prompt,
            output_asset_id=stored["asset_id"],
            harness_res=harness_res,
            parent_asset_ids=ref_ids,
            relationship_type=relationship_type,
            started_at=started_at,
            seed=tool_input.get("seed"),
            mature=effective_mature,
        )

        progress.advance("COMPLETED", "Image stored")
        return {
            "generation_id": gen_id,
            "status": "succeeded",
            "tool": tool,
            "input": tool_input,
            "outputs": [stored],
            "envelope_id": receipt.envelope.envelope_id,
            "persona_id": receipt.persona_id,
            "persona_version": receipt.persona_version,
            "mature": effective_mature,
        }

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_no_engine_message(tool),
    )
