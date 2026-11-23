"""tests/test_pr9_billing_age2_c2pa.py
ADR-005 / Bible v2 §21, §25, §27, §40, §43 Verification Suite for PR9:
  1. test_credit_hold_settle_release_idempotent_no_double_charge
  2. test_dual_rail_blocks_stripe_for_unrestricted
  3. test_stage2_adult_processor_webhook_verifies_age_and_deposits
  4. test_c2pa_manifest_stamped_with_separate_key
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import struct
import uuid
import zlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import (
    Asset,
    AuditEvent,
    Base,
    CreditAccount,
    CreditLedger,
    Job,
    Project,
    UsageRecord,
    User,
)
from apps.api.src.db.session import get_db
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.routers.billing import billing_manager
from apps.api.src.server import app
from apps.api.src.services.c2pa_credentials import (
    get_c2pa_signing_key,
    sign_c2pa_manifest,
    verify_c2pa_manifest,
)
from apps.api.src.services.credits import (
    deposit,
    get_balance,
    get_transactions,
    hold_for_job,
    release_hold,
    settle_hold,
)
from apps.api.src.services.gate import GateService
from services.authority.src.credits_ledger import credits_ledger
from services.workers.src.worker import KeystoneWorker


def _make_png_bytes(width: int = 16, height: int = 16) -> bytes:
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x40\x80\xc0" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")


class _AsyncSessionAdapter:
    """Adapts a sync SQLAlchemy Session for async FastAPI dependencies & KeystoneWorker."""

    def __init__(self, sync_session):
        self._s = sync_session

    def __getattr__(self, name):
        return getattr(self._s, name)

    async def execute(self, *args, **kwargs):
        return self._s.execute(*args, **kwargs)

    async def commit(self):
        return self._s.commit()

    async def flush(self):
        return self._s.flush()

    async def refresh(self, instance, *args, **kwargs):
        return self._s.refresh(instance, *args, **kwargs)

    async def rollback(self):
        return self._s.rollback()

    async def close(self):
        return None


@pytest.fixture()
def billing_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(billing_db):
    billing_manager.clear()
    credits_ledger.clear()
    adapter = _AsyncSessionAdapter(billing_db)

    def _override_get_db():
        try:
            yield adapter
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(db, *, age_verified: bool = False, content_mode: str = "sfw") -> tuple[User, dict[str, str]]:
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"bill_{uid[:8]}@example.com",
        password_hash="testhash",
        role="user",
        age_verified=age_verified,
        content_mode=content_mode,
    )
    db.add(user)
    db.commit()
    token = generate_token(user_id=user.id, role=user.role)
    return user, {"Authorization": f"Bearer {token}"}


def test_credit_hold_settle_release_idempotent_no_double_charge(client, billing_db):
    user, headers = _create_user(billing_db)
    job_1 = str(uuid.uuid4())
    job_2 = str(uuid.uuid4())
    job_worker = str(uuid.uuid4())

    # 1. Idempotent deposit (duplicate idempotency_key credits only once)
    e1 = deposit(
        billing_db,
        user_id=user.id,
        amount=100,
        processor="stripe",
        content_mode="sfw",
        idempotency_key="topup_once",
    )
    e2 = deposit(
        billing_db,
        user_id=user.id,
        amount=100,
        processor="stripe",
        content_mode="sfw",
        idempotency_key="topup_once",
    )
    billing_db.commit()
    assert e1.id == e2.id
    bal = get_balance(billing_db, user.id)
    assert bal["balance"] == 100
    assert bal["held"] == 0

    # 2. Idempotent hold (duplicate idempotency_key holds only once)
    h1 = hold_for_job(
        billing_db,
        user_id=user.id,
        job_id=job_1,
        amount=30,
        content_mode="sfw",
        idempotency_key=f"hold:{job_1}",
    )
    h2 = hold_for_job(
        billing_db,
        user_id=user.id,
        job_id=job_1,
        amount=30,
        content_mode="sfw",
        idempotency_key=f"hold:{job_1}",
    )
    billing_db.commit()
    assert h1.id == h2.id
    bal = get_balance(billing_db, user.id)
    assert bal["balance"] == 70
    assert bal["held"] == 30

    # 3. Settle hold with usage record (actual=25, 5 refunded, held drops to 0)
    s1, u1 = settle_hold(
        billing_db,
        user_id=user.id,
        job_id=job_1,
        actual_amount=25,
        capability_id="image.generation",
        vram_minutes=0.25,
        eval_seconds=0.42,
    )
    s2, _ = settle_hold(
        billing_db,
        user_id=user.id,
        job_id=job_1,
        actual_amount=25,
        capability_id="image.generation",
    )
    billing_db.commit()
    assert s1.id == s2.id
    assert u1.vram_minutes == pytest.approx(0.25)
    assert u1.evaluator_ms == 420
    assert u1.cost_units == 25

    bal = get_balance(billing_db, user.id)
    assert bal["balance"] == 75
    assert bal["held"] == 0

    # 4. Release hold on failed job restores full balance & clears held amount
    hold_for_job(
        billing_db,
        user_id=user.id,
        job_id=job_2,
        amount=40,
        content_mode="sfw",
        idempotency_key=f"hold:{job_2}",
    )
    assert get_balance(billing_db, user.id)["held"] == 40
    rel = release_hold(billing_db, user_id=user.id, job_id=job_2, reason="worker_crash")
    billing_db.commit()
    assert rel is not None and rel.entry_type == "release"
    bal = get_balance(billing_db, user.id)
    assert bal["balance"] == 75
    assert bal["held"] == 0

    # 5. Live KeystoneWorker executes a job with credit_cost=15 -> hold -> settle -> UsageRecord
    receipt = GateService.authorize_and_sign(
        db=billing_db,
        user=user,
        intent="generate",
        prompt_text="Scenic alpine valley at sunrise",
        capability_id="image.generation",
        arguments={"prompt": "Scenic alpine valley at sunrise"},
    )
    job_id = receipt.job_id
    png_bytes = _make_png_bytes()

    async def _mock_exec(env, payload, verified):
        return {"bytes": png_bytes, "mime_type": "image/png", "asset_id": str(uuid.uuid4())}

    worker = KeystoneWorker(executor=_mock_exec, enforce_khf=False)
    res = asyncio.run(
        worker.process_job(
            {
                "job_id": job_id,
                "user_id": user.id,
                "envelope": receipt.envelope.model_dump(),
                "credit_cost": 15,
            },
            db=_AsyncSessionAdapter(billing_db),
        )
    )
    assert res.status == "COMPLETED"
    bal_after_worker = get_balance(billing_db, user.id)
    assert bal_after_worker["balance"] == 60
    assert bal_after_worker["held"] == 0
    assert (
        billing_db.query(UsageRecord).filter(UsageRecord.user_id == user.id, UsageRecord.job_id == job_id).first()
        is not None
    )

    # 6. HTTP /v1/billing/balance and /v1/billing/transactions query DB ledger accurately
    http_bal = client.get("/v1/billing/balance", headers=headers)
    assert http_bal.status_code == 200
    assert http_bal.json()["balance"] == 60
    assert http_bal.json()["held"] == 0

    http_txs = client.get("/v1/billing/transactions", headers=headers)
    assert http_txs.status_code == 200
    assert len(http_txs.json()) >= 5


def test_dual_rail_blocks_stripe_for_unrestricted(client, billing_db):
    user, headers = _create_user(billing_db, age_verified=True, content_mode="unrestricted")

    # 1. Service-level Stripe + unrestricted rejected
    with pytest.raises(ValueError, match="PROCESSOR_MODE_VIOLATION"):
        deposit(billing_db, user_id=user.id, amount=50, processor="stripe", content_mode="unrestricted")

    # 2. Service-level Adult rail + unrestricted succeeds for age-verified user
    entry = deposit(billing_db, user_id=user.id, amount=50, processor="adult_rail", content_mode="unrestricted")
    billing_db.commit()
    assert entry.processor == "adult_rail"
    assert entry.amount == 50

    # 3. HTTP Stripe webhook carrying content_mode="unrestricted" rejected with 400
    unrestricted_event = {
        "id": f"evt_unres_{uuid.uuid4().hex[:8]}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"user_id": user.id, "credits": "100", "content_mode": "unrestricted"}
            }
        },
    }
    raw = json.dumps(unrestricted_event).encode("utf-8")
    sig = hmac.new(
        os.environ["STRIPE_WEBHOOK_SECRET"].encode("utf-8"),
        raw,
        hashlib.sha256,
    ).hexdigest()
    bad_webhook = client.post(
        "/v1/billing/webhook",
        content=raw,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig},
    )
    assert bad_webhook.status_code == 400
    assert "PROCESSOR_MODE_VIOLATION" in bad_webhook.text

    # 4. Checkout session with unrestricted rejected with 400
    bad_checkout = client.post(
        "/v1/billing/checkout/session",
        headers=headers,
        json={"user_id": user.id, "tier": "pro", "content_mode": "unrestricted"},
    )
    assert bad_checkout.status_code == 400

    # 5. Valid Stripe SFW webhook writes DB credit deposit
    sfw_event = {
        "id": f"evt_sfw_{uuid.uuid4().hex[:8]}",
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"user_id": user.id, "credits": "75", "content_mode": "sfw"}}},
    }
    raw_sfw = json.dumps(sfw_event).encode("utf-8")
    sig_sfw = hmac.new(
        os.environ["STRIPE_WEBHOOK_SECRET"].encode("utf-8"),
        raw_sfw,
        hashlib.sha256,
    ).hexdigest()
    ok_webhook = client.post(
        "/v1/billing/webhook",
        content=raw_sfw,
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_sfw},
    )
    assert ok_webhook.status_code == 200
    assert get_balance(billing_db, user.id)["balance"] == 125


def test_stage2_adult_processor_webhook_verifies_age_and_deposits(client, billing_db):
    user, _ = _create_user(billing_db, age_verified=False, content_mode="sfw")
    event_id = f"ap_evt_{uuid.uuid4().hex[:10]}"

    payload_dict = {
        "event_id": event_id,
        "user_id": user.id,
        "event_type": "card_verified",
        "processor": "adult_rail",
        "credits": 60,
        "card_last4": "4242",
    }
    raw = json.dumps(payload_dict).encode("utf-8")
    secret = os.environ["ADULT_PROCESSOR_WEBHOOK_SECRET"]
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()

    # 1. Invalid HMAC signature rejected
    bad_sig_resp = client.post(
        "/v1/billing/webhooks/adult-processor",
        content=raw,
        headers={"Content-Type": "application/json", "X-Adult-Processor-Signature": "bad_hex"},
    )
    assert bad_sig_resp.status_code == 400
    assert "INVALID_ADULT_PROCESSOR_SIGNATURE" in bad_sig_resp.text

    # 2. Valid HMAC marks age_verified=True (card_adult_processor), deposits credits, writes AuditEvent
    ok_resp = client.post(
        "/v1/billing/webhooks/adult-processor",
        content=raw,
        headers={"Content-Type": "application/json", "X-Adult-Processor-Signature": sig},
    )
    assert ok_resp.status_code == 200, ok_resp.text
    data = ok_resp.json()
    assert data["status"] == "success"
    assert data["duplicate"] is False
    assert data["age_verified"] is True
    assert data["method"] == "card_adult_processor"
    assert data["credits_added"] == 60

    billing_db.refresh(user)
    assert user.age_verified is True
    assert user.age_verification_method == "card_adult_processor"
    assert get_balance(billing_db, user.id)["balance"] == 60
    assert (
        billing_db.query(AuditEvent)
        .filter(AuditEvent.user_id == user.id, AuditEvent.event_type == "account.age_verified_stage2")
        .first()
        is not None
    )

    # 3. Replaying identical event_id is idempotent and does NOT double-credit
    dup_resp = client.post(
        "/v1/billing/webhooks/adult-processor",
        content=raw,
        headers={"Content-Type": "application/json", "X-Adult-Processor-Signature": sig},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["duplicate"] is True
    assert dup_resp.json()["status"] == "ALREADY_PROCESSED"
    assert get_balance(billing_db, user.id)["balance"] == 60


def test_c2pa_manifest_stamped_with_separate_key(client, billing_db, monkeypatch):
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "envelope-secret-key-abc")
    monkeypatch.setenv("KEYSTONE_C2PA_SIGNING_KEY", "c2pa-dedicated-signing-key-xyz")

    key = get_c2pa_signing_key()
    assert key == "c2pa-dedicated-signing-key-xyz"
    assert key != os.getenv("KEYSTONE_ENVELOPE_SECRET")

    user, headers = _create_user(billing_db, age_verified=True, content_mode="sfw")
    asset_bytes = _make_png_bytes(32, 32)
    asset_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # 1. AssetRepository auto-stamps c2pa_manifest & checksum when asset_bytes supplied
    repo = AssetRepository(_AsyncSessionAdapter(billing_db), tenant_id=user.id)
    created = asyncio.run(
        repo.create_asset(
            id=asset_id,
            filename="hero_render.png",
            mime_type="image/png",
            byte_size=len(asset_bytes),
            storage_key=f"tenants/{user.id}/assets/{asset_id}/hero_render.png",
            media_type="image",
            asset_bytes=asset_bytes,
            content_mode="sfw",
            fabric="comfyui",
            job_id=job_id,
            metadata={"job_id": job_id},
        )
    )
    billing_db.commit()

    assert created.c2pa_manifest is not None
    assert created.c2pa_manifest["platform"] == "KEYSTONE"
    assert created.c2pa_manifest["asset_sha256"] == hashlib.sha256(asset_bytes).hexdigest()
    assert verify_c2pa_manifest(created.c2pa_manifest, asset_bytes=asset_bytes) is True

    # 2. HTTP GET /v1/assets/{id}/credentials returns persisted signed manifest
    cred_resp = client.get(f"/v1/assets/{asset_id}/credentials", headers=headers)
    assert cred_resp.status_code == 200, cred_resp.text
    assert cred_resp.json()["signature"] == created.c2pa_manifest["signature"]

    # 3. Pre-existing asset without c2pa_manifest still signs lazily without asset.job_id AttributeError
    legacy_aid = str(uuid.uuid4())
    legacy_asset = Asset(
        id=legacy_aid,
        user_id=user.id,
        asset_type="image",
        storage_key=f"tenants/{user.id}/assets/{legacy_aid}/legacy.png",
        filename="legacy.png",
        mime_type="image/png",
        size_bytes=128,
        metadata_={"kind": "legacy"},
    )
    billing_db.add(legacy_asset)
    billing_db.commit()

    legacy_cred_resp = client.get(f"/v1/assets/{legacy_aid}/credentials", headers=headers)
    assert legacy_cred_resp.status_code == 200, legacy_cred_resp.text
    assert verify_c2pa_manifest(legacy_cred_resp.json()) is True

    # 4. Key collision with KEYSTONE_ENVELOPE_SECRET is rejected
    monkeypatch.setenv("KEYSTONE_C2PA_SIGNING_KEY", "envelope-secret-key-abc")
    with pytest.raises(ValueError, match="C2PA_KEY_COLLISION"):
        get_c2pa_signing_key()
