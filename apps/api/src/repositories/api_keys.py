"""
KEYSTONE API Key Repository
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import ApiKey
from apps.api.src.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    async def create_api_key(
        self,
        id: str | uuid.UUID,
        name: str,
        key_hash: str,
        key_prefix: str,
        scopes: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None
    ) -> ApiKey:
        api_key = ApiKey(
            id=str(id),
            user_id=self.tenant_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=scopes or ["*"],
            status="active",
            expires_at=expires_at
        )
        self.session.add(api_key)
        await self.session.flush()
        return api_key

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.key_hash == key_hash)
            .where(ApiKey.status == "active")
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_api_keys(self) -> List[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == self.tenant_id)
            .order_by(ApiKey.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
