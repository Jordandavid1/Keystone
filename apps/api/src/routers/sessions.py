"""
KEYSTONE Session & Message Router (/v1/sessions)
Tenant-isolated chat/collaboration sessions and messages.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_tenant_id
from apps.api.src.db.session import get_db
from apps.api.src.repositories.sessions import MessageRepository, SessionRepository

router = APIRouter(prefix="/v1/sessions", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    project_id: Optional[str] = None
    title: Optional[str] = "Creative Session"


class CreateMessageRequest(BaseModel):
    role: str  # 'user' or 'keystone'
    content: str
    metadata: Optional[Dict[str, Any]] = None


@router.post("", summary="Create a new creative session")
async def create_session(
    req: CreateSessionRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    session_repo = SessionRepository(db, tenant_id=tenant_id)
    session_id = str(uuid.uuid4())
    try:
        session = await session_repo.create_session(
            id=session_id,
            project_id=req.project_id,
            title=req.title
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err)
        )
    return {
        "status": "ok",
        "id": session.id,
        "user_id": session.user_id,
        "project_id": session.project_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None
    }


@router.get("", summary="List sessions for tenant")
async def list_sessions(
    project_id: Optional[str] = None,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    session_repo = SessionRepository(db, tenant_id=tenant_id)
    sessions = await session_repo.get_sessions(project_id=project_id)
    return {
        "sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "project_id": s.project_id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in sessions
        ]
    }


@router.get("/{session_id}", summary="Get session by ID")
async def get_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    session_repo = SessionRepository(db, tenant_id=tenant_id)
    session = await session_repo.get_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or forbidden"
        )
    return {
        "id": session.id,
        "user_id": session.user_id,
        "project_id": session.project_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None
    }


@router.post("/{session_id}/messages", summary="Send message in session")
async def send_message(
    session_id: str,
    req: CreateMessageRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    session_repo = SessionRepository(db, tenant_id=tenant_id)
    session = await session_repo.get_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or forbidden"
        )

    msg_repo = MessageRepository(db)
    msg_id = str(uuid.uuid4())
    try:
        msg = await msg_repo.create_message(
            id=msg_id,
            session_id=session.id,
            role=req.role,
            content=req.content,
            metadata=req.metadata
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err)
        )

    return {
        "status": "ok",
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None
    }


@router.get("/{session_id}/messages", summary="List messages for session")
async def list_messages(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    session_repo = SessionRepository(db, tenant_id=tenant_id)
    session = await session_repo.get_session_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or forbidden"
        )

    msg_repo = MessageRepository(db)
    messages = await msg_repo.get_messages(session.id)
    return {
        "messages": [
            {
                "id": m.id,
                "session_id": m.session_id,
                "role": m.role,
                "content": m.content,
                "metadata": m.metadata_,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }
