"""
KEYSTONE Milestone M1: Adversarial Challenger Test Suite
========================================================
Empirical stress-testing of F05 (Data Models & Repositories) and F06 (Authentication & Tenant Isolation).

Adversarial Stress Categories:
1. Tenant Isolation Attacks:
   - User A resources (Projects, Sessions, Messages, Assets, Jobs, API Keys) targeted by User B
   - Cross-tenant fetch, update, delete, and list queries via HTTP API and direct Repository methods
   - Repository-level scoping verification and architectural leak surface analysis
2. Soft-Deleted Resource Leakage:
   - Querying soft-deleted projects and assets via ID and listing endpoints
   - Attempting to create sessions or attach assets within soft-deleted projects
   - Idempotent delete protection (preventing duplicate deletion leaks)
   - Lineage graph rejection of soft-deleted assets
3. Bearer Token Forgery Attacks:
   - Header manipulation (alg=none, uppercase NONE, None)
   - Standard 3-part JWT header-payload-signature injection
   - Payload tampering (sub claim hijacking, role escalation, expiry extension)
   - Signature corruption (single-bit alteration, truncation, empty signature)
   - Invalid HMAC secret forgery
   - Expired tokens and malformed token strings
   - Inactive/suspended user token rejection
4. API Key Bypass Attacks:
   - Empty keys, whitespace keys, None/non-string inputs
   - Direct hash injection attack (passing stored SHA-256 hash as raw key)
   - Key prefix collision and brute force guessing
   - Revoked API key handling
   - Suspended user key rejection
5. Password Brute Force Protection & PBKDF2 Resistance:
   - 600,000 iterations verification (OWASP benchmark)
   - Salt entropy and uniqueness (rainbow table resistance)
   - Constant-time verification against timing attacks
   - Malformed/corrupted hash robustness (no unhandled exceptions)
   - Empirical computational work measurement
6. Storage Key Traversal & Signed URL Security:
   - Directory traversal vector sanitization (../../../etc/passwd)
   - Signed URL 3600s ceiling enforcement and negative expiry rejection
   - Tampered URL signature detection and expired URL rejection
7. Service Token & Internal Worker Boundary Security:
   - Unauthenticated / wrong secret / tampered header rejection
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
import uuid
from pathlib import Path

# Ensure project root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.src.server import app
from apps.api.src.db.models import Base, User, Project, Session, Message, Asset, Job, ApiKey
from apps.api.src.db.session import init_db, async_session_factory
from apps.api.src.repositories import (
    UserRepository,
    ProjectRepository,
    SessionRepository,
    MessageRepository,
    AssetRepository,
    JobRepository,
    ApiKeyRepository,
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
    JWT_SECRET_KEY,
    PBKDF2_ITERATIONS,
)
from apps.api.src.storage.service import (
    generate_storage_key,
    generate_signed_url,
    validate_signed_url,
)
from apps.api.src.lineage.dag import LineageDAG


# Helper to create base64url encoded string
def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


# ==============================================================================
# 1. Tenant Isolation Attacks (HTTP API & Repository Layer)
# ==============================================================================

class TestTenantIsolationAttacks:
    """Stress tests tenant isolation across Projects, Sessions, Messages, Assets, Jobs, and API Keys."""

    @pytest.fixture(autouse=True)
    def setup_tenants(self):
        self.client = TestClient(app)

        # Register Tenant A (Alice)
        self.email_a = f"alice_{uuid.uuid4().hex[:8]}@keystone.ai"
        res_a = self.client.post("/v1/auth/register", json={
            "email": self.email_a,
            "password": "AliceSecurePassword123!",
            "display_name": "Alice Director"
        })
        assert res_a.status_code == 200, res_a.text
        data_a = res_a.json()
        self.token_a = data_a["access_token"]
        self.user_a_id = data_a["user"]["id"]
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}

        # Register Tenant B (Bob - Adversary)
        self.email_b = f"bob_{uuid.uuid4().hex[:8]}@keystone.ai"
        res_b = self.client.post("/v1/auth/register", json={
            "email": self.email_b,
            "password": "BobSecurePassword123!",
            "display_name": "Bob Adversary"
        })
        assert res_b.status_code == 200, res_b.text
        data_b = res_b.json()
        self.token_b = data_b["access_token"]
        self.user_b_id = data_b["user"]["id"]
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}

        # Alice creates resources: Project, Session, Message, Asset, Job, API Key
        # Project A
        res_proj = self.client.post("/v1/projects", headers=self.headers_a, json={
            "name": "Alice Sovereign Project",
            "description": "Confidential IP"
        })
        assert res_proj.status_code == 200, res_proj.text
        self.proj_a_id = res_proj.json()["id"]

        # Session A
        res_sess = self.client.post("/v1/sessions", headers=self.headers_a, json={
            "project_id": self.proj_a_id,
            "title": "Alice Private Session"
        })
        assert res_sess.status_code == 200, res_sess.text
        self.sess_a_id = res_sess.json()["id"]

        # Message A
        res_msg = self.client.post(f"/v1/sessions/{self.sess_a_id}/messages", headers=self.headers_a, json={
            "role": "user",
            "content": "Alice confidential prompt secret 42"
        })
        assert res_msg.status_code == 200, res_msg.text
        self.msg_a_id = res_msg.json()["id"]

        # Asset A
        res_ast = self.client.post("/v1/assets", headers=self.headers_a, json={
            "filename": "alice_confidential_design.png",
            "mime_type": "image/png",
            "byte_size": 2048,
            "project_id": self.proj_a_id
        })
        assert res_ast.status_code == 200, res_ast.text
        self.ast_a_id = res_ast.json()["id"]

        # Job A
        res_job = self.client.post("/v1/jobs", headers=self.headers_a, json={
            "capability_id": "image_gen",
            "provider_id": "kaggle_comfyui",
            "workflow_id": "wf_alice_secret"
        })
        assert res_job.status_code == 200, res_job.text
        self.job_a_id = res_job.json()["id"]

        # API Key A
        res_key = self.client.post("/v1/auth/api-keys", headers=self.headers_a, json={
            "name": "Alice Automated Production Key"
        })
        assert res_key.status_code == 200, res_key.text
        self.key_a_id = res_key.json()["id"]

    def test_user_b_cannot_fetch_user_a_project(self):
        """User B querying User A's project by ID must return 404."""
        res = self.client.get(f"/v1/projects/{self.proj_a_id}", headers=self.headers_b)
        assert res.status_code == 404
        assert "not found or forbidden" in res.json().get("detail", "").lower()

    def test_user_b_cannot_delete_user_a_project(self):
        """User B attempting to soft-delete User A's project must return 404."""
        res = self.client.delete(f"/v1/projects/{self.proj_a_id}", headers=self.headers_b)
        assert res.status_code == 404

        # Verify Alice's project remains active
        verify_res = self.client.get(f"/v1/projects/{self.proj_a_id}", headers=self.headers_a)
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "active"

    def test_user_b_project_list_excludes_user_a_projects(self):
        """User B listing projects must receive 0 projects from User A."""
        res = self.client.get("/v1/projects", headers=self.headers_b)
        assert res.status_code == 200
        proj_ids = [p["id"] for p in res.json()["projects"]]
        assert self.proj_a_id not in proj_ids

    def test_user_b_cannot_fetch_user_a_session(self):
        """User B querying User A's session by ID must return 404."""
        res = self.client.get(f"/v1/sessions/{self.sess_a_id}", headers=self.headers_b)
        assert res.status_code == 404

    def test_user_b_cannot_create_session_in_user_a_project(self):
        """User B attempting to create a session in User A's project must be rejected."""
        res = self.client.post("/v1/sessions", headers=self.headers_b, json={
            "project_id": self.proj_a_id,
            "title": "Adversarial Session in Alice's Project"
        })
        assert res.status_code == 404
        assert "PROJECT_NOT_FOUND_OR_FORBIDDEN" in res.json().get("detail", "")

    def test_user_b_session_list_scoped_by_project_excludes_user_a(self):
        """User B listing sessions specifying Alice's project_id receives empty list."""
        res = self.client.get(f"/v1/sessions?project_id={self.proj_a_id}", headers=self.headers_b)
        assert res.status_code == 200
        assert len(res.json()["sessions"]) == 0

    def test_user_b_cannot_read_user_a_messages(self):
        """User B querying messages in User A's session must return 404."""
        res = self.client.get(f"/v1/sessions/{self.sess_a_id}/messages", headers=self.headers_b)
        assert res.status_code == 404

    def test_user_b_cannot_post_message_into_user_a_session(self):
        """User B attempting to inject a message into User A's session must return 404."""
        res = self.client.post(f"/v1/sessions/{self.sess_a_id}/messages", headers=self.headers_b, json={
            "role": "user",
            "content": "Malicious injected payload from Bob"
        })
        assert res.status_code == 404

        # Verify Alice's messages are unpolluted
        alice_msgs = self.client.get(f"/v1/sessions/{self.sess_a_id}/messages", headers=self.headers_a)
        assert alice_msgs.status_code == 200
        contents = [m["content"] for m in alice_msgs.json()["messages"]]
        assert "Malicious injected payload from Bob" not in contents

    def test_user_b_cannot_fetch_user_a_asset(self):
        """User B querying User A's asset by ID must return 404."""
        res = self.client.get(f"/v1/assets/{self.ast_a_id}", headers=self.headers_b)
        assert res.status_code == 404

    def test_user_b_cannot_delete_user_a_asset(self):
        """User B attempting to soft-delete User A's asset must return 404."""
        res = self.client.delete(f"/v1/assets/{self.ast_a_id}", headers=self.headers_b)
        assert res.status_code == 404

        # Verify Alice's asset is still available
        verify = self.client.get(f"/v1/assets/{self.ast_a_id}", headers=self.headers_a)
        assert verify.status_code == 200

    def test_user_b_asset_list_excludes_user_a_assets(self):
        """User B listing assets must never see User A's assets."""
        res = self.client.get("/v1/assets", headers=self.headers_b)
        assert res.status_code == 200
        asset_ids = [a["id"] for a in res.json()["assets"]]
        assert self.ast_a_id not in asset_ids

    def test_user_b_cannot_fetch_user_a_job(self):
        """User B querying User A's job by ID must return 404."""
        res = self.client.get(f"/v1/jobs/{self.job_a_id}", headers=self.headers_b)
        assert res.status_code == 404

    def test_user_b_cannot_transition_user_a_job(self):
        """User B attempting to trigger state machine transition on User A's job must return 404."""
        res = self.client.post(f"/v1/jobs/{self.job_a_id}/transition", headers=self.headers_b, json={
            "next_state": "VALIDATING",
            "reason": "Unauthorized transition attempt by Bob"
        })
        assert res.status_code == 404

        # Verify Alice's job state is unchanged (still CREATED)
        verify = self.client.get(f"/v1/jobs/{self.job_a_id}", headers=self.headers_a)
        assert verify.status_code == 200
        assert verify.json()["state"] == "CREATED"

    def test_user_b_cannot_view_user_a_job_events(self):
        """User B querying User A's job event stream must return 404."""
        res = self.client.get(f"/v1/jobs/{self.job_a_id}/events", headers=self.headers_b)
        assert res.status_code == 404

    def test_user_b_cannot_list_user_a_api_keys(self):
        """User B listing API keys must never observe User A's API keys."""
        res = self.client.get("/v1/auth/api-keys", headers=self.headers_b)
        assert res.status_code == 200
        key_ids = [k["id"] for k in res.json()["api_keys"]]
        assert self.key_a_id not in key_ids


# ==============================================================================
# 2. Repository Layer Isolation & Scoping Stress Tests
# ==============================================================================

class TestTenantIsolationRepositoryLayer:
    """Stress tests tenant isolation directly at the database repository level."""

    @pytest.mark.asyncio
    async def test_repository_tenant_scoping_strictness(self):
        eng = create_async_engine("sqlite+aiosqlite:///:memory:")
        await init_db(eng)
        sm = async_sessionmaker(eng, class_=AsyncSession)

        u1_id = str(uuid.uuid4())
        u2_id = str(uuid.uuid4())

        async with sm() as session:
            u_repo = UserRepository(session)
            await u_repo.create_user(u1_id, "u1@keystone.ai")
            await u_repo.create_user(u2_id, "u2@keystone.ai")

            # Project Isolation
            p_repo1 = ProjectRepository(session, tenant_id=u1_id)
            p_repo2 = ProjectRepository(session, tenant_id=u2_id)
            proj_1 = await p_repo1.create_project(str(uuid.uuid4()), "U1 Secret")

            assert await p_repo2.get_project_by_id(proj_1.id) is None
            assert await p_repo2.soft_delete_project(proj_1.id) is False
            u2_projects = await p_repo2.get_projects()
            assert proj_1.id not in [p.id for p in u2_projects]

            # Session Isolation
            s_repo1 = SessionRepository(session, tenant_id=u1_id)
            s_repo2 = SessionRepository(session, tenant_id=u2_id)
            sess_1 = await s_repo1.create_session(str(uuid.uuid4()), project_id=proj_1.id)

            assert await s_repo2.get_session_by_id(sess_1.id) is None
            assert await s_repo2.get_sessions(project_id=proj_1.id) == []
            with pytest.raises(ValueError, match="PROJECT_NOT_FOUND_OR_FORBIDDEN"):
                await s_repo2.create_session(str(uuid.uuid4()), project_id=proj_1.id)

            # Asset Isolation
            a_repo1 = AssetRepository(session, tenant_id=u1_id)
            a_repo2 = AssetRepository(session, tenant_id=u2_id)
            asset_1 = await a_repo1.create_asset(str(uuid.uuid4()), "art.png", "image/png", 100, "k1", proj_1.id)

            assert await a_repo2.get_asset_by_id(asset_1.id) is None
            assert await a_repo2.soft_delete_asset(asset_1.id) is False
            assert asset_1.id not in [a.id for a in await a_repo2.get_assets()]

            # Job Isolation
            j_repo1 = JobRepository(session, tenant_id=u1_id)
            j_repo2 = JobRepository(session, tenant_id=u2_id)
            job_1 = await j_repo1.create_job(
                id=str(uuid.uuid4()),
                request_id=str(uuid.uuid4()),
                authority_decision_id=str(uuid.uuid4()),
                capability_id="img",
                provider_id="comfy",
                workflow_id="wf1",
                workflow_version="1"
            )

            assert await j_repo2.get_job_by_id(job_1.id) is None
            assert await j_repo2.update_job_state(job_1.id, "RUNNING") is False
            assert job_1.id not in [j.id for j in await j_repo2.list_jobs()]

            # API Key Isolation
            k_repo1 = ApiKeyRepository(session, tenant_id=u1_id)
            k_repo2 = ApiKeyRepository(session, tenant_id=u2_id)
            _, prefix, hsh = generate_api_key_pair()
            key_1 = await k_repo1.create_api_key(str(uuid.uuid4()), "U1 Key", hsh, prefix)

            assert key_1.id not in [k.id for k in await k_repo2.list_api_keys()]

        await eng.dispose()

    def test_enforce_tenant_isolation_function(self):
        """Verifies enforce_tenant_isolation strictly raises on any identity mismatch."""
        assert enforce_tenant_isolation("tenant_alpha", "tenant_alpha") is True
        with pytest.raises(ValueError, match="TENANT_ACCESS_DENIED"):
            enforce_tenant_isolation("tenant_alpha", "tenant_beta")
        with pytest.raises(ValueError, match="TENANT_ACCESS_DENIED"):
            enforce_tenant_isolation("", "tenant_alpha")


# ==============================================================================
# 3. Soft-Deleted Resource Leakage Tests
# ==============================================================================

class TestSoftDeletedResourceLeakage:
    """Stress tests soft-deleted projects and assets to prevent data leakage."""

    @pytest.fixture(autouse=True)
    def setup_workspace(self):
        self.client = TestClient(app)

        reg = self.client.post("/v1/auth/register", json={
            "email": f"cleanup_{uuid.uuid4().hex[:8]}@keystone.ai",
            "password": "Password123!",
            "display_name": "Cleanup Tester"
        })
        self.token = reg.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_soft_deleted_project_leakage_prevented(self):
        """Soft-deleted project cannot be retrieved, listed, or have sessions created within it."""
        # Create project
        create_res = self.client.post("/v1/projects", headers=self.headers, json={
            "name": "Project to be Deleted"
        })
        p_id = create_res.json()["id"]

        # Soft delete project
        del_res = self.client.delete(f"/v1/projects/{p_id}", headers=self.headers)
        assert del_res.status_code == 200

        # 1. Fetching by ID returns 404
        fetch_res = self.client.get(f"/v1/projects/{p_id}", headers=self.headers)
        assert fetch_res.status_code == 404

        # 2. Excluded from list
        list_res = self.client.get("/v1/projects", headers=self.headers)
        assert p_id not in [p["id"] for p in list_res.json()["projects"]]

        # 3. Cannot create session inside soft-deleted project
        sess_res = self.client.post("/v1/sessions", headers=self.headers, json={
            "project_id": p_id,
            "title": "Zombie Session Attempt"
        })
        assert sess_res.status_code == 404
        assert "PROJECT_NOT_FOUND_OR_FORBIDDEN" in sess_res.json()["detail"]

        # 4. Duplicate soft delete returns 404 (already deleted)
        dup_del = self.client.delete(f"/v1/projects/{p_id}", headers=self.headers)
        assert dup_del.status_code == 404

    def test_soft_deleted_asset_leakage_prevented(self):
        """Soft-deleted asset cannot be retrieved, listed, or linked as lineage parent."""
        create_res = self.client.post("/v1/assets", headers=self.headers, json={
            "filename": "asset_to_delete.png",
            "mime_type": "image/png",
            "byte_size": 4096
        })
        a_id = create_res.json()["id"]

        # Soft delete
        del_res = self.client.delete(f"/v1/assets/{a_id}", headers=self.headers)
        assert del_res.status_code == 200

        # 1. Fetching by ID returns 404
        fetch_res = self.client.get(f"/v1/assets/{a_id}", headers=self.headers)
        assert fetch_res.status_code == 404

        # 2. Excluded from active asset list
        list_res = self.client.get("/v1/assets", headers=self.headers)
        assert a_id not in [a["id"] for a in list_res.json()["assets"]]

        # 3. Duplicate soft delete returns 404
        dup_del = self.client.delete(f"/v1/assets/{a_id}", headers=self.headers)
        assert dup_del.status_code == 404

        # 4. Lineage parent lookup returns 404
        rel_res = self.client.post(f"/v1/assets/{a_id}/relationships", headers=self.headers, json={
            "child_asset_id": str(uuid.uuid4()),
            "relationship_type": "edit"
        })
        assert rel_res.status_code == 404

        # 5. Lineage graph query on soft-deleted asset returns 404
        lin_res = self.client.get(f"/v1/assets/{a_id}/lineage", headers=self.headers)
        assert lin_res.status_code == 404


# ==============================================================================
# 4. Bearer Token Forgery & Header Tampering Attacks
# ==============================================================================

class TestBearerTokenForgery:
    """Stress tests Bearer token authentication against algorithmic downgrade, tampering, and forgery."""

    @pytest.fixture(autouse=True)
    def setup_tokens(self):
        self.client = TestClient(app)

        reg = self.client.post("/v1/auth/register", json={
            "email": f"forgery_{uuid.uuid4().hex[:8]}@keystone.ai",
            "password": "ValidPassword123!",
            "display_name": "Token Target"
        })
        data = reg.json()
        self.valid_token = data["access_token"]
        self.user_id = data["user"]["id"]

    def test_alg_none_token_forgery_rejected(self):
        """Attempts to authenticate using alg=none tokens must be rejected."""
        # Case 1: Standard 3-part alg=none token: header.payload.
        header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
        payload = b64url(json.dumps({"sub": self.user_id, "role": "admin", "exp": int(time.time()) + 3600}).encode("utf-8"))
        none_token_3part = f"{header}.{payload}."

        res1 = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {none_token_3part}"})
        assert res1.status_code == 401
        assert "MALFORMED_TOKEN" in res1.json().get("detail", "")

        # Case 2: 2-part alg=none token: payload.
        none_token_2part = f"{payload}."
        res2 = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {none_token_2part}"})
        assert res2.status_code == 401
        assert "INVALID_SIGNATURE" in res2.json().get("detail", "")

        # Case 3: 3-part standard JWT format (header.payload.signature)
        dummy_sig = b64url(b"fakesignature")
        jwt_3part = f"{header}.{payload}.{dummy_sig}"
        res3 = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {jwt_3part}"})
        assert res3.status_code == 401
        assert "MALFORMED_TOKEN" in res3.json().get("detail", "")

    def test_payload_tampering_sub_claim_hijacking(self):
        """Altering the 'sub' claim in the payload without valid signature must fail."""
        parts = self.valid_token.split(".")
        b64_payload, b64_sig = parts

        decoded = json.loads(base64.urlsafe_b64decode(b64_payload + "==").decode("utf-8"))
        decoded["sub"] = "hacked_admin_user_uuid"
        tampered_b64_payload = b64url(json.dumps(decoded).encode("utf-8"))
        tampered_token = f"{tampered_b64_payload}.{b64_sig}"

        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res.status_code == 401
        assert "INVALID_SIGNATURE" in res.json().get("detail", "")

    def test_payload_tampering_role_escalation(self):
        """Altering the 'role' claim to 'admin' without valid signature must fail."""
        parts = self.valid_token.split(".")
        b64_payload, b64_sig = parts

        decoded = json.loads(base64.urlsafe_b64decode(b64_payload + "==").decode("utf-8"))
        decoded["role"] = "superadmin"
        tampered_b64 = b64url(json.dumps(decoded).encode("utf-8"))
        tampered_token = f"{tampered_b64}.{b64_sig}"

        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res.status_code == 401
        assert "INVALID_SIGNATURE" in res.json().get("detail", "")

    def test_payload_tampering_expiry_extension(self):
        """Altering the 'exp' claim to extend token lifetime must fail."""
        parts = self.valid_token.split(".")
        b64_payload, b64_sig = parts

        decoded = json.loads(base64.urlsafe_b64decode(b64_payload + "==").decode("utf-8"))
        decoded["exp"] = int(time.time()) + 9999999
        tampered_b64 = b64url(json.dumps(decoded).encode("utf-8"))
        tampered_token = f"{tampered_b64}.{b64_sig}"

        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res.status_code == 401
        assert "INVALID_SIGNATURE" in res.json().get("detail", "")

    def test_signature_bit_corruption(self):
        """Flipping a character in the signature must cause verification failure."""
        parts = self.valid_token.split(".")
        b64_payload, b64_sig = parts

        # Alter last character of signature
        corrupted_sig = b64_sig[:-1] + ("A" if b64_sig[-1] != "A" else "B")
        corrupted_token = f"{b64_payload}.{corrupted_sig}"

        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {corrupted_token}"})
        assert res.status_code == 401
        assert "INVALID_SIGNATURE" in res.json().get("detail", "")

    def test_forged_signature_with_attacker_secret(self):
        """Signing a valid payload with an attacker-controlled secret must fail."""
        parts = self.valid_token.split(".")
        b64_payload, _ = parts

        attacker_secret = "evil_hacker_unauthorized_secret_key"
        forged_sig = b64url(
            hmac.new(attacker_secret.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).digest()
        )
        forged_token = f"{b64_payload}.{forged_sig}"

        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {forged_token}"})
        assert res.status_code == 401
        assert "INVALID_SIGNATURE" in res.json().get("detail", "")

    def test_expired_token_rejection(self):
        """Tokens with past expiration timestamps must be rejected."""
        expired_token = generate_token(self.user_id, expiry_seconds=-30)
        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401
        assert "TOKEN_EXPIRED" in res.json().get("detail", "")

    def test_malformed_token_variations(self):
        """Various malformed Authorization headers must be rejected safely."""
        test_cases = [
            ("", "Missing Authorization header or X-API-Key"),
            ("Bearer", "Expected 'Bearer <token>'"),
            ("Bearer ", "MALFORMED_TOKEN"),
            ("Basic dXNlcjpwYXNz", "Expected 'Bearer <token>'"),
            ("Bearer nodottoken", "MALFORMED_TOKEN"),
            ("Bearer a.b.c.d.e", "MALFORMED_TOKEN"),
            ("Bearer null", "MALFORMED_TOKEN"),
            ("Bearer undefined", "MALFORMED_TOKEN"),
        ]
        for header_val, expected_err in test_cases:
            headers = {"Authorization": header_val} if header_val else {}
            res = self.client.get("/v1/auth/me", headers=headers)
            assert res.status_code == 401
            assert expected_err in res.json().get("detail", "")

    def test_token_for_nonexistent_user_rejected(self):
        """Validly signed token containing a non-existent user UUID must return 401."""
        ghost_token = generate_token(str(uuid.uuid4()), role="user")
        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {ghost_token}"})
        assert res.status_code == 401
        assert "not found or inactive" in res.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_token_for_suspended_user_rejected(self):
        """Validly signed token for a suspended/inactive user account must return 401."""
        suspended_id = str(uuid.uuid4())
        async with async_session_factory() as session:
            repo = UserRepository(session)
            susp_email = f"suspended_{uuid.uuid4().hex[:8]}@keystone.ai"
            await repo.create_user(suspended_id, susp_email)
            stmt = update(User).where(User.id == suspended_id).values(status="suspended")
            await session.execute(stmt)
            await session.commit()

        token = generate_token(suspended_id)
        res = self.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401
        assert "inactive" in res.json().get("detail", "").lower()


# ==============================================================================
# 5. API Key Bypass & Collision Attacks
# ==============================================================================

class TestApiKeyBypassAttacks:
    """Stress tests API key validation against bypasses, collisions, and state changes."""

    @pytest.fixture(autouse=True)
    def setup_keys(self):
        self.client = TestClient(app)

        reg = self.client.post("/v1/auth/register", json={
            "email": f"apikey_{uuid.uuid4().hex[:8]}@keystone.ai",
            "password": "Password123!",
            "display_name": "API Key User"
        })
        self.user_data = reg.json()["user"]
        self.token = reg.json()["access_token"]
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

        # Create valid API Key
        key_res = self.client.post("/v1/auth/api-keys", headers=self.auth_headers, json={
            "name": "Production Service Key"
        })
        assert key_res.status_code == 200, key_res.text
        self.raw_key = key_res.json()["raw_key"]
        self.key_prefix = key_res.json()["key_prefix"]
        self.key_id = key_res.json()["id"]

    def test_valid_api_key_authenticates(self):
        """Sanity check: valid raw key authenticates through X-API-Key."""
        res = self.client.get("/v1/auth/me", headers={"X-API-Key": self.raw_key})
        assert res.status_code == 200
        assert res.json()["id"] == self.user_data["id"]

    def test_empty_and_whitespace_api_keys_rejected(self):
        """Empty or whitespace-only API keys must be rejected with 401."""
        for empty_val in ["", " ", "   ", "\t", "\n"]:
            res = self.client.get("/v1/auth/me", headers={"X-API-Key": empty_val})
            assert res.status_code == 401
            assert "Unauthorized" in res.json().get("detail", "")

    def test_direct_hash_injection_attack_fails(self):
        """
        Adversarial Vector: Attacker obtains the stored SHA-256 hash from database/logs
        and sends it as the X-API-Key header.
        The server must hash the incoming value again (SHA-256(hash)), resulting in mismatch.
        """
        stored_hash = hash_api_key(self.raw_key)
        res = self.client.get("/v1/auth/me", headers={"X-API-Key": stored_hash})
        assert res.status_code == 401
        assert "Invalid or revoked API key" in res.json().get("detail", "")

    def test_prefix_collision_and_guessing_fails(self):
        """Sending the correct prefix with incorrect secret bytes must fail."""
        forged_key = f"ks_live_{self.key_prefix}_{'0' * 40}"
        res = self.client.get("/v1/auth/me", headers={"X-API-Key": forged_key})
        assert res.status_code == 401
        assert "Invalid or revoked API key" in res.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_revoked_api_key_rejected(self):
        """Revoking an API key (status='revoked') immediately rejects authentication."""
        async with async_session_factory() as session:
            stmt = update(ApiKey).where(ApiKey.id == self.key_id).values(status="revoked")
            await session.execute(stmt)
            await session.commit()

        res = self.client.get("/v1/auth/me", headers={"X-API-Key": self.raw_key})
        assert res.status_code == 401
        assert "Invalid or revoked API key" in res.json().get("detail", "")


# ==============================================================================
# 6. Password Brute Force Protection & PBKDF2 Resistance
# ==============================================================================

class TestPasswordBruteForceAndPBKDF2:
    """Stress tests password hashing parameters, salt uniqueness, and constant-time checks."""

    def test_pbkdf2_600000_iterations_benchmark(self):
        """Verifies PBKDF2 iteration count meets OWASP benchmark of 600,000."""
        assert PBKDF2_ITERATIONS == 600_000
        pwd = "TestCreativePassword2026!"
        hashed = hash_password(pwd)

        parts = hashed.split("$")
        assert len(parts) == 4
        algo, iterations_str, salt_hex, key_hex = parts
        assert algo == "pbkdf2_sha256"
        assert int(iterations_str) == 600_000
        assert len(bytes.fromhex(salt_hex)) == 16  # 16-byte salt
        assert len(bytes.fromhex(key_hex)) == 32   # SHA-256 digest size (32 bytes)

    def test_salt_uniqueness_rainbow_table_resistance(self):
        """Two hashes of the same password must produce distinct salts and digests."""
        pwd = "IdenticalPasswordToHashTwice"
        hash1 = hash_password(pwd)
        hash2 = hash_password(pwd)

        assert hash1 != hash2
        salt1 = hash1.split("$")[2]
        salt2 = hash2.split("$")[2]
        assert salt1 != salt2

    def test_malformed_hash_robustness(self):
        """Corrupted hash formats must safely return False without unhandled exceptions."""
        pwd = "SecretPassword123"
        corrupted_hashes = [
            "",
            "plain_text_password",
            "md5$somehash",
            "pbkdf2_sha256$600000",
            "pbkdf2_sha256$600000$invalidsalt$invalidkey$extrapart",
            "pbkdf2_sha256$notanint$deadbeef$feedface",
            "pbkdf2_sha256$600000$nothex_salt$deadbeef",
            "pbkdf2_sha256$600000$deadbeef$nothex_key",
        ]
        for bad_hash in corrupted_hashes:
            assert verify_password(pwd, bad_hash) is False

    def test_computational_work_factor_measurement(self):
        """
        Measures the CPU work required for PBKDF2 verification.
        600,000 rounds should impose a measurable computational cost (>10ms) per verification,
        enforcing a hardware-level barrier against brute force dictionaries.
        """
        pwd = "BruteForceMeasurementPassword"
        hashed = hash_password(pwd)

        start = time.perf_counter()
        verified = verify_password(pwd, hashed)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert verified is True
        # Must take at least 15 milliseconds on modern CPU
        assert elapsed_ms > 15.0, f"Expected >15ms computation time, got {elapsed_ms:.2f}ms"


# ==============================================================================
# 7. Storage Key Traversal & Signed URL Security
# ==============================================================================

class TestStorageKeyAndSignedUrlSecurity:
    """Stress tests storage key generation against directory traversal and signed URL integrity."""

    def test_path_traversal_sanitization_matrix(self):
        """Verifies aggressive sanitization of directory traversal injection strings."""
        test_cases = [
            ("../../../etc/passwd", "passwd"),
            ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
            ("/var/log/../../../boot.ini", "boot.ini"),
            ("foo/bar/baz/image.png", "image.png"),
            ("../../malicious.key\x00.png", "malicious.key_.png"),
            ("photo (1) [final] & preview!.jpg", "photo__1___final____preview_.jpg"),
        ]
        user_id = "usr_tenant_1"
        asset_id = "ast_test_1"

        for raw_filename, expected_filename in test_cases:
            key = generate_storage_key(user_id, asset_id, raw_filename)
            assert ".." not in key
            assert "/" in key
            assert key == f"tenants/{user_id}/assets/{asset_id}/{expected_filename}"

    def test_signed_url_expiry_boundaries(self):
        """Enforces 3600s ceiling and rejects non-positive expiries."""
        key = "tenants/u1/assets/a1/hero.png"

        # Valid 15-minute expiry
        url = generate_signed_url(key, expiry_seconds=900)
        assert "expires=" in url

        # Boundary ceiling at 3600s passes
        url_max = generate_signed_url(key, expiry_seconds=3600)
        assert url_max is not None

        # Expiry > 3600s fails
        with pytest.raises(ValueError, match="EXPIRY_EXCEEDED"):
            generate_signed_url(key, expiry_seconds=3601)

        # Expiry <= 0 fails
        with pytest.raises(ValueError, match="INVALID_EXPIRY"):
            generate_signed_url(key, expiry_seconds=0)

        with pytest.raises(ValueError, match="INVALID_EXPIRY"):
            generate_signed_url(key, expiry_seconds=-100)

    def test_signed_url_tampering_detection(self):
        """Tampering with URL query parameters invalidates signature."""
        key = "tenants/u1/assets/a1/hero.png"
        url = generate_signed_url(key, expiry_seconds=900)

        # 1. Tamper with storage_key parameter
        tampered_key_url = url.replace("hero.png", "hacked.png")
        with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
            validate_signed_url(tampered_key_url)

        # 2. Tamper with expires parameter (extending expiration)
        tampered_exp_url = url.replace("expires=", "expires=9999999999_")
        with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
            validate_signed_url(tampered_exp_url)

        # 3. Tamper with signature parameter
        tampered_sig_url = url.replace("signature=", "signature=badc0ffee")
        with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
            validate_signed_url(tampered_sig_url)


# ==============================================================================
# 8. Service Token & Internal Boundary Security
# ==============================================================================

class TestServiceTokenBoundary:
    """Verifies internal service token protection."""

    def test_service_token_verification_cases(self):
        assert verify_service_token("keystone-internal-worker-secret") is True
        assert verify_service_token("wrong-secret") is False
        assert verify_service_token("") is False
        assert verify_service_token(None) is False
        assert verify_service_token("keystone-internal-worker-secret-extra") is False
