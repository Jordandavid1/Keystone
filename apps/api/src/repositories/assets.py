"""
KEYSTONE Asset Repository (Tenant Scoped with Soft-Deletion)
"""

from __future__ import annotations

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
        metadata: Optional[Dict[str, Any]] = None
    ) -> Asset:
        if not mime_type or byte_size <= 0 or not storage_key:
            raise ValueError("INVALID_ASSET_PARAMS")
        if ".." in storage_key or "\\" in storage_key:
            raise ValueError(f"ILLEGAL_STORAGE_KEY: Key traversal attempted: {storage_key}")

        asset = Asset(
            id=str(id),
            owner_id=self.tenant_id,
            project_id=str(project_id) if project_id else None,
            media_type=media_type,
            mime_type=mime_type,
            storage_provider=storage_provider,
            storage_key=storage_key,
            byte_size=byte_size,
            status="available",
            metadata_=metadata or {},
            deleted_at=None
        )
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def get_assets(self, project_id: Optional[str | uuid.UUID] = None) -> List[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.owner_id == self.tenant_id)
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
            .where(Asset.owner_id == self.tenant_id)
            .where(Asset.deleted_at.is_(None))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def soft_delete_asset(self, asset_id: str | uuid.UUID) -> bool:
        stmt = (
            update(Asset)
            .where(Asset.id == str(asset_id))
            .where(Asset.owner_id == self.tenant_id)
            .where(Asset.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc), status="deleted")
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0
