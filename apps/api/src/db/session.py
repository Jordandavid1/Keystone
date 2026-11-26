"""
Database engine and async session factory (Bible v2 §21; ADR-005 PR1).
Uses PostgreSQL when configured or reachable on localhost:5432, and automatically
falls back to a persistent local SQLite v2 database (data/keystone_v2.db) on
developer workstations when PostgreSQL is not running.
"""

from __future__ import annotations

import os
import secrets
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import sqlalchemy as sa
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

from apps.api.src.db.models import Base


@compiles(sa.UUID, "sqlite")
def _compile_uuid_sqlite(_type: object, _compiler: object, **_kw: object) -> str:
    """Ensure SQLite stores UUIDs as CHAR(32) text instead of NUMERIC/REAL affinity."""
    return "CHAR(32)"


@event.listens_for(Engine, "connect")
def _register_sqlite_functions(dbapi_conn: object, _record: object) -> None:
    """Provide SQLite compatibility for PostgreSQL server_default=now()."""
    if hasattr(dbapi_conn, "create_function") and dbapi_conn.__class__.__module__.startswith("sqlite3"):
        dbapi_conn.create_function("now", 0, lambda: datetime.now(timezone.utc).isoformat())

try:
    from services.cognition.src.client import load_keystone_dotenv
    load_keystone_dotenv()
except Exception:
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _ensure_local_runtime_secrets() -> None:
    """Ensure required Gate/C2PA/Service signing keys exist in local dev environments."""
    if os.getenv("KEYSTONE_ENV", "development").strip().lower() == "production":
        return
    required_defaults = {
        "KEYSTONE_ENVELOPE_SECRET": f"ks_env_{secrets.token_hex(24)}",
        "KEYSTONE_C2PA_SIGNING_KEY": f"ks_c2pa_{secrets.token_hex(24)}",
        "KEYSTONE_INTERNAL_SERVICE_TOKEN": f"ks_svc_{secrets.token_hex(24)}",
        "STRIPE_WEBHOOK_SECRET": f"whsec_{secrets.token_hex(16)}",
        "ADULT_PROCESSOR_WEBHOOK_SECRET": f"whsec_adult_{secrets.token_hex(16)}",
    }
    missing_to_persist = {}
    for key, generated in required_defaults.items():
        if not os.getenv(key, "").strip():
            os.environ[key] = generated
            missing_to_persist[key] = generated

    if missing_to_persist and "pytest" not in sys.modules:
        env_path = _repo_root() / ".env"
        try:
            existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
            lines = existing.splitlines()
            for k, v in missing_to_persist.items():
                lines.append(f"{k}={v}")
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError:
            pass


_ensure_local_runtime_secrets()


def _is_tcp_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


DEFAULT_PG_URL = "postgresql+asyncpg://keystone:keystone_test_password@localhost:5432/keystone_test"


def _resolve_database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        if explicit.startswith("postgresql://") and "+asyncpg" not in explicit:
            return explicit.replace("postgresql://", "postgresql+asyncpg://")
        return explicit

    if _is_tcp_open("127.0.0.1", 5432):
        return DEFAULT_PG_URL

    data_dir = _repo_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sqlite_file = (data_dir / "keystone_v2.db").resolve()
    sync_sqlite_url = f"sqlite:///{sqlite_file.as_posix()}"
    try:
        sync_eng = create_engine(sync_sqlite_url)
        Base.metadata.create_all(sync_eng)
        sync_eng.dispose()
    except Exception as exc:
        print(f"[Warning] SQLite create_all failed: {exc}")
    return f"sqlite+aiosqlite:///{sqlite_file.as_posix()}"


DATABASE_URL = _resolve_database_url()

_engine_kwargs = {"echo": False}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["pool_pre_ping"] = True

engine: AsyncEngine = create_async_engine(DATABASE_URL, **_engine_kwargs)

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
    """Initialize schema on SQLite dev fallback if needed."""
    active_eng = target_engine or engine
    if str(active_eng.url).startswith("sqlite"):
        async with active_eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
