"""
KEYSTONE Authentication Router (/v1/auth)
Handles registration, login, token refresh, and programmatic API key management.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_user
from apps.api.src.auth.security import (
    generate_api_key_pair,
    generate_token,
    hash_password,
    verify_password,
)
from apps.api.src.db.models import User
from apps.api.src.db.session import get_db
from apps.api.src.repositories.api_keys import ApiKeyRepository
from apps.api.src.repositories.users import UserRepository

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = "Creator"


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: Optional[List[str]] = ["*"]


@router.post("/register", summary="Register new user account")
async def register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    user_repo = UserRepository(db)
    existing = await user_repo.get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(req.password)
    user = await user_repo.create_user(
        id=user_id,
        email=req.email,
        password_hash=pw_hash,
        display_name=req.display_name or "Creator"
    )

    token = generate_token(user.id, role="user")
    return {
        "status": "ok",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status
        },
        "access_token": token,
        "token_type": "bearer"
    }


@router.post("/login", summary="Authenticate with email and password")
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_email(req.email)
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = generate_token(user.id, role="user")
    return {
        "status": "ok",
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status
        },
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/me", summary="Get current authenticated user profile")
async def me(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "status": current_user.status,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }


@router.post("/api-keys", summary="Create new API key")
async def create_api_key(
    req: CreateApiKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    api_key_repo = ApiKeyRepository(db, tenant_id=current_user.id)
    raw_key, prefix, key_hash = generate_api_key_pair()
    key_id = str(uuid.uuid4())

    key = await api_key_repo.create_api_key(
        id=key_id,
        name=req.name,
        key_hash=key_hash,
        key_prefix=prefix,
        scopes=req.scopes or ["*"]
    )

    return {
        "status": "ok",
        "id": key.id,
        "name": key.name,
        "raw_key": raw_key,  # Only returned once upon creation!
        "key_prefix": prefix,
        "scopes": key.scopes,
        "status": key.status
    }


@router.get("/api-keys", summary="List API keys for current tenant")
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    api_key_repo = ApiKeyRepository(db, tenant_id=current_user.id)
    keys = await api_key_repo.list_api_keys()
    return {
        "api_keys": [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key_prefix,
                "scopes": k.scopes,
                "status": k.status,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                "created_at": k.created_at.isoformat() if k.created_at else None
            }
            for k in keys
        ]
    }
