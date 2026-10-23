"""
KEYSTONE Project Repository (Tenant Scoped with Soft-Deletion)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import Project, User
from apps.api.src.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    async def create_project(
        self,
        id: str | uuid.UUID,
        name: str,
        description: Optional[str] = None
    ) -> Project:
        # Check if user exists
        stmt_user = select(User).where(User.id == self.tenant_id)
        res_user = await self.session.execute(stmt_user)
        if not res_user.scalar_one_or_none():
            raise ValueError("USER_NOT_FOUND")

        project = Project(
            id=str(id),
            user_id=self.tenant_id,
            name=name,
            description=description,
            status="active",
            deleted_at=None
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def get_projects(self) -> List[Project]:
        """Returns all non-deleted projects for the current tenant."""
        stmt = (
            select(Project)
            .where(Project.user_id == self.tenant_id)
            .where(Project.deleted_at.is_(None))
            .order_by(Project.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_projects_for_user(self, user_id: str | uuid.UUID) -> List[Project]:
        """Scoped query for user projects, honoring soft deletion."""
        stmt = (
            select(Project)
            .where(Project.user_id == str(user_id))
            .where(Project.deleted_at.is_(None))
            .order_by(Project.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_project_by_id(self, project_id: str | uuid.UUID) -> Optional[Project]:
        stmt = (
            select(Project)
            .where(Project.id == str(project_id))
            .where(Project.user_id == self.tenant_id)
            .where(Project.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete_project(self, project_id: str | uuid.UUID) -> bool:
        stmt = (
            update(Project)
            .where(Project.id == str(project_id))
            .where(Project.user_id == self.tenant_id)
            .where(Project.deleted_at.is_(None))
            .values(deleted_at=datetime.now(timezone.utc), status="deleted")
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0
