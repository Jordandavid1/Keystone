"""
KEYSTONE Base Repository
Provides tenant-isolated repository operations.
"""

from __future__ import annotations

import uuid
from typing import Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base class enforcing tenant-level isolation on all queries and mutations."""

    def __init__(self, session: AsyncSession, tenant_id: str | uuid.UUID) -> None:
        self.session = session
        self.tenant_id = str(tenant_id)
