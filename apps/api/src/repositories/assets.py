"""
KEYSTONE Asset Repository (Tenant Scoped with Soft-Deletion)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import Asset
from apps.api.src.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    async def create_asset(
        self,
        id: str | uuid.UUID,
        filename: str,
        mime_type: str,
        byte_size: int,
        storage_key: str,
        project_id: Optional[str | uuid.UUID] = None,
        media_type: str = "image",
        storage_provider: str = "local",
        metadata: Optional[Dict[str, Any]] = None,
        mature: bool = False,
        c2pa_manifest: Optional[Dict[str, Any]] = None,
        asset_bytes: Optional[bytes] = None,
        content_mode: Optional[str] = None,
        fabric: str = "comfyui",
        recipe_id: Optional[str] = None,
        job_id: Optional[str] = None,
        stamp_c2pa: bool = False,
    ) -> Asset:
        if not mime_type or byte_size <= 0 or not storage_key:
            raise ValueError("INVALID_ASSET_PARAMS")
        if ".." in storage_key or "\\" in storage_key:
            raise ValueError(f"ILLEGAL_STORAGE_KEY: Key traversal attempted: {storage_key}")

        checksum_val = hashlib.sha256(asset_bytes).hexdigest() if asset_bytes is not None else None
        resolved_c2pa = c2pa_manifest
        if resolved_c2pa is None and (asset_bytes is not None or stamp_c2pa):
            from apps.api.src.services.c2pa_credentials import sign_c2pa_manifest

            eff_meta = dict(metadata) if metadata else {}
            eff_job_id = str(job_id or eff_meta.get("job_id") or id)
            eff_mode = content_mode or ("unrestricted" if mature else "sfw")
            resolved_c2pa = sign_c2pa_manifest(
                asset_id=str(id),
                job_id=eff_job_id,
                user_id=str(self.tenant_id),
                asset_bytes=asset_bytes,
                asset_sha256=checksum_val,
                fabric=fabric,
                recipe_id=recipe_id or eff_meta.get("recipe_id"),
                content_mode=eff_mode,
                title=filename or f"Keystone Asset {id}",
            )

        asset = Asset(
            id=str(id),
            user_id=self.tenant_id,
            project_id=str(project_id) if project_id else None,
            asset_type=media_type,
            filename=filename,
            mime_type=mime_type,
            storage_key=storage_key,
            size_bytes=byte_size,
            checksum=checksum_val,
            metadata_=dict(metadata) if metadata else {},
            mature=bool(mature),
            c2pa_manifest=resolved_c2pa,
            deleted_at=None,
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def get_assets(self, project_id: Optional[str | uuid.UUID] = None) -> List[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.user_id == self.tenant_id)
            .where(Asset.deleted_at.is_(None))
        )
        if project_id:
            stmt = stmt.where(Asset.project_id == str(project_id))
        stmt = stmt.order_by(Asset.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_asset_by_id(self, asset_id: str | uuid.UUID) -> Optional[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.id == str(asset_id))
            .where(Asset.user_id == self.tenant_id)
            .where(Asset.deleted_at.is_(None))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def soft_delete_asset(self, asset_id: str | uuid.UUID) -> bool:
        stmt = (
            update(Asset)
            .where(Asset.id == str(asset_id))
            .where(Asset.user_id == self.tenant_id)
            .where(Asset.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc), status="deleted")
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0
