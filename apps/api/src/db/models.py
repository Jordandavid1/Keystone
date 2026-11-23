"""
KEYSTONE DeclarativeBase ORM Models (Bible v2 §21, §22, §27, §40–§43; ADR-004 / ADR-005 PR1).
Defines all 27 canonical database tables synchronized with Alembic baseline 0001_baseline_v2.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sa_text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from pgvector.sqlalchemy import Vector


def gen_uuid_str() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# -----------------------------------------------------------------------------
# 1. User (Bible v2 §21)
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user", server_default="user")
    content_mode: Mapped[str] = mapped_column(Text, nullable=False, default="sfw", server_default="sfw")
    age_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    age_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    age_verified_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    is_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_users_content_mode"),
        Index("uq_users_email_lower", func.lower(email), unique=True),
        Index("ix_users_role", "role", postgresql_where=sa_text("role <> 'user'")),
    )

    credit_account: Mapped[Optional["CreditAccount"]] = relationship("CreditAccount", back_populates="user", uselist=False)
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="user")
    personas: Mapped[List["Persona"]] = relationship("Persona", back_populates="user")


# -----------------------------------------------------------------------------
# 2. Subscription (Bible v2 §21)
# -----------------------------------------------------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default="active")
    processor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))


# -----------------------------------------------------------------------------
# 3. ApiKey (Bible v2 §21)
# -----------------------------------------------------------------------------
class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_api_keys_user", "user_id"),
    )


# -----------------------------------------------------------------------------
# 4. Project (Bible v2 §21)
# -----------------------------------------------------------------------------
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_mode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_projects_content_mode"),
        Index("ix_projects_user", "user_id", "created_at"),
    )

    user: Mapped["User"] = relationship("User", back_populates="projects")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="project")


# -----------------------------------------------------------------------------
# 5. Session (Bible v2 §21)
# -----------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_mode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_sessions_content_mode"),
        Index("ix_sessions_user", "user_id", "updated_at"),
    )

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="sessions")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="session")


# -----------------------------------------------------------------------------
# 6. Message (Bible v2 §21)
# -----------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    session_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("role IN ('user','keystone')", name="ck_messages_role"),
        Index("ix_messages_session", "session_id", "created_at"),
    )

    session: Mapped["Session"] = relationship("Session", back_populates="messages")


# -----------------------------------------------------------------------------
# 7. Asset (Bible v2 §21)
# -----------------------------------------------------------------------------
class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    asset_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    c2pa_manifest: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_assets_user", "user_id", "created_at"),
        Index("ix_assets_project", "project_id", "created_at"),
        Index(
            "ix_assets_project_sfw",
            "project_id",
            "created_at",
            postgresql_where=sa_text("mature = FALSE AND deleted_at IS NULL"),
        ),
    )


# -----------------------------------------------------------------------------
# 8. AssetRelationship (Bible v2 §21)
# -----------------------------------------------------------------------------
class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    parent_asset_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("assets.id"), nullable=True)
    child_asset_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("assets.id"), nullable=True)
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    persona_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    persona_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ('source','edit','variation','animation','upscale','reference','selected-final','intermediate','depicts')",
            name="ck_rel_type",
        ),
    )


# -----------------------------------------------------------------------------
# 9. Request (Bible v2 §21)
# -----------------------------------------------------------------------------
class Request(Base):
    __tablename__ = "requests"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=True)
    intent_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_requests_user", "user_id", "created_at"),
    )


# -----------------------------------------------------------------------------
# 10. RequestAsset (Bible v2 §21)
# -----------------------------------------------------------------------------
class RequestAsset(Base):
    __tablename__ = "request_assets"

    request_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("requests.id"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("assets.id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)


# -----------------------------------------------------------------------------
# 11. Job (Bible v2 §21)
# -----------------------------------------------------------------------------
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("projects.id"), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("requests.id"), nullable=True)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    envelope_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), unique=True, nullable=True)
    envelope: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    content_mode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persona_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    outputs: Mapped[List[Any]] = mapped_column(JSONB, nullable=False, default=list, server_default=sa_text("'[]'"))
    failure_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED','VALIDATING','PLANNING','AUTHORIZING','QUEUED','RUNNING','VALIDATING_OUTPUT','RETRY_PENDING','REPLAN_REQUIRED','COMPLETED','FAILED','CANCELLED','REJECTED')",
            name="ck_jobs_status",
        ),
        CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_jobs_content_mode"),
        Index("ix_jobs_user", "user_id", "created_at"),
        Index("ix_jobs_dispatch", "status", "priority", "queued_at"),
        Index("ix_jobs_mode", "content_mode", postgresql_where=sa_text("content_mode IS NOT NULL")),
    )


# -----------------------------------------------------------------------------
# 12. GenerationAttempt (Bible v2 §21)
# -----------------------------------------------------------------------------
class GenerationAttempt(Base):
    __tablename__ = "generation_attempts"

    attempt_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    job_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seed: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    output_asset_ids: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=sa_text("'[]'"))
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    resource_cost: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_attempts_job", "job_id", "started_at"),
        Index("ix_attempts_prompt_hash", "prompt_hash"),
    )


# -----------------------------------------------------------------------------
# 13. AttemptAsset (Bible v2 §21)
# -----------------------------------------------------------------------------
class AttemptAsset(Base):
    __tablename__ = "attempt_assets"

    attempt_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("generation_attempts.attempt_id"), primary_key=True)
    asset_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("assets.id"), primary_key=True)


# -----------------------------------------------------------------------------
# 14. CognitiveRun (Bible v2 §21)
# -----------------------------------------------------------------------------
class CognitiveRun(Base):
    __tablename__ = "cognitive_runs"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    request_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("sessions.id"), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manifest_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    tokens_in: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_cog_runs_request", "request_id"),
    )


# -----------------------------------------------------------------------------
# 15. CompiledPrompt (Bible v2 §21)
# -----------------------------------------------------------------------------
class CompiledPrompt(Base):
    __tablename__ = "compiled_prompts"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    request_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("requests.id"), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    compiler_version: Mapped[str] = mapped_column(Text, nullable=False)
    target_capability: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_provider: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    positive_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False)
    content_mode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_compiled_prompts_content_mode"),
        Index("ix_compiled_prompts_hash", "prompt_hash"),
        Index("ix_compiled_prompts_request", "request_id"),
    )


# -----------------------------------------------------------------------------
# 16. AuthorityDecision (Bible v2 §21)
# -----------------------------------------------------------------------------
class AuthorityDecision(Base):
    __tablename__ = "authority_decisions"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    request_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sanitized_arguments: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    reason_codes: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    policy_bundle_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capability_registry_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    harness_bundle_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_mode: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    floor_verdict: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("decision IN ('approve','deny','replan')", name="ck_authdec_decision"),
        CheckConstraint("floor_verdict IN ('pass','fail','uncertain') OR floor_verdict IS NULL", name="ck_authdec_floor_verdict"),
        Index("ix_authdec_job", "job_id"),
        Index("ix_authdec_request", "request_id"),
    )


# -----------------------------------------------------------------------------
# 17. AuditEvent (Bible v2 §21)
# -----------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_audit_type", "event_type", "created_at"),
        Index("ix_audit_job", "job_id"),
        Index("ix_audit_user", "user_id", "created_at"),
    )


# -----------------------------------------------------------------------------
# 18. HarnessRun (Bible v2 §21)
# -----------------------------------------------------------------------------
class HarnessRun(Base):
    __tablename__ = "harness_runs"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    attempt_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("generation_attempts.attempt_id"), nullable=True)
    harness_id: Mapped[str] = mapped_column(Text, nullable=False)
    harness_version: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    reason_codes: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    runtime_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    resource_cost: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("verdict IN ('pass','warn','fail')", name="ck_harness_verdict"),
        Index("ix_harness_job", "job_id"),
        Index("ix_harness_attempt", "attempt_id", "created_at"),
    )


# -----------------------------------------------------------------------------
# 19. UserFeedback (Bible v2 §21)
# -----------------------------------------------------------------------------
class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    accepted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    regeneration_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    selected_asset_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("assets.id"), nullable=True)
    feedback_tags: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_feedback_job", "job_id"),
    )


# -----------------------------------------------------------------------------
# 20. CreditAccount (Bible v2 §21)
# -----------------------------------------------------------------------------
class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), unique=True, nullable=False)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    user: Mapped["User"] = relationship("User", back_populates="credit_account")


# -----------------------------------------------------------------------------
# 21. CreditLedger (Bible v2 §21, append-only)
# -----------------------------------------------------------------------------
class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("credit_accounts.id"), nullable=False)
    entry_type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    processor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(Text, unique=True, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('topup','hold','settle','release','refund','adjustment')",
            name="ck_credit_ledger_entry_type",
        ),
        Index("ix_ledger_user", "user_id", "created_at"),
        Index("ix_ledger_job", "job_id"),
    )


# -----------------------------------------------------------------------------
# 22. UsageRecord (Bible v2 §21, §27)
# -----------------------------------------------------------------------------
class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("jobs.id"), nullable=True)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gpu_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vram_minutes: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    gpu_seconds: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    evaluator_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    cost_units: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_usage_user", "user_id", "created_at"),
    )


# -----------------------------------------------------------------------------
# 23. ConfigurationBundle (Bible v2 §21)
# -----------------------------------------------------------------------------
class ConfigurationBundle(Base):
    __tablename__ = "configuration_bundles"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_configuration_bundles_name_version"),
    )


# -----------------------------------------------------------------------------
# 24. Persona (Bible v2 §21, §41 — versioned immutable rows)
# -----------------------------------------------------------------------------
class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True, default=1, server_default="1")
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traits: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    backstory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_assets: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=sa_text("'[]'"))
    identity_adapter: Mapped[str] = mapped_column(Text, nullable=False, default="reference_set", server_default="reference_set")
    voice: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    mature: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("identity_adapter IN ('reference_set','ip')", name="ck_personas_identity_adapter"),
        Index("ix_personas_current", "id", unique=True, postgresql_where=sa_text("is_current")),
        Index("ix_personas_user", "user_id", "created_at"),
    )

    user: Mapped["User"] = relationship("User", back_populates="personas")


# -----------------------------------------------------------------------------
# 25. Recipe (Bible v2 §21, §42 — project memory)
# -----------------------------------------------------------------------------
class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False)
    persona_id: Mapped[Optional[str]] = mapped_column(sa.UUID(as_uuid=False), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    envelope: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    compiled_prompt: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    seed: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    fabric_versions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scores: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa_text("'{}'"))
    content_mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="candidate", server_default="candidate")
    promotion_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_recipes_content_mode"),
        CheckConstraint("status IN ('candidate','promoted','retired')", name="ck_recipes_status"),
        Index("ix_recipes_scope", "user_id", "project_id", "created_at"),
        Index("ix_recipes_promoted", "project_id", postgresql_where=sa_text("status = 'promoted'")),
        Index("ix_recipes_persona", "persona_id", postgresql_where=sa_text("persona_id IS NOT NULL")),
    )

    embedding: Mapped[Optional["RecipeEmbedding"]] = relationship("RecipeEmbedding", back_populates="recipe", uselist=False, cascade="all, delete-orphan")


# -----------------------------------------------------------------------------
# 26. RecipeEmbedding (Bible v2 §21, §42.3 — Matryoshka 1024-dim embedding)
# -----------------------------------------------------------------------------
class RecipeEmbedding(Base):
    __tablename__ = "recipe_embeddings"

    recipe_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True)
    embedding: Mapped[List[float]] = mapped_column(Vector(1024), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index(
            "ix_recipe_emb_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="embedding")


# -----------------------------------------------------------------------------
# 27. StyleRule (Bible v2 §21, §42.2 — project style constraints)
# -----------------------------------------------------------------------------
class StyleRule(Base):
    __tablename__ = "style_rules"

    id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), primary_key=True, default=gen_uuid_str)
    user_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(sa.UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Numeric, nullable=False, default=1.0, server_default="1.0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), server_default=sa_text("now()"))

    __table_args__ = (
        Index("ix_style_rules_active", "project_id", postgresql_where=sa_text("active")),
    )
