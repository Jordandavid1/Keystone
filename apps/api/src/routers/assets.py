"""
KEYSTONE Asset Router (/v1/assets)
Asset registration, storage keys, short-expiry signed URLs, and Lineage DAG tracking.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status, File, UploadFile, Form
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.models import Asset, AuthorityDecision, Job
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.services.gate import (
    GateService,
    ensure_job_for_receipt,
    load_persona_reference_media,
    resolve_content_mode,
)
from apps.api.src.storage.service import (
    STORAGE_BASE_URL,
    AssetStorageService,
    generate_signed_url,
    generate_storage_key,
    validate_signed_url,
)
from services.comfy.src.client import (
    ComfyUIError,
    ComfyUINotConfigured,
    comfy_client,
)

STORAGE_KEY_PATTERN = re.compile(r"^tenants/([a-zA-Z0-9_-]+)/assets/([a-zA-Z0-9_-]+)/([a-zA-Z0-9._-]+)$")
SIGNED_URL_TTL_SECONDS = 900

router = APIRouter(prefix="/v1/assets", tags=["Assets"])


def content_url(asset: Any) -> str:
    """Relative, signed URL that serves this asset's bytes from the API itself."""
    signed = generate_signed_url(asset.storage_key, expiry_seconds=SIGNED_URL_TTL_SECONDS)
    return f"/v1/assets/{asset.id}/content?{signed.split('?', 1)[1]}"


class CreateAssetRequest(BaseModel):
    filename: str
    mime_type: str
    byte_size: int
    storage_key: Optional[str] = None
    project_id: Optional[str] = None
    media_type: Optional[str] = "image"
    storage_provider: Optional[str] = "local"
    metadata: Optional[Dict[str, Any]] = None


class UploadAssetRequest(BaseModel):
    filename: str
    mime_type: str
    byte_size: int
    project_id: Optional[str] = None
    media_type: Optional[str] = "image"


class GenerateAssetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(..., min_length=1, description="Compiled generation prompt")
    negative_prompt: Optional[str] = None
    title: Optional[str] = None
    width: int = Field(1024, ge=256, le=4096)
    height: int = Field(1024, ge=256, le=4096)
    steps: int = Field(25, ge=1, le=100)
    cfg: float = Field(6.0, ge=1.0, le=30.0)
    seed: Optional[int] = Field(None, ge=0)
    checkpoint: Optional[str] = None
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    parent_asset_id: Optional[str] = None
    reference_asset_id: Optional[str] = Field(None, description="Anchor asset used as visual or motion reference")
    reference_type: Optional[str] = Field("img2img", description="Reference role: img2img, style, composition, video_anchor")
    denoise: Optional[float] = Field(0.65, ge=0.05, le=1.0, description="Denoising strength for reference conditioning")
    mode: Optional[str] = Field("text2image", description="text2image, img2img, upscale, i2v, minimax_h3")
    intent: Optional[str] = Field(None, description="Intent hint: create, edit, vary, animate")
    playbook_id: Optional[Any] = Field(None, description="Optional domain playbook ID")
    as_persona: Optional[str] = Field(None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(None, description="Optional persona ID (alias for `as`)")
    scale_factor: Optional[int] = Field(2, ge=2, le=4)
    duration_seconds: Optional[int] = Field(5, ge=1, le=15)
    resolution: Optional[str] = Field("720p", description="Video resolution: 480p, 720p, 1080p, 2k, 4k")
    relationship_type: Optional[str] = None
    job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpscaleAssetRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scale_factor: int = Field(2, ge=2, le=4, description="Resolution scale multiplier (2 for 2x, 4 for 4x)")
    scale: Optional[int] = Field(None, ge=2, le=4, description="Alias for scale_factor")
    prompt: Optional[str] = Field(None, description="Optional guidance prompt for detail synthesis")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    as_persona: Optional[str] = Field(None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(None, description="Optional persona ID (alias for `as`)")


class CreateRelationshipRequest(BaseModel):
    child_asset_id: str
    relationship_type: str
    job_id: Optional[str] = None


@router.post("", summary="Register an asset and receive signed storage URL")
async def register_asset(
    req: CreateAssetRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    if req.storage_key:
        match = STORAGE_KEY_PATTERN.match(req.storage_key)
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ILLEGAL_STORAGE_KEY: Malformed storage key format: {req.storage_key}"
            )
        key_tenant, _, key_filename = match.groups()
        if key_tenant != str(tenant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ILLEGAL_STORAGE_KEY: Key belongs to tenant '{key_tenant}', caller is '{tenant_id}'"
            )
        if key_filename in {".", ".."} or key_filename.strip(".") == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ILLEGAL_STORAGE_KEY: Invalid filename in storage key: {key_filename}"
            )
        storage_key = req.storage_key
    else:
        storage_key = generate_storage_key(tenant_id, asset_id, req.filename)

    try:
        asset = await asset_repo.create_asset(
            id=asset_id,
            filename=req.filename,
            mime_type=req.mime_type,
            byte_size=req.byte_size,
            storage_key=storage_key,
            project_id=req.project_id,
            media_type=req.media_type or "image",
            storage_provider=req.storage_provider or "local",
            metadata=req.metadata
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    download_url = content_url(asset)
    return {
        "status": "ok",
        "id": asset.id,
        "owner_id": asset.user_id,
        "project_id": asset.project_id,
        "media_type": asset.asset_type,
        "mime_type": asset.mime_type,
        "storage_provider": req.storage_provider or "local",
        "storage_key": asset.storage_key,
        "byte_size": asset.size_bytes,
        "metadata": getattr(asset, "metadata_", None) or {},
        "download_url": download_url,
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


ALLOWED_UPLOAD_MIMES = frozenset({
    "image/png",
    "image/jpeg",
    "image/webp",
    "video/mp4",
    "video/webm",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
})
DEFAULT_MAX_UPLOAD_BYTES = 250 * 1024 * 1024


@router.post("/upload-file", summary="Upload photo or video file directly via multipart/form-data")
async def upload_asset_file(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    media_type: Optional[str] = Form(None),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    mime_type = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    if mime_type not in ALLOWED_UPLOAD_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"UNSUPPORTED_MIME_TYPE: '{mime_type}' is not in the upload allowlist",
        )
    max_bytes = int(os.getenv("KEYSTONE_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES)))
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"PAYLOAD_TOO_LARGE: Upload exceeds {max_bytes} bytes",
        )
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    raw_filename = file.filename or "upload.bin"

    detected_media = media_type
    if not detected_media:
        if mime_type.startswith("video/") or raw_filename.lower().endswith((".mp4", ".webm", ".mov", ".mkv", ".avi")):
            detected_media = "video"
        else:
            detected_media = "image"

    storage_key = generate_storage_key(tenant_id, asset_id, raw_filename)
    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, content, mime_type)

    asset = await asset_repo.create_asset(
        id=asset_id,
        filename=raw_filename,
        mime_type=mime_type,
        byte_size=len(content),
        storage_key=storage_key,
        project_id=project_id,
        media_type=detected_media,
        storage_provider=storage.provider.__class__.__name__,
        metadata={
            "source": "user_upload",
            "original_filename": raw_filename,
            "media_type": detected_media,
        }
    )

    download_url = content_url(asset)
    asset_meta = getattr(asset, "metadata_", None) or {}
    return {
        "status": "ok",
        "id": asset.id,
        "filename": asset_meta.get("filename", asset.storage_key.split("/")[-1]),
        "media_type": asset.asset_type,
        "mime_type": asset.mime_type,
        "byte_size": asset.size_bytes,
        "storage_key": asset.storage_key,
        "download_url": download_url,
        "metadata": asset_meta,
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


@router.post(
    "/generate",
    summary="Generate an image on ComfyUI and persist the returned bytes"
)
async def generate_asset(
    req: GenerateAssetRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Runs a real text-to-image workflow against the configured ComfyUI runtime,
    stores the PNG, registers the asset, and links it into the lineage DAG."""
    if not comfy_client.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "COMFY_NOT_CONFIGURED: no ComfyUI runtime is wired up. Set "
                "COMFY_BASE_URL to the daemon or Kaggle tunnel URL and restart the API."
            )
        )

    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    parent_asset = None
    ref_asset = None
    ref_bytes = None

    if req.reference_asset_id:
        ref_asset = await asset_repo.get_asset_by_id(req.reference_asset_id)
        if not ref_asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reference asset not found or access denied",
            )
        storage_svc = AssetStorageService()
        try:
            ref_bytes = await storage_svc.provider.get_object(ref_asset.storage_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"REFERENCE_ASSET_LOAD_FAILED: {exc}",
            ) from exc

    if req.parent_asset_id:
        parent_asset = await asset_repo.get_asset_by_id(req.parent_asset_id)
        if not parent_asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent asset not found or access denied"
            )

    if req.project_id:
        from apps.api.src.repositories.projects import ProjectRepository
        project = await ProjectRepository(db, tenant_id=tenant_id).get_project_by_id(req.project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied",
            )

    target_persona_id = req.as_persona or req.persona_id
    mode_lower = (req.mode or "").lower()
    is_video_mode = (
        mode_lower in ("minimax_h3", "animate", "i2v", "video")
        or "minimax" in mode_lower
        or (req.intent or "").lower() == "animate"
    )
    gate_intent = (req.intent or ("animate" if is_video_mode else ("edit" if req.reference_asset_id else "generate"))).lower()
    if gate_intent == "create":
        gate_intent = "generate"
    elif gate_intent == "vary":
        gate_intent = "variate"
    capability_id = (
        "video.minimax_h3_ref2va"
        if is_video_mode
        else ("image.editing" if gate_intent == "edit" and req.reference_asset_id else "image.generation")
    )

    receipt = None
    persona_id_resolved: Optional[str] = None
    persona_version_resolved: Optional[int] = None
    persona_sheet: Optional[str] = None
    persona_descriptors: Optional[str] = None
    persona_ref_ids: List[str] = []
    effective_mature = False

    if not req.job_id:
        gate_args: Dict[str, Any] = {
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "width": req.width,
            "height": req.height,
            "steps": req.steps,
            "guidance": req.cfg,
        }
        if req.reference_asset_id:
            gate_args["input_asset_id"] = req.reference_asset_id
        if is_video_mode:
            gate_args["duration_seconds"] = max(1, min(10, int(req.duration_seconds or 5)))
            gate_args["resolution"] = req.resolution or "720p"

        input_ids = [aid for aid in (req.parent_asset_id, req.reference_asset_id) if aid]
        receipt = await GateService.authorize_async(
            db,
            user_id=tenant_id,
            intent=gate_intent,
            prompt_text=req.prompt,
            capability_id=capability_id,
            arguments=gate_args,
            project_id=req.project_id,
            session_id=req.session_id,
            persona_id=target_persona_id,
            input_asset_ids=input_ids,
            playbook=req.playbook_id,
        )
        job = await ensure_job_for_receipt(
            db,
            receipt=receipt,
            user_id=tenant_id,
            project_id=req.project_id,
            capability_id=capability_id,
            provider_id="comfyui",
            workflow_id="wf_default",
            status_value="RUNNING",
        )
        await db.commit()
        await db.refresh(job)
        req.job_id = receipt.job_id
        persona_id_resolved = receipt.persona_id
        persona_version_resolved = receipt.persona_version
        persona_sheet = receipt.persona_sheet
        persona_descriptors = receipt.persona_descriptors
        persona_ref_ids = list(receipt.persona_reference_assets or [])
        effective_mature = bool(
            receipt.mature
            or getattr(parent_asset, "mature", False)
            or getattr(ref_asset, "mature", False)
        )
    else:
        job_result = await db.execute(
            select(Job)
            .where(Job.id == str(req.job_id))
            .where(Job.user_id == tenant_id)
        )
        job = job_result.scalar_one_or_none()
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found or access denied",
            )
        if job.status != "RUNNING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generation can only execute for a job in RUNNING state.",
            )

        decision_result = await db.execute(
            select(AuthorityDecision)
            .where(AuthorityDecision.request_id == job.request_id)
        )
        from services.authority.src.rules import CAPABILITY_NAMESPACES
        decision = decision_result.scalar_one_or_none()
        if (
            decision is None
            or decision.decision != "approve"
            or decision.capability_id not in CAPABILITY_NAMESPACES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The job has no persisted approval for the requested creative capability.",
            )

        authorized = decision.sanitized_arguments or {}
        if authorized.get("prompt") and authorized.get("prompt") != req.prompt:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Generation parameters do not match the persisted authority approval.",
            )
        for key in ("width", "height", "steps"):
            if key in authorized and getattr(req, key) is not None:
                if int(authorized[key]) != int(getattr(req, key)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Generation parameter '{key}' does not match the persisted authority approval.",
                    )

        effective_persona_id = target_persona_id or job.persona_id
        effective_mature = (
            (job.content_mode == "unrestricted")
            or bool(getattr(parent_asset, "mature", False))
            or bool(getattr(ref_asset, "mature", False))
        )
        if effective_persona_id:
            from apps.api.src.services.gate import (
                collect_persona_reference_asset_ids,
                format_persona_descriptors,
                format_persona_sheet,
                resolve_content_mode,
            )
            from apps.api.src.db.models import Persona, User as DbUser

            def _resolve_job_persona(sync_db):
                u = sync_db.query(DbUser).filter(DbUser.id == tenant_id).first()
                mode = job.content_mode or resolve_content_mode(u, None, None)
                pq = sync_db.query(Persona).filter(
                    Persona.id == str(effective_persona_id),
                    Persona.is_current.is_(True),
                    Persona.deleted_at.is_(None),
                ).first()
                if not pq or str(pq.user_id) != str(tenant_id):
                    raise HTTPException(status_code=404, detail="Persona not found")
                if getattr(pq, "mature", False) and mode == "sfw":
                    raise HTTPException(status_code=403, detail={"code": "MATURE_PERSONA_BLOCKED_IN_SFW", "message": "Mature persona cannot be used in SFW mode."})
                return (
                    str(pq.id),
                    int(pq.version),
                    bool(getattr(pq, "mature", False)),
                    format_persona_sheet(pq),
                    format_persona_descriptors(pq),
                    collect_persona_reference_asset_ids(pq),
                )

            p_id, p_ver, p_mat, p_sheet, p_desc, p_refs = await db.run_sync(_resolve_job_persona)
            persona_id_resolved = p_id
            persona_version_resolved = p_ver
            persona_sheet = p_sheet
            persona_descriptors = p_desc
            persona_ref_ids = p_refs
            effective_mature = effective_mature or p_mat

    if ref_bytes is None and persona_ref_ids:
        loaded_persona_refs = await load_persona_reference_media(db, tenant_id, persona_ref_ids, media_kind="image")
        if loaded_persona_refs:
            ref_asset, _, _, ref_bytes = loaded_persona_refs[0]
            effective_mature = effective_mature or bool(getattr(ref_asset, "mature", False))

    # KEYSTONE Prompt Authority + Embedded Cognition digest step:
    # Digests raw user prompt + reference count via KEYSTONE & seated Qwen model,
    # producing the finished positive_prompt that the downstream model ingests.
    from packages.prompt_engine import compiler as keystone_prompting
    compiled_prompt_obj = await keystone_prompting.digest_and_compile_prompt(
        user_text=req.prompt,
        reference_count=1 if ref_bytes else 0,
        intent_hint=req.mode or "generate",
        job_id=str(req.job_id),
        persona_sheet=persona_sheet,
    )
    final_positive_prompt = compiled_prompt_obj.positive_prompt
    if persona_descriptors and persona_descriptors not in final_positive_prompt:
        final_positive_prompt = f"{final_positive_prompt}\n\n[Persona: {persona_descriptors}]"

    comfy_mode = req.mode or "text2image"
    if comfy_mode.lower() in ("sfw", "unrestricted"):
        comfy_mode = "img2img" if ref_bytes else "text2image"

    try:
        if is_video_mode:
            result = await run_in_threadpool(
                comfy_client.generate_minimax_h3_video,
                final_positive_prompt,
                ref_image_bytes=ref_bytes,
                duration_seconds=req.duration_seconds or 5,
                resolution=req.resolution or "720p"
            )
        else:
            result = await run_in_threadpool(
                comfy_client.generate_image,
                final_positive_prompt,
                negative_prompt=req.negative_prompt if req.negative_prompt is not None else None,
                width=req.width,
                height=req.height,
                steps=req.steps,
                cfg=req.cfg,
                seed=req.seed,
                checkpoint=req.checkpoint,
                reference_image_bytes=ref_bytes,
                reference_filename=(
                    (getattr(ref_asset, "metadata_", None) or {}).get("filename")
                    or getattr(ref_asset, "filename", None)
                    or ref_asset.storage_key.split("/")[-1]
                ) if ref_asset else None,
                denoise=req.denoise or 0.65,
                mode=comfy_mode,
            )
    except ComfyUINotConfigured as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err))
    except ComfyUIError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))

    payload = result["bytes"]
    mime_type = result["mime_type"]
    extension = {
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "video/mp4": ".mp4"
    }.get(mime_type, ".png")
    is_video = mime_type.startswith("video/") or req.mode == "minimax_h3"
    asset_id = str(uuid.uuid4())
    prefix = "minimax_h3_" if is_video else "keystone_"
    storage_key = generate_storage_key(
        tenant_id, asset_id, f"{prefix}{asset_id[:8]}{extension}"
    )

    storage = AssetStorageService()
    await storage.provider.put_object(storage_key, payload, mime_type)

    relationship = req.relationship_type or "variation"
    metadata: Dict[str, Any] = {
        "kind": "keystone_comfy_render",
        "title": req.title,
        "prompt": req.prompt,
        "compiled_prompt": final_positive_prompt,
        "prompt_hash": compiled_prompt_obj.prompt_hash,
        "cognition_provenance": compiled_prompt_obj.provenance.get("cognition"),
        "seed": result.get("seed"),
        "steps": result.get("steps"),
        "cfg": result.get("cfg"),
        "checkpoint": result.get("checkpoint"),
        "comfy_prompt_id": result.get("prompt_id"),
        "width": result.get("width"),
        "height": result.get("height"),
        "relationship": relationship,
        "parent_asset_id": req.parent_asset_id,
        "job_id": req.job_id,
        "reference_used": bool(ref_asset),
    }
    if req.reference_asset_id:
        metadata["reference_asset_id"] = req.reference_asset_id
        metadata["reference_type"] = req.reference_type or "img2img"
        metadata["denoise"] = req.denoise or 0.65
    if persona_id_resolved:
        metadata["persona_id"] = persona_id_resolved
        metadata["persona_version"] = persona_version_resolved
    if req.metadata:
        metadata.update(req.metadata)

    try:
        asset = await asset_repo.create_asset(
            id=asset_id,
            filename=f"{prefix}{asset_id[:8]}{extension}",
            mime_type=mime_type,
            byte_size=len(payload),
            storage_key=storage_key,
            project_id=req.project_id,
            media_type="video" if is_video else "image",
            storage_provider=storage.provider.__class__.__name__,
            metadata=metadata,
            mature=effective_mature,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    dag = LineageDAG(session=db)
    active_parent = parent_asset or ref_asset
    if active_parent is not None:
        try:
            rel_type = "reference" if (ref_asset and not parent_asset) else relationship
            await dag.persist_relationship(
                parent_id=active_parent.id,
                child_id=asset.id,
                relationship_type=rel_type,
                job_id=req.job_id,
                mature=effective_mature,
            )
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    if persona_id_resolved:
        await dag.persist_depicts_edge(
            child_asset_id=asset.id,
            persona_id=persona_id_resolved,
            persona_version=persona_version_resolved or 1,
            job_id=req.job_id,
            mature=effective_mature,
        )

    job.status = "COMPLETED"
    job.outputs = [asset.id]
    await db.commit()

    return {
        "status": "ok",
        "id": asset.id,
        "owner_id": asset.user_id,
        "project_id": asset.project_id,
        "media_type": asset.asset_type,
        "mime_type": asset.mime_type,
        "storage_provider": getattr(asset, "storage_provider", storage.provider.__class__.__name__),
        "storage_key": asset.storage_key,
        "byte_size": asset.size_bytes,
        "mature": bool(asset.mature),
        "persona_id": persona_id_resolved,
        "persona_version": persona_version_resolved,
        "envelope_id": receipt.envelope.envelope_id if receipt else None,
        "metadata": metadata,
        "download_url": content_url(asset),
        "job_id": req.job_id,
        "comfy_prompt_id": result.get("prompt_id"),
        "seed": result.get("seed"),
        "width": result.get("width"),
        "height": result.get("height"),
        "reference_used": bool(ref_asset),
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


@router.post("/{asset_id}/upscale", summary="Upscale an asset image to 2x or 4x high-resolution")
async def upscale_asset(
    asset_id: str,
    req: UpscaleAssetRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    source_asset = await asset_repo.get_asset_by_id(asset_id)
    if not source_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source asset not found")

    storage = AssetStorageService()
    try:
        source_bytes = await storage.provider.get_object(source_asset.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source asset media bytes not found")

    effective_scale = req.scale or req.scale_factor
    target_persona_id = req.as_persona or req.persona_id
    try:
        receipt = await GateService.authorize_async(
            db,
            user_id=tenant_id,
            intent="upscale",
            prompt_text=req.prompt or "Neural ESRGAN upscale",
            capability_id="upscale.clarity",
            arguments={"scale_factor": effective_scale, "input_asset_id": asset_id},
            project_id=req.project_id or source_asset.project_id,
            session_id=req.session_id,
            persona_id=target_persona_id,
            input_asset_ids=[asset_id],
        )
        upscale_prompt = receipt.compiled_prompt or (req.prompt or "")
        upscale_res = await run_in_threadpool(
            comfy_client.upscale_image,
            source_bytes,
            scale_factor=effective_scale,
            prompt=upscale_prompt,
        )
    except HTTPException:
        raise
    except ComfyUINotConfigured as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err))
    except ComfyUIError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"UPSCALE_FAILED: {err}")

    out_bytes = upscale_res["bytes"]
    out_mime = upscale_res.get("mime_type", "image/png")
    out_asset_id = str(uuid.uuid4())
    out_filename = f"keystone_upscaled_{source_asset.id[:8]}_{effective_scale}x.png"
    out_storage_key = generate_storage_key(tenant_id, out_asset_id, out_filename)

    await storage.provider.put_object(out_storage_key, out_bytes, out_mime)

    effective_mature = bool(receipt.mature or getattr(source_asset, "mature", False))
    upscaled_asset = await asset_repo.create_asset(
        id=out_asset_id,
        filename=out_filename,
        mime_type=out_mime,
        byte_size=len(out_bytes),
        storage_key=out_storage_key,
        project_id=req.project_id or source_asset.project_id,
        media_type="image",
        storage_provider=storage.provider.__class__.__name__,
        mature=effective_mature,
        metadata={
            "kind": "keystone_upscale",
            "source_asset_id": source_asset.id,
            "scale_factor": effective_scale,
            "width": upscale_res.get("width"),
            "height": upscale_res.get("height"),
            "prompt": req.prompt,
            "persona_id": receipt.persona_id,
            "persona_version": receipt.persona_version,
        }
    )

    await ensure_job_for_receipt(
        db,
        receipt=receipt,
        user_id=tenant_id,
        project_id=req.project_id or source_asset.project_id,
        capability_id="upscale.clarity",
        provider_id="comfyui",
        workflow_id="esrgan_upscale",
        output_asset_id=upscaled_asset.id,
        status_value="COMPLETED",
    )

    dag = LineageDAG(session=db)
    try:
        await dag.persist_relationship(
            parent_id=source_asset.id,
            child_id=upscaled_asset.id,
            relationship_type="upscale",
            job_id=receipt.job_id,
            mature=effective_mature,
        )
        if receipt.persona_id:
            await dag.persist_depicts_edge(
                child_asset_id=upscaled_asset.id,
                persona_id=receipt.persona_id,
                persona_version=receipt.persona_version or 1,
                job_id=receipt.job_id,
                mature=effective_mature,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LINEAGE_PERSIST_FAILED: {exc}",
        ) from exc

    await db.commit()
    up_meta = getattr(upscaled_asset, "metadata_", None) or {}
    return {
        "status": "ok",
        "id": upscaled_asset.id,
        "filename": up_meta.get("filename", upscaled_asset.storage_key.split("/")[-1]),
        "media_type": upscaled_asset.asset_type,
        "mime_type": upscaled_asset.mime_type,
        "byte_size": upscaled_asset.size_bytes,
        "scale_factor": effective_scale,
        "width": upscale_res.get("width"),
        "height": upscale_res.get("height"),
        "source_asset_id": source_asset.id,
        "mature": bool(upscaled_asset.mature),
        "persona_id": receipt.persona_id,
        "persona_version": receipt.persona_version,
        "envelope_id": receipt.envelope.envelope_id,
        "download_url": content_url(upscaled_asset),
        "metadata": up_meta,
        "created_at": upscaled_asset.created_at.isoformat() if upscaled_asset.created_at else None
    }


@router.post("/upload", summary="Prepare asset upload and generate signed upload URL")
async def prepare_upload(
    req: UploadAssetRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    storage_key = generate_storage_key(tenant_id, asset_id, req.filename)

    try:
        asset = await asset_repo.create_asset(
            id=asset_id,
            filename=req.filename,
            mime_type=req.mime_type,
            byte_size=req.byte_size,
            storage_key=storage_key,
            project_id=req.project_id,
            media_type=req.media_type or "image",
            storage_provider="local"
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    signed_url = generate_signed_url(storage_key, expiry_seconds=900)
    return {
        "status": "ok",
        "asset_id": asset.id,
        "storage_key": storage_key,
        "upload_url": signed_url,
        "download_url": signed_url
    }


@router.get("", summary="List assets for current tenant")
async def list_assets(
    project_id: Optional[str] = None,
    content_mode: Optional[str] = Query(None, description="Resolved content mode: sfw or unrestricted"),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    from apps.api.src.db.models import Project as _DbProject, User as _DbUser
    user_res = await db.execute(select(_DbUser).where(_DbUser.id == tenant_id))
    user_obj = user_res.scalar_one_or_none()
    project_obj = None
    if project_id:
        proj_res = await db.execute(
            select(_DbProject).where(_DbProject.id == project_id, _DbProject.user_id == tenant_id, _DbProject.deleted_at.is_(None))
        )
        project_obj = proj_res.scalar_one_or_none()

    resolved_mode = (
        content_mode
        if content_mode in ("sfw", "unrestricted")
        else resolve_content_mode(user_obj, project_obj, None)
    )
    allow_mature = (
        resolved_mode == "unrestricted"
        and user_obj is not None
        and bool(getattr(user_obj, "age_verified", False))
    )
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    assets = await asset_repo.get_assets(project_id=project_id)
    if not allow_mature:
        assets = [a for a in assets if not getattr(a, "mature", False)]
    return {
        "assets": [
            {
                "id": a.id,
                "owner_id": a.user_id,
                "project_id": a.project_id,
                "media_type": a.asset_type,
                "mime_type": a.mime_type,
                "storage_key": a.storage_key,
                "byte_size": a.size_bytes,
                "mature": bool(getattr(a, "mature", False)),
                "metadata": getattr(a, "metadata_", None) or {},
                "download_url": content_url(a),
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in assets
        ]
    }


@router.get("/{asset_id}", summary="Get asset by ID with freshly signed URL")
async def get_asset(
    asset_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset = await asset_repo.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found or forbidden"
        )

    return {
        "id": asset.id,
        "owner_id": asset.user_id,
        "project_id": asset.project_id,
        "media_type": asset.asset_type,
        "mime_type": asset.mime_type,
        "storage_key": asset.storage_key,
        "byte_size": asset.size_bytes,
        "mature": bool(getattr(asset, "mature", False)),
        "metadata": getattr(asset, "metadata_", None) or {},
        "download_url": content_url(asset),
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


@router.get("/{asset_id}/credentials", summary="Get C2PA Content Credentials for Asset (Bible v2 §25)")
async def get_asset_credentials(
    asset_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset = await asset_repo.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found or forbidden"
        )

    from apps.api.src.services.c2pa_credentials import sign_c2pa_manifest
    manifest = sign_c2pa_manifest(
        asset_id=asset.id,
        job_id=asset.job_id or asset.id,
        user_id=asset.user_id,
        title=f"Keystone Asset {asset.id}",
    )
    return manifest



def _parse_byte_range(range_header: str, total_size: int) -> Optional[Tuple[int, int]]:
    """
    Parse an HTTP Range header (`bytes=start-end`, `bytes=start-`, `bytes=-suffix`)
    per RFC 9110 §14.1.2. Returns None for non-bytes units and raises ValueError
    when a `bytes=` range is malformed or unsatisfiable.
    """
    raw = (range_header or "").strip()
    if not raw or "=" not in raw:
        raise ValueError("RANGE_NOT_SATISFIABLE")
    unit, _, spec_str = raw.partition("=")
    if unit.strip().lower() != "bytes":
        return None
    spec = spec_str.strip()
    if not spec or "," in spec or "-" not in spec:
        raise ValueError("RANGE_NOT_SATISFIABLE")
    if total_size <= 0:
        raise ValueError("RANGE_NOT_SATISFIABLE")

    start_s, end_s = spec.split("-", 1)
    start_s = start_s.strip()
    end_s = end_s.strip()

    if not start_s and not end_s:
        raise ValueError("RANGE_NOT_SATISFIABLE")

    try:
        if not start_s:
            suffix_len = int(end_s)
            if suffix_len <= 0:
                raise ValueError("RANGE_NOT_SATISFIABLE")
            start = max(0, total_size - suffix_len)
            end = total_size - 1
        elif not end_s:
            start = int(start_s)
            if start < 0 or start >= total_size:
                raise ValueError("RANGE_NOT_SATISFIABLE")
            end = total_size - 1
        else:
            start = int(start_s)
            end = int(end_s)
            if start < 0 or start >= total_size or end < start:
                raise ValueError("RANGE_NOT_SATISFIABLE")
            end = min(end, total_size - 1)
    except ValueError as exc:
        raise ValueError("RANGE_NOT_SATISFIABLE") from exc

    return start, end


@router.get("/{asset_id}/content", summary="Serve asset bytes for a signed URL")
async def get_asset_content(
    asset_id: str,
    expires: int = Query(..., description="Signed URL expiry (unix seconds)"),
    signature: str = Query(..., description="HMAC-SHA256 signature"),
    range_header: Optional[str] = Header(None, alias="Range"),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Streams the stored bytes with HTTP Range support (206 Partial Content).
    Authorised by the HMAC signature rather than a bearer token, so <img src>
    and <video src> timeline seeking work without exposing credentials."""
    result = await db.execute(select(Asset).where(Asset.id == str(asset_id)))
    asset = result.scalar_one_or_none()
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    signed_url = f"{STORAGE_BASE_URL}/{asset.storage_key}?expires={expires}&signature={signature}"
    try:
        validate_signed_url(signed_url)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))

    storage = AssetStorageService()
    try:
        payload = await storage.provider.get_object(asset.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ASSET_BYTES_UNAVAILABLE: this asset has no stored file",
        )

    total_size = len(payload)
    media_type = asset.mime_type or "application/octet-stream"
    mime_clean = media_type.split(";")[0].strip().lower()
    disposition = "inline" if mime_clean in ALLOWED_UPLOAD_MIMES else "attachment"
    base_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'{disposition}; filename="{asset_id}"',
    }

    if range_header is not None:
        try:
            byte_range = _parse_byte_range(range_header, total_size)
        except ValueError:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes */{total_size}",
                },
            )
        if byte_range is not None:
            start, end = byte_range
            chunk = payload[start : end + 1]
            return Response(
                content=chunk,
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=media_type,
                headers={
                    **base_headers,
                    "Content-Range": f"bytes {start}-{end}/{total_size}",
                    "Content-Length": str(len(chunk)),
                },
            )

    return Response(
        content=payload,
        status_code=status.HTTP_200_OK,
        media_type=media_type,
        headers={
            **base_headers,
            "Content-Length": str(total_size),
        },
    )


@router.delete("/{asset_id}", summary="Soft-delete asset")
async def delete_asset(
    asset_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    deleted = await asset_repo.soft_delete_asset(asset_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found or already deleted"
        )
    return {"status": "ok", "message": "Asset soft-deleted successfully"}


# ----------------------------------------------------------------------------
# Lineage DAG Endpoints
# ----------------------------------------------------------------------------

@router.post("/{asset_id}/relationships", summary="Add relationship edge to Lineage DAG")
async def add_lineage_relationship(
    asset_id: str,
    req: CreateRelationshipRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    # Verify parent asset belongs to tenant
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    parent_asset = await asset_repo.get_asset_by_id(asset_id)
    if not parent_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent asset not found")

    # Verify child asset belongs to caller tenant
    child_asset = await asset_repo.get_asset_by_id(req.child_asset_id)
    if not child_asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Child asset not found or access denied")

    dag = LineageDAG(session=db)
    try:
        edge = await dag.persist_relationship(
            parent_id=asset_id,
            child_id=req.child_asset_id,
            relationship_type=req.relationship_type,
            job_id=req.job_id
        )
        return {
            "status": "ok",
            "relationship": {
                "id": str(edge.id),
                "parent_asset_id": str(edge.parent_asset_id),
                "child_asset_id": str(edge.child_asset_id),
                "relationship_type": edge.relationship_type,
                "job_id": str(edge.job_id) if edge.job_id else None
            }
        }
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/{asset_id}/lineage", summary="Get ancestor and descendant lineage for asset")
async def get_lineage(
    asset_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset = await asset_repo.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    dag = LineageDAG(session=db)
    await dag.load_from_db()
    ancestors = dag.get_ancestors(asset_id)
    descendants = dag.get_descendants(asset_id)
    depicts = dag.get_depicts(asset_id)
    related_nodes = {str(asset_id), *ancestors, *descendants}
    edges = [
        {
            "id": e.get("id"),
            "parent_asset_id": e.get("parent_id"),
            "child_asset_id": e.get("child_id"),
            "relationship_type": e.get("relationship_type"),
            "persona_id": e.get("persona_id"),
            "persona_version": e.get("persona_version"),
            "mature": bool(e.get("mature", False)),
            "job_id": e.get("job_id"),
        }
        for e in dag.edges
        if e.get("child_id") in related_nodes or e.get("parent_id") in related_nodes
    ]

    return {
        "asset_id": asset_id,
        "ancestors": ancestors,
        "descendants": descendants,
        "depicts": depicts,
        "edges": edges,
    }
