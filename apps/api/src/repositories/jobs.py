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
from apps.api.src.jobs.state_machine import TERMINAL_STATES
from apps.api.src.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    async def create_job(
        self,
        id: str | uuid.UUID,
        request_id: Optional[str | uuid.UUID] = None,
        authority_decision_id: Optional[str | uuid.UUID] = None,
        capability_id: str = "image_gen",
        provider_id: str = "kaggle_comfyui",
        workflow_id: str = "wf_default",
        workflow_version: str = "1.0.0",
        state: str = "CREATED",
        priority: int = 100,
        project_id: Optional[str | uuid.UUID] = None,
        content_mode: Optional[str] = None,
        envelope_id: Optional[str | uuid.UUID] = None,
        envelope: Optional[Dict[str, Any]] = None,
        persona_id: Optional[str | uuid.UUID] = None,
    ) -> Job:
        now = datetime.now(timezone.utc)
        job = Job(
            id=str(id),
            request_id=str(request_id) if request_id else None,
            user_id=self.tenant_id,
            project_id=str(project_id) if project_id else None,
            capability_id=capability_id,
            provider_id=provider_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            status=state,
            priority=priority,
            content_mode=content_mode,
            envelope_id=str(envelope_id) if envelope_id else None,
            envelope=envelope,
            persona_id=str(persona_id) if persona_id else None,
            queued_at=now if state == "QUEUED" else None,
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
        now = datetime.now(timezone.utc)
        values: Dict[str, Any] = {
            "status": next_state,
            "updated_at": now,
        }
        if next_state == "QUEUED":
            values["queued_at"] = now
        elif next_state == "RUNNING":
            values["started_at"] = now
        elif next_state in TERMINAL_STATES:
            values["completed_at"] = now

        if error_code is not None:
            values["failure_code"] = error_code

        stmt = (
            update(Job)
            .where(Job.id == str(job_id))
            .where(Job.user_id == self.tenant_id)
            .values(**values)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0
