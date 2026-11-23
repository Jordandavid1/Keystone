"""
Account, Stage-1 Age Verification, and Content Mode Router (PR3b).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from apps.api.src.auth.dependencies import get_current_user
from apps.api.src.db.models import AuditEvent, Project, Session as ChatSession, User
from apps.api.src.db.session import get_db

router = APIRouter(prefix="/v1/account", tags=["account"])


class AgeVerificationRequest(BaseModel):
    confirmed_adult_18_plus: bool
    method: str = "attestation"


class ContentModeUpdateRequest(BaseModel):
    content_mode: Literal["sfw", "unrestricted"]
    project_id: Optional[str] = None
    session_id: Optional[str] = None


@router.get("")
def get_account(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "role": current_user.role,
        "content_mode": getattr(current_user, "content_mode", "sfw"),
        "age_verified": bool(getattr(current_user, "age_verified", False)),
        "age_verified_at": getattr(current_user, "age_verified_at", None),
        "age_verification_method": getattr(current_user, "age_verification_method", None),
    }


@router.post("/age-verification")
def verify_age(
    payload: AgeVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    if payload.confirmed_adult_18_plus is not True:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AGE_VERIFICATION_DECLINED",
                "message": "confirmed_adult_18_plus must be true.",
            },
        )

    now = datetime.now(timezone.utc)
    current_user.age_verified = True
    current_user.age_verified_at = now
    current_user.age_verification_method = payload.method or "attestation"

    audit = AuditEvent(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        event_type="account.age_verified",
        payload={
            "method": current_user.age_verification_method,
            "verified_at": now.isoformat(),
        },
    )
    db.add(audit)
    db.commit()

    return {
        "age_verified": True,
        "age_verified_at": now.isoformat(),
        "age_verification_method": current_user.age_verification_method,
    }


@router.patch("/content-mode")
def update_content_mode(
    payload: ContentModeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    if payload.content_mode == "unrestricted" and not getattr(current_user, "age_verified", False):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AGE_VERIFICATION_REQUIRED",
                "message": "Age verification is required to enable unrestricted content mode.",
            },
        )

    target_type = "user"
    target_id = current_user.id

    if payload.session_id:
        sess = (
            db.query(ChatSession)
            .filter(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        sess.content_mode = payload.content_mode
        target_type = "session"
        target_id = sess.id
    elif payload.project_id:
        proj = (
            db.query(Project)
            .filter(Project.id == payload.project_id, Project.user_id == current_user.id)
            .first()
        )
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found")
        proj.content_mode = payload.content_mode
        target_type = "project"
        target_id = proj.id
    else:
        current_user.content_mode = payload.content_mode

    audit = AuditEvent(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        event_type="account.content_mode_updated",
        payload={
            "target_type": target_type,
            "target_id": target_id,
            "content_mode": payload.content_mode,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "target_type": target_type,
        "target_id": target_id,
        "content_mode": payload.content_mode,
    }
