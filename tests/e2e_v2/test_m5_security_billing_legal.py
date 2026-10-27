"""
Milestone M5 E2E Test Suite: Security, Policies, Legal & Credits (F24–F28)
Empirical verification of append-only credits ledger, Stripe webhook idempotency,
proprietary secret scanner, 10 legal policies, and admin telemetry.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.server import app
from apps.api.src.routers.billing import billing_manager, DEFAULT_STRIPE_WEBHOOK_SECRET
from services.authority.src.credits_ledger import credits_ledger, CreditsLedgerEngine
from packages.security.secret_scanner import ProprietaryPolicyService, COPYRIGHT_STATEMENT


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Section 1: Credits Ledger Two-Phase Commitment (F25)
# ============================================================================

class TestCreditsLedgerEngine:
    """Verifies append-only ledger, two-phase holds, settlement, release, and refund."""

    def setup_method(self):
        credits_ledger.clear()

    def test_initial_balance_and_available(self):
        ledger = CreditsLedgerEngine(default_initial_balance=100)
        assert ledger.get_available_balance("acc_1") == 100
        assert ledger.get_held_balance("acc_1") == 0

    def test_hold_lifecycle_successful_settlement(self):
        ledger = CreditsLedgerEngine(default_initial_balance=100)
        hold_id = ledger.hold(account_id="acc_1", amount=25, job_id="job_001")
        assert hold_id.startswith("hold_")
        assert ledger.get_available_balance("acc_1") == 75
        assert ledger.get_held_balance("acc_1") == 25

        # Settle the hold
        settled = ledger.settle(hold_id)
        assert settled is True
        assert ledger.get_available_balance("acc_1") == 75  # Kept deducted
        assert ledger.get_held_balance("acc_1") == 0       # No longer held

    def test_hold_lifecycle_release(self):
        ledger = CreditsLedgerEngine(default_initial_balance=100)
        hold_id = ledger.hold(account_id="acc_1", amount=40, job_id="job_002")
        assert ledger.get_available_balance("acc_1") == 60
        assert ledger.get_held_balance("acc_1") == 40

        # Release the hold back to available
        released = ledger.release(hold_id)
        assert released is True
        assert ledger.get_available_balance("acc_1") == 100
        assert ledger.get_held_balance("acc_1") == 0

    def test_hold_exceeding_balance_fails(self):
        ledger = CreditsLedgerEngine(default_initial_balance=50)
        with pytest.raises(ValueError, match="INSUFFICIENT_CREDITS"):
            ledger.hold(account_id="acc_poor", amount=60, job_id="job_too_costly")

    def test_double_settlement_rejected(self):
        ledger = CreditsLedgerEngine(default_initial_balance=100)
        hold_id = ledger.hold(account_id="acc_1", amount=10, job_id="job_003")
        ledger.settle(hold_id)
        with pytest.raises(ValueError, match="HOLD_ALREADY_FINALIZED"):
            ledger.settle(hold_id)

    def test_double_release_rejected(self):
        ledger = CreditsLedgerEngine(default_initial_balance=100)
        hold_id = ledger.hold(account_id="acc_1", amount=10, job_id="job_004")
        ledger.release(hold_id)
        with pytest.raises(ValueError, match="HOLD_ALREADY_FINALIZED"):
            ledger.release(hold_id)

    def test_refund_and_topup(self):
        ledger = CreditsLedgerEngine(default_initial_balance=10)
        ledger.refund(account_id="acc_1", amount=15, reason="SLA compensation")
        assert ledger.get_available_balance("acc_1") == 25

        ledger.topup(account_id="acc_1", amount=100, reason="Purchased 100 credits")
        assert ledger.get_available_balance("acc_1") == 125
        assert len(ledger.get_entries("acc_1")) == 2


# ============================================================================
# Section 2: Stripe Billing & Idempotent Webhook Processing (F26)
# ============================================================================

class TestStripeBilling:
    """Verifies Stripe webhook HMAC signature checking and event deduplication."""

    def setup_method(self):
        billing_manager.clear()
        credits_ledger.clear()

    def _sign_payload(self, payload_dict: dict, secret: str = DEFAULT_STRIPE_WEBHOOK_SECRET) -> str:
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    def test_valid_webhook_adds_credits(self, client: TestClient):
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        user_id = "user_stripe_test_1"
        payload = {
            "id": event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"user_id": user_id, "credits": "150"}
                }
            }
        }
        raw_bytes = json.dumps(payload).encode("utf-8")
        sig = hmac.new(DEFAULT_STRIPE_WEBHOOK_SECRET.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

        res = client.post(
            "/v1/billing/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "PROCESSED"
        assert data["duplicate"] is False
        assert data["credits_added"] == 150
        assert credits_ledger.get_available_balance(user_id) == 250  # 100 initial + 150 topup

    def test_duplicate_webhook_is_idempotent(self, client: TestClient):
        event_id = f"evt_idempotent_{uuid.uuid4().hex[:8]}"
        user_id = "user_stripe_test_2"
        payload = {
            "id": event_id,
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_123",
                    "metadata": {"user_id": user_id, "credits": "100"}
                }
            }
        }
        raw_bytes = json.dumps(payload).encode("utf-8")
        sig = hmac.new(DEFAULT_STRIPE_WEBHOOK_SECRET.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

        # First request
        res1 = client.post(
            "/v1/billing/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig}
        )
        assert res1.status_code == 200
        assert res1.json()["duplicate"] is False
        assert credits_ledger.get_available_balance(user_id) == 200

        # Duplicate request (Replay attack / network retry)
        res2 = client.post(
            "/v1/billing/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "Stripe-Signature": sig}
        )
        assert res2.status_code == 200
        assert res2.json()["duplicate"] is True
        assert res2.json()["status"] == "ALREADY_PROCESSED"
        # Credits must NOT be added twice!
        assert credits_ledger.get_available_balance(user_id) == 200

    def test_tampered_signature_rejected(self, client: TestClient):
        payload = {"id": "evt_tampered", "type": "checkout.session.completed"}
        raw_bytes = json.dumps(payload).encode("utf-8")

        res = client.post(
            "/v1/billing/webhook",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "Stripe-Signature": "invalid_hex_signature"}
        )
        assert res.status_code == 400
        assert "INVALID_STRIPE_SIGNATURE" in res.json()["detail"]


# ============================================================================
# Section 3: Proprietary Policy & Secret Scanner (F27)
# ============================================================================

class TestSecretScannerAndProprietaryPolicy:
    """Verifies pre-push secret scanning and closed-source compliance."""

    def test_detects_live_credentials(self):
        # 1. Stripe live key
        s1 = ProprietaryPolicyService.scan_content_for_secrets("export STRIPE_KEY=sk_live_1234567890abcdef123456")
        assert s1["hasSecrets"] is True

        # 2. GitHub Token
        s2 = ProprietaryPolicyService.scan_content_for_secrets("token: ghp_1234567890abcdef1234567890abcdef")
        assert s2["hasSecrets"] is True

        # 3. AWS Key
        s3 = ProprietaryPolicyService.scan_content_for_secrets("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
        assert s3["hasSecrets"] is True

        # 4. Google API Key
        s4 = ProprietaryPolicyService.scan_content_for_secrets("key=AIzaSyD-1234567890abcdefghijklmnopqrstuv")
        assert s4["hasSecrets"] is True

        # 5. RSA Private Key
        s5 = ProprietaryPolicyService.scan_content_for_secrets("-----BEGIN RSA PRIVATE KEY-----\nMIIEow...")
        assert s5["hasSecrets"] is True

    def test_clean_content_passes_scan(self):
        clean = "def generate_image(prompt: str) -> dict:\n    return {'status': 'ok'}"
        res = ProprietaryPolicyService.scan_content_for_secrets(clean)
        assert res["hasSecrets"] is False
        assert len(res["violations"]) == 0

    def test_closed_source_enforcement(self):
        # Public repo must fail
        pub = ProprietaryPolicyService.verify_closed_source_compliance("https://github.com/org/keystone", is_private=False)
        assert pub["compliant"] is False
        assert "PUBLIC_REPOSITORY_PROHIBITED" in pub["reason"]

        # Private repo passes
        priv = ProprietaryPolicyService.verify_closed_source_compliance("git@github.com:org/keystone.git", is_private=True)
        assert priv["compliant"] is True
        assert priv["copyright"] == COPYRIGHT_STATEMENT


# ============================================================================
# Section 4: 10 Commercial Legal Policies (F28)
# ============================================================================

class TestLegalPoliciesSuite:
    """Verifies all 10 required commercial legal policy documents exist."""

    REQUIRED_POLICIES = [
        "privacy_policy.md",
        "terms_of_service.md",
        "acceptable_use.md",
        "retention_and_deletion.md",
        "cookie_notice.md",
        "copyright_and_ip.md",
        "refund_terms.md",
        "subprocessors.md",
        "model_and_license_inventory.md",
        "premium_local_agreement.md"
    ]

    def test_all_ten_policies_exist_and_non_empty(self):
        legal_dir = REPO_ROOT / "docs" / "legal"
        assert legal_dir.exists(), "docs/legal directory must exist"

        for policy_name in self.REQUIRED_POLICIES:
            p_file = legal_dir / policy_name
            assert p_file.exists(), f"Missing required legal policy: {policy_name}"
            content = p_file.read_text(encoding="utf-8")
            assert len(content.strip()) > 100, f"Policy {policy_name} is too brief or empty"
            assert "Jordan Maxwell" in content or "KEYSTONE" in content


# ============================================================================
# Section 5: Operator Admin Console & Telemetry (F24)
# ============================================================================

class TestAdminConsoleEndpoints:
    """Verifies /v1/admin endpoints."""

    def test_get_telemetry(self, client: TestClient):
        res = client.get("/v1/admin/telemetry")
        assert res.status_code == 200
        data = res.json()
        assert "active_workers" in data
        assert "gpu_vram_utilization_pct" in data
        assert "host_ram_used_bytes" in data
        assert "queue_depth" in data
        assert data["copyright"] == COPYRIGHT_STATEMENT

    def test_get_audit_logs(self, client: TestClient):
        res = client.get("/v1/admin/audit/logs")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_legal_policies_endpoint(self, client: TestClient):
        res = client.get("/v1/admin/legal/policies")
        assert res.status_code == 200
        data = res.json()
        assert data["policy_count"] == 10
        assert len(data["policies"]) == 10
