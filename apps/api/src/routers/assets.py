"""
KEYSTONE Asset Router (/v1/assets)
Asset registration, storage keys, short-expiry signed URLs, and Lineage DAG tracking.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.storage.service import (
    generate_signed_url,
    generate_storage_key,
)

STORAGE_KEY_PATTERN = re.compile(r"^tenants/([a-zA-Z0-9_-]+)/assets/([a-zA-Z0-9_-]+)/([a-zA-Z0-9._-]+)$")

router = APIRouter(prefix="/v1/assets", tags=["Assets"])


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

    download_url = generate_signed_url(asset.storage_key, expiry_seconds=900)
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
        "download_url": download_url,
        "created_at": asset.created_at.isoformat() if asset.created_at else None
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
                "download_url": generate_signed_url(a.storage_key, expiry_seconds=900),
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

    download_url = generate_signed_url(asset.storage_key, expiry_seconds=900)
    return {
        "id": asset.id,
        "owner_id": asset.owner_id,
        "project_id": asset.project_id,
        "media_type": asset.media_type,
        "mime_type": asset.mime_type,
        "storage_key": asset.storage_key,
        "byte_size": asset.byte_size,
        "download_url": download_url,
        "created_at": asset.created_at.isoformat() if asset.created_at else None
    }


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
