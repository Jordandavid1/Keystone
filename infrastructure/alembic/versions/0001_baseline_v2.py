"""0001_baseline_v2

Revision ID: 0001_baseline_v2
Revises: None
Create Date: 2026-11-23 04:55:00

Complete normative baseline migration for Keystone Bible v2 establishing all 27 tables,
indexes, triggers, and pgvector support per ADR-004 and ADR-005.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "0001_baseline_v2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ PREAMBLE ============
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))

    # ============ IDENTITY ============
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
        sa.Column("content_mode", sa.Text(), nullable=False, server_default="sfw"),
        sa.Column("age_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("age_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("age_verified_method", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_users_content_mode"),
    )
    op.execute(sa.text("CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));"))
    op.execute(sa.text("CREATE INDEX ix_users_role ON users (role) WHERE role <> 'user';"))

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("processor", sa.Text(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("key_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_api_keys_user", "api_keys", ["user_id"])

    # ============ WORKSPACE ============
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content_mode", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_projects_content_mode"),
    )
    op.create_index("ix_projects_user", "projects", ["user_id", "created_at"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content_mode", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_sessions_content_mode"),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("session_id", sa.UUID(as_uuid=False), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('user','keystone')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_session", "messages", ["session_id", "created_at"])

    # ============ ASSETS & LINEAGE ============
    op.create_table(
        "assets",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("mature", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("c2pa_manifest", postgresql.JSONB(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_assets_user", "assets", ["user_id", "created_at"])
    op.create_index("ix_assets_project", "assets", ["project_id", "created_at"])
    op.execute(sa.text("""
        CREATE INDEX ix_assets_project_sfw ON assets (project_id, created_at)
        WHERE mature = FALSE AND deleted_at IS NULL;
    """))

    op.create_table(
        "asset_relationships",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("parent_asset_id", sa.UUID(as_uuid=False), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("child_asset_id", sa.UUID(as_uuid=False), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("persona_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("persona_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "relationship_type IN ('source','edit','variation','animation','upscale','reference','selected-final','intermediate','depicts')",
            name="ck_rel_type"
        ),
    )

    op.create_table(
        "requests",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("session_id", sa.UUID(as_uuid=False), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("intent_hint", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_requests_user", "requests", ["user_id", "created_at"])

    op.create_table(
        "request_assets",
        sa.Column("request_id", sa.UUID(as_uuid=False), sa.ForeignKey("requests.id"), primary_key=True),
        sa.Column("asset_id", sa.UUID(as_uuid=False), sa.ForeignKey("assets.id"), primary_key=True),
        sa.Column("role", sa.Text(), primary_key=True),
    )

    # ============ JOBS & ATTEMPTS ============
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("request_id", sa.UUID(as_uuid=False), sa.ForeignKey("requests.id"), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("workflow_id", sa.Text(), nullable=True),
        sa.Column("workflow_version", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("envelope_id", sa.UUID(as_uuid=False), unique=True, nullable=True),
        sa.Column("envelope", postgresql.JSONB(), nullable=True),
        sa.Column("content_mode", sa.Text(), nullable=True),
        sa.Column("persona_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("outputs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('CREATED','VALIDATING','PLANNING','AUTHORIZING','QUEUED','RUNNING','VALIDATING_OUTPUT','RETRY_PENDING','REPLAN_REQUIRED','COMPLETED','FAILED','CANCELLED','REJECTED')",
            name="ck_jobs_status"
        ),
        sa.CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_jobs_content_mode"),
    )
    op.create_index("ix_jobs_user", "jobs", ["user_id", "created_at"])
    op.create_index("ix_jobs_dispatch", "jobs", ["status", "priority", "queued_at"])
    op.execute(sa.text("CREATE INDEX ix_jobs_mode ON jobs (content_mode) WHERE content_mode IS NOT NULL;"))

    # Foreign key for asset_relationships.job_id
    op.create_foreign_key("fk_rel_job", "asset_relationships", "jobs", ["job_id"], ["id"])

    op.create_table(
        "generation_attempts",
        sa.Column("attempt_id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("prompt_hash", sa.Text(), nullable=True),
        sa.Column("workflow_version", sa.Text(), nullable=True),
        sa.Column("seed", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("output_asset_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("resource_cost", postgresql.JSONB(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
    )
    op.create_index("ix_attempts_job", "generation_attempts", ["job_id", "started_at"])
    op.create_index("ix_attempts_prompt_hash", "generation_attempts", ["prompt_hash"])

    op.create_table(
        "attempt_assets",
        sa.Column("attempt_id", sa.UUID(as_uuid=False), sa.ForeignKey("generation_attempts.attempt_id"), primary_key=True),
        sa.Column("asset_id", sa.UUID(as_uuid=False), sa.ForeignKey("assets.id"), primary_key=True),
    )

    # ============ INTELLIGENCE ============
    op.create_table(
        "cognitive_runs",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("request_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.UUID(as_uuid=False), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("prompt_hash", sa.Text(), nullable=True),
        sa.Column("manifest_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("tokens_in", sa.BigInteger(), nullable=True),
        sa.Column("tokens_out", sa.BigInteger(), nullable=True),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cog_runs_request", "cognitive_runs", ["request_id"])

    op.create_table(
        "compiled_prompts",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("request_id", sa.UUID(as_uuid=False), sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("compiler_version", sa.Text(), nullable=False),
        sa.Column("target_capability", sa.Text(), nullable=True),
        sa.Column("target_provider", sa.Text(), nullable=True),
        sa.Column("positive_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("parameters", postgresql.JSONB(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column("prompt_hash", sa.Text(), nullable=False),
        sa.Column("content_mode", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_compiled_prompts_content_mode"),
    )
    op.create_index("ix_compiled_prompts_hash", "compiled_prompts", ["prompt_hash"])
    op.create_index("ix_compiled_prompts_request", "compiled_prompts", ["request_id"])

    # ============ AUTHORITY & AUDIT ============
    op.create_table(
        "authority_decisions",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("request_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("sanitized_arguments", postgresql.JSONB(), nullable=True),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=True),
        sa.Column("policy_bundle_version", sa.Text(), nullable=True),
        sa.Column("capability_registry_version", sa.Text(), nullable=True),
        sa.Column("harness_bundle_version", sa.Text(), nullable=True),
        sa.Column("content_mode", sa.Text(), nullable=True),
        sa.Column("floor_verdict", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("decision IN ('approve','deny','replan')", name="ck_authdec_decision"),
        sa.CheckConstraint("floor_verdict IN ('pass','fail','uncertain') OR floor_verdict IS NULL", name="ck_authdec_floor_verdict"),
    )
    op.create_index("ix_authdec_job", "authority_decisions", ["job_id"])
    op.create_index("ix_authdec_request", "authority_decisions", ["request_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("job_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_type", "audit_events", ["event_type", "created_at"])
    op.create_index("ix_audit_job", "audit_events", ["job_id"])
    op.create_index("ix_audit_user", "audit_events", ["user_id", "created_at"])

    # ============ QUALITY ============
    op.create_table(
        "harness_runs",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("attempt_id", sa.UUID(as_uuid=False), sa.ForeignKey("generation_attempts.attempt_id"), nullable=True),
        sa.Column("harness_id", sa.Text(), nullable=False),
        sa.Column("harness_version", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=True),
        sa.Column("reason_codes", postgresql.JSONB(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("runtime_ms", sa.BigInteger(), nullable=True),
        sa.Column("resource_cost", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("verdict IN ('pass','warn','fail')", name="ck_harness_verdict"),
    )
    op.create_index("ix_harness_job", "harness_runs", ["job_id"])
    op.create_index("ix_harness_attempt", "harness_runs", ["attempt_id", "created_at"])

    op.create_table(
        "user_feedback",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("rating", sa.Numeric(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("regeneration_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("selected_asset_id", sa.UUID(as_uuid=False), sa.ForeignKey("assets.id"), nullable=True),
        sa.Column("feedback_tags", postgresql.JSONB(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_feedback_job", "user_feedback", ["job_id"])

    # ============ BILLING ============
    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", sa.UUID(as_uuid=False), sa.ForeignKey("credit_accounts.id"), nullable=False),
        sa.Column("entry_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("processor", sa.Text(), nullable=True),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("idempotency_key", sa.Text(), unique=True, nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "entry_type IN ('topup','hold','settle','release','refund','adjustment')",
            name="ck_credit_ledger_entry_type"
        ),
    )
    op.create_index("ix_ledger_user", "credit_ledger", ["user_id", "created_at"])
    op.create_index("ix_ledger_job", "credit_ledger", ["job_id"])

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION forbid_ledger_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'credit_ledger is append-only'; END;
        $$ LANGUAGE plpgsql;
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_ledger_immutable BEFORE UPDATE OR DELETE ON credit_ledger
        FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();
    """))

    op.create_table(
        "usage_records",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.UUID(as_uuid=False), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("gpu_class", sa.Text(), nullable=True),
        sa.Column("vram_minutes", sa.Numeric(), nullable=True),
        sa.Column("gpu_seconds", sa.Numeric(), nullable=True),
        sa.Column("evaluator_ms", sa.BigInteger(), nullable=True),
        sa.Column("cost_units", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_usage_user", "usage_records", ["user_id", "created_at"])

    # ============ CONFIG ============
    op.create_table(
        "configuration_bundles",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("name", "version", name="uq_configuration_bundles_name_version"),
    )

    # ============ PERSONAS (§41) ============
    op.create_table(
        "personas",
        sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("traits", postgresql.JSONB(), nullable=True),
        sa.Column("backstory", sa.Text(), nullable=True),
        sa.Column("reference_assets", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("identity_adapter", sa.Text(), nullable=False, server_default="reference_set"),
        sa.Column("voice", postgresql.JSONB(), nullable=True),
        sa.Column("mature", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", "version", name="pk_personas"),
        sa.CheckConstraint("identity_adapter IN ('reference_set','ip')", name="ck_personas_identity_adapter"),
    )
    op.execute(sa.text("CREATE UNIQUE INDEX ix_personas_current ON personas (id) WHERE is_current;"))
    op.create_index("ix_personas_user", "personas", ["user_id", "created_at"])

    # ============ MEMORY (§42) ============
    op.create_table(
        "recipes",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("persona_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("envelope", postgresql.JSONB(), nullable=False),
        sa.Column("compiled_prompt", postgresql.JSONB(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=True),
        sa.Column("fabric_versions", postgresql.JSONB(), nullable=False),
        sa.Column("scores", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("content_mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="candidate"),
        sa.Column("promotion_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("content_mode IN ('sfw','unrestricted')", name="ck_recipes_content_mode"),
        sa.CheckConstraint("status IN ('candidate','promoted','retired')", name="ck_recipes_status"),
    )
    op.create_index("ix_recipes_scope", "recipes", ["user_id", "project_id", "created_at"])
    op.execute(sa.text("CREATE INDEX ix_recipes_promoted ON recipes (project_id) WHERE status = 'promoted';"))
    op.execute(sa.text("CREATE INDEX ix_recipes_persona ON recipes (persona_id) WHERE persona_id IS NOT NULL;"))

    op.create_table(
        "recipe_embeddings",
        sa.Column("recipe_id", sa.UUID(as_uuid=False), sa.ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(sa.text("CREATE INDEX ix_recipe_emb_hnsw ON recipe_embeddings USING hnsw (embedding vector_cosine_ops);"))

    op.create_table(
        "style_rules",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("weight", sa.Numeric(), nullable=False, server_default="1.0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(sa.text("CREATE INDEX ix_style_rules_active ON style_rules (project_id) WHERE active;"))


def downgrade() -> None:
    op.drop_table("style_rules")
    op.drop_table("recipe_embeddings")
    op.drop_table("recipes")
    op.drop_table("personas")
    op.drop_table("configuration_bundles")
    op.drop_table("usage_records")
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_ledger_immutable ON credit_ledger;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS forbid_ledger_mutation;"))
    op.drop_table("credit_ledger")
    op.drop_table("credit_accounts")
    op.drop_table("user_feedback")
    op.drop_table("harness_runs")
    op.drop_table("audit_events")
    op.drop_table("authority_decisions")
    op.drop_table("compiled_prompts")
    op.drop_table("cognitive_runs")
    op.drop_table("attempt_assets")
    op.drop_table("generation_attempts")
    op.drop_constraint("fk_rel_job", "asset_relationships", type_="foreignkey")
    op.drop_table("jobs")
    op.drop_table("request_assets")
    op.drop_table("requests")
    op.drop_table("asset_relationships")
    op.drop_table("assets")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("projects")
    op.drop_table("api_keys")
    op.drop_table("subscriptions")
    op.drop_table("users")
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector;"))
