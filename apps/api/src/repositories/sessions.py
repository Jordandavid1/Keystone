"""
KEYSTONE Session & Message Repository (Tenant Scoped)
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import Session, Message, Project
from apps.api.src.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    async def create_session(
        self,
        id: str | uuid.UUID,
        project_id: Optional[str | uuid.UUID] = None,
        title: Optional[str] = "Creative Session"
    ) -> Session:
        # If project_id is provided, verify it belongs to this tenant and is not soft-deleted
        if project_id is not None:
            stmt_proj = (
                select(Project)
                .where(Project.id == str(project_id))
                .where(Project.user_id == self.tenant_id)
                .where(Project.deleted_at.is_(None))
            )
            res_proj = await self.session.execute(stmt_proj)
            project = res_proj.scalar_one_or_none()
            if not project:
                raise ValueError("PROJECT_NOT_FOUND_OR_FORBIDDEN")
            pid_str = str(project_id)
        else:
            pid_str = None

        session = Session(
            id=str(id),
            user_id=self.tenant_id,
            project_id=pid_str,
            title=title,
            status="active"
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_sessions(self, project_id: Optional[str | uuid.UUID] = None) -> List[Session]:
        stmt = select(Session).where(Session.user_id == self.tenant_id)
        if project_id:
            stmt = stmt.where(Session.project_id == str(project_id))
        stmt = stmt.order_by(Session.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_session_by_id(self, session_id: str | uuid.UUID) -> Optional[Session]:
        stmt = (
            select(Session)
            .where(Session.id == str(session_id))
            .where(Session.user_id == self.tenant_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_message(
        self,
        id: str | uuid.UUID,
        session_id: str | uuid.UUID,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        if role not in ("user", "keystone"):
            raise ValueError(f"INVALID_MESSAGE_ROLE: {role}")

        msg = Message(
            id=str(id),
            session_id=str(session_id),
            role=role,
            content=content,
            metadata_=metadata or {}
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_messages(self, session_id: str | uuid.UUID) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.session_id == str(session_id))
            .order_by(Message.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
