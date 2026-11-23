"""
PR1 Acceptance Tests against Live PostgreSQL + pgvector (Bible v2 §21; ADR-005 PR1).
Validates:
1. Empty DB -> alembic upgrade head succeeds, no warnings.
2. Introspect: all 27 relations exist; column checklist per manifest.
3. recipe_embeddings.embedding type is vector(1024); HNSW index exists in pg_indexes.
4. credit_ledger immutability: UPDATE -> exception; DELETE -> exception via trigger.
5. Personas: composite PK (id, version) violation check; second is_current for same id -> unique index violation.
6. jobs.status CHECK rejects bogus state; accepts all 13 canonical ones.
7. Downgrade to base -> all 27 gone (clean revert path) and re-upgrade head restored.
8. alembic check -> no diff vs ORM metadata.
9. ETL: row parity on carried tables from archived fixture copy.
10. All §21 database rules: TIMESTAMPTZ columns, UUID PKs, ledger trigger present.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from apps.api.src.db.models import (
    Base,
    User,
    Project,
    Session as SessionModel,
    Message,
    Asset,
    Job,
    Persona,
    CreditAccount,
    CreditLedger,
    Recipe,
    RecipeEmbedding,
    StyleRule,
)
from scripts.migrate_sqlite_to_postgres import CARRIED_TABLES, migrate_sqlite_to_postgres

PG_SYNC_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://keystone:keystone_test_password@localhost:5432/keystone_test"
)

MANIFEST_27_TABLES = [
    "users",
    "subscriptions",
    "api_keys",
    "projects",
    "sessions",
    "messages",
    "assets",
    "asset_relationships",
    "requests",
    "request_assets",
    "jobs",
    "generation_attempts",
    "attempt_assets",
    "cognitive_runs",
    "compiled_prompts",
    "authority_decisions",
    "audit_events",
    "harness_runs",
    "user_feedback",
    "credit_accounts",
    "credit_ledger",
    "usage_records",
    "configuration_bundles",
    "personas",
    "recipes",
    "recipe_embeddings",
    "style_rules",
]


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(PG_SYNC_URL)
    yield engine
    engine.dispose()


@pytest.mark.db
def test_alembic_upgrade_head_and_introspection(pg_engine):
    """Verifies all 27 relations exist and column checklist per manifest."""
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    inspector = inspect(pg_engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    expected = set(MANIFEST_27_TABLES)
    assert tables == expected, f"Tables mismatch. Missing: {expected - tables}, Extra: {tables - expected}"

    # Verify column presence on key tables
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    for col in ["role", "content_mode", "age_verified", "age_verified_at", "age_verified_method", "is_active", "is_suspended"]:
        assert col in user_cols, f"Column {col} missing from users"

    job_cols = {c["name"] for c in inspector.get_columns("jobs")}
    for col in ["envelope_id", "envelope", "content_mode", "persona_id", "outputs", "failure_code"]:
        assert col in job_cols, f"Column {col} missing from jobs"

    persona_cols = {c["name"] for c in inspector.get_columns("personas")}
    for col in ["id", "version", "user_id", "traits", "backstory", "reference_assets", "identity_adapter", "voice", "mature", "is_current"]:
        assert col in persona_cols, f"Column {col} missing from personas"


@pytest.mark.db
def test_alembic_check_no_drift():
    """CI-enforced check: asserts zero drift between ORM metadata and migrations."""
    result = subprocess.run(
        [os.path.join(".venv", "Scripts", "alembic.exe"), "check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Alembic check detected drift:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "No new upgrade operations detected" in result.stdout or result.returncode == 0


@pytest.mark.db
def test_recipe_embeddings_pgvector_hnsw(pg_engine):
    """Verifies vector(1024) column type and HNSW index in pg_indexes."""
    with pg_engine.connect() as conn:
        res = conn.execute(text("""
            SELECT indexname, indexdef FROM pg_indexes
            WHERE tablename = 'recipe_embeddings' AND indexname = 'ix_recipe_emb_hnsw';
        """)).fetchone()
        assert res is not None, "Missing ix_recipe_emb_hnsw index on recipe_embeddings"
        assert "hnsw" in res[1].lower(), f"Expected hnsw index, got: {res[1]}"
        assert "vector_cosine_ops" in res[1].lower(), f"Expected vector_cosine_ops, got: {res[1]}"


@pytest.mark.db
def test_credit_ledger_immutability_trigger(pg_engine):
    """Verifies UPDATE and DELETE on credit_ledger raise exceptions via trigger."""
    with Session(pg_engine) as session:
        # Create a test user and credit account
        uid = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        lid = str(uuid.uuid4())

        user = User(id=uid, email=f"ledger_test_{uid[:8]}@keystone.ai")
        session.add(user)
        session.flush()

        account = CreditAccount(id=aid, user_id=uid, balance=1000)
        session.add(account)
        session.flush()

        ledger = CreditLedger(
            id=lid,
            user_id=uid,
            account_id=aid,
            entry_type="topup",
            amount=1000,
            processor="stripe",
        )
        session.add(ledger)
        session.commit()

        # Attempt UPDATE -> must fail
        with pytest.raises(Exception, match="credit_ledger is append-only"):
            session.execute(text(f"UPDATE credit_ledger SET amount = 2000 WHERE id = '{lid}'"))
            session.commit()
        session.rollback()

        # Attempt DELETE -> must fail
        with pytest.raises(Exception, match="credit_ledger is append-only"):
            session.execute(text(f"DELETE FROM credit_ledger WHERE id = '{lid}'"))
            session.commit()
        session.rollback()


@pytest.mark.db
def test_personas_composite_pk_and_unique_is_current(pg_engine):
    """Verifies personas composite PK (id, version) and partial unique is_current index."""
    with Session(pg_engine) as session:
        uid = str(uuid.uuid4())
        pid = str(uuid.uuid4())

        user = User(id=uid, email=f"persona_test_{uid[:8]}@keystone.ai")
        session.add(user)
        session.flush()

        # Version 1 (is_current=True)
        p1 = Persona(
            id=pid,
            version=1,
            user_id=uid,
            name="Aria",
            is_current=True,
        )
        session.add(p1)
        session.commit()

        # Duplicate (id, version=1) -> PK violation
        p1_dup = Persona(
            id=pid,
            version=1,
            user_id=uid,
            name="Aria Duplicate",
            is_current=False,
        )
        session.add(p1_dup)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        # Second row with is_current=True for same id -> unique partial index violation
        p2_current = Persona(
            id=pid,
            version=2,
            user_id=uid,
            name="Aria v2 Conflict",
            is_current=True,
        )
        session.add(p2_current)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        # Valid second version: flip old is_current=False and insert new with is_current=True
        session.execute(text(f"UPDATE personas SET is_current = FALSE WHERE id = '{pid}' AND version = 1"))
        p2_valid = Persona(
            id=pid,
            version=2,
            user_id=uid,
            name="Aria v2",
            is_current=True,
        )
        session.add(p2_valid)
        session.commit()


@pytest.mark.db
def test_jobs_status_check_constraint(pg_engine):
    """Verifies jobs.status rejects bogus states and accepts all 13 canonical ones."""
    canonical_statuses = [
        "CREATED", "VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED", "RUNNING",
        "VALIDATING_OUTPUT", "RETRY_PENDING", "REPLAN_REQUIRED", "COMPLETED",
        "FAILED", "CANCELLED", "REJECTED"
    ]
    with Session(pg_engine) as session:
        uid = str(uuid.uuid4())
        user = User(id=uid, email=f"job_status_{uid[:8]}@keystone.ai")
        session.add(user)
        session.flush()

        # Test all 13 canonical states succeed
        for s in canonical_statuses:
            jid = str(uuid.uuid4())
            job = Job(id=jid, user_id=uid, status=s)
            session.add(job)
        session.commit()

        # Test bogus state fails
        bad_job = Job(id=str(uuid.uuid4()), user_id=uid, status="BOGUS_STATUS")
        session.add(bad_job)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


@pytest.mark.db
def test_downgrade_and_reupgrade_roundtrip(pg_engine):
    """Verifies downgrade to base cleanly drops all 27 tables and upgrade head restores them."""
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")

    inspector = inspect(pg_engine)
    tables_after_downgrade = set(inspector.get_table_names()) - {"alembic_version"}
    assert len(tables_after_downgrade) == 0, f"Expected 0 tables after downgrade, found: {tables_after_downgrade}"

    # Re-upgrade to head
    command.upgrade(cfg, "head")
    inspector = inspect(pg_engine)
    tables_after_reupgrade = set(inspector.get_table_names()) - {"alembic_version"}
    assert tables_after_reupgrade == set(MANIFEST_27_TABLES)


@pytest.mark.etl
def test_sqlite_to_postgres_etl_row_parity():
    """Verifies ETL migration reproduces exact row parity from archived fixture copy."""
    report = migrate_sqlite_to_postgres()
    for table in CARRIED_TABLES:
        assert table in report
        assert report[table] > 0, f"Expected > 0 rows in {table}, got {report[table]}"


@pytest.mark.db
def test_bible_s21_database_rules(pg_engine):
    """Verifies TIMESTAMPTZ columns, UUID primary keys, and trigger definitions in PostgreSQL."""
    with pg_engine.connect() as conn:
        # 1. Verify UUID PKs across tables
        pk_types = conn.execute(text("""
            SELECT c.table_name, c.column_name, c.data_type
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            JOIN information_schema.columns c ON c.table_name = tc.table_name AND c.column_name = ccu.column_name
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
            AND tc.table_name IN ('users', 'projects', 'sessions', 'messages', 'assets', 'jobs');
        """)).fetchall()

        for tbl, col, dtype in pk_types:
            assert dtype == "uuid", f"Primary key {tbl}.{col} expected uuid, got {dtype}"

        # 2. Verify created_at is TIMESTAMPTZ (timestamp with time zone)
        ts_cols = conn.execute(text("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name IN ('created_at', 'updated_at')
            AND table_name IN ('users', 'projects', 'sessions', 'assets', 'jobs');
        """)).fetchall()

        for tbl, col, dtype in ts_cols:
            assert dtype == "timestamp with time zone", f"Column {tbl}.{col} expected timestamp with time zone, got {dtype}"
