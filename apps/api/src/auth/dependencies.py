"""
KEYSTONE FastAPI Authentication Dependencies
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status
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


_log = logging.getLogger("keystone.auth")

DEV_BYPASS_ENV = "KEYSTONE_DEV_AUTH_BYPASS"
DEV_BYPASS_EMAIL = "dev@keystone.local"
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def dev_bypass_enabled() -> bool:
    """Local-development auth bypass. Off unless KEYSTONE_DEV_AUTH_BYPASS=1 is set."""
    return os.environ.get(DEV_BYPASS_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def dev_bypass_applies(request: Optional[Request], authorization: Optional[str], x_api_key: Optional[str]) -> bool:
    """The bypass only covers credential-less requests that arrive over loopback."""
    if authorization or x_api_key or not dev_bypass_enabled():
        return False
    if request is None:
        return False
    host = getattr(getattr(request, "client", None), "host", None)
    if host not in _LOOPBACK_HOSTS:
        return False
    # Behind the Next.js /v1 proxy every request arrives from loopback, so also
    # require the original client (X-Forwarded-For) to be loopback when present.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [h.strip().removeprefix("::ffff:") for h in forwarded.split(",") if h.strip()]
        if any(h not in _LOOPBACK_HOSTS for h in hops):
            return False
    return True


async def _dev_bypass_user(user_repo: UserRepository) -> User:
    user = await user_repo.get_user_by_email(DEV_BYPASS_EMAIL)
    if user is None:
        user = await user_repo.create_user(
            id=str(uuid.uuid4()),
            email=DEV_BYPASS_EMAIL,
            password_hash=None,
            display_name="Local developer",
        )
        _log.warning("%s is on: created local developer account %s", DEV_BYPASS_ENV, DEV_BYPASS_EMAIL)
    return user


async def get_current_user(
    request: Request,
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

    # 3. Local development bypass (explicit env opt-in, loopback only)
    if dev_bypass_applies(request, authorization, x_api_key):
        return await _dev_bypass_user(user_repo)

    # Neither provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Missing Authorization header or X-API-Key"
    )


async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    For routes that also serve signed-out callers: returns None when no credentials
    are sent (and the dev bypass doesn't apply). Credentials that are sent must be valid.
    """
    if not authorization and not x_api_key and not dev_bypass_applies(request, authorization, x_api_key):
        return None
    return await get_current_user(request, authorization, x_api_key, db)


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
