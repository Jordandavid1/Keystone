"""tests/test_pr9_billing_age2_c2pa.py
ADR-005 / Bible v2 §21, §25, §27 Verification Suite for PR9:
  1. test_immutable_db_credit_ledger_hold_and_settle
  2. test_dual_rail_stripe_unrestricted_rejected
  3. test_stage_2_age_gate_adult_processor_webhook
  4. test_c2pa_signature_key_independence
"""

import os
import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.src.db.models import Base, CreditAccount, CreditLedger, UsageRecord, User
from apps.api.src.services.credits import (
    deposit,
    hold_for_job,
    settle_hold,
    release_hold,
    get_balance,
)
from apps.api.src.services.c2pa_credentials import (
    sign_c2pa_manifest,
    get_c2pa_signing_key,
)


@pytest.fixture
def billing_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_immutable_db_credit_ledger_hold_and_settle(billing_db):
    user_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    # 1. Deposit
    entry = deposit(billing_db, user_id=user_id, amount=100, processor="stripe", content_mode="sfw")
    billing_db.commit()
    assert entry.entry_type == "topup"
    assert entry.amount == 100

    bal = get_balance(billing_db, user_id)
    assert bal["balance"] == 100

    # 2. Hold 30 credits for a job
    hold = hold_for_job(billing_db, user_id=user_id, job_id=job_id, amount=30, content_mode="sfw", processor="stripe")
    billing_db.commit()
    assert hold.entry_type == "hold"
    assert hold.amount == -30
    assert hold.job_id == job_id

    bal = get_balance(billing_db, user_id)
    assert bal["balance"] == 70

    # 3. Settle hold (actual usage 25, 5 refund)
    settle, usage = settle_hold(
        billing_db,
        user_id=user_id,
        job_id=job_id,
        actual_amount=25,
        capability_id="image.generation",
    )
    billing_db.commit()
    assert settle.entry_type == "settle"
    assert settle.amount == -25
    assert usage.cost_units == 25
    assert usage.job_id == job_id

    bal = get_balance(billing_db, user_id)
    # 70 + 5 (refund difference between 30 and 25) = 75
    assert bal["balance"] == 75


def test_dual_rail_stripe_unrestricted_rejected(billing_db):
    user_id = str(uuid.uuid4())

    # Stripe + unrestricted must be rejected
    with pytest.raises(ValueError, match="DUAL_RAIL_VIOLATION"):
        deposit(billing_db, user_id=user_id, amount=50, processor="stripe", content_mode="unrestricted")

    # Adult processor (ccbill) + unrestricted must be accepted
    entry = deposit(billing_db, user_id=user_id, amount=50, processor="ccbill", content_mode="unrestricted")
    billing_db.commit()
    assert entry.processor == "ccbill"
    assert entry.amount == 50


def test_stage_2_age_gate_adult_processor_webhook(billing_db):
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email="creator@example.com",
        password_hash="testhash",
        age_verified=False,
        content_mode="sfw",
    )
    billing_db.add(user)
    billing_db.commit()

    from apps.api.src.routers.billing import handle_adult_processor_webhook, AdultProcessorWebhookRequest

    req = AdultProcessorWebhookRequest(
        user_id=user_id,
        event_type="card_verified",
        processor="ccbill",
        credits=50,
    )
    res = handle_adult_processor_webhook(req, db=billing_db)
    assert res["status"] == "success"
    assert res["age_verified"] is True
    assert res["method"] == "card_ccbill"

    # Verify user state updated in DB
    updated_user = billing_db.query(User).filter(User.id == user_id).first()
    assert updated_user.age_verified is True
    assert updated_user.content_mode == "unrestricted"
    assert updated_user.age_verification_method == "card_ccbill"


def test_c2pa_signature_key_independence(monkeypatch):
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "envelope-secret-key-abc")
    monkeypatch.setenv("KEYSTONE_C2PA_SIGNING_KEY", "c2pa-dedicated-signing-key-xyz")

    key = get_c2pa_signing_key()
    assert key == "c2pa-dedicated-signing-key-xyz"
    assert key != os.getenv("KEYSTONE_ENVELOPE_SECRET")

    manifest = sign_c2pa_manifest(
        asset_id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        title="Test Asset",
    )
    assert manifest["c2pa_version"] == "2.0.0"
    assert "signature" in manifest
    assert len(manifest["signature"]) == 64  # SHA256 hex length
    assert manifest["claim"]["title"] == "Test Asset"

    # Key collision check raises ValueError
    monkeypatch.setenv("KEYSTONE_C2PA_SIGNING_KEY", "envelope-secret-key-abc")
    with pytest.raises(ValueError, match="C2PA_KEY_COLLISION"):
        get_c2pa_signing_key()
