"""
Milestone M6 E2E Test Suite: Cloud Run Deployment & Live Integration (F29–F31)
Empirical verification of Cloud Run manifests, GDPR Article 17 cascading erasure,
and PII vault context auditing.
"""

from __future__ import annotations

import os
import sys
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.server import app
from packages.security.gdpr_erasure import GdprErasureService
from services.authority.src.credits_ledger import credits_ledger


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Section 1: Cloud Run Deployment Manifests (F29)
# ============================================================================

class TestCloudRunDeploymentManifests:
    """Verifies Cloud Run service config, Dockerfile, and port 8000 invariant."""

    def test_service_yaml_structure_and_port_invariant(self):
        service_yaml_path = REPO_ROOT / "infrastructure" / "cloudrun" / "service.yaml"
        assert service_yaml_path.exists(), "infrastructure/cloudrun/service.yaml must exist"

        content = service_yaml_path.read_text(encoding="utf-8")

        assert "apiVersion: serving.knative.dev/v1" in content
        assert "kind: Service" in content
        assert "name: keystone-api" in content
        assert "containerPort: 8000" in content, "Cloud Run port must strictly be 8000"

        # Check resource limits
        assert "cpu:" in content
        assert "memory:" in content

        # Check pinned cognition checkpoint
        assert "huihui-ai/Huihui-Qwen3.8-27B-abliterated" in content
        assert "KEYSTONE_ENVELOPE_SECRET" in content
        assert "STRIPE_WEBHOOK_SECRET" in content

    def test_dockerfile_multi_stage_and_port(self):
        dockerfile_path = REPO_ROOT / "infrastructure" / "cloudrun" / "Dockerfile"
        assert dockerfile_path.exists(), "infrastructure/cloudrun/Dockerfile must exist"

        df_content = dockerfile_path.read_text(encoding="utf-8")
        assert "EXPOSE 8000" in df_content
        assert "apps.api.src.server:app" in df_content
        assert "FROM python:" in df_content

    def test_cloudbuild_pipeline_steps(self):
        cb_path = REPO_ROOT / "infrastructure" / "cloudrun" / "cloudbuild.yaml"
        assert cb_path.exists(), "infrastructure/cloudrun/cloudbuild.yaml must exist"

        cb_content = cb_path.read_text(encoding="utf-8")
        assert "steps:" in cb_content
        assert "keystone-api" in cb_content
        assert "replace" in cb_content


# ============================================================================
# Section 2: GDPR Article 17 Cascading Erasure & PII Vault Audit (F30)
# ============================================================================

class TestGdprErasureAndPiiAudit:
    """Verifies right to erasure and PII context cleanliness."""

    def test_audit_prompt_context_flags_raw_pii(self):
        # Email leak in context
        context_with_email = [
            "Project aesthetic: Cyberpunk realism",
            "Contact user at jordan.maxwell@example.com for approvals"
        ]
        res1 = GdprErasureService.audit_prompt_context(context_with_email)
        assert res1["compliant"] is False
        assert "jordan.maxwell@example.com" in res1["violation"]

        # Phone leak in context
        context_with_phone = [
            "Asset: warrior_hero.png",
            "Direct hotline: +1 (555) 234-5678"
        ]
        res2 = GdprErasureService.audit_prompt_context(context_with_phone)
        assert res2["compliant"] is False
        assert "+1 (555) 234-5678" in res2["violation"]

    def test_audit_prompt_context_clean_context_passes(self):
        clean_context = [
            "Project objective: High fashion editorial portrait",
            "Tokenized subject: <pii_token:person_7f3d>",
            "Lighting: soft volumetric morning illumination"
        ]
        res = GdprErasureService.audit_prompt_context(clean_context)
        assert res["compliant"] is True
        assert res["violation"] is None

    def test_cascading_erasure_anonymizes_ledger(self):
        user_to_erase = "user_gdpr_subject_01"
        credits_ledger.clear()
        credits_ledger.topup(user_to_erase, 200, reason="Initial grant")
        credits_ledger.hold(user_to_erase, 50, job_id="job_gdpr_01")

        # Prior to erasure, entries carry user_to_erase
        assert any(e["account_id"] == user_to_erase for e in credits_ledger.get_entries())

        # Execute cascading erasure
        cert = GdprErasureService.cascade_erase_user(user_to_erase)
        assert cert["status"] == "ERASED"
        assert cert["user_id"] == user_to_erase
        assert cert["cascaded_entities"]["ledger_entries_anonymized"] >= 2

        # Post-erasure, zero ledger entries carry user_to_erase; all are replaced with ANONYMIZED_GDPR_USER
        assert not any(e["account_id"] == user_to_erase for e in credits_ledger.get_entries())
        assert any(e["account_id"] == "ANONYMIZED_GDPR_USER" for e in credits_ledger.get_entries())
