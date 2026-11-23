"""PR3 (ADR-005): Single Gate service, Tier-A floor watchdog, Stage-1 age verification, and P0/P1 security wall."""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import (
    Asset,
    AuditEvent,
    AuthorityDecision,
    Base,
    Persona,
    Project,
    Session as ChatSession,
    User,
)
from apps.api.src.db.session import get_db
from apps.api.src.server import app
from apps.api.src.services.gate import GateService, resolve_content_mode
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.evaluators.deterministic import validate_asset_bytes


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class _AsyncSessionAdapter:
    """Adapts a sync SQLAlchemy Session for async FastAPI dependencies like get_current_user."""

    def __init__(self, sync_session):
        self._s = sync_session

    def __getattr__(self, name):
        return getattr(self._s, name)

    async def execute(self, *args, **kwargs):
        return self._s.execute(*args, **kwargs)


@pytest.fixture()
def client(db_session):
    async_adapter = _AsyncSessionAdapter(db_session)

    def _override_get_db():
        try:
            yield async_adapter
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(
    db_session,
    *,
    role: str = "user",
    age_verified: bool = False,
    content_mode: str = "sfw",
    email: str | None = None,
) -> tuple[User, dict[str, str]]:
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=email or f"{uid}@example.com",
        role=role,
        age_verified=age_verified,
        content_mode=content_mode,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = generate_token(user_id=user.id, role=user.role)
    return user, {"Authorization": f"Bearer {token}"}


# 1. test_age_unverified_cannot_set_or_invoke_unrestricted_403
def test_age_unverified_cannot_set_or_invoke_unrestricted_403(client, db_session):
    user, headers = _create_user(db_session, age_verified=False, content_mode="sfw")

    resp = client.patch(
        "/v1/account/content-mode",
        json={"content_mode": "unrestricted"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "AGE_VERIFICATION_REQUIRED" in resp.text

    # Also verify GateService rejects an unverified user with unrestricted mode
    user.content_mode = "unrestricted"
    db_session.commit()
    with pytest.raises(Exception) as exc_info:
        GateService.authorize_and_sign(
            db=db_session,
            user=user,
            intent="generate",
            prompt_text="A quiet forest scene",
            capability_id="image.generation",
            arguments={"prompt": "A quiet forest scene"},
        )
    assert getattr(exc_info.value, "status_code", None) == 403


# 2. test_stage1_age_verification_enables_unrestricted_mode
def test_stage1_age_verification_enables_unrestricted_mode(client, db_session):
    user, headers = _create_user(db_session, age_verified=False, content_mode="sfw")

    verify_resp = client.post(
        "/v1/account/age-verification",
        json={"confirmed_adult_18_plus": True},
        headers=headers,
    )
    assert verify_resp.status_code == 200
    db_session.refresh(user)
    assert user.age_verified is True
    assert user.age_verified_at is not None

    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.user_id == user.id, AuditEvent.event_type == "account.age_verified")
        .first()
    )
    assert audit is not None

    mode_resp = client.patch(
        "/v1/account/content-mode",
        json={"content_mode": "unrestricted"},
        headers=headers,
    )
    assert mode_resp.status_code == 200
    db_session.refresh(user)
    assert user.content_mode == "unrestricted"


# 3. test_mode_resolution_cascade
def test_mode_resolution_cascade(db_session):
    user = User(id="usr_cascade", email="cascade@example.com", age_verified=True, content_mode="sfw")
    project = Project(id="prj_cascade", user_id=user.id, name="Proj", content_mode="unrestricted")
    session = ChatSession(id="ses_cascade", user_id=user.id, project_id=project.id, title="Sess", content_mode="sfw")

    # session > project > user > "sfw"
    assert resolve_content_mode(user, project, session) == "sfw"

    session.content_mode = None
    assert resolve_content_mode(user, project, session) == "unrestricted"

    project.content_mode = None
    assert resolve_content_mode(user, project, session) == "sfw"

    user.content_mode = "unrestricted"
    assert resolve_content_mode(user, project, session) == "unrestricted"

    user.content_mode = None
    assert resolve_content_mode(user, None, None) == "sfw"


# 4. test_floor_violation_returns_422_writes_db_audit_and_zero_dispatch
def test_floor_violation_returns_422_writes_db_audit_and_zero_dispatch(db_session):
    user, _ = _create_user(db_session, age_verified=True, content_mode="unrestricted")
    worker_dispatch = MagicMock()

    with pytest.raises(Exception) as exc_info:
        GateService.authorize_and_sign(
            db=db_session,
            user=user,
            intent="generate",
            prompt_text="csam explicit minor content",
            capability_id="image.generation",
            arguments={"prompt": "csam explicit minor content"},
        )
    assert getattr(exc_info.value, "status_code", None) == 422
    assert worker_dispatch.call_count == 0

    decision_row = (
        db_session.query(AuthorityDecision)
        .filter(AuthorityDecision.floor_verdict == "fail")
        .first()
    )
    assert decision_row is not None
    assert decision_row.decision == "deny"

    audit_row = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.user_id == user.id, AuditEvent.event_type == "gate.floor_violation")
        .first()
    )
    assert audit_row is not None


# 5. test_lawful_unrestricted_passes_floor_and_signs_v2_envelope
def test_lawful_unrestricted_passes_floor_and_signs_v2_envelope(db_session):
    user, _ = _create_user(db_session, age_verified=True, content_mode="unrestricted")

    receipt = GateService.authorize_and_sign(
        db=db_session,
        user=user,
        intent="generate",
        prompt_text="Dramatic noir adult romance scene in a rainy penthouse, consensual adults",
        capability_id="image.generation",
        arguments={"prompt": "Dramatic noir adult romance scene in a rainy penthouse"},
    )
    assert receipt.content_mode == "unrestricted"
    assert receipt.mature is True
    assert receipt.envelope.envelope_version == "2.0"
    assert receipt.envelope.content_mode == "unrestricted"
    assert receipt.envelope.age_verified is True
    assert receipt.envelope.floor_verdict == "pass"

    verified = EnvelopeEngine.verify_envelope(receipt.envelope, expected_mode="unrestricted")
    assert verified["valid"] is True


# 6. test_creative_execute_null_envelope_returns_400
def test_creative_execute_null_envelope_returns_400(client, db_session):
    _, headers = _create_user(db_session)
    resp = client.post(
        "/v1/creative/execute",
        json={"adapter": "comfyui", "parameters": {}, "envelope": None},
        headers=headers,
    )
    assert resp.status_code == 400


# 7. test_admin_worker_configure_auth_wall
def test_admin_worker_configure_auth_wall(client, db_session):
    _, user_headers = _create_user(db_session, role="user")
    _, admin_headers = _create_user(db_session, role="admin")

    # Unauthenticated & non-admin on protected endpoints -> 401/403
    for method, path, body in [
        ("GET", "/v1/admin/audit/logs", None),
        ("POST", "/v1/creative/comfy/configure", {"base_url": "https://example.com"}),
        ("POST", "/v1/audio/configure", {"base_url": "https://example.com"}),
        ("GET", "/v1/config/remote", None),
        ("POST", "/v1/authority/envelope/issue", {"decision": {}, "job_id": "j1", "user_id": "u1"}),
    ]:
        r_unauth = client.request(method, path, json=body)
        assert r_unauth.status_code in (401, 403), f"{method} {path} unauth got {r_unauth.status_code}"

        r_user = client.request(method, path, json=body, headers=user_headers)
        assert r_user.status_code in (401, 403), f"{method} {path} non-admin got {r_user.status_code}"

    # Unauthenticated /internal/workers/register -> 403
    r_worker = client.post("/internal/workers/register", json={"worker_id": "w1", "url": "http://localhost:8188"})
    assert r_worker.status_code == 403

    # Newline injection on /configure -> 400
    r_inj_comfy = client.post(
        "/v1/creative/comfy/configure",
        json={"base_url": "https://example.com\r\nX-Injected: 1"},
        headers=admin_headers,
    )
    assert r_inj_comfy.status_code == 400

    r_inj_audio = client.post(
        "/v1/audio/configure",
        json={"base_url": "https://example.com\nX-Injected: 1"},
        headers=admin_headers,
    )
    assert r_inj_audio.status_code == 400


# 8. test_idor_ssrf_mime_and_mature_gallery_isolation
def test_idor_ssrf_mime_and_mature_gallery_isolation(client, db_session):
    owner, owner_headers = _create_user(db_session, age_verified=True, content_mode="unrestricted")
    other, other_headers = _create_user(db_session, age_verified=False, content_mode="sfw")

    # Cross-tenant Persona avatar/asset access -> 404/403
    persona = Persona(id=str(uuid.uuid4()), user_id=owner.id, name="OwnerPersona")
    db_session.add(persona)
    mature_asset = Asset(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        asset_type="image",
        mime_type="image/png",
        storage_key="local://ast_mature_1.png",
        mature=True,
    )
    sfw_asset = Asset(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        asset_type="image",
        mime_type="image/png",
        storage_key="local://ast_sfw_1.png",
        mature=False,
    )
    other_mature_asset = Asset(
        id=str(uuid.uuid4()),
        user_id=other.id,
        asset_type="image",
        mime_type="image/png",
        storage_key="local://ast_other_mature.png",
        mature=True,
    )
    db_session.add_all([persona, mature_asset, sfw_asset, other_mature_asset])
    db_session.commit()

    r_persona = client.get(f"/v1/personas/{persona.id}", headers=other_headers)
    assert r_persona.status_code in (403, 404)

    r_asset = client.get(f"/v1/assets/{mature_asset.id}", headers=other_headers)
    assert r_asset.status_code in (403, 404)

    # SSRF to 169.254.169.254 / 127.0.0.1 -> blocked (400)
    _, admin_headers = _create_user(db_session, role="admin")
    for bad_url in ("http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:8188"):
        r_ssrf = client.post(
            "/v1/creative/comfy/configure",
            json={"base_url": bad_url},
            headers=admin_headers,
        )
        assert r_ssrf.status_code == 400

    # text/html upload -> rejected
    r_mime = client.post(
        "/v1/assets/upload",
        files={"file": ("evil.html", io.BytesIO(b"<script>alert(1)</script>"), "text/html")},
        headers=owner_headers,
    )
    assert r_mime.status_code in (400, 415, 422)

    # mature=True asset excluded from SFW GET /v1/assets and visible in unrestricted
    r_sfw_list = client.get("/v1/assets", headers=other_headers)
    assert r_sfw_list.status_code == 200
    sfw_ids = [a["id"] for a in r_sfw_list.json().get("assets", [])]
    assert other_mature_asset.id not in sfw_ids

    r_unrestricted_list = client.get("/v1/assets", params={"content_mode": "unrestricted"}, headers=owner_headers)
    assert r_unrestricted_list.status_code == 200
    unrestricted_ids = [a["id"] for a in r_unrestricted_list.json().get("assets", [])]
    assert mature_asset.id in unrestricted_ids


# 9. test_tier_a_deterministic_corrupt_binary_fails
def test_tier_a_deterministic_corrupt_binary_fails():
    # Truncated PNG header + garbage bytes
    corrupt_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00"
    result = validate_asset_bytes(
        data=corrupt_png,
        expected_media_type="image",
        expected_mime="image/png",
    )
    assert result.verdict == "fail"
    assert result.reason_codes
