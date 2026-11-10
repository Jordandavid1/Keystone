"""
KEYSTONE studio generative router.

Keeps the /v1/zencreator request/response contract used by the Next.js studio UX,
but never calls the paid ZenCreator API and never returns mock or placeholder media.

Generation is routed to Jordan's Colab engine:
  - run_any_llm -> OpenAI-compatible LLM (OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL)
  - videogen    -> MiniMax H3 / PinkCherry reference-to-video via apps.api.src.creative.h3
  - all other tools -> an explicit NO_ENGINE_CONFIGURED error
"""

from __future__ import annotations

import json
import os
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.creative import h3
from apps.api.src.db.models import Asset, User
from apps.api.src.db.session import get_db
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.routers.assets import content_url
from apps.api.src.storage.service import AssetStorageService, generate_storage_key
from packages.prompt_engine.playbooks import PlaybookRegistry
from services.cognition.src.client import CognitionConnector, load_keystone_dotenv

router = APIRouter(prefix="/v1/zencreator", tags=["ZenCreator Generative Pipeline"])

_CATALOG_FILE = Path(__file__).resolve().parents[4] / ".firecrawl" / "zc-tools-catalog.json"

STUDIO_USER_ID = "00000000-0000-4000-8000-000000000001"
STUDIO_EMAIL = "studio@local.keystone"

LLM_TOOLS = {"run_any_llm"}
H3_VIDEO_TOOLS = {"videogen"}

ALL_TOOLS = {
    "by_prompt",
    "by_ref",
    "image_editor",
    "faceswap",
    "photoshoot",
    "facegen",
    "carousel",
    "collaber",
    "couplegen",
    "upscaler",
    "videogen",
    "text_to_video",
    "video2video",
    "lipsync",
    "video_upscaler",
    "video_merger",
    "run_any_llm",
}


class ToolGenerationRequest(BaseModel):
    tool: str = Field(..., description="Tool name from the 17-tool catalog")
    input: Dict[str, Any] = Field(default_factory=dict, description="Tool input matching input_schema")
    async_mode: bool = Field(default=False, description="Reserved; this router runs tools synchronously")


def _no_engine_message(tool: str) -> str:
    return (
        f"NO_ENGINE_CONFIGURED: tool '{tool}' has no engine or model available on the Colab runtime. "
        "The connected engine provides an OpenAI-compatible LLM for run_any_llm and MiniMax H3 / "
        "PinkCherry reference-to-video for videogen. Image tools, faceswap, upscalers, lipsync, "
        "text_to_video, video2video, couplegen, and video_merger are not configured. "
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
            display_name="KEYSTONE Studio",
            status="active",
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
) -> Dict[str, Any]:
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ENGINE_EMPTY_OUTPUT: the engine returned no bytes",
        )
    tenant_id = await _ensure_studio_user(db)
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
        media_type=media_type,
        storage_provider=storage.provider.__class__.__name__,
        metadata=metadata or {},
    )
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
        "created_at": time.time(),
    }


async def _load_reference_bytes(
    db: AsyncSession, asset_id: str
) -> Optional[Tuple[str, str, bytes]]:
    result = await db.execute(select(Asset).where(Asset.id == str(asset_id)).where(Asset.deleted_at.is_(None)))
    asset = result.scalar_one_or_none()
    if asset is None:
        return None
    storage = AssetStorageService()
    try:
        payload = await storage.provider.get_object(asset.storage_key)
    except FileNotFoundError:
        return None
    filename = (asset.metadata_ or {}).get("original_filename") or asset.storage_key.split("/")[-1] or f"{asset_id}.bin"
    return filename, asset.mime_type or "application/octet-stream", payload


def _collect_ref_ids(tool_input: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for key in (
        "ref_asset_id",
        "reference_asset_id",
        "image_asset_id",
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
    # de-dupe while preserving order
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
    if _CATALOG_FILE.exists():
        try:
            return json.loads(_CATALOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "source": "builtin_catalog",
        "tools": {name: {"metadata": {"description": name}} for name in sorted(ALL_TOOLS)},
    }


@router.get("/playbooks", summary="List canonical prompt-engine playbooks")
def list_playbooks() -> Dict[str, Any]:
    playbooks = [item.to_dict() for item in PlaybookRegistry.list_playbooks()]
    return {"count": len(playbooks), "playbooks": playbooks}


@router.get("/engine", summary="Describe the configured Colab generation engine")
def engine_status() -> Dict[str, Any]:
    llm_configured, endpoint, _api_key, model = _llm_endpoint()
    comfy = h3.describe()
    return {
        "online": bool(llm_configured or comfy.get("configured")),
        "llm": {
            "configured": llm_configured,
            "endpoint_present": bool(endpoint),
            "model": model if llm_configured else None,
        },
        "comfy": comfy,
        "wired_tools": sorted(LLM_TOOLS | H3_VIDEO_TOOLS),
        "unwired_tools": sorted(ALL_TOOLS - LLM_TOOLS - H3_VIDEO_TOOLS),
    }


@router.get("/balance", summary="Get Credit Balance")
def get_balance() -> Dict[str, Any]:
    return {
        "balance": None,
        "currency": "credits",
        "status": "local_engine",
        "note": "ZenCreator billing is disabled. Generation uses the Colab engine and is not charged per tool.",
    }


@router.post("/upload", summary="Upload Media Asset (Image, Video, Audio)")
async def upload_asset(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
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


@router.post("/generate", summary="Execute Any Generative Pipeline Tool")
async def generate_tool(
    request: ToolGenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    tool = (request.tool or "").strip()
    tool_input = request.input or {}
    if tool not in ALL_TOOLS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tool '{tool}'. Expected one of: {', '.join(sorted(ALL_TOOLS))}",
        )

    gen_id = str(uuid.uuid4())
    playbook_ctx = _playbook_context(tool_input)
    prompt = _user_prompt(tool_input)
    if playbook_ctx and tool != "run_any_llm" and playbook_ctx not in prompt:
        prompt = f"{playbook_ctx}\n\nUser request:\n{prompt}".strip()

    if tool in LLM_TOOLS:
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="run_any_llm requires a prompt",
            )
        default_system = (
            "You are KEYSTONE Creative Prompt Cognition. Expand user ideas into rich cinematic "
            "details with camera, lighting, and composition specifics."
        )
        system_prompt = str(tool_input.get("system_prompt") or default_system)
        if playbook_ctx:
            system_prompt = f"{system_prompt}\n\nAttached playbook context:\n{playbook_ctx}"
        text = _call_llm(
            prompt,
            system_prompt,
            int(tool_input.get("max_tokens") or 2048),
            tool_input,
        )
        return {
            "generation_id": gen_id,
            "status": "succeeded",
            "tool": tool,
            "input": tool_input,
            "outputs": [],
            "text": text,
        }

    if tool in H3_VIDEO_TOOLS:
        ref_ids = _collect_ref_ids(tool_input)
        references: List[Tuple[str, str, bytes]] = []
        for ref_id in ref_ids:
            loaded = await _load_reference_bytes(db, ref_id)
            if loaded is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reference asset '{ref_id}' was not found in studio storage",
                )
            filename, mime_type, payload = loaded
            references.append((filename, mime_type, payload))
        if not references:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="videogen requires a reference image. Upload or attach one before running.",
            )
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="videogen requires a prompt describing the motion and scene",
            )
        try:
            video_bytes, mime_type, meta = await h3.generate(prompt, references)
        except h3.H3Error as exc:
            message = str(exc)
            if message.startswith("H3_NOT_CONFIGURED"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "NO_ENGINE_CONFIGURED: MiniMax H3 / PinkCherry ComfyUI is not wired. "
                        "Set KEYSTONE_COMFY_URL or KEYSTONE_COMFY_PUBLIC_URL to the Colab "
                        "ComfyUI address and keep KEYSTONE_COMFY_WORKFLOW at workflows/h3-ref2va.json. "
                        f"{message}"
                    ),
                ) from exc
            if message.startswith("COMFY_UNREACHABLE") or "UNREACHABLE" in message:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"ENGINE_UNREACHABLE: {message}",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ENGINE_ERROR: {message}",
            ) from exc

        stored = await _persist_bytes(
            db,
            video_bytes,
            mime_type or "video/mp4",
            f"h3_{gen_id[:8]}.mp4",
            "video",
            metadata={
                "source": "colab_h3",
                "tool": tool,
                "prompt": prompt,
                "engine_meta": meta,
                "playbook_id": tool_input.get("playbook_id"),
            },
        )
        stored["width"] = tool_input.get("width")
        stored["height"] = tool_input.get("height")
        return {
            "generation_id": gen_id,
            "status": "succeeded",
            "tool": tool,
            "input": tool_input,
            "outputs": [stored],
        }

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_no_engine_message(tool),
    )
