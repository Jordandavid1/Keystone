"""
KEYSTONE Milestone M1 Comprehensive Test Suite (F05–F09 & Wave 1 Shell)
Covers:
  - F05: SQLAlchemy 2.0 ORM (23 Tables) & Tenant Repositories
  - F06: Authentication & Tenant Isolation
  - F07: Asset Storage & Short-Expiry Signed URLs
  - F08: Lineage DAG Tracking & Cycle Prevention
  - F09: 13-State Job State Machine Engine
  - Wave 1: 10-Step Vertical Shell HTTP Integration Flow
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.src.server import app
from apps.api.src.db.models import Base
from apps.api.src.db.session import init_db
from apps.api.src.repositories import (
    UserRepository,
    ProjectRepository,
    SessionRepository,
    MessageRepository,
    AssetRepository,
    JobRepository,
)
from apps.api.src.auth.security import (
    hash_password,
    verify_password,
    generate_token,
    verify_token,
    hash_api_key,
    generate_api_key_pair,
    enforce_tenant_isolation,
    verify_service_token,
)
from apps.api.src.storage import (
    generate_storage_key,
    generate_signed_url,
    validate_signed_url,
    LocalStorageProvider,
)
from apps.api.src.lineage import LineageDAG, VALID_RELATIONSHIPS
from apps.api.src.jobs import (
    JobState,
    JobStateMachine,
    STATES,
    TERMINAL_STATES,
    ALLOWED_TRANSITIONS,
    transition,
    normalize_state,
)


# ============================================================================
# F05: Database Schema & Tenant Repositories Tests
# ============================================================================

@pytest.mark.asyncio
async def test_f05_23_tables_schema_creation():
    """Verify modern SQLAlchemy 2.0 ORM declares all 23 database tables."""
    assert len(Base.metadata.tables) == 23
    required_tables = [
        "users", "subscriptions", "api_keys", "projects", "sessions",
        "messages", "assets", "requests", "request_assets", "cognitive_runs",
        "authority_decisions", "jobs", "generation_attempts", "compiled_prompts",
        "attempt_assets", "harness_runs", "user_feedback", "credit_accounts",
        "credit_ledger", "usage_records", "audit_events", "configuration_bundles",
        "asset_relationships"
    ]
    for table in required_tables:
        assert table in Base.metadata.tables

    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(eng)
    await eng.dispose()

    # Verify UniversalUUID PostgreSQL dialect mapping
    from apps.api.src.db.models import UniversalUUID
    from sqlalchemy.dialects.postgresql import dialect as pg_dialect, UUID as PG_UUID
    from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect
    from sqlalchemy.types import CHAR

    uuid_type = UniversalUUID()
    pg_impl = uuid_type.load_dialect_impl(pg_dialect())
    assert isinstance(pg_impl, PG_UUID)
    sqlite_impl = uuid_type.load_dialect_impl(sqlite_dialect())
    assert isinstance(sqlite_impl, CHAR)


@pytest.mark.asyncio
async def test_f05_user_repository_crud():
    """Verify UserRepository creates and retrieves users with initial credit account."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(eng)
    sm = async_sessionmaker(eng, class_=AsyncSession)

    async with sm() as session:
        repo = UserRepository(session)
        user_id = str(uuid.uuid4())
        user = await repo.create_user(user_id, "creator@keystone.ai", hash_password("pass123"))
        assert user.email == "creator@keystone.ai"

        fetched = await repo.get_user_by_id(user_id)
        assert fetched is not None
        assert fetched.id == user_id

        by_email = await repo.get_user_by_email("creator@keystone.ai")
        assert by_email is not None
        assert by_email.id == user_id

    # Edge case: empty email or id
    async with sm() as session:
        repo = UserRepository(session)
        with pytest.raises(ValueError, match="INVALID_USER"):
            await repo.create_user("", "")

    await eng.dispose()


@pytest.mark.asyncio
async def test_f05_project_repository_scoping_and_soft_delete():
    """Verify ProjectRepository enforces tenant user_id scoping and soft-deletion filtering."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(eng)
    sm = async_sessionmaker(eng, class_=AsyncSession)

    u1_id = str(uuid.uuid4())
    u2_id = str(uuid.uuid4())

    async with sm() as session:
        u_repo = UserRepository(session)
        await u_repo.create_user(u1_id, "u1@keystone.ai")
        await u_repo.create_user(u2_id, "u2@keystone.ai")

        p_repo1 = ProjectRepository(session, tenant_id=u1_id)
        proj_1 = await p_repo1.create_project(str(uuid.uuid4()), "Movie 1")
        proj_2 = await p_repo1.create_project(str(uuid.uuid4()), "Movie 2")

        p_repo2 = ProjectRepository(session, tenant_id=u2_id)
        proj_u2 = await p_repo2.create_project(str(uuid.uuid4()), "U2 Movie")

        # Scoping check
        u1_projs = await p_repo1.get_projects()
        assert len(u1_projs) == 2
        u2_projs = await p_repo2.get_projects()
        assert len(u2_projs) == 1
        assert u2_projs[0].id == proj_u2.id

        # Cross-tenant get returns None
        assert await p_repo2.get_project_by_id(proj_1.id) is None

        # Soft delete
        deleted = await p_repo1.soft_delete_project(proj_1.id)
        assert deleted is True

        # Soft-deleted project excluded from active list
        u1_projs_after = await p_repo1.get_projects()
        assert len(u1_projs_after) == 1
        assert u1_projs_after[0].id == proj_2.id

    # Edge case: non-existent user throws USER_NOT_FOUND
    async with sm() as session:
        ghost_repo = ProjectRepository(session, tenant_id=str(uuid.uuid4()))
        with pytest.raises(ValueError, match="USER_NOT_FOUND"):
            await ghost_repo.create_project(str(uuid.uuid4()), "Ghost Project")

    await eng.dispose()


@pytest.mark.asyncio
async def test_f05_session_and_asset_repository_validation():
    """Verify session and asset creation validations."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(eng)
    sm = async_sessionmaker(eng, class_=AsyncSession)

    u_id = str(uuid.uuid4())
    p_id = str(uuid.uuid4())

    async with sm() as session:
        u_repo = UserRepository(session)
        await u_repo.create_user(u_id, "valid@keystone.ai")
        p_repo = ProjectRepository(session, tenant_id=u_id)
        await p_repo.create_project(p_id, "Active Proj")

        s_repo = SessionRepository(session, tenant_id=u_id)
        sess = await s_repo.create_session(str(uuid.uuid4()), project_id=p_id)
        assert sess.project_id == p_id

        # Missing project raises PROJECT_NOT_FOUND_OR_FORBIDDEN
        with pytest.raises(ValueError, match="PROJECT_NOT_FOUND_OR_FORBIDDEN"):
            await s_repo.create_session(str(uuid.uuid4()), project_id=str(uuid.uuid4()))

        # Invalid asset params
        a_repo = AssetRepository(session, tenant_id=u_id)
        with pytest.raises(ValueError, match="INVALID_ASSET_PARAMS"):
            await a_repo.create_asset(str(uuid.uuid4()), "f.png", "", 100, "key")  # empty mime
        with pytest.raises(ValueError, match="INVALID_ASSET_PARAMS"):
            await a_repo.create_asset(str(uuid.uuid4()), "f.png", "image/png", 0, "key")  # 0 byte_size
        with pytest.raises(ValueError, match="INVALID_ASSET_PARAMS"):
            await a_repo.create_asset(str(uuid.uuid4()), "f.png", "image/png", 100, "")  # empty key

    await eng.dispose()


# ============================================================================
# F06: Authentication & Tenant Isolation Tests
# ============================================================================

def test_f06_password_hashing():
    """Verify PBKDF2 password hashing and verification."""
    pwd = "super_secret_creative_pwd_123!"
    hashed = hash_password(pwd)
    assert hashed.startswith("pbkdf2_sha256$600000$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False
    assert verify_password("", hashed) is False


def test_f06_api_key_hashing():
    """Verify SHA-256 API key hashing and edge cases."""
    raw_key, prefix, key_hash = generate_api_key_pair()
    assert len(key_hash) == 64
    assert hash_api_key(raw_key) == key_hash

    # Edge cases
    with pytest.raises(ValueError, match="INVALID_KEY"):
        hash_api_key("")
    with pytest.raises(ValueError, match="INVALID_KEY"):
        hash_api_key(None)  # type: ignore


def test_f06_jwt_token_lifecycle():
    """Verify stateless JWT token generation, verification, and boundary errors."""
    u_id = "usr_creative_42"
    token = generate_token(u_id, role="admin", expiry_seconds=3600)
    payload = verify_token(token)
    assert payload["sub"] == u_id
    assert payload["role"] == "admin"
    assert payload["exp"] > time.time()

    # Malformed token without dot
    with pytest.raises(ValueError, match="MALFORMED_TOKEN"):
        verify_token("malformed_token_without_dot")

    # Tampered signature
    tampered = token[:-4] + "bad1"
    with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
        verify_token(tampered)

    # Expired token
    expired_token = generate_token(u_id, expiry_seconds=-10)
    with pytest.raises(ValueError, match="TOKEN_EXPIRED"):
        verify_token(expired_token)


def test_f06_tenant_isolation_guard():
    """Verify enforce_tenant_isolation prevents cross-tenant access."""
    assert enforce_tenant_isolation("usr_alice", "usr_alice") is True
    with pytest.raises(ValueError, match="TENANT_ACCESS_DENIED"):
        enforce_tenant_isolation("usr_alice", "usr_bob")


def test_f06_service_token_verification():
    """Verify service token verification."""
    assert verify_service_token("keystone-internal-worker-secret") is True
    assert verify_service_token("wrong-secret") is False
    assert verify_service_token(None) is False


# ============================================================================
# F07: Asset Storage & Short-Expiry URLs Tests
# ============================================================================

def test_f07_storage_key_generation_and_sanitization():
    """Verify storage key layout and path traversal sanitization."""
    key = generate_storage_key("usr_123", "ast_456", "character portrait.png")
    assert key == "tenants/usr_123/assets/ast_456/character_portrait.png"

    # Path traversal attack vector
    traversal_key = generate_storage_key("u1", "a1", "../../../etc/passwd.png")
    assert ".." not in traversal_key
    assert traversal_key == "tenants/u1/assets/a1/passwd.png"

    # Adversarial user_id traversal sanitization
    user_trav = generate_storage_key("../../admin", "a1", "avatar.png")
    assert ".." not in user_trav
    assert user_trav == "tenants/______admin/assets/a1/avatar.png"

    # Dot-only and dotdot filename sanitization
    assert generate_storage_key("u1", "a1", "..").endswith("asset.bin")
    assert generate_storage_key("u1", "a1", "....").endswith("asset.bin")


def test_f07_signed_url_generation_and_validation():
    """Verify 15-minute signed URL generation, expiration ceiling, and signature validation."""
    storage_key = "tenants/usr_1/assets/ast_1/hero.png"
    url = generate_signed_url(storage_key, expiry_seconds=900)
    assert "expires=" in url
    assert "signature=" in url
    assert url.startswith("https://storage.keystone.internal/")

    # Valid validation
    validated = validate_signed_url(url)
    assert validated["valid"] is True
    assert validated["storage_key"] == storage_key

    # Expiry exceeded (> 3600s)
    with pytest.raises(ValueError, match="EXPIRY_EXCEEDED"):
        generate_signed_url(storage_key, expiry_seconds=7200)

    # Non-positive expiry
    with pytest.raises(ValueError, match="INVALID_EXPIRY"):
        generate_signed_url(storage_key, expiry_seconds=0)

    # Tampered signature
    tampered_url = url.replace("signature=", "signature=badc0ffee")
    with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
        validate_signed_url(tampered_url)


@pytest.mark.asyncio
async def test_f07_local_storage_provider():
    """Verify LocalStorageProvider persists and retrieves object bytes."""
    provider = LocalStorageProvider()
    key = "tenants/test/assets/test_asset.txt"
    data = b"KEYSTONE Binary Content 2026"
    stored_path = await provider.put_object(key, data)
    assert Path(stored_path).exists()

    assert await provider.exists(key) is True
    retrieved = await provider.get_object(key)
    assert retrieved == data

    assert await provider.delete_object(key) is True
    assert await provider.exists(key) is False

    # Sibling directory prefix containment rejection (CWE-22)
    with pytest.raises(ValueError, match="ILLEGAL_STORAGE_PATH"):
        provider._resolve_path("../storage_evil/file.txt")


# ============================================================================
# F08: Lineage DAG Tracking Tests
# ============================================================================

def test_f08_lineage_dag_valid_relationships():
    """Verify all 8 relationship types are supported."""
    assert len(VALID_RELATIONSHIPS) == 8
    dag = LineageDAG()
    for rel_type in VALID_RELATIONSHIPS:
        edge = dag.add_relationship("root", f"child_{rel_type}", rel_type, "j1")
        assert edge["relationship_type"] == rel_type


def test_f08_lineage_dag_self_referential_protection():
    """Verify asset cannot be its own parent."""
    dag = LineageDAG()
    with pytest.raises(ValueError, match="SELF_REFERENTIAL_LINEAGE"):
        dag.add_relationship("ast_same", "ast_same", "edit", "j1")


def test_f08_lineage_dag_cycle_detection():
    """Verify direct and multi-hop cycle detection."""
    dag = LineageDAG()
    dag.add_relationship("ast_A", "ast_B", "source", "j1")

    # Direct cycle A -> B -> A
    with pytest.raises(ValueError, match="CYCLE_DETECTED"):
        dag.add_relationship("ast_B", "ast_A", "edit", "j2")

    # Multi-hop cycle A -> B -> C -> A
    dag.add_relationship("ast_B", "ast_C", "animation", "j3")
    with pytest.raises(ValueError, match="CYCLE_DETECTED"):
        dag.add_relationship("ast_C", "ast_A", "variation", "j4")


def test_f08_lineage_dag_traversals():
    """Verify ancestor and descendant multi-hop graph traversals."""
    dag = LineageDAG()
    dag.add_relationship("root", "v1", "source", "j1")
    dag.add_relationship("v1", "v2", "edit", "j2")
    dag.add_relationship("v2", "v3", "animation", "j3")

    ancestors = dag.get_ancestors("v3")
    assert len(ancestors) == 3
    assert set(ancestors) == {"root", "v1", "v2"}

    descendants = dag.get_descendants("root")
    assert len(descendants) == 3
    assert set(descendants) == {"v1", "v2", "v3"}

    # Boundary checks: root has no ancestors, leaf has no descendants
    assert dag.get_ancestors("root") == []
    assert dag.get_descendants("v3") == []


# ============================================================================
# F09: Job State Machine Engine Tests
# ============================================================================

def test_f09_job_state_machine_states():
    """Verify all 13 states and 4 terminal states exist."""
    assert len(STATES) == 13
    assert len(TERMINAL_STATES) == 4
    for term in ["COMPLETED", "FAILED", "CANCELLED", "REJECTED"]:
        assert term in TERMINAL_STATES


def test_f09_happy_path_transitions():
    """Verify complete happy-path job lifecycle transitions."""
    state = "CREATED"
    happy_flow = [
        "VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED",
        "RUNNING", "VALIDATING_OUTPUT", "COMPLETED"
    ]
    for target in happy_flow:
        state = transition(state, target)
    assert state == "COMPLETED"


def test_f09_retry_and_replan_loops():
    """Verify retry and cognitive replan transition cycles."""
    # Retry cycle
    s = "VALIDATING_OUTPUT"
    s = transition(s, "RETRY_PENDING")
    assert s == "RETRY_PENDING"
    s = transition(s, "QUEUED")
    assert s == "QUEUED"

    # Replan cycle
    s = "VALIDATING_OUTPUT"
    s = transition(s, "REPLAN_REQUIRED")
    assert s == "REPLAN_REQUIRED"
    s = transition(s, "PLANNING")
    assert s == "PLANNING"


def test_f09_idempotency():
    """Verify state transition is an idempotent no-op when target matches current."""
    assert transition("RUNNING", "RUNNING") == "RUNNING"
    assert transition("QUEUED", "QUEUED") == "QUEUED"


def test_f09_terminal_state_protection():
    """Verify transitioning out of ANY terminal state is forbidden."""
    for term in TERMINAL_STATES:
        with pytest.raises(ValueError, match="ILLEGAL_TRANSITION"):
            transition(term, "RUNNING")


def test_f09_illegal_skips_and_unknown_states():
    """Verify illegal transitions and unknown states throw appropriate errors."""
    with pytest.raises(ValueError, match="ILLEGAL_TRANSITION"):
        transition("CREATED", "RUNNING")  # Illegal skip

    with pytest.raises(ValueError, match="UNKNOWN_CURRENT_STATE"):
        transition("NON_EXISTENT_STATE", "RUNNING")

    with pytest.raises(ValueError, match="UNKNOWN_NEXT_STATE"):
        transition("CREATED", "NON_EXISTENT_STATE")


# ============================================================================
# Wave 1 Vertical Shell: Complete 10-Step HTTP Integration Flow
# ============================================================================

@pytest.mark.asyncio
async def test_wave1_10_step_vertical_shell_e2e():
    """
    Executes the authoritative 10-step Wave 1 Vertical Shell lifecycle (Bible §33):
      1. Register user (/v1/auth/register)
      2. Create project (/v1/projects)
      3. Create session (/v1/sessions)
      4. Upload input asset (/v1/assets/upload)
      5. Send message (/v1/sessions/{id}/messages)
      6. Create job (/v1/jobs)
      7. Transition job through state machine (/v1/jobs/{id}/transition)
      8. Persist output asset and register lineage (/v1/assets/{id}/relationships)
      9. Retrieve asset lineage (/v1/assets/{id}/lineage)
      10. Refresh & recover state (/v1/projects/{id}, /v1/assets)
    """
    await init_db()
    client = TestClient(app)

    # Step 1: Register User
    reg_email = f"creator_{uuid.uuid4().hex[:8]}@keystone.ai"
    reg_res = client.post("/v1/auth/register", json={
        "email": reg_email,
        "password": "SecurePassword123!",
        "display_name": "Visionary Director"
    })
    assert reg_res.status_code == 200, reg_res.text
    reg_data = reg_res.json()
    token = reg_data["access_token"]
    user_id = reg_data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Create Project
    proj_res = client.post("/v1/projects", headers=headers, json={
        "name": "Neon Odyssey Sci-Fi Short",
        "description": "Multi-shot cyberpunk cinematic series"
    })
    assert proj_res.status_code == 200, proj_res.text
    project_id = proj_res.json()["id"]

    # Step 3: Create Session
    sess_res = client.post("/v1/sessions", headers=headers, json={
        "project_id": project_id,
        "title": "Act I Scene Composer"
    })
    assert sess_res.status_code == 200, sess_res.text
    session_id = sess_res.json()["id"]

    # Step 4: Upload Asset
    upload_res = client.post("/v1/assets/upload", headers=headers, json={
        "filename": "cyberpunk_hero.png",
        "mime_type": "image/png",
        "byte_size": 3145728,
        "project_id": project_id
    })
    assert upload_res.status_code == 200, upload_res.text
    input_asset_id = upload_res.json()["asset_id"]
    assert "upload_url" in upload_res.json()
    assert "download_url" in upload_res.json()

    # Step 5: Send Message
    msg_res = client.post(f"/v1/sessions/{session_id}/messages", headers=headers, json={
        "role": "user",
        "content": "Animate cyberpunk_hero walking through neon rain at 24fps"
    })
    assert msg_res.status_code == 200, msg_res.text
    assert msg_res.json()["role"] == "user"

    # Step 6: Create Job
    job_res = client.post("/v1/jobs", headers=headers, json={
        "capability_id": "wan_i2v",
        "provider_id": "kaggle_comfyui",
        "workflow_id": "wf_wan_cinematic",
        "workflow_version": "2.1.0",
        "initial_state": "CREATED"
    })
    assert job_res.status_code == 200, job_res.text
    job_id = job_res.json()["id"]
    assert job_res.json()["state"] == "CREATED"

    # Step 7: Stream/Execute State Machine Transitions
    transitions = [
        "VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED",
        "RUNNING", "VALIDATING_OUTPUT", "COMPLETED"
    ]
    for nxt in transitions:
        t_res = client.post(f"/v1/jobs/{job_id}/transition", headers=headers, json={
            "next_state": nxt,
            "reason": f"Transition to {nxt}"
        })
        assert t_res.status_code == 200, t_res.text
        assert t_res.json()["current_state"] == nxt

    # Verify event history
    events_res = client.get(f"/v1/jobs/{job_id}/events", headers=headers)
    assert events_res.status_code == 200
    assert len(events_res.json()["events"]) >= len(transitions)

    # Step 8: Return Output Asset and Link Lineage
    out_asset_res = client.post("/v1/assets", headers=headers, json={
        "filename": "neon_rain_walk_animated.mp4",
        "mime_type": "video/mp4",
        "byte_size": 15728640,
        "project_id": project_id,
        "media_type": "video"
    })
    assert out_asset_res.status_code == 200
    output_asset_id = out_asset_res.json()["id"]

    # Reject arbitrary caller-supplied traversal storage_key
    bad_storage_key_res = client.post("/v1/assets", headers=headers, json={
        "filename": "evil.png",
        "mime_type": "image/png",
        "byte_size": 1024,
        "storage_key": "../storage_evil/escaped_asset.png"
    })
    assert bad_storage_key_res.status_code == 400
    assert "ILLEGAL_STORAGE_KEY" in bad_storage_key_res.json()["detail"]

    # Reject cross-tenant or non-existent child asset relationship
    fake_child_res = client.post(
        f"/v1/assets/{input_asset_id}/relationships",
        headers=headers,
        json={
            "child_asset_id": str(uuid.uuid4()),
            "relationship_type": "animation"
        }
    )
    assert fake_child_res.status_code == 404
    assert "Child asset not found or access denied" in fake_child_res.json()["detail"]

    # Add Lineage edge: input_asset -> output_asset (animation)
    rel_res = client.post(
        f"/v1/assets/{input_asset_id}/relationships",
        headers=headers,
        json={
            "child_asset_id": output_asset_id,
            "relationship_type": "animation",
            "job_id": job_id
        }
    )
    assert rel_res.status_code == 200, rel_res.text
    assert rel_res.json()["relationship"]["relationship_type"] == "animation"

    # Step 9: Verify Lineage Tracking
    lineage_res = client.get(f"/v1/assets/{output_asset_id}/lineage", headers=headers)
    assert lineage_res.status_code == 200
    assert input_asset_id in lineage_res.json()["ancestors"]

    # Step 10: Refresh & Recover State
    proj_verify = client.get(f"/v1/projects/{project_id}", headers=headers)
    assert proj_verify.status_code == 200
    assert proj_verify.json()["name"] == "Neon Odyssey Sci-Fi Short"

    assets_verify = client.get(f"/v1/assets?project_id={project_id}", headers=headers)
    assert assets_verify.status_code == 200
    asset_ids = [a["id"] for a in assets_verify.json()["assets"]]
    assert input_asset_id in asset_ids
    assert output_asset_id in asset_ids
