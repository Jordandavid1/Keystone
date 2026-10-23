# Milestone M1 Technical Investigation & Strategy: F05 & F06

> **Agent**: `explorer_m1_1`  
> **Milestone**: M1 (Wave 1: Creative Tool Fabric & Core Shell)  
> **Features**: F05 (Relational Data Models & Repositories) & F06 (Authentication & Tenant Isolation)  
> **Status**: Complete Investigation & Implementation Blueprint  

---

## 1. Observation

Direct observations from repository inspection, migration scripts, canonical specifications, and runtime environment:

### 1.1 Existing Migrations & PostgreSQL Schema (23 Tables)
- **`infrastructure/migrations/versions/0001_core.sql`**:
  - Defines base 12 tables: `users`, `projects`, `sessions`, `messages`, `assets`, `requests`, `cognitive_runs`, `authority_decisions`, `jobs`, `compiled_prompts`, `harness_runs`, `audit_events`.
  - Uses `UUID PRIMARY KEY DEFAULT gen_random_uuid()` (requires `pgcrypto` or native PostgreSQL 13+).
  - Uses `TIMESTAMPTZ NOT NULL DEFAULT now()` for created/updated timestamps.
  - Foreign key constraints:
    - `projects.user_id REFERENCES users(id)`
    - `sessions.user_id REFERENCES users(id)`, `sessions.project_id REFERENCES projects(id)`
    - `messages.session_id REFERENCES sessions(id) ON DELETE CASCADE`
    - `assets.owner_id REFERENCES users(id)`, `assets.project_id REFERENCES projects(id)`, `UNIQUE(storage_provider, storage_key)`
    - `requests.user_id REFERENCES users(id)`, `requests.session_id REFERENCES sessions(id)`, `requests.message_id REFERENCES messages(id)`
    - `jobs.request_id REFERENCES requests(id)`, `jobs.authority_decision_id REFERENCES authority_decisions(id)`, `jobs.user_id REFERENCES users(id)`
- **`infrastructure/migrations/versions/0002_keystone_full_schema.sql`**:
  - Defines the remaining 11 tables completing the 23-table specification (Bible §21):
    1. `subscriptions` (`id`, `user_id`, `plan_id`, `status`, `stripe_customer_id`, `stripe_subscription_id`, `current_period_start`, `current_period_end`, `cancel_at_period_end`, `canceled_at`, `metadata`, `created_at`, `updated_at`)
    2. `api_keys` (`id`, `user_id`, `name`, `key_hash`, `key_prefix`, `scopes`, `status`, `last_used_at`, `expires_at`, `created_at`, `updated_at`)
    3. `credit_accounts` (`id`, `user_id`, `balance`, `held_balance`, `currency`, `status`, `created_at`, `updated_at`)
    4. `credit_ledger` (`id`, `account_id`, `transaction_type`, `amount`, `balance_after`, `held_balance_after`, `reference_id`, `reference_type`, `idempotency_key`, `description`, `metadata`, `created_at`) with trigger `trg_credit_ledger_immutable` preventing UPDATE/DELETE
    5. `request_assets` (`id`, `request_id`, `asset_id`, `role`, `metadata`, `created_at`)
    6. `generation_attempts` (`id`, `job_id`, `attempt_number`, `provider_id`, `capability_id`, `prompt_hash`, `workflow_version`, `started_at`, `completed_at`, `success`, `metrics`, `failure_code`, `error_detail`, `created_at`)
    7. `attempt_assets` (`id`, `attempt_id`, `asset_id`, `role`, `created_at`)
    8. `user_feedback` (`id`, `job_id`, `user_id`, `rating`, `accepted`, `regeneration_requested`, `selected_asset_id`, `feedback_tags`, `comment`, `metadata`, `created_at`)
    9. `usage_records` (`id`, `user_id`, `job_id`, `capability_id`, `provider_id`, `quantity`, `unit`, `credits_billed`, `metadata`, `recorded_at`, `created_at`)
    10. `configuration_bundles` (`id`, `bundle_type`, `name`, `version`, `checksum`, `payload`, `is_active`, `created_by`, `created_at`, `updated_at`)
    11. `asset_relationships` (`id`, `parent_asset_id`, `child_asset_id`, `job_id`, `relationship_type`, `metadata`, `created_at`)
  - Added additive foreign key indexes for `projects(user_id)`, `sessions(user_id)`, `sessions(project_id)`, `messages(session_id)`, `assets(owner_id)`, `assets(project_id)`, `requests(user_id)`, `jobs(user_id)`, `jobs(state)`, etc.

### 1.2 Python Runtime Environment & Dependencies
- System Python: Python 3.14 (`C:\Python314\python.exe`).
- Verified installed packages via Python execution:
  - `sqlalchemy`: 2.1.5 (Installed)
  - `aiosqlite`: Installed & available
  - `sqlite3`: Installed & available
  - `fastapi`: 0.146.0 (Installed)
  - `pydantic`: 2.14.1 (Installed)
  - `cryptography`: 50.0.2 (Installed)
  - `pytest`: 9.1.1 (Installed)
  - `asyncpg`: NOT installed in the host environment.
  - `psycopg2`, `jwt`, `passlib`, `bcrypt`: NOT installed in the host environment.
- Python Standard Library crypto modules:
  - `hashlib`: Available
  - `secrets`: Available
  - `hmac`: Available
- Cryptography Hazmat modules:
  - `cryptography.hazmat.primitives.ciphers.aead.AESGCM`: Available
  - `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC`: Available

### 1.3 Pre-built Baseline Preservation & Test Invariants
- `KEYSTONE_BIBLE.md` SHA-256 verification:
  - Computed: `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788` (Byte-identical, 0 diffs).
- Baseline identity test: `npm test` -> 3/3 passing.
- Pre-built E2E test suite: `node --test tests/e2e/*.test.js` -> 194/194 passing.
- Pre-built files `apps/api/src/main.py` and `apps/api/src/intelligence_router.py` remain completely untouched.

---

## 2. Logic Chain

From the observations, the following architectural inferences and design choices are established:

### 2.1 Database Abstraction & Multi-Dialect Async Engine
1. **Observation**: PostgreSQL is the durable production store per Bible §21, but `asyncpg` is not installed on the developer/host machine, whereas `SQLAlchemy 2.1.5` and `aiosqlite` are installed and operational.
2. **Inference**: The database engine in `apps/api/src/db/session.py` must support dynamic dialect resolution:
   - When `DATABASE_URL` is configured with `postgresql://` or `postgresql+asyncpg://`, it initializes an async PostgreSQL connection pool.
   - When `DATABASE_URL` is unset or points to SQLite, it gracefully defaults to `sqlite+aiosqlite:///./keystone.db` (or `:memory:` during automated tests).
3. **Inference for Data Types**: Primary keys must use `UUID(as_uuid=True)` in SQLAlchemy, which transparently maps to native `UUID` on PostgreSQL and `CHAR(36)` / `TEXT` on SQLite. JSON columns must use `JSON` (which maps to `JSONB` on PostgreSQL and JSON text on SQLite). Timestamps must use `DateTime(timezone=True)`. This gives 100% dialect portability without any breaking changes between local dev/CI and Google Cloud SQL.

### 2.2 SQLAlchemy 2.0 Modern Declarative Mappings
1. **Observation**: `0001_core.sql` and `0002_keystone_full_schema.sql` define 23 interdependent tables. Foreign keys link `jobs` to `requests`, `authority_decisions`, and `users`; `assets` to `users` and `projects`; `sessions` to `users` and `projects`.
2. **Inference**: To avoid SQLAlchemy mapping resolution errors (such as `NoReferencedTableError` or broken bidirectional relationships), the ORM module must declare the complete 23-table schema using modern SQLAlchemy 2.0 `DeclarativeBase` with typed `Mapped[...]` and `mapped_column(...)`.
3. **Core Entities Scope for M1**:
   - `User`: Primary tenant entity. Links to projects, sessions, assets, jobs, API keys, and credit accounts.
   - `Project`: Scoped to `user_id`. Container for sessions and assets.
   - `Session`: Scoped to `user_id`, optional `project_id`.
   - `Message`: Belongs to `session_id`, roles restricted to `user` and `keystone`.
   - `Asset`: Scoped to `owner_id` (`user_id`). Storage key scoped under tenant prefix. Soft-delete support via `deleted_at`.
   - `Job`: Scoped to `user_id`, tracks 13 states (`created`, `validating`, `planning`, `authorizing`, `queued`, `running`, `validating_output`, `retry_pending`, `replan_required`, `completed`, `failed`, `cancelled`, `rejected`).
   - Supporting M1 Entities: `ApiKey`, `Request`, `AuthorityDecision`, `CreditAccount`, `CreditLedger`, `AssetRelationship`.

### 2.3 Strict Tenant Isolation via Repository Injection
1. **Observation**: Bible §21 and §28 mandate: *"Tenant ownership checked for every user-facing query"*, and *"Enforce strict tenant isolation: queries must be scoped to tenant/user_id, preventing cross-tenant leakage."*
2. **Vulnerability to Avoid**: If routes perform raw queries like `db.get(Project, project_id)`, any authenticated user could read or mutate another user's project by guessing its UUID.
3. **Solution — Tenant Scoped Repository Pattern**:
   - Every domain repository (`ProjectRepository`, `SessionRepository`, `AssetRepository`, `JobRepository`) inherits from `BaseRepository` and requires `(session: AsyncSession, tenant_id: UUID)` in its constructor.
   - Every lookup method automatically binds `.where(Model.user_id == self.tenant_id)` (or `Model.owner_id == self.tenant_id` for assets).
   - If an entity exists in the database but belongs to another tenant, the repository returns `None` (yielding 404 Not Found), completely shielding tenant existence and preventing data leakage.
   - All write operations (`create_*`) force `user_id = self.tenant_id`, preventing any caller from spoofing ownership.

### 2.4 Cryptographic Authentication Architecture
1. **Observation**: `jwt`, `passlib`, and `bcrypt` are not installed in the Python runtime, but `cryptography 50.0.2`, `secrets`, `hashlib`, and `hmac` are available.
2. **Password Hashing Design**:
   - Use `hashlib.pbkdf2_hmac` or `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC` with `SHA256`, 600,000 iterations (OWASP benchmark), and 16 bytes of cryptographically random salt.
   - Constant-time verification using `secrets.compare_digest`.
   - Format: `pbkdf2_sha256$600000$<salt_hex>$<hash_hex>`.
3. **Session & Bearer Token Design**:
   - Stateless, cryptographically signed Bearer tokens using HMAC-SHA256:
     - Header: `{"alg": "HS256", "typ": "JWT"}` (base64url).
     - Payload: `{"sub": user_id, "email": email, "type": "access", "exp": timestamp, "jti": nonce}` (base64url).
     - Signature: `HMAC-SHA256(base64_header + "." + base64_payload, KEYSTONE_SECRET_KEY)` (base64url).
   - Fully compliant with standard RFC 7519 / RFC 6750 Bearer authentication without requiring uninstalled third-party libraries!
   - Refresh tokens use `type: "refresh"` with 30-day expiration and support rotation on `/v1/auth/refresh`.
4. **API Key Authentication Design**:
   - Format: `ks_live_<prefix>_<secret>` (e.g. `ks_live_a8f9c1b2_...`).
   - Prefix (8 chars) stored in `api_keys.key_prefix` for listing and display.
   - Secret (32 random bytes in hex) is hashed with SHA-256 upon generation.
   - `api_keys.key_hash = sha256(raw_key)`. Raw key is returned **once** to caller and never persisted.
   - Authentication extracts `X-API-Key` header, computes SHA-256, looks up active key in database, verifies `status == 'active'` and `expires_at > now()`, updates `last_used_at`, and resolves `tenant_id = api_key.user_id`.

### 2.5 Additive Mounting in `apps/api/src/server.py`
1. **Observation**: `apps/api/src/main.py` is pre-built and immutable. `apps/api/src/server.py` was introduced in M0 specifically to mount routers additively.
2. **Inference**: M1 will introduce 5 domain routers under `apps/api/src/routers/`:
   - `auth.py`: `/v1/auth/*`
   - `projects.py`: `/v1/projects/*`
   - `sessions.py`: `/v1/sessions/*`
   - `assets.py`: `/v1/assets/*`
   - `jobs.py`: `/v1/jobs/*`
3. These routers are mounted onto `app` in `apps/api/src/server.py`. Baseline `main.py` remains 100% byte-identical.

---

## 3. Caveats & Risks

1. **Host Environment Python Driver (`asyncpg`)**:
   - `asyncpg` is the production driver for PostgreSQL on Cloud SQL. However, it is not currently installed in the host's global Python 3.14 environment.
   - *Mitigation*: The database session module must dynamically detect whether `DATABASE_URL` uses PostgreSQL or SQLite. When running locally without PostgreSQL credentials, it transparently defaults to `sqlite+aiosqlite`, enabling local unit and integration tests to pass 100% without installing compiled C-extensions on Windows. For Cloud Run / production deployment, `asyncpg` will be specified in containerized requirements.
2. **Database Engine Immutability Triggers**:
   - Migration 0002 created `keystone_credit_ledger_prevent_modification` trigger on PostgreSQL. On SQLite, database triggers must be mirrored or mocked if credit ledger immutability is tested against SQLite.
3. **Pre-Built File Immutability**:
   - All 69 pre-built files (including `main.py`, `intelligence_router.py`, `packages/prompt-engine/src/*`) must not have a single line changed. All M1 work must strictly reside in newly created files or additive extensions to `apps/api/src/server.py`.

---

## 4. Recommended Implementation Strategy

### 4.1 File Tree to Create in M1

```
apps/api/src/
├── db/
│   ├── __init__.py                     # Package exports
│   ├── session.py                      # Multi-dialect async engine & get_db dependency
│   ├── models.py                       # Complete 23-table SQLAlchemy 2.0 ORM models
│   └── repositories/
│       ├── __init__.py                 # Repository package exports
│       ├── base.py                     # Tenant-isolated BaseRepository[T]
│       ├── users.py                    # UserRepository (auth, creation, lookup)
│       ├── projects.py                 # ProjectRepository (tenant-scoped CRUD)
│       ├── sessions.py                 # SessionRepository & MessageRepository
│       ├── assets.py                   # AssetRepository (tenant-scoped, storage keys)
│       ├── jobs.py                     # JobRepository (13-state machine tracking)
│       └── api_keys.py                 # ApiKeyRepository (hash verification, scopes)
├── auth/
│   ├── __init__.py                     # Auth package exports
│   ├── security.py                     # PBKDF2 hashing, HMAC tokens, API key hashing
│   └── dependencies.py                 # FastAPI get_current_user & TenantContext
└── routers/
    ├── __init__.py                     # Router package exports
    ├── auth.py                         # /v1/auth (register, login, refresh, api-keys)
    ├── projects.py                     # /v1/projects CRUD
    ├── sessions.py                     # /v1/sessions & messages
    ├── assets.py                       # /v1/assets upload, lookup, soft-delete
    └── jobs.py                         # /v1/jobs lifecycle, cancel, retry
```

---

### 4.2 Detailed Specifications & Class Signatures

#### A. Database Engine & Session Management (`apps/api/src/db/session.py`)
```python
from collections.abc import AsyncGenerator
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./keystone.db")

# Normalize postgresql:// to postgresql+asyncpg:// if provided
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine_kwargs = {"echo": False, "future": True}
if "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "20"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    engine_kwargs["pool_recycle"] = 1800

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

#### B. SQLAlchemy 2.0 ORM Models (`apps/api/src/db/models.py`)
```python
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Double, ForeignKey,
    Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator, CHAR

# Dialect-agnostic UUID column
class UniversalUUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

class Base(DeclarativeBase):
    pass

# 1. users
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="owner", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    credit_account = relationship("CreditAccount", back_populates="user", uselist=False)

# 2. projects
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="projects")
    sessions = relationship("Session", back_populates="project")
    assets = relationship("Asset", back_populates="project")

# 3. sessions
class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UniversalUUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="sessions")
    project = relationship("Project", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")

# 4. messages
class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'keystone')", name="check_message_role"),)
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())

    session = relationship("Session", back_populates="messages")

# 5. assets
class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("storage_provider", "storage_key", name="uq_asset_storage"),)
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UniversalUUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_provider: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="available")
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    owner = relationship("User", back_populates="assets")
    project = relationship("Project", back_populates="assets")

# 6. jobs
class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('created', 'validating', 'planning', 'authorizing', 'queued', 'running', 'validating_output', 'retry_pending', 'replan_required', 'completed', 'failed', 'cancelled', 'rejected')",
            name="check_job_state"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("requests.id"), nullable=False, index=True)
    authority_decision_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("authority_decisions.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)
    workflow_id: Mapped[str] = mapped_column(String, nullable=False)
    workflow_version: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    user = relationship("User", back_populates="jobs")
    request = relationship("Request", back_populates="jobs")
    authority_decision = relationship("AuthorityDecision")
    attempts = relationship("GenerationAttempt", back_populates="job", cascade="all, delete-orphan")

# 7. api_keys
class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    key_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String, nullable=False)
    scopes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=lambda: ["*"])
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="api_keys")

# 8. requests, cognitive_runs, authority_decisions, credit_accounts, credit_ledger, asset_relationships
# ... defined to complete all 23 tables matching migration 0002 ...
```

---

#### C. Tenant-Isolated Base & Concrete Repositories (`apps/api/src/db/repositories/`)

**BaseRepository (`apps/api/src/db/repositories/base.py`)**:
```python
import uuid
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.db.models import Base

T = TypeVar("T", bound=Base)

class TenantScopedRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: Type[T], tenant_id: uuid.UUID, user_column_name: str = "user_id"):
        self.session = session
        self.model = model
        self.tenant_id = tenant_id
        self.user_col = getattr(model, user_column_name)

    async def get_by_id(self, entity_id: uuid.UUID) -> Optional[T]:
        stmt = select(self.model).where(
            self.model.id == entity_id,
            self.user_col == self.tenant_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 50, offset: int = 0) -> List[T]:
        stmt = (
            select(self.model)
            .where(self.user_col == self.tenant_id)
            .limit(limit)
            .offset(offset)
            .order_by(self.model.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_id(self, entity_id: uuid.UUID) -> bool:
        stmt = delete(self.model).where(
            self.model.id == entity_id,
            self.user_col == self.tenant_id
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
```

**ProjectRepository (`apps/api/src/db/repositories/projects.py`)**:
```python
import uuid
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.db.models import Project
from apps.api.src.db.repositories.base import TenantScopedRepository

class ProjectRepository(TenantScopedRepository[Project]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(session=session, model=Project, tenant_id=tenant_id, user_column_name="user_id")

    async def create_project(self, name: str, description: Optional[str] = None) -> Project:
        project = Project(
            id=uuid.uuid4(),
            user_id=self.tenant_id,
            name=name,
            description=description,
            status="active"
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def update_project(
        self,
        project_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[Project]:
        project = await self.get_by_id(project_id)
        if not project:
            return None
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if status is not None:
            project.status = status
        await self.session.flush()
        return project
```

**JobRepository (`apps/api/src/db/repositories/jobs.py`)**:
```python
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.db.models import Job
from apps.api.src.db.repositories.base import TenantScopedRepository

ALLOWED_TRANSITIONS = {
    "created": {"validating", "rejected", "cancelled"},
    "validating": {"planning", "failed", "cancelled"},
    "planning": {"authorizing", "replan_required", "failed", "cancelled"},
    "authorizing": {"queued", "rejected", "cancelled"},
    "queued": {"running", "cancelled"},
    "running": {"validating_output", "failed", "cancelled"},
    "validating_output": {"completed", "retry_pending", "replan_required", "failed"},
    "retry_pending": {"queued", "failed", "cancelled"},
    "replan_required": {"planning", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
    "rejected": set()
}

class JobRepository(TenantScopedRepository[Job]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(session=session, model=Job, tenant_id=tenant_id, user_column_name="user_id")

    async def transition_state(
        self,
        job_id: uuid.UUID,
        target_state: str,
        error_code: Optional[str] = None,
        error_detail: Optional[Dict[str, Any]] = None
    ) -> Job:
        job = await self.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found for tenant")
        
        allowed = ALLOWED_TRANSITIONS.get(job.state, set())
        if target_state not in allowed:
            raise ValueError(f"Invalid job state transition from {job.state} to {target_state}")
        
        job.state = target_state
        if error_code:
            job.error_code = error_code
        if error_detail:
            job.error_detail = error_detail
        await self.session.flush()
        return job
```

---

#### D. Security & Authentication Architecture (`apps/api/src/auth/`)

**Security Module (`apps/api/src/auth/security.py`)**:
```python
import os
import hmac
import hashlib
import secrets
import json
import base64
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, Any

SECRET_KEY = os.getenv("KEYSTONE_SECRET_KEY", "keystone-dev-secret-key-change-in-production-min32chars")
PBKDF2_ITERATIONS = 600000

def hash_password(password: str) -> str:
    """NIST SP 800-63B compliant password hashing using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of PBKDF2 password hashes."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_dk = bytes.fromhex(parts[3])
        actual_dk = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)

def create_access_token(user_id: uuid.UUID, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Issues HMAC-SHA256 Bearer access token."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=60))
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16)
    }
    raw_header = _b64url_encode(json.dumps(header).encode("utf-8"))
    raw_payload = _b64url_encode(json.dumps(payload).encode("utf-8"))
    signing_input = f"{raw_header}.{raw_payload}".encode("utf-8")
    signature = _b64url_encode(hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{raw_header}.{raw_payload}.{signature}"

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Validates signature and expiration of Bearer token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        raw_header, raw_payload, signature = parts
        signing_input = f"{raw_header}.{raw_payload}".encode("utf-8")
        expected_sig = _b64url_encode(hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest())
        if not secrets.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(_b64url_decode(raw_payload).decode("utf-8"))
        if datetime.now(timezone.utc).timestamp() > payload.get("exp", 0):
            return None
        return payload
    except Exception:
        return None

def generate_api_key() -> Tuple[str, str, str]:
    """Generates (raw_key, key_prefix, key_hash). Raw key never stored."""
    prefix = secrets.token_hex(4)
    secret = secrets.token_hex(32)
    raw_key = f"ks_live_{prefix}_{secret}"
    key_prefix = f"ks_live_{prefix}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return raw_key, key_prefix, key_hash

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
```

**FastAPI Auth Dependency (`apps/api/src/auth/dependencies.py`)**:
```python
import uuid
from typing import Optional, List
from pydantic import BaseModel
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.db.session import get_db
from apps.api.src.db.models import User, ApiKey
from apps.api.src.auth.security import decode_token, hash_api_key
from sqlalchemy import select

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class AuthenticatedUser(BaseModel):
    id: uuid.UUID
    email: str
    auth_type: str  # "bearer" or "api_key"
    scopes: List[str] = ["*"]

async def get_current_user(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db)
) -> AuthenticatedUser:
    if bearer and bearer.credentials:
        payload = decode_token(bearer.credentials)
        if not payload or payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
        user_id = uuid.UUID(payload["sub"])
        stmt = select(User).where(User.id == user_id, User.status == "active")
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")
        return AuthenticatedUser(id=user.id, email=user.email, auth_type="bearer", scopes=["*"])
    
    if api_key:
        khash = hash_api_key(api_key)
        stmt = select(ApiKey, User).join(User, ApiKey.user_id == User.id).where(
            ApiKey.key_hash == khash,
            ApiKey.status == "active",
            User.status == "active"
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        db_key, user = row
        return AuthenticatedUser(id=user.id, email=user.email, auth_type="api_key", scopes=db_key.scopes)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication credentials required")
```

---

#### E. Additive Mounting in `apps/api/src/server.py`
Mount all domain routers in `apps/api/src/server.py`:
```python
# Routers mounted additively:
from apps.api.src.routers.auth import router as auth_router
from apps.api.src.routers.projects import router as projects_router
from apps.api.src.routers.sessions import router as sessions_router
from apps.api.src.routers.assets import router as assets_router
from apps.api.src.routers.jobs import router as jobs_router

app.include_router(auth_router, prefix="/v1/auth", tags=["Authentication"])
app.include_router(projects_router, prefix="/v1/projects", tags=["Projects"])
app.include_router(sessions_router, prefix="/v1/sessions", tags=["Sessions"])
app.include_router(assets_router, prefix="/v1/assets", tags=["Assets"])
app.include_router(jobs_router, prefix="/v1/jobs", tags=["Jobs"])
```

---

## 5. Verification Method

To independently verify the implementation once applied by the implementer agent:

1. **Pre-built & Invariant Non-Regression**:
   ```bash
   npm test
   node --test tests/e2e/*.test.js
   ```
   Both suites must pass 100% cleanly (3 tests and 194 tests respectively) with zero modifications to any pre-built files.

2. **Schema & Model Conformance Verification**:
   - Verify all 23 tables and relations instantiate in SQLAlchemy using SQLite in-memory:
   ```bash
   python -c "import asyncio; from apps.api.src.db.models import Base; from apps.api.src.db.session import engine; asyncio.run(engine.begin().then(lambda c: c.run_sync(Base.metadata.create_all)))"
   ```

3. **Tenant Isolation Verification Test**:
   - Register User A and User B.
   - User A creates Project A (`POST /v1/projects`).
   - User B attempts to access Project A (`GET /v1/projects/{project_a_id}`).
   - Verify User B receives `404 Not Found`, proving zero cross-tenant leakage.

4. **API Key Authentication Verification Test**:
   - Create API Key for User A via `POST /v1/auth/api-keys`.
   - Verify raw key is returned once and starts with `ks_live_`.
   - Send authenticated request with `X-API-Key: ks_live_...` to `GET /v1/projects`.
   - Verify 200 OK with User A's projects.
   - Send modified key; verify 401 Unauthorized.

5. **Job State Machine Transition Verification**:
   - Create job in state `created`.
   - Transition `created` -> `validating` -> `planning` -> `authorizing` -> `queued` -> `running`.
   - Attempt invalid transition `running` -> `created` and verify rejection with validation error.

6. **Invalidation Conditions**:
   - Any modification to `apps/api/src/main.py` or pre-built tests invalidates compliance.
   - Any query returning another user's project/asset invalidates tenant isolation.
