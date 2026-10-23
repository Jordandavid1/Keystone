"""
KEYSTONE Job Repository (Tenant Scoped)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import Job
from apps.api.src.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    async def create_job(
        self,
        id: str | uuid.UUID,
        request_id: str | uuid.UUID,
        authority_decision_id: str | uuid.UUID,
        capability_id: str,
        provider_id: str,
        workflow_id: str,
        workflow_version: str,
        state: str = "CREATED",
        priority: int = 100
    ) -> Job:
        job = Job(
            id=str(id),
            request_id=str(request_id),
            authority_decision_id=str(authority_decision_id),
            user_id=self.tenant_id,
            capability_id=capability_id,
            provider_id=provider_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            state=state,
            priority=priority
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job_by_id(self, job_id: str | uuid.UUID) -> Optional[Job]:
        stmt = (
            select(Job)
            .where(Job.id == str(job_id))
            .where(Job.user_id == self.tenant_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_jobs(self) -> List[Job]:
        stmt = (
            select(Job)
            .where(Job.user_id == self.tenant_id)
            .order_by(Job.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_job_state(
        self,
        job_id: str | uuid.UUID,
        next_state: str,
        error_code: Optional[str] = None,
        error_detail: Optional[Dict[str, Any]] = None
    ) -> bool:
        values: Dict[str, Any] = {
            "state": next_state,
            "updated_at": datetime.now(timezone.utc)
        }
        if error_code is not None:
            values["error_code"] = error_code
        if error_detail is not None:
            values["error_detail"] = error_detail

        stmt = (
            update(Job)
            .where(Job.id == str(job_id))
            .where(Job.user_id == self.tenant_id)
            .values(**values)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0
