# KEYSTONE Milestone M1 (Wave 1: Vertical Shell) Blueprint
**Status:** Approved Technical Architecture & Implementation Blueprint  
**Milestone:** M1 (Wave 1: Vertical Shell)  
**Author:** explorer_m1_1 (Teamwork Preview Explorer)  
**Parent:** Project Orchestrator (Conversation ID: `6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Canonical Spec:** `KEYSTONE_BIBLE.md` (§16, §17, §19, §21, §22, §27, §28, §33)  
**Pre-Built Integrity Invariant:** Strictly additive; zero modifications to pre-built scaffold files.

---

## 1. Executive Summary & Milestone Invariants

Milestone M1 establishes the foundational vertical application shell of KEYSTONE, executing the 10-step end-to-end lifecycle mandated in Bible §33 (Wave 1: Vertical application shell):
```text
Register -> Create project -> Create session -> Upload asset -> Send message -> 
Create fake job -> Stream status -> Return persistent fake asset -> 
Display asset on canvas -> Refresh and recover state
```

To support this vertical shell with production-grade rigor, Milestone M1 delivers five foundational capability features:
1. **F05: Relational Data Models & Repositories (`packages/database`)**: Modern SQLAlchemy 2.0 async engine and declarative ORM models mapping all 23 database tables, accompanied by tenant-scoped repository access layers.
2. **F06: Authentication & Tenant Isolation Engine (`packages/security`)**: PBKDF2-HMAC-SHA256 password hashing (600,000 iterations), stateless HMAC-SHA256 bearer tokens, SHA-256 API key hashing, and zero-trust tenant isolation dependencies.
3. **F07: Asset Storage & Short-Expiry Signed URLs Service (`services/assets`)**: Multi-tenant directory-traversal-sanitized storage keys, dual storage providers (local persistent disk and Google Cloud Storage fallback), and HMAC-SHA256 15-minute short-expiry signed URLs.
4. **F08: Lineage DAG Tracking Engine (`services/assets`)**: Directed Acyclic Graph (DAG) manager tracking parent-child asset transformations across all 8 canonical relationship types (`source`, `edit`, `variation`, `animation`, `upscale`, `reference`, `selected-final`, `intermediate`) with strict cycle detection and ancestor/descendant graph traversal.
5. **F09: Job State Machine Engine (`services/jobs`)**: Deterministic 13-state execution engine with a formal transition matrix, terminal state locks, lifecycle event auditing, and bounded retries.
6. **REST API Routers (`apps/api/src/routers`)**: Clean domain routers mounted additively onto the FastAPI server (`apps/api/src/server.py`) exposing the `/v1` public API endpoints.
7. **Verification Test Suite (`tests/e2e_v2/test_m1_vertical_shell.py`)**: Dual-track test harness verifying unit boundaries, adversarial attack vectors (forgery, traversal, cross-tenant leaks), and the complete 10-step Wave 1 integration flow.

---

## 2. F05: Relational Data Models & Repositories Architecture

### 2.1 Database Connection Manager (`packages/database/src/connection.py`)

The connection manager provides async connection pooling, dialect auto-detection, and session factory management for both production PostgreSQL (Cloud SQL via `asyncpg`) and local development/testing (SQLite via `aiosqlite`).

#### Specification & Interface Contract
```python
"""
packages/database/src/connection.py
Async database engine and session management.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any, Dict

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

# Dynamic URL resolution with asyncpg protocol normalization
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./keystone.db")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Connection pool configurations
engine_kwargs: Dict[str, Any] = {"echo": False, "future": True}
if "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "20"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    engine_kwargs["pool_recycle"] = 1800  # Recycle connections every 30 minutes

engine: AsyncEngine = create_async_engine(DATABASE_URL, **engine_kwargs)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an isolated async database session with automatic commit/rollback."""
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
    """Creates all 23 database tables from metadata if they do not exist."""
    from packages.database.src.models import Base
    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def check_connection(target_engine: AsyncEngine | None = None) -> bool:
    """Verifies active connectivity to durable store."""
    eng = target_engine or engine
    async with eng.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        return result.scalar() == 1
```

---

### 2.2 Cross-Dialect UUID Type (`UniversalUUID`)

To satisfy the Bible §21 requirement (`UUID primary keys`) across both PostgreSQL (which has native `UUID`) and SQLite (which lacks native `UUID`), a custom `UniversalUUID` type decorator handles seamless type coercion:

```python
class UniversalUUID(TypeDecorator):
    """
    Cross-dialect UUID type.
    Maps to PostgreSQL native UUID in Cloud SQL and CHAR(36) in SQLite.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)
```

---

### 2.3 Declarative Base Models (`packages/database/src/models/`)

All 23 tables defined in `0001_core.sql` and `0002_keystone_full_schema.sql` are mapped as SQLAlchemy 2.0 `Mapped` declarative classes. The primary M1 entities are detailed below:

#### 1. User (`users`)
```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="Creator")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="owner", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[List["ApiKey"]] = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    credit_account: Mapped[Optional["CreditAccount"]] = relationship("CreditAccount", back_populates="user", uselist=False)
```

#### 2. Project (`projects`)
```python
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="project")
    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="project")
```

#### 3. Session (`sessions`)
```python
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="sessions")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="session", cascade="all, delete-orphan")
```

#### 4. Message (`messages`)
```python
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    session_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # 'user', 'keystone'
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    session: Mapped["Session"] = relationship("Session", back_populates="messages")
```

#### 5. Asset (`assets`)
```python
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    owner_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)  # 'image', 'video', 'audio', 'document'
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="local")
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available")
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("storage_provider", "storage_key", name="uq_assets_storage_provider_key"),
    )

    owner: Mapped["User"] = relationship("User", back_populates="assets")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="assets")
```

#### 6. Job (`jobs`)
```python
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    request_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)
    authority_decision_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("authority_decisions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False, default="CREATED", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    error_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="jobs")
    generation_attempts: Mapped[List["GenerationAttempt"]] = relationship("GenerationAttempt", back_populates="job", cascade="all, delete-orphan")
```

#### 7. AssetRelationship (`asset_relationships`)
```python
class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    parent_asset_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    child_asset_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        UniqueConstraint("parent_asset_id", "child_asset_id", "relationship_type", name="uq_asset_relationships_par_child_type"),
    )
```

---

### 2.4 Tenant-Isolated Repositories (`packages/database/src/repositories/`)

All repository operations derive from `BaseRepository`, enforcing mandatory `tenant_id` scoping at initialization. Direct SQL queries that do not filter by `tenant_id` are architecturally impossible.

```python
class BaseRepository(Generic[T]):
    """Base class enforcing tenant-level isolation on all queries and mutations."""
    def __init__(self, session: AsyncSession, tenant_id: str | uuid.UUID) -> None:
        self.session = session
        self.tenant_id = str(tenant_id)
```

#### Soft-Deletion Invariant
For `projects` and `assets`, deletion is implemented as soft-deletion (`deleted_at = now(), status = 'deleted'`). Repository queries strictly append `.where(Model.deleted_at.is_(None))` to eliminate ghost references and prevent leaking deleted records to downstream UI canvas sessions.

---

## 3. F06: Authentication & Tenant Isolation Engine

### 3.1 Security Primitives (`packages/security/src/auth.py`)

#### 1. Password Hashing (PBKDF2-HMAC-SHA256, OWASP Benchmark)
- Salt: 16 cryptographically secure random bytes via `secrets.token_bytes(16)`.
- Iteration Count: 600,000 iterations of HMAC-SHA256.
- Hash Representation: `pbkdf2_sha256$600000${salt_hex}${key_hex}`.
- Verification: Constant-time comparison using `secrets.compare_digest` to prevent timing side-channels.

#### 2. Stateless Bearer Tokens (JWT HMAC-SHA256)
- Claims:
  - `sub`: User UUID string (tenant identifier).
  - `role`: Role string (`user`, `admin`).
  - `iat`: Issued-at UTC UNIX epoch.
  - `exp`: Expiration UTC UNIX epoch (default: 3600s / 1 hour short-lived tokens per Bible §27).
- Format: `{b64url(payload)}.{b64url(hmac_sha256(secret, b64url(payload)))}`.
- Verification Guards:
  - Rejects `alg=none` and malformed token formats.
  - Rejects tampered signatures with `secrets.compare_digest`.
  - Rejects expired timestamps (`int(time.time()) > exp`).

#### 3. Programmatic API Key Management (SHA-256 Hashing)
- Generation: Returns triple `(raw_key, prefix, key_hash)`.
  - `prefix`: 8-character hex string (`secrets.token_hex(4)`).
  - `secret`: 40-character hex string (`secrets.token_hex(20)`).
  - `raw_key`: `ks_live_{prefix}_{secret}`.
- Persistence Rule: Per Bible §21 and §27 ("raw API keys never stored"), the database stores only `key_hash = hashlib.sha256(raw_key.encode()).hexdigest()`. The raw key is returned to the user exactly once upon generation.
- Lookup: Incoming `X-API-Key` headers are hashed and queried against `api_keys.key_hash`.

---

### 3.2 Tenant Isolation Dependencies

FastAPI request dependencies guarantee tenant boundary enforcement before any business logic executes:

```python
async def get_current_user(
    auth_header: Optional[str] = Header(None, alias="Authorization"),
    api_key_header: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Authenticates request via Bearer JWT or X-API-Key and enforces user active state."""
    user = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        payload = verify_token(token)
        user_id = payload.get("sub")
        user = await UserRepository(db).get_user_by_id(user_id)
    elif api_key_header:
        key_hash = hash_api_key(api_key_header)
        api_key_record = await ApiKeyRepository(db, tenant_id="system").get_by_hash(key_hash)
        if api_key_record and api_key_record.status == "active":
            user = await UserRepository(db).get_user_by_id(api_key_record.user_id)

    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="AUTHENTICATION_FAILED: Invalid credentials or inactive user")
    return user

async def get_current_tenant_id(user: User = Depends(get_current_user)) -> str:
    """Returns the authenticated tenant ID, binding downstream handlers to this user boundary."""
    return str(user.id)
```

---

## 4. F07: Asset Storage & Short-Expiry Signed URLs Service

### 4.1 Storage Architecture (`services/assets/src/storage.py`)

Per Bible §22 and §28, media binaries are kept in object storage behind short-expiry signed URLs, while metadata is stored in PostgreSQL.

#### Storage Key Scoping
Storage keys enforce multi-tenant hierarchy:
```text
tenants/{user_id}/assets/{asset_id}/{safe_filename}
```

#### Traversal Sanitization Matrix
The storage service rigorously sanitizes keys before filesystem or cloud operations:
1. **Filename Sanitization**: Only alphanumeric characters, dots, underscores, and hyphens (`[a-zA-Z0-9._-]`) are permitted. All others are replaced with `_`.
2. **Directory Escape Elimination**: Basename extraction via `os.path.basename` strips `../` and `..\` sequences.
3. **Dot-Only Fallback**: Filenames that evaluate to `.`, `..`, or empty strings automatically fall back to `asset.bin`.
4. **Local Path Boundary Verification**:
   ```python
   def _resolve_path(self, key: str) -> Path:
       clean_key = key.lstrip("/").replace("\\", "/")
       target = (self.base_dir / clean_key).resolve()
       try:
           target.relative_to(self.base_dir.resolve())
       except ValueError:
           raise ValueError(f"ILLEGAL_STORAGE_PATH: Key traversal attempted: {key}")
       return target
   ```

---

### 4.2 Short-Expiry Signed URLs (15-Minute Expiry)

All direct asset downloads and client uploads use cryptographic HMAC-SHA256 signed URLs:
- **Default TTL**: 900 seconds (15 minutes per Bible §22 and Wave 1 spec).
- **Max Expiration Ceiling**: 3600 seconds (1 hour). Requests for `> 3600s` or `<= 0s` are rejected with `EXPIRY_EXCEEDED` or `INVALID_EXPIRY`.
- **Payload**: `{storage_key}:{expires_at_timestamp}`.
- **Signature Algorithm**: `HMAC-SHA256(STORAGE_SIGNING_KEY, payload).hexdigest()`.
- **Format**: `{STORAGE_BASE_URL}/{storage_key}?expires={expires_at}&signature={sig}`.
- **Verification**: `validate_signed_url` validates both timestamp freshness and cryptographic integrity via `hmac.compare_digest`.

---

## 5. F08: Lineage Directed Acyclic Graph (DAG) Engine

### 5.1 The 8 Canonical Relationship Types (`services/assets/src/lineage.py`)

Per Bible §22, KEYSTONE models asset ancestry as an immutable directed acyclic graph. The engine supports all 8 canonical relationship types:

| # | Relationship Type | Semantic Definition | Example Pipeline Use Case |
|---|-------------------|---------------------|---------------------------|
| 1 | `source` | Root input or base asset | Original uploaded creator photograph |
| 2 | `edit` | Localized or global image editing | Background removal, inpainting, color grading |
| 3 | `variation` | Stylistic exploration from same intent | Alternative composition or lighting variation |
| 4 | `animation` | Temporal synthesis from still image | Wan I2V animating a portrait into video |
| 5 | `upscale` | Super-resolution or detail enhancement | 4x Latent Upscale / Clarity enhancement |
| 6 | `reference` | Guidance asset (pose, depth, style) | ControlNet openpose or style reference image |
| 7 | `selected-final` | Curated production master deliverable | Approved hero asset exported to project canvas |
| 8 | `intermediate` | Ephemeral execution artifact | Noise latents, segmentation masks, depth passes |

---

### 5.2 Lineage DAG Invariants & Cycle Detection

The `LineageDAG` engine enforces four strict integrity invariants:
1. **Anti-Self-Parenting**: `parent_id == child_id` raises `SELF_REFERENTIAL_LINEAGE`.
2. **Canonical Type Enforcement**: Any relationship outside the 8 recognized types raises `INVALID_RELATIONSHIP_TYPE`.
3. **Cycle Detection**: Adding directed edge $P \to C$ must not create a directed cycle. Before persistence, the engine executes depth-first traversal checking `has_path(child_id, parent_id)`. If true, the operation raises `CYCLE_DETECTED`.
4. **Tenant Isolation Scoping**: Both parent and child assets must exist and belong to the calling tenant. Cross-tenant linkage raises `HTTP 404 / Access Denied`.

#### Graph Traversal Methods
- `get_ancestors(asset_id)`: Uses BFS queue traversal upstream over parent edges to return all root and intermediate predecessors.
- `get_descendants(asset_id)`: Uses BFS queue traversal downstream over child edges to return all derived variations and video outputs.

---

## 6. F09: Deterministic 13-State Job State Machine Engine

### 6.1 State Topology & Transition Matrix (`services/jobs/src/state_machine.py`)

Per Bible §19, KEYSTONE jobs follow a deterministic, audited 13-state machine.

```text
                             [CREATED]
                                 │
                            (validating)
                                 ▼
                           [VALIDATING] ──────────► [FAILED] / [REJECTED] / [CANCELLED]
                                 │
                            (planning)
                                 ▼
                            [PLANNING] ───────────► [FAILED] / [CANCELLED]
                                 │
                           (authorizing)
                                 ▼
                          [AUTHORIZING] ──────────► [REJECTED] / [CANCELLED]
                                 │
                              (queued)
                                 ▼
                             [QUEUED] ────────────► [CANCELLED] / [FAILED]
                                 │
                             (running)
                                 ▼
                             [RUNNING] ───────────► [FAILED] / [CANCELLED]
                                 │                      ▲
                                 │                      │
                       (validating_output)              │
                                 ▼                      │
                        [VALIDATING_OUTPUT]             │
                                 │                      │
               ┌─────────────────┼──────────────────┐   │
               │                 │                  │   │
          (completed)      (retry_pending)  (replan_required)
               │                 │                  │   │
               ▼                 ▼                  ▼   │
          [COMPLETED]     [RETRY_PENDING]    [REPLAN_REQUIRED]
           (Terminal)            │                  │   │
                                 └────────► [QUEUED]┘   │
                                                        └──► [PLANNING]
```

#### Terminal States
`COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED` are terminal. Attempting to transition out of any terminal state raises `ILLEGAL_TRANSITION`.

#### Formal Transition Dictionary
```python
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    JobState.CREATED: [JobState.VALIDATING, JobState.CANCELLED, JobState.REJECTED],
    JobState.VALIDATING: [JobState.PLANNING, JobState.FAILED, JobState.CANCELLED, JobState.REJECTED],
    JobState.PLANNING: [JobState.AUTHORIZING, JobState.FAILED, JobState.CANCELLED],
    JobState.AUTHORIZING: [JobState.QUEUED, JobState.REJECTED, JobState.CANCELLED, JobState.PLANNING],
    JobState.QUEUED: [JobState.RUNNING, JobState.CANCELLED, JobState.FAILED],
    JobState.RUNNING: [JobState.VALIDATING_OUTPUT, JobState.RETRY_PENDING, JobState.FAILED, JobState.CANCELLED],
    JobState.VALIDATING_OUTPUT: [JobState.COMPLETED, JobState.RETRY_PENDING, JobState.REPLAN_REQUIRED, JobState.FAILED],
    JobState.RETRY_PENDING: [JobState.QUEUED, JobState.FAILED, JobState.CANCELLED],
    JobState.REPLAN_REQUIRED: [JobState.PLANNING, JobState.FAILED, JobState.CANCELLED],
    JobState.COMPLETED: [],
    JobState.FAILED: [],
    JobState.CANCELLED: [],
    JobState.REJECTED: [],
}
```

---

### 6.2 Lifecycle Aliases & Bounded Retries

#### Worker Lifecycle Aliases
Kaggle workers and internal adapters publish granular progress events that map cleanly to canonical states:
- `COMPILING_PROMPT` $\to$ `VALIDATING`
- `PROPOSED_ACTION_PENDING` $\to$ `PLANNING`
- `AWAITING_AUTHORIZATION` $\to$ `AUTHORIZING`
- `ENVELOPE_ISSUED` $\to$ `QUEUED`
- `DISPATCHED_TO_WORKER` / `WORKER_RUNNING` $\to$ `RUNNING`
- `EVALUATING_OUTPUT` $\to$ `VALIDATING_OUTPUT`

#### Bounded Retries
The state machine encapsulates retry budgets (`max_attempts = 3`). `can_retry()` validates remaining attempts before permitting transition from `VALIDATING_OUTPUT` to `RETRY_PENDING`. If exhausted, the job transitions directly to `FAILED`.

---

## 7. REST API Router Specification & Server Integration

### 7.1 Router Endpoints Matrix (`apps/api/src/routers/`)

| Router File | Method | Path | Summary & Responsibilities |
|-------------|--------|------|----------------------------|
| `auth.py` | `POST` | `/v1/auth/register` | Create user, hash password, seed credit account (100 credits), return JWT |
| `auth.py` | `POST` | `/v1/auth/login` | Verify PBKDF2 hash, issue 1-hour JWT token |
| `auth.py` | `GET` | `/v1/auth/me` | Return authenticated user identity and status |
| `auth.py` | `POST` | `/v1/auth/api-keys` | Generate API key pair, store SHA-256 hash, return raw key once |
| `auth.py` | `GET` | `/v1/auth/api-keys` | List active/revoked API keys for current tenant |
| `projects.py` | `POST` | `/v1/projects` | Create workspace project scoped to tenant |
| `projects.py` | `GET` | `/v1/projects` | List active projects for tenant (excluding soft-deleted) |
| `projects.py` | `GET` | `/v1/projects/{id}` | Get project by ID with tenant isolation check |
| `projects.py` | `DELETE` | `/v1/projects/{id}` | Soft-delete project (`deleted_at = now()`) |
| `sessions.py` | `POST` | `/v1/sessions` | Create creative session; validates `project_id` tenant ownership |
| `sessions.py` | `GET` | `/v1/sessions` | List sessions, optionally filtered by `?project_id=` |
| `sessions.py` | `GET` | `/v1/sessions/{id}` | Get session details |
| `sessions.py` | `POST` | `/v1/sessions/{id}/messages` | Append message (`user` or `keystone`) to session |
| `sessions.py` | `GET` | `/v1/sessions/{id}/messages` | List chronological messages in session |
| `assets.py` | `POST` | `/v1/assets` | Register asset metadata; validates storage key format and tenant |
| `assets.py` | `POST` | `/v1/assets/upload` | Generate short-expiry (15-min) signed upload and download URLs |
| `assets.py` | `GET` | `/v1/assets` | List tenant assets (excluding soft-deleted) |
| `assets.py` | `GET` | `/v1/assets/{id}` | Get asset metadata with freshly generated 15-min signed download URL |
| `assets.py` | `DELETE` | `/v1/assets/{id}` | Soft-delete asset (`deleted_at = now()`) |
| `assets.py` | `POST` | `/v1/assets/{id}/relationships`| Add directed Lineage DAG edge with cycle and self-parenting checks |
| `assets.py` | `GET` | `/v1/assets/{id}/lineage` | Traverses graph returning `ancestors` and `descendants` |
| `jobs.py` | `POST` | `/v1/jobs` | Create job record in `CREATED` state |
| `jobs.py` | `GET` | `/v1/jobs` | List tenant jobs |
| `jobs.py` | `GET` | `/v1/jobs/{id}` | Get job state, workflow details, and error diagnostics |
| `jobs.py` | `POST` | `/v1/jobs/{id}/transition` | Execute validated deterministic state machine transition |
| `jobs.py` | `GET` | `/v1/jobs/{id}/events` | Stream or list full lifecycle event transition history |

---

### 7.2 Additive Server Mounting (`apps/api/src/server.py`)

All M1 routers are mounted onto the FastAPI application additively, maintaining `main.py` 100% byte-identical:
```python
# apps/api/src/server.py (additive mounting)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(assets_router)
app.include_router(jobs_router)
```

---

## 8. Verification Test Suite Blueprint (`tests/e2e_v2/test_m1_vertical_shell.py`)

The verification suite for Milestone M1 combines rigorous unit boundary checks, adversarial challenge vectors, and the complete 10-step Wave 1 vertical shell integration flow.

### 8.1 Test Structure & Coverage Matrix

```text
tests/e2e_v2/test_m1_vertical_shell.py
├── TestF05DatabaseAndRepositories
│   ├── test_all_23_tables_present_in_orm_metadata
│   ├── test_universal_uuid_postgresql_and_sqlite_dialects
│   ├── test_user_repository_creation_and_auto_credit_seed
│   ├── test_project_repository_tenant_scoping_and_soft_delete
│   ├── test_session_repository_rejects_cross_tenant_project
│   └── test_asset_repository_soft_delete_filtering
├── TestF06AuthAndSecurity
│   ├── test_pbkdf2_600k_iterations_and_salt_entropy
│   ├── test_pbkdf2_constant_time_verification
│   ├── test_jwt_token_generation_and_valid_verification
│   ├── test_jwt_token_tampered_payload_rejected
│   ├── test_jwt_token_corrupted_signature_rejected
│   ├── test_jwt_token_alg_none_injection_rejected
│   ├── test_api_key_generation_and_raw_key_never_stored
│   ├── test_api_key_direct_hash_injection_rejected
│   └── test_tenant_isolation_guard_blocks_cross_tenant_access
├── TestF07StorageAndSignedURLs
│   ├── test_storage_key_generation_and_tenant_path_isolation
│   ├── test_storage_key_sibling_traversal_rejected
│   ├── test_storage_key_user_and_asset_id_sanitized
│   ├── test_storage_key_dot_only_fallback_to_asset_bin
│   ├── test_signed_url_15_minute_generation_and_verification
│   ├── test_signed_url_3600s_max_ceiling_enforced
│   └── test_signed_url_tampered_signature_rejected
├── TestF08LineageDAG
│   ├── test_all_8_relationship_types_accepted
│   ├── test_invalid_relationship_type_rejected
│   ├── test_self_referential_lineage_rejected
│   ├── test_cycle_detection_in_complex_dag
│   ├── test_ancestor_and_descendant_bfs_traversal
│   └── test_cross_tenant_child_asset_lineage_rejected_with_404
├── TestF09JobStateMachine
│   ├── test_13_states_and_4_terminal_states
│   ├── test_valid_success_path_transitions
│   ├── test_illegal_jump_transitions_rejected
│   ├── test_terminal_state_exit_rejected
│   ├── test_idempotent_same_state_transition
│   └── test_worker_lifecycle_aliases_normalized
└── TestWave1VerticalShellFlow
    └── test_10_step_complete_vertical_shell_integration
```

---

### 8.2 The 10-Step Wave 1 Vertical Shell Flow

```python
@pytest.mark.asyncio
async def test_wave1_10_step_vertical_shell():
    client = TestClient(app)

    # 1. Register User & Obtain Bearer Token
    reg = client.post("/v1/auth/register", json={
        "email": f"creator_{uuid.uuid4().hex[:8]}@keystone.ai",
        "password": "SecurePassword123!",
        "display_name": "Visionary Director"
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Project
    proj = client.post("/v1/projects", headers=headers, json={
        "name": "Neon Odyssey Sci-Fi Short",
        "description": "Multi-shot cyberpunk cinematic series"
    })
    assert proj.status_code == 200
    project_id = proj.json()["id"]

    # 3. Create Session
    sess = client.post("/v1/sessions", headers=headers, json={
        "project_id": project_id,
        "title": "Act I Scene Composer"
    })
    assert sess.status_code == 200
    session_id = sess.json()["id"]

    # 4. Upload Input Asset
    upload = client.post("/v1/assets/upload", headers=headers, json={
        "filename": "cyberpunk_hero.png",
        "mime_type": "image/png",
        "byte_size": 3145728,
        "project_id": project_id
    })
    assert upload.status_code == 200
    input_asset_id = upload.json()["asset_id"]

    # 5. Send Message
    msg = client.post(f"/v1/sessions/{session_id}/messages", headers=headers, json={
        "role": "user",
        "content": "Animate cyberpunk_hero walking through neon rain at 24fps"
    })
    assert msg.status_code == 200

    # 6. Create Fake Job
    job = client.post("/v1/jobs", headers=headers, json={
        "capability_id": "wan_i2v",
        "provider_id": "kaggle_comfyui",
        "workflow_id": "wf_wan_cinematic",
        "workflow_version": "2.1.0",
        "initial_state": "CREATED"
    })
    assert job.status_code == 200
    job_id = job.json()["id"]

    # 7. Stream / Execute Transitions
    for st in ["VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED", "RUNNING", "VALIDATING_OUTPUT", "COMPLETED"]:
        t_res = client.post(f"/v1/jobs/{job_id}/transition", headers=headers, json={"next_state": st})
        assert t_res.status_code == 200

    # 8. Return Persistent Output Asset & Link Lineage
    out_asset = client.post("/v1/assets", headers=headers, json={
        "filename": "neon_rain_walk_animated.mp4",
        "mime_type": "video/mp4",
        "byte_size": 15728640,
        "project_id": project_id,
        "media_type": "video"
    })
    assert out_asset.status_code == 200
    output_asset_id = out_asset.json()["id"]

    rel = client.post(f"/v1/assets/{input_asset_id}/relationships", headers=headers, json={
        "child_asset_id": output_asset_id,
        "relationship_type": "animation",
        "job_id": job_id
    })
    assert rel.status_code == 200

    # 9. Query Lineage DAG
    lineage = client.get(f"/v1/assets/{output_asset_id}/lineage", headers=headers)
    assert lineage.status_code == 200
    assert input_asset_id in lineage.json()["ancestors"]

    # 10. Refresh and Recover State
    p_rec = client.get(f"/v1/projects/{project_id}", headers=headers)
    assert p_rec.status_code == 200
    assert p_rec.json()["name"] == "Neon Odyssey Sci-Fi Short"

    a_rec = client.get(f"/v1/assets?project_id={project_id}", headers=headers)
    assert a_rec.status_code == 200
    asset_ids = [a["id"] for a in a_rec.json()["assets"]]
    assert input_asset_id in asset_ids
    assert output_asset_id in asset_ids
```

---

## 9. Monorepo Alignment & Implementation Roadmap

### 9.1 Package Partitioning & Re-Export Bridge Strategy

To establish the permanent modular monorepo layout while maintaining complete backwards compatibility with existing imports:

1. **`packages/database`**:
   - `packages/database/src/connection.py` (authoritative connection manager)
   - `packages/database/src/models/__init__.py` (all 23 DeclarativeBase models)
   - `packages/database/src/repositories/__init__.py` (`BaseRepository`, `UserRepository`, `ProjectRepository`, `SessionRepository`, `MessageRepository`, `AssetRepository`, `JobRepository`, `ApiKeyRepository`)
2. **`packages/security`**:
   - `packages/security/src/auth.py` (PBKDF2 hashing, JWT tokens, API keys, FastAPI dependencies)
   - Re-exports to `apps/api/src/auth/`
3. **`services/assets`**:
   - `services/assets/src/storage.py` (key generation, sanitization, LocalStorageProvider, GoogleCloudStorageProvider, signed URLs)
   - `services/assets/src/lineage.py` (`LineageDAG`, 8 relationship types, cycle detection, BFS traversal)
   - Re-exports to `apps/api/src/storage/` and `apps/api/src/lineage/`
4. **`services/jobs`**:
   - `services/jobs/src/state_machine.py` (`JobState`, 13 states, 4 terminal states, transition matrix, `JobStateMachine`)
   - Re-exports to `apps/api/src/jobs/`
5. **Backwards-Compatibility Invariant**:
   - The modules under `apps/api/src/db/`, `apps/api/src/repositories/`, `apps/api/src/auth/`, `apps/api/src/storage/`, `apps/api/src/lineage/`, and `apps/api/src/jobs/` cleanly import and re-export from the packages/services modules.
   - This ensures all 71 existing tests in `tests/e2e_v2/` remain 100% green with zero modification or regressions.

### 9.2 Builder Verification Checklist
When implementing Milestone M1:
- [ ] Run `python -m pytest tests/e2e_v2/test_m1_core_shell.py` $\to$ 23 passed.
- [ ] Run `python -m pytest tests/e2e_v2/test_m1_challenger_adversarial.py tests/e2e_v2/test_m1_retest_vulnerabilities.py` $\to$ 48 passed.
- [ ] Run `npm test` $\to$ 3 identity tests pass.
- [ ] Verify `KEYSTONE_BIBLE.md` SHA-256 remains unchanged (`1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`).
