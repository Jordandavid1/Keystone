"""
KEYSTONE Asset Router (/v1/assets)
Asset registration, storage keys, short-expiry signed URLs, and Lineage DAG tracking.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, File, UploadFile, Form
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.models import Asset, AuthorityDecision, Job
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.repositories.assets import AssetRepository
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
    prompt: str = Field(..., min_length=1, description="Compiled generation prompt")
    negative_prompt: Optional[str] = None
    title: Optional[str] = None
    width: int = Field(1024, ge=256, le=2048)
    height: int = Field(1024, ge=256, le=2048)
    steps: int = Field(25, ge=1, le=60)
    cfg: float = Field(6.0, ge=1.0, le=20.0)
    seed: Optional[int] = Field(None, ge=0)
    checkpoint: Optional[str] = None
    project_id: Optional[str] = None
    parent_asset_id: Optional[str] = None
    reference_asset_id: Optional[str] = Field(None, description="Anchor asset used as visual or motion reference")
    reference_type: Optional[str] = Field("img2img", description="Reference role: img2img, style, composition, video_anchor")
    denoise: Optional[float] = Field(0.65, ge=0.05, le=1.0, description="Denoising strength for reference conditioning")
    mode: Optional[str] = Field("text2image", description="text2image, img2img, upscale, i2v")
    scale_factor: Optional[int] = Field(2, ge=2, le=4)
    relationship_type: Optional[str] = None
    job_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpscaleAssetRequest(BaseModel):
    scale_factor: int = Field(2, ge=2, le=4, description="Resolution scale multiplier (2 for 2x, 4 for 4x)")
    prompt: Optional[str] = Field(None, description="Optional guidance prompt for detail synthesis")
    project_id: Optional[str] = None


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
        "owner_id": asset.owner_id,
        "project_id": asset.project_id,
        "media_type": asset.media_type,
        "mime_type": asset.mime_type,
        "storage_provider": asset.storage_provider,
        "storage_key": asset.storage_key,
        "byte_size": asset.byte_size,
        "metadata": asset.metadata_ or {},
        "download_url": download_url,
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


@router.post("/upload-file", summary="Upload photo or video file directly via multipart/form-data")
async def upload_asset_file(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    media_type: Optional[str] = Form(None),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    asset_id = str(uuid.uuid4())
    content = await file.read()
    raw_filename = file.filename or "upload.bin"
    mime_type = file.content_type or "application/octet-stream"

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
    asset_meta = asset.metadata_ or {}
    return {
        "status": "ok",
        "id": asset.id,
        "filename": asset_meta.get("filename", asset.storage_key.split("/")[-1]),
        "media_type": asset.media_type,
        "mime_type": asset.mime_type,
        "byte_size": asset.byte_size,
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
        except Exception:
            ref_bytes = None

    if not req.job_id:
        # Auto-provision request, authority decision, and RUNNING job for seamless caller UX
        from apps.api.src.db.models import Request as DBRequest
        req_id = str(uuid.uuid4())
        dec_id = str(uuid.uuid4())
        auto_job_id = str(uuid.uuid4())

        persisted_req = DBRequest(
            id=req_id,
            user_id=tenant_id,
            request_text=req.prompt,
            preferences={
                "action_type": "generate",
                "capability_id": "image.generation",
            },
            state="created",
        )
        persisted_dec = AuthorityDecision(
            id=dec_id,
            request_id=req_id,
            decision="approve",
            capability_id="image.generation",
            provider_id="comfyui",
            sanitized_arguments={
                "prompt": req.prompt,
                "negative_prompt": req.negative_prompt,
                "width": req.width,
                "height": req.height,
                "steps": req.steps,
                "guidance": req.cfg,
            },
            reason_codes=["AUTO_AUTHORIZED"],
            policy_bundle_version="1.0.0",
            capability_registry_version="1.0.0",
            harness_bundle_version="1.0.0",
        )
        persisted_job = Job(
            id=auto_job_id,
            user_id=tenant_id,
            request_id=req_id,
            authority_decision_id=dec_id,
            capability_id="image.generation",
            provider_id="comfyui",
            workflow_id="wf_default",
            workflow_version="1.0.0",
            state="RUNNING",
            priority=100,
        )
        db.add(persisted_req)
        db.add(persisted_dec)
        db.add(persisted_job)
        await db.commit()
        await db.refresh(persisted_job)
        job = persisted_job
        req.job_id = auto_job_id
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
        if job.state != "RUNNING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Generation can only execute for a job in RUNNING state.",
            )

        decision_result = await db.execute(
            select(AuthorityDecision)
            .where(AuthorityDecision.id == job.authority_decision_id)
            .where(AuthorityDecision.request_id == job.request_id)
        )
        decision = decision_result.scalar_one_or_none()
        if (
            decision is None
            or decision.decision != "approve"
            or decision.capability_id != "image.generation"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The job has no persisted approval for image.generation.",
            )

        authorized = decision.sanitized_arguments or {}
        requested = {
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt,
            "width": req.width,
            "height": req.height,
            "steps": req.steps,
            "guidance": req.cfg,
        }
        for key in ("seed", "checkpoint"):
            value = getattr(req, key)
            if value is not None:
                requested[key] = value
        if any(authorized.get(key) != value for key, value in requested.items()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Generation parameters do not match the persisted authority approval.",
            )

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

    # KEYSTONE Prompt Authority + Embedded Cognition digest step:
    # Digests raw user prompt + reference count via KEYSTONE & seated Qwen model,
    # producing the finished positive_prompt that the downstream model ingests.
    from apps.api.src.keystone import prompting as keystone_prompting
    compiled_prompt_obj = await keystone_prompting.digest_and_compile_prompt(
        user_text=req.prompt,
        reference_count=1 if ref_bytes else 0,
        intent_hint=req.mode or "generate",
        job_id=str(req.job_id),
    )
    final_positive_prompt = compiled_prompt_obj.positive_prompt

    try:
        if req.mode == "minimax_h3" or "minimax" in (req.mode or "").lower():
            result = await run_in_threadpool(
                comfy_client.generate_minimax_h3_video,
                final_positive_prompt,
                ref_image_bytes=ref_bytes,
                duration_seconds=5,
                resolution="720p"
            )
        else:
            result = await run_in_threadpool(
                comfy_client.generate_image,
                final_positive_prompt,
                negative_prompt=req.negative_prompt or compiled_prompt_obj.negative_prompt or None,
                width=req.width,
                height=req.height,
                steps=req.steps,
                cfg=req.cfg,
                seed=req.seed,
                checkpoint=req.checkpoint,
                reference_image_bytes=ref_bytes,
                reference_filename=(ref_asset.metadata_ or {}).get("filename", ref_asset.storage_key.split("/")[-1]) if ref_asset else None,
                denoise=req.denoise or 0.65,
                mode=req.mode or "text2image",
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
            media_type="video" if is_video else (req.media_type or "image"),
            storage_provider=storage.provider.__class__.__name__,
            metadata=metadata,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    active_parent = parent_asset or ref_asset
    if active_parent is not None:
        dag = LineageDAG(session=db)
        try:
            rel_type = "reference" if (ref_asset and not parent_asset) else relationship
            await dag.persist_relationship(
                parent_id=active_parent.id,
                child_id=asset.id,
                relationship_type=rel_type,
                job_id=req.job_id,
            )
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    return {
        "status": "ok",
        "id": asset.id,
        "owner_id": asset.owner_id,
        "project_id": asset.project_id,
        "media_type": asset.media_type,
        "mime_type": asset.mime_type,
        "storage_provider": asset.storage_provider,
        "storage_key": asset.storage_key,
        "byte_size": asset.byte_size,
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

    try:
        upscale_res = await run_in_threadpool(
            comfy_client.upscale_image,
            source_bytes,
            scale_factor=req.scale_factor,
            prompt=req.prompt or ""
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"UPSCALE_FAILED: {err}")

    out_bytes = upscale_res["bytes"]
    out_mime = upscale_res.get("mime_type", "image/png")
    out_asset_id = str(uuid.uuid4())
    out_filename = f"keystone_upscaled_{source_asset.id[:8]}_{req.scale_factor}x.png"
    out_storage_key = generate_storage_key(tenant_id, out_asset_id, out_filename)

    await storage.provider.put_object(out_storage_key, out_bytes, out_mime)

    upscaled_asset = await asset_repo.create_asset(
        id=out_asset_id,
        filename=out_filename,
        mime_type=out_mime,
        byte_size=len(out_bytes),
        storage_key=out_storage_key,
        project_id=req.project_id or source_asset.project_id,
        media_type="image",
        storage_provider=storage.provider.__class__.__name__,
        metadata={
            "kind": "keystone_upscale",
            "source_asset_id": source_asset.id,
            "scale_factor": req.scale_factor,
            "width": upscale_res.get("width"),
            "height": upscale_res.get("height"),
            "prompt": req.prompt,
        }
    )

    dag = LineageDAG(session=db)
    try:
        await dag.persist_relationship(
            parent_id=source_asset.id,
            child_id=upscaled_asset.id,
            relationship_type="upscale",
            job_id=None
        )
    except Exception:
        pass

    up_meta = upscaled_asset.metadata_ or {}
    return {
        "status": "ok",
        "id": upscaled_asset.id,
        "filename": up_meta.get("filename", upscaled_asset.storage_key.split("/")[-1]),
        "media_type": upscaled_asset.media_type,
        "mime_type": upscaled_asset.mime_type,
        "byte_size": upscaled_asset.byte_size,
        "scale_factor": req.scale_factor,
        "width": upscale_res.get("width"),
        "height": upscale_res.get("height"),
        "source_asset_id": source_asset.id,
        "download_url": content_url(upscaled_asset),
        "metadata": upscaled_asset.metadata_ or {},
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
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    asset_repo = AssetRepository(db, tenant_id=tenant_id)
    assets = await asset_repo.get_assets(project_id=project_id)
    return {
        "assets": [
            {
                "id": a.id,
                "owner_id": a.owner_id,
                "project_id": a.project_id,
                "media_type": a.media_type,
                "mime_type": a.mime_type,
                "storage_key": a.storage_key,
                "byte_size": a.byte_size,
                "metadata": a.metadata_ or {},
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
        "owner_id": asset.owner_id,
        "project_id": asset.project_id,
        "media_type": asset.media_type,
        "mime_type": asset.mime_type,
        "storage_key": asset.storage_key,
        "byte_size": asset.byte_size,
        "metadata": asset.metadata_ or {},
        "download_url": content_url(asset),
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


@router.get("/{asset_id}/content", summary="Serve asset bytes for a signed URL")
async def get_asset_content(
    asset_id: str,
    expires: int = Query(..., description="Signed URL expiry (unix seconds)"),
    signature: str = Query(..., description="HMAC-SHA256 signature"),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Streams the stored bytes. Authorised by the HMAC signature rather than a
    bearer token, so <img src> works without exposing credentials to markup."""
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

    return Response(
        content=payload,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{asset_id}"',
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

    return {
        "asset_id": asset_id,
        "ancestors": ancestors,
        "descendants": descendants
    }
