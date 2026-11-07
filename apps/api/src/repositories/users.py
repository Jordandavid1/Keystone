"""
KEYSTONE User Repository
"""

from __future__ import annotations

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.db.models import User, CreditAccount


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(
        self,
        id: str | uuid.UUID,
        email: str,
        password_hash: Optional[str] = None,
        display_name: str = "Creator"
    ) -> User:
        if not id or not email:
            raise ValueError("INVALID_USER")

        user_id_str = str(id)
        user = User(
            id=user_id_str,
            email=email.strip().lower(),
            password_hash=password_hash,
            display_name=display_name,
            status="active"
        )
        self.session.add(user)

        # Automatically initialize credit account for user with 100,000 studio credits
        credit_account = CreditAccount(
            id=str(uuid.uuid4()),
            user_id=user_id_str,
            balance=100000,
            held_balance=0,
            currency="credits",
            status="active"
        )
        self.session.add(credit_account)

        await self.session.flush()
        return user

    async def get_user_by_id(self, user_id: str | uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.id == str(user_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
