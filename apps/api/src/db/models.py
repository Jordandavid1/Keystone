"""
KEYSTONE DeclarativeBase ORM Models
Defines all 23 database tables matching migrations 0001_core.sql and 0002_keystone_full_schema.sql.
Compatible with SQLite (local development/tests) and PostgreSQL (production).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, JSON, TypeDecorator


class UniversalUUID(TypeDecorator):
    """
    Cross-dialect UUID type.
    Stores UUID as a 36-character string in SQLite and handles UUID conversions.
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
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        return str(value)


def gen_uuid_str() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base class for all Keystone entities."""
    pass


# -----------------------------------------------------------------------------
# 1. User
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# 2. Project
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# 3. Session
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# 4. Message
# -----------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    session_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # 'user', 'keystone'
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")


# -----------------------------------------------------------------------------
# 5. Asset
# -----------------------------------------------------------------------------
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    owner_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
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

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="assets")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="assets")


# -----------------------------------------------------------------------------
# 6. Request
# -----------------------------------------------------------------------------
class Request(Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    message_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    request_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferences: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# -----------------------------------------------------------------------------
# 7. CognitiveRun
# -----------------------------------------------------------------------------
class CognitiveRun(Base):
    __tablename__ = "cognitive_runs"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    request_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_action: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# -----------------------------------------------------------------------------
# 8. AuthorityDecision
# -----------------------------------------------------------------------------
class AuthorityDecision(Base):
    __tablename__ = "authority_decisions"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    request_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)
    cognitive_run_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("cognitive_runs.id", ondelete="SET NULL"), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)  # 'approve', 'deny', 'replan'
    capability_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sanitized_arguments: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reason_codes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    policy_bundle_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    harness_bundle_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


# -----------------------------------------------------------------------------
# 9. Job
# -----------------------------------------------------------------------------
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

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")
    generation_attempts: Mapped[List["GenerationAttempt"]] = relationship("GenerationAttempt", back_populates="job", cascade="all, delete-orphan")


# -----------------------------------------------------------------------------
# 10. CompiledPrompt
# -----------------------------------------------------------------------------
class CompiledPrompt(Base):
    __tablename__ = "compiled_prompts"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    request_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    compiler_id: Mapped[str] = mapped_column(String(128), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    positive_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provenance: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


# -----------------------------------------------------------------------------
# 11. HarnessRun
# -----------------------------------------------------------------------------
class HarnessRun(Base):
    __tablename__ = "harness_runs"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    request_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("requests.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    harness_id: Mapped[str] = mapped_column(String(128), nullable=False)
    harness_version: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)  # 'pass', 'warn', 'fail'
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason_codes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


# -----------------------------------------------------------------------------
# 12. AuditEvent
# -----------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, nullable=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


# -----------------------------------------------------------------------------
# 13. Subscription
# -----------------------------------------------------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


# -----------------------------------------------------------------------------
# 14. ApiKey
# -----------------------------------------------------------------------------
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    scopes: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=lambda: ["*"])
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")


# -----------------------------------------------------------------------------
# 15. CreditAccount
# -----------------------------------------------------------------------------
class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    held_balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(32), nullable=False, default="credits")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="credit_account")
    ledger_entries: Mapped[List["CreditLedger"]] = relationship("CreditLedger", back_populates="account")


# -----------------------------------------------------------------------------
# 16. CreditLedger
# -----------------------------------------------------------------------------
class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    account_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("credit_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'DEPOSIT', 'HOLD', 'SETTLEMENT', 'RELEASE', 'REFUND'
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    held_balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)

    # Relationships
    account: Mapped["CreditAccount"] = relationship("CreditAccount", back_populates="ledger_entries")


# -----------------------------------------------------------------------------
# 17. RequestAsset
# -----------------------------------------------------------------------------
class RequestAsset(Base):
    __tablename__ = "request_assets"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    request_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="input")
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        UniqueConstraint("request_id", "asset_id", "role", name="uq_request_assets_req_ast_role"),
    )


# -----------------------------------------------------------------------------
# 18. GenerationAttempt
# -----------------------------------------------------------------------------
class GenerationAttempt(Base):
    __tablename__ = "generation_attempts"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    job_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    failure_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_generation_attempts_job_attempt"),
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="generation_attempts")


# -----------------------------------------------------------------------------
# 19. AttemptAsset
# -----------------------------------------------------------------------------
class AttemptAsset(Base):
    __tablename__ = "attempt_assets"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    attempt_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("generation_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="output")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    __table_args__ = (
        UniqueConstraint("attempt_id", "asset_id", name="uq_attempt_assets_att_ast"),
    )


# -----------------------------------------------------------------------------
# 20. UserFeedback
# -----------------------------------------------------------------------------
class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    job_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accepted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    regeneration_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selected_asset_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    feedback_tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)


# -----------------------------------------------------------------------------
# 21. UsageRecord
# -----------------------------------------------------------------------------
class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    credits_billed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


# -----------------------------------------------------------------------------
# 22. ConfigurationBundle
# -----------------------------------------------------------------------------
class ConfigurationBundle(Base):
    __tablename__ = "configuration_bundles"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    bundle_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("bundle_type", "version", name="uq_config_bundles_type_version"),
    )


# -----------------------------------------------------------------------------
# 23. AssetRelationship
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# 24. Persona
# -----------------------------------------------------------------------------
class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(UniversalUUID, primary_key=True, default=gen_uuid_str)
    owner_id: Mapped[str] = mapped_column(UniversalUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_asset_id: Mapped[Optional[str]] = mapped_column(UniversalUUID, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    voice_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default="21m00Tcm4TlvDq8ikWAM")
    voice_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, default="Rachel (American Calm)")
    voice_settings: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    personality_traits: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
