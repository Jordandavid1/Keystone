"""
KEYSTONE FastAPI Authentication Dependencies
"""

from __future__ import annotations

import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.security import (
    enforce_tenant_isolation,
    hash_api_key,
    verify_service_token,
    verify_token,
)
from apps.api.src.db.models import ApiKey, User
from apps.api.src.db.session import get_db
from apps.api.src.repositories.api_keys import ApiKeyRepository
from apps.api.src.repositories.users import UserRepository


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Extracts and authenticates the current user from Bearer JWT token or API key.
    """
    user_repo = UserRepository(db)

    # 1. Check Bearer Token
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid Authorization header format. Expected 'Bearer <token>'"
            )
        token = authorization[7:].strip()
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized: Token missing subject claim"
                )
            user = await user_repo.get_user_by_id(user_id)
            if not user or user.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unauthorized: User account not found or inactive"
                )
            return user
        except ValueError as err:
            err_msg = str(err)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unauthorized: {err_msg}"
            )

    # 2. Check API Key
    if x_api_key:
        try:
            key_hash = hash_api_key(x_api_key)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid API key format"
            )

        api_key_repo = ApiKeyRepository(db, tenant_id=str(uuid.UUID(int=0)))
        api_key = await api_key_repo.get_by_hash(key_hash)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid or revoked API key"
            )

        user = await user_repo.get_user_by_id(api_key.user_id)
        if not user or user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: User associated with API key not found"
            )
        return user

    # Neither provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Missing Authorization header or X-API-Key"
    )


async def get_current_tenant_id(
    current_user: User = Depends(get_current_user)
) -> str:
    """Dependency that resolves the authenticated tenant user_id."""
    return str(current_user.id)


def require_service_token(
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token")
) -> None:
    """Dependency protecting internal worker endpoints."""
    if not verify_service_token(x_service_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Valid service token required"
        )
