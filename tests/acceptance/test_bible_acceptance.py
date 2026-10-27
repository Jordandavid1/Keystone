"""
KEYSTONE Bible §35 Acceptance Test Automation Suite
Empirical verification of 6 Identity Tests and 7 Authority Tests.
Adheres strictly to KEYSTONE_BIBLE.md (§2, §34, §35).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.server import app
from apps.api.src.main import PlanRequest
from packages.prompt_engine.engine import generate
from packages.prompt_engine.compiler import PromptCompiler
from packages.prompt_engine.playbooks import PlaybookRegistry, PLAYBOOK_IDS
from services.authority.src.engine import AuthorityEngine, authority_engine
from services.authority.src.rules import CAPABILITY_NAMESPACES
from services.harness.src.envelope import EnvelopeEngine, generate_signature
from services.harness.src.worker_bridge import worker_bridge
from packages.contracts.src.models import (
    AuthorityDecision,
    ExecutionEnvelope,
    PromptAnatomy,
    PromptIntent,
    ProposedAction
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Section 1: Bible §35.1 — The Six Identity Tests
# ============================================================================

class TestBibleIdentityAcceptance:
    """The 6 Identity Tests mandated by KEYSTONE Bible §35."""

    def test_identity_01_product_name_remains_keystone(self, client: TestClient):
        """Identity Test 1: Product name remains KEYSTONE."""
        res = client.get("/v1/contracts")
        assert res.status_code == 200
        data = res.json()
        assert data["product"] == "KEYSTONE"
        assert app.title == "KEYSTONE API"

    def test_identity_02_plan_v1_output_remains_valid(self):
        """Identity Test 2: generate(goal, options) -> plan.v1 remains a supported contract."""
        plan = generate("Generate a sci-fi city concept video", {"duration": 5})
        assert isinstance(plan, dict)
        assert plan.get("contract") == "plan.v1" or plan.get("version") == "plan.v1"
        assert "path" in plan or "steps" in plan
        steps = plan.get("path") or plan.get("steps")
        assert len(steps) >= 1

    def test_identity_03_all_thirteen_playbooks_load(self):
        """Identity Test 3: The original thirteen domain playbooks remain first-class prompt-engine data."""
        playbooks = PlaybookRegistry.list_playbooks()
        assert len(playbooks) == 13
        expected_playbooks = [
            "software", "writing", "marketing", "business", "learning",
            "career", "content", "research", "design", "fitness",
            "events", "finance", "general"
        ]
        ids = [p.id.lower() for p in playbooks]
        for pb in expected_playbooks:
            assert pb in ids, f"Missing required playbook: {pb}"

    def test_identity_04_prompt_anatomy_has_all_six_fields(self):
        """Identity Test 4: PromptAnatomy remains Role, Task, Context, Constraints, Output Format, and Reasoning."""
        anatomy = PromptAnatomy(
            role="Expert Cinematographer",
            task="Compose a 720p 24fps drone flyover",
            context=["Asset: mountain_ridge_01.png"],
            constraints=["No lens flare", "No camera shake"],
            outputFormat="ComfyUI Wan2.1 Workflow Graph",
            reasoning="Balance dynamic motion with temporal coherence"
        )
        data = anatomy.model_dump()
        for field in ["role", "task", "context", "constraints", "outputFormat", "reasoning"]:
            assert field in data, f"Missing PromptAnatomy field: {field}"

    def test_identity_05_standard_chat_and_reasoning_compilers_pass(self):
        """Identity Test 5: Standard, chat, and reasoning compilers execute cleanly."""
        intent = PromptIntent(objective="Architect a resilient distributed queue")

        # 1. Standard Profile
        res_std = PromptCompiler.compile(intent, playbook="software", profile="standard")
        assert res_std["positive_prompt"]
        assert "software" in res_std["positive_prompt"].lower()

        # 2. Chat Profile
        res_chat = PromptCompiler.compile(intent, playbook="software", profile="chat")
        assert res_chat["positive_prompt"]

        # 3. Reasoning Profile
        res_reas = PromptCompiler.compile(intent, playbook="software", profile="reasoning")
        assert res_reas["positive_prompt"]
        assert res_reas.get("anatomy") is not None

    def test_identity_06_model_facing_calls_carry_keystone_provenance(self):
        """Identity Test 6: Every model-facing call carries KEYSTONE prompt provenance."""
        intent = PromptIntent(objective="Generate landscape painting")
        compiled = PromptCompiler.compile(intent, playbook="design")

        prompt_str = compiled["positive_prompt"]
        expected_hash = hashlib.sha256(prompt_str.encode("utf-8")).hexdigest()
        assert len(expected_hash) == 64
        assert compiled.get("provenance") is not None
        assert compiled["prompt_hash"] == expected_hash


# ============================================================================
# Section 2: Bible §35.2 — The Seven Authority Tests
# ============================================================================

class TestBibleAuthorityAcceptance:
    """The 7 Authority Tests mandated by KEYSTONE Bible §35."""

    def test_authority_01_raw_user_to_worker_fails(self, client: TestClient):
        """Authority Test 1: Raw user-to-worker request fails."""
        # Invoking worker execution without signed ExecutionEnvelope must fail
        raw_payload = {"adapter": "image_gen", "parameters": {"prompt": "unauthorized raw request"}}
        res = client.post("/v1/creative/execute", json={
            "adapter": "image_gen",
            "parameters": raw_payload["parameters"],
            "envelope": {
                "envelope_id": "fake_env",
                "signature": "unsigned_tampered",
                "nonce": "fake_nonce"
            }
        })
        assert res.status_code == 400
        assert "INVALID_ENVELOPE" in res.json()["detail"]

    def test_authority_02_raw_model_to_worker_fails(self):
        """Authority Test 2: Raw model-to-worker request fails (ProposedAction must pass AuthorityEngine)."""
        # Proposed action with destructive bash command
        proposed = ProposedAction(
            action_type="execute_command",
            capability="system.exec",
            parameters={"cmd": "rm -rf /"},
            rationale="Clean scratch space",
            estimated_credits=1
        )
        decision = authority_engine.evaluate(
            action=proposed,
            credit_balance=100
        )
        assert decision.decision == "DENY"
        assert any("DESTRUCTIVE" in r for r in decision.reason_codes)

    def test_authority_03_unknown_capability_fails(self):
        """Authority Test 3: Unknown capability fails."""
        proposed = ProposedAction(
            action_type="execute_tool",
            capability="unregistered.nonexistent.tool",
            parameters={"arg": "val"},
            rationale="Testing unknown capability",
            estimated_credits=1
        )
        decision = authority_engine.evaluate(
            action=proposed,
            credit_balance=100
        )
        assert decision.decision == "DENY"
        assert any("UNKNOWN_CAPABILITY" in r for r in decision.reason_codes)

    def test_authority_04_malformed_arguments_fail_or_clamp(self):
        """Authority Test 4: Malformed arguments fail or clamp safely."""
        proposed = ProposedAction(
            action_type="generate_image",
            capability="image.generation",
            parameters={"steps": 500, "guidance": 100.0, "width": 8192},
            rationale="Test out of bounds clamping",
            estimated_credits=5
        )
        decision = authority_engine.evaluate(
            action=proposed,
            credit_balance=100
        )
        # Bounds must clamp extreme values safely
        sanitized = decision.sanitized_arguments
        assert sanitized["steps"] <= 50
        assert sanitized["guidance"] <= 20.0
        assert sanitized["width"] <= 2048

    def test_authority_05_expired_or_replayed_envelope_fails(self):
        """Authority Test 5: Expired or replayed envelope fails."""
        decision = AuthorityDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfy.flux",
            required_credits=5,
            sanitized_arguments={"prompt": "valid prompt"}
        )
        env = EnvelopeEngine.create_envelope(
            decision=decision,
            job_id="job_replay_test",
            user_id="user_test_01",
            ttl_seconds=300
        )

        # 1. First verification passes and consumes nonce
        ver1 = EnvelopeEngine.verify_envelope(env, check_nonce=True)
        assert ver1["valid"] is True

        # 2. Replay with identical envelope must fail
        with pytest.raises(ValueError, match="REPLAY_ATTACK_DETECTED"):
            EnvelopeEngine.verify_envelope(env, check_nonce=True)

        # 3. Expired envelope must fail
        with pytest.raises(ValueError, match="ENVELOPE_EXPIRED"):
            EnvelopeEngine.verify_envelope(env, now_timestamp=time.time() + 1000, check_nonce=False)

    def test_authority_06_valid_signed_envelope_succeeds(self):
        """Authority Test 6: Valid signed envelope succeeds."""
        decision = AuthorityDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfy.flux",
            required_credits=1,
            sanitized_arguments={"prompt": "high quality output"}
        )
        env = EnvelopeEngine.create_envelope(
            decision=decision,
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            user_id="user_test_02"
        )
        ver = EnvelopeEngine.verify_envelope(env, check_nonce=False)
        assert ver["valid"] is True
        assert ver["job_id"] == env.job_id

    def test_authority_07_worker_cannot_mutate_approved_prompt(self):
        """Authority Test 7: Worker cannot mutate approved prompt."""
        decision = AuthorityDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfy.flux",
            required_credits=1,
            sanitized_arguments={"prompt": "Original sovereign prompt"}
        )
        env = EnvelopeEngine.create_envelope(
            decision=decision,
            job_id="job_tamper_prompt",
            user_id="user_test_03"
        )

        # Tampering with arguments payload invalidates HMAC signature
        tampered_data = env.model_dump()
        tampered_data["arguments"]["prompt"] = "Mutated adversarial prompt"

        with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
            EnvelopeEngine.verify_envelope(tampered_data, check_nonce=False)
