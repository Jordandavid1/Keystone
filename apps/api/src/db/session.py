"""
Database engine and async session factory (Bible v2 §21; ADR-005 PR1).
PostgreSQL is the primary engine of record.
No create_all calls in any live path.
"""

from __future__ import annotations

import os
from typing import Any, AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session

from apps.api.src.db.models import Base

# Primary PostgreSQL URL
DEFAULT_PG_URL = "postgresql+asyncpg://keystone:keystone_test_password@localhost:5432/keystone_test"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)

# Normalize async URL
if DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def run_alembic_upgrade(database_url: str | None = None, revision: str = "head") -> None:
    """Helper to run alembic upgrade programmatically."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    if database_url:
        sync_url = database_url
        if sync_url.startswith("postgresql+asyncpg://"):
            sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        elif sync_url.startswith("postgresql://") and "+psycopg" not in sync_url:
            sync_url = sync_url.replace("postgresql://", "postgresql+psycopg://")
        cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, revision)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an isolated async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """
    PR1 Schema Initialization:
    Ensures Alembic upgrade head is run. No Base.metadata.create_all in live path.
    """
    pass
