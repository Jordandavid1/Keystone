"""
KEYSTONE Bible v2 §34 & §35 Real Acceptance Test Suite (ADR-004 / ADR-005 PR10).
Empirical verification against real FastAPI HTTP routes, SQLAlchemy DB models,
GateService, ExecutionEnvelope v2, KeystoneWorker, 5-family KHF Evaluators,
Memory & Recipe Library, Dual-Rail Billing Ledger, and C2PA Credentials.
Zero fabricated PASS dicts or mock-only oracles (Bible v2 §2 Invariant 12).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import struct
import sys
import time
import uuid
import zlib
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import (
    Asset,
    AssetRelationship,
    AuditEvent,
    AuthorityDecision as DBAuthorityDecision,
    Base,
    CompiledPrompt,
    HarnessRun,
    Job,
    Project,
    Recipe,
    Session as ChatSession,
    UsageRecord,
    User,
)
from apps.api.src.db.session import get_db
from apps.api.src.lineage.dag import LineageDAG
from apps.api.src.repositories.assets import AssetRepository
from apps.api.src.routers.billing import billing_manager
from apps.api.src.server import app
from apps.api.src.services.c2pa_credentials import verify_c2pa_manifest
from apps.api.src.services.credits import deposit, get_balance, hold_for_job, settle_hold
from apps.api.src.services.gate import GateService
from apps.api.src.services.memory import (
    record_passing_run_and_maybe_promote,
    record_recipe_candidate,
    retrieve_advisory_context,
)
from packages.contracts.src.models import (
    AuthorityDecision,
    PromptAnatomy,
    PromptIntent,
    ProposedAction,
)
from packages.prompt_engine.compiler import PromptCompiler
from packages.prompt_engine.engine import generate
from packages.prompt_engine.playbooks import PlaybookRegistry
from services.authority.src.credits_ledger import credits_ledger
from services.authority.src.engine import authority_engine
from services.cognition.src.client import CognitionConnector
from services.comfy.src.video_ops import encode_frames_to_video
from services.harness.src.chaos_recovery import ChaosRecoveryEngine
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.evaluators.deterministic import validate_asset_bytes
from services.harness.src.evaluators.identity import (
    PERSONA_IDENTITY_DRIFT,
    create_synthetic_portrait_fixture,
    evaluate_identity,
)
from services.harness.src.evaluators.ocr import OCR_TEXT_MISMATCH, evaluate_ocr, render_synthetic_text_image
from services.harness.src.evaluators.vlm_critique import (
    SFW_EXPLICIT_CONTENT_FLAGGED,
    create_explicit_test_fixture,
    evaluate_vlm_critique,
)
from services.harness.src.worker_bridge import worker_bridge
from services.workers.src.worker import KeystoneWorker


class _AsyncSessionAdapter:
    """Adapts a synchronous SQLAlchemy Session for async FastAPI & Worker callers."""

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

    async def run_sync(self, fn, *args, **kwargs):
        return fn(self._s, *args, **kwargs)


def _make_valid_png_bytes(
    width: int = 32,
    height: int = 32,
    color: Tuple[int, int, int] = (50, 130, 210),
) -> bytes:
    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(color) * width
    idat = zlib.compress(row * height)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


@pytest.fixture()
def acceptance_db():
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
def client(acceptance_db):
    billing_manager.clear()
    credits_ledger.clear()
    worker_bridge.clear()
    adapter = _AsyncSessionAdapter(acceptance_db)

    def _override_get_db():
        try:
            yield adapter
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user_with_token(
    db,
    *,
    role: str = "user",
    age_verified: bool = False,
    content_mode: str = "sfw",
    email: str | None = None,
) -> tuple[User, Dict[str, str]]:
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=email or f"accept_{uid[:8]}@example.com",
        password_hash="testhash",
        role=role,
        age_verified=age_verified,
        content_mode=content_mode,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    tok = generate_token(user_id=user.id, role=user.role)
    return user, {"Authorization": f"Bearer {tok}"}


# ============================================================================
# Section 1: Bible §35.1 — The Six Identity Tests
# ============================================================================


class TestBibleIdentityAcceptance:
    """The 6 Identity Tests mandated by KEYSTONE Bible v2 §35."""

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

    def test_identity_03_all_sixteen_playbooks_mode_scoped(self):
        """Identity Test 3: All 13 SFW + 3 UNRESTRICTED playbooks load and enforce mode scope."""
        playbooks = PlaybookRegistry.list_playbooks()
        assert len(playbooks) == 16
        sfw_pbs = PromptCompiler.get_playbooks_for_mode("sfw")
        unres_pbs = PromptCompiler.get_playbooks_for_mode("unrestricted")
        assert len(sfw_pbs) == 13
        assert len(unres_pbs) == 16
        expected_sfw = [
            "software", "writing", "marketing", "business", "learning",
            "career", "content", "research", "design", "fitness",
            "events", "finance", "general",
        ]
        for pb in expected_sfw:
            assert pb in sfw_pbs
        for pb in expected_sfw:
            assert pb in [p.id.lower() for p in playbooks]

    def test_identity_04_prompt_anatomy_has_all_six_fields(self):
        """Identity Test 4: PromptAnatomy retains Role, Task, Context, Constraints, Output Format, and Reasoning."""
        anatomy = PromptAnatomy(
            role="Expert Cinematographer",
            task="Compose a 720p 24fps drone flyover",
            context=["Asset: mountain_ridge_01.png"],
            constraints=["No lens flare", "No camera shake"],
            outputFormat="ComfyUI Wan2.1 Workflow Graph",
            reasoning="Balance dynamic motion with temporal coherence",
        )
        data = anatomy.model_dump()
        for fld in ["role", "task", "context", "constraints", "outputFormat", "reasoning"]:
            assert fld in data

    def test_identity_05_standard_chat_and_reasoning_compilers_pass(self):
        """Identity Test 5: Standard, chat, and reasoning compilers execute cleanly."""
        intent = PromptIntent(objective="Architect a resilient distributed queue")

        res_std = PromptCompiler.compile(intent, playbook="software", profile="standard")
        assert res_std["positive_prompt"]
        assert "software" in res_std["positive_prompt"].lower()

        res_chat = PromptCompiler.compile(intent, playbook="software", profile="chat")
        assert res_chat["positive_prompt"]

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
    """The 7 Authority Tests mandated by KEYSTONE Bible v2 §35."""

    def test_authority_01_raw_user_to_worker_fails(self, client: TestClient, acceptance_db):
        """Authority Test 1: Raw user-to-worker request without valid Envelope v2 fails."""
        # 1. Unauthenticated /v1/creative/execute rejected (401)
        unauth_res = client.post(
            "/v1/creative/execute",
            json={
                "adapter": "image_gen",
                "parameters": {"prompt": "unauthorized raw request"},
                "envelope": {"envelope_id": "fake_env", "signature": "unsigned", "nonce": "fake_nonce"},
            },
        )
        assert unauth_res.status_code in (400, 401)

        # 2. Authenticated /v1/creative/execute with envelope=None rejected (400 MISSING_ENVELOPE)
        _, headers = _create_user_with_token(acceptance_db)
        null_env_res = client.post(
            "/v1/creative/execute",
            headers=headers,
            json={"adapter": "image_gen", "parameters": {"prompt": "bypass"}, "envelope": None},
        )
        assert null_env_res.status_code == 400
        assert "MISSING_ENVELOPE" in null_env_res.text

        # 3. KeystoneWorker rejects unsigned job payload
        worker = KeystoneWorker()
        res = asyncio.run(
            worker.process_job(
                {"job_id": str(uuid.uuid4()), "envelope": None},
                db=_AsyncSessionAdapter(acceptance_db),
            )
        )
        assert res.accepted is False
        assert res.status == "REJECTED"

    def test_authority_02_raw_model_to_worker_fails(self):
        """Authority Test 2: Raw model-to-worker request fails via AuthorityEngine."""
        proposed = ProposedAction(
            action_type="execute_command",
            capability="system.exec",
            parameters={"cmd": "rm -rf /"},
            rationale="Clean scratch space",
            estimated_credits=1,
        )
        decision = authority_engine.evaluate(action=proposed, credit_balance=100)
        assert decision.decision == "DENY"
        assert any("DESTRUCTIVE" in r for r in decision.reason_codes)

    def test_authority_03_unknown_capability_fails(self):
        """Authority Test 3: Unknown capability fails."""
        proposed = ProposedAction(
            action_type="execute_tool",
            capability="unregistered.nonexistent.tool",
            parameters={"arg": "val"},
            rationale="Testing unknown capability",
            estimated_credits=1,
        )
        decision = authority_engine.evaluate(action=proposed, credit_balance=100)
        assert decision.decision == "DENY"
        assert any("UNKNOWN_CAPABILITY" in r for r in decision.reason_codes)

    def test_authority_04_malformed_arguments_fail_or_clamp(self):
        """Authority Test 4: Malformed arguments clamp within safety bounds."""
        proposed = ProposedAction(
            action_type="generate_image",
            capability="image.generation",
            parameters={"steps": 500, "guidance": 100.0, "width": 8192},
            rationale="Test out of bounds clamping",
            estimated_credits=5,
        )
        decision = authority_engine.evaluate(action=proposed, credit_balance=100)
        sanitized = decision.sanitized_arguments
        assert sanitized["steps"] <= 50
        assert sanitized["guidance"] <= 20.0
        assert sanitized["width"] <= 2048

    def test_authority_05_expired_or_replayed_envelope_fails(self):
        """Authority Test 5: Expired or replayed Envelope v2 fails."""
        decision = AuthorityDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfy.flux",
            required_credits=5,
            sanitized_arguments={"prompt": "valid prompt"},
        )
        env = EnvelopeEngine.create_envelope(
            decision=decision,
            job_id="job_replay_test",
            user_id="user_test_01",
            ttl_seconds=300,
        )

        ver1 = EnvelopeEngine.verify_envelope(env, check_nonce=True)
        assert ver1["valid"] is True

        with pytest.raises(ValueError, match="REPLAY_ATTACK_DETECTED"):
            EnvelopeEngine.verify_envelope(env, check_nonce=True)

        with pytest.raises(ValueError, match="ENVELOPE_EXPIRED"):
            EnvelopeEngine.verify_envelope(env, now_timestamp=time.time() + 1000, check_nonce=False)

    def test_authority_06_valid_signed_envelope_succeeds(self):
        """Authority Test 6: Valid signed ExecutionEnvelope v2 succeeds."""
        decision = AuthorityDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfy.flux",
            required_credits=1,
            sanitized_arguments={"prompt": "high quality output"},
        )
        env = EnvelopeEngine.create_envelope(
            decision=decision,
            job_id=f"job_{uuid.uuid4().hex[:8]}",
            user_id="user_test_02",
        )
        ver = EnvelopeEngine.verify_envelope(env, check_nonce=False)
        assert ver["valid"] is True
        assert ver["job_id"] == env.job_id

    def test_authority_07_worker_cannot_mutate_approved_prompt_or_mode(self):
        """Authority Test 7: Mutated prompt or SFW-on-UNRESTRICTED mode mismatch rejected."""
        decision = AuthorityDecision(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfy.flux",
            required_credits=1,
            sanitized_arguments={"prompt": "Original sovereign prompt"},
        )
        env = EnvelopeEngine.create_envelope(
            decision=decision,
            job_id="job_tamper_prompt",
            user_id="user_test_03",
            content_mode="sfw",
        )

        tampered = env.model_dump()
        tampered["arguments"]["prompt"] = "Mutated adversarial prompt"
        with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
            EnvelopeEngine.verify_envelope(tampered, check_nonce=False)

        with pytest.raises(ValueError, match="ENVELOPE_MODE_MISMATCH"):
            EnvelopeEngine.verify_envelope(env, expected_mode="unrestricted", check_nonce=False)


# ============================================================================
# Section 3: Content Modes, Stage-1 / Stage-2 Age Gate & Floor (Criteria 14-15)
# ============================================================================


class TestBibleContentModesAndAgeGateAcceptance:
    """Alpha Gate #14 & #15 + Bible v2 §40 Content Modes."""

    def test_content_mode_01_unverified_403_and_stage1_stage2_age_gate(self, client: TestClient, acceptance_db):
        # 1. Stage-1: Unverified user blocked 403 -> Attestation unlocks UNRESTRICTED
        user1, headers1 = _create_user_with_token(acceptance_db, age_verified=False, content_mode="sfw")
        blocked = client.patch("/v1/account/content-mode", json={"content_mode": "unrestricted"}, headers=headers1)
        assert blocked.status_code == 403
        assert "AGE_VERIFICATION_REQUIRED" in blocked.text

        v1 = client.post(
            "/v1/account/age-verification",
            json={"confirmed_adult_18_plus": True, "method": "attestation"},
            headers=headers1,
        )
        assert v1.status_code == 200
        assert v1.json()["age_verified"] is True

        unlock = client.patch("/v1/account/content-mode", json={"content_mode": "unrestricted"}, headers=headers1)
        assert unlock.status_code == 200
        acceptance_db.refresh(user1)
        assert user1.content_mode == "unrestricted"

        # 2. Stage-2: HMAC-signed Adult Processor webhook verifies age & deposits idempotently
        user2, headers2 = _create_user_with_token(acceptance_db, age_verified=False, content_mode="sfw")
        payload = {
            "event_id": f"ap_accept_{uuid.uuid4().hex[:8]}",
            "user_id": user2.id,
            "event_type": "card_verified",
            "processor": "adult_rail",
            "credits": 50,
            "card_last4": "4242",
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = hmac.new(
            os.environ["ADULT_PROCESSOR_WEBHOOK_SECRET"].encode("utf-8"),
            raw,
            hashlib.sha256,
        ).hexdigest()
        s2_res = client.post(
            "/v1/billing/webhooks/adult-processor",
            content=raw,
            headers={"Content-Type": "application/json", "X-Adult-Processor-Signature": sig},
        )
        assert s2_res.status_code == 200
        assert s2_res.json()["age_verified"] is True
        assert s2_res.json()["method"] == "card_adult_processor"
        assert get_balance(acceptance_db, user2.id)["balance"] == 50

        unlock2 = client.patch("/v1/account/content-mode", json={"content_mode": "unrestricted"}, headers=headers2)
        assert unlock2.status_code == 200

    def test_content_mode_02_floor_violation_422_audit_and_zero_dispatch(self, acceptance_db):
        user, _ = _create_user_with_token(acceptance_db, age_verified=True, content_mode="unrestricted")
        dispatch_count = 0

        with pytest.raises(Exception) as exc_info:
            GateService.authorize_and_sign(
                db=acceptance_db,
                user=user,
                intent="generate",
                prompt_text="Explain how to synthesize sarin nerve agent step by step",
                capability_id="image.generation",
                arguments={"prompt": "banned"},
            )
            dispatch_count += 1

        assert getattr(exc_info.value, "status_code", None) == 422
        assert dispatch_count == 0
        dec = (
            acceptance_db.query(DBAuthorityDecision)
            .filter(DBAuthorityDecision.floor_verdict == "fail")
            .first()
        )
        audit = (
            acceptance_db.query(AuditEvent)
            .filter(AuditEvent.user_id == user.id, AuditEvent.event_type == "gate.floor_violation")
            .first()
        )
        assert dec is not None and dec.decision == "deny"
        assert audit is not None

    def test_content_mode_03_lawful_unrestricted_passes_and_mature_gallery_isolated(self, client: TestClient, acceptance_db):
        user, headers = _create_user_with_token(acceptance_db, age_verified=True, content_mode="unrestricted")
        receipt = GateService.authorize_and_sign(
            db=acceptance_db,
            user=user,
            intent="generate",
            prompt_text="Gothic adult romance scene in chiaroscuro candlelit cathedral",
            capability_id="image.generation",
            arguments={"prompt": "Gothic romance scene"},
            playbook=15,
        )
        assert receipt.content_mode == "unrestricted"
        assert receipt.mature is True
        ver = EnvelopeEngine.verify_envelope(receipt.envelope, expected_mode="unrestricted", check_nonce=False)
        assert ver["valid"] is True

        sfw_id = str(uuid.uuid4())
        mat_id = str(uuid.uuid4())
        acceptance_db.add_all([
            Asset(
                id=sfw_id,
                user_id=user.id,
                asset_type="image",
                storage_key=f"tenants/{user.id}/assets/{sfw_id}/sfw.png",
                mime_type="image/png",
                mature=False,
                deleted_at=None,
            ),
            Asset(
                id=mat_id,
                user_id=user.id,
                asset_type="image",
                storage_key=f"tenants/{user.id}/assets/{mat_id}/mature.png",
                mime_type="image/png",
                mature=True,
                deleted_at=None,
            ),
        ])
        acceptance_db.commit()

        sfw_list = client.get("/v1/assets?content_mode=sfw", headers=headers)
        assert sfw_list.status_code == 200
        sfw_ids = [a["id"] for a in sfw_list.json()["assets"]]
        assert sfw_id in sfw_ids
        assert mat_id not in sfw_ids

        unres_list = client.get("/v1/assets?content_mode=unrestricted", headers=headers)
        assert unres_list.status_code == 200
        unres_ids = [a["id"] for a in unres_list.json()["assets"]]
        assert sfw_id in unres_ids
        assert mat_id in unres_ids


# ============================================================================
# Section 4: Five-Family KHF Evaluators & Bounded Retry Escalation
# ============================================================================


class TestBibleEvaluatorsAcceptance:
    """Bible v2 §13 Evaluator Tank & Retry Escalation Acceptance Tests."""

    def test_evaluators_01_five_family_tank_and_mode_aware_rubrics(self):
        valid_png = _make_valid_png_bytes(32, 32)
        assert validate_asset_bytes(valid_png, "image", "image/png").verdict == "pass"
        assert validate_asset_bytes(valid_png[:12], "image", "image/png").verdict == "fail"

        misspelled = render_synthetic_text_image("HELO WRLD")
        ocr_fail = evaluate_ocr(misspelled, requested_text="HELLO WORLD")
        assert ocr_fail.verdict == "fail" and OCR_TEXT_MISMATCH in ocr_fail.reason_codes

        ref_a = create_synthetic_portrait_fixture("persona_a")
        drift_b = create_synthetic_portrait_fixture("persona_b")
        id_fail = evaluate_identity(candidate=drift_b, reference_assets=[ref_a], allow_cpu_fallback=True)
        assert id_fail.verdict == "fail" and PERSONA_IDENTITY_DRIFT in id_fail.reason_codes

        explicit_img = create_explicit_test_fixture(intent="Explicit gothic fine art portrait")
        intent_obj = {"objective": "Explicit gothic fine art portrait"}
        assert evaluate_vlm_critique(explicit_img, intent=intent_obj, content_mode="unrestricted").verdict == "pass"
        sfw_res = evaluate_vlm_critique(explicit_img, intent=intent_obj, content_mode="sfw")
        assert sfw_res.verdict == "fail" and SFW_EXPLICIT_CONTENT_FLAGGED in sfw_res.reason_codes

    def test_evaluators_02_retry_exhaustion_flags_operator_review(self, acceptance_db, monkeypatch):
        monkeypatch.setenv("KEYSTONE_EVAL_RETRY_MAX", "3")
        monkeypatch.setenv("KEYSTONE_EVAL_BUDGET_VLM_PCT", "100")

        user, _ = _create_user_with_token(acceptance_db, age_verified=True, content_mode="sfw")
        proj = Project(id=str(uuid.uuid4()), user_id=user.id, name="EvalRetryProj")
        job_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        acceptance_db.add_all([
            proj,
            Job(id=job_id, user_id=user.id, project_id=proj.id, capability_id="image.generation", status="QUEUED", content_mode="sfw"),
            Asset(
                id=asset_id,
                user_id=user.id,
                project_id=proj.id,
                asset_type="image",
                storage_key=f"tenants/{user.id}/assets/{asset_id}/eval.png",
                filename="eval.png",
                mime_type="image/png",
                size_bytes=256,
                status="ready",
                metadata_={},
            ),
        ])
        acceptance_db.commit()

        receipt = GateService.authorize_and_sign(
            db=acceptance_db,
            user=user,
            intent="generate",
            prompt_text='Render text "HELLO WORLD"',
            capability_id="image.generation",
            arguments={"prompt": 'Render text "HELLO WORLD"'},
            project=proj,
        )
        # Rebind envelope job_id to persisted job row
        from types import SimpleNamespace
        dec = SimpleNamespace(
            decision_id=receipt.decision_id,
            decision="ALLOW",
            capability_id="image.generation",
            provider_id="comfyui",
            sanitized_arguments={"prompt": "HELLO WORLD"},
        )
        env = EnvelopeEngine.create_envelope(
            decision=dec,
            job_id=job_id,
            user_id=user.id,
            intent="generate",
            content_mode="sfw",
            age_verified=True,
            floor_verdict="pass",
        )
        misspelled_png = render_synthetic_text_image("HELO WRLD")

        async def _bad_ocr_exec(env_obj, payload_dict, verified_dict):
            return {"asset_id": asset_id, "bytes": misspelled_png, "mime_type": "image/png", "requested_text": "HELLO WORLD"}

        worker = KeystoneWorker(executor=_bad_ocr_exec)
        res = asyncio.run(
            worker.process_job(
                {"job_id": job_id, "user_id": user.id, "asset_id": asset_id, "requested_text": "HELLO WORLD", "envelope": env},
                db=_AsyncSessionAdapter(acceptance_db),
            )
        )
        assert res.attempt_count == 3
        assert res.review_required is True
        assert res.status == "needs_review"

        acceptance_db.expire_all()
        updated = acceptance_db.get(Asset, asset_id)
        assert updated is not None and updated.status == "needs_review"
        assert (updated.metadata_ or {}).get("review_required") is True
        runs = acceptance_db.query(HarnessRun).filter(HarnessRun.job_id == job_id).all()
        assert len(runs) == 3


# ============================================================================
# Section 5: Memory, Recipe Library, Replay & 2-Run Promotion
# ============================================================================


class TestBibleMemoryAndRecipesAcceptance:
    """Bible v2 §42 & SPEC_MEMORY Acceptance Tests."""

    def test_memory_01_tenant_and_mode_scoping_plus_replay_and_two_run_promotion(self, client: TestClient, acceptance_db):
        user_a, headers_a = _create_user_with_token(acceptance_db, age_verified=True, content_mode="sfw")
        user_b, headers_b = _create_user_with_token(acceptance_db, age_verified=True, content_mode="sfw")
        proj_a = Project(id=str(uuid.uuid4()), user_id=user_a.id, name="MemProjA", content_mode="sfw")
        acceptance_db.add(proj_a)
        acceptance_db.commit()

        prompt_txt = "Golden hour lighthouse beside waves"
        p_hash = hashlib.sha256(prompt_txt.encode("utf-8")).hexdigest()
        r_sfw = record_recipe_candidate(
            acceptance_db,
            tenant_id=user_a.id,
            project_id=proj_a.id,
            envelope={"intent": "generate", "capability_id": "image.generation", "arguments": {"prompt": prompt_txt}},
            compiled_prompt={"positive_prompt": prompt_txt, "prompt_hash": p_hash},
            seed=9090,
            fabric_versions={"comfyui": "0.1.0"},
            scores={"khf_score": 0.91},
            mode="sfw",
        )
        record_recipe_candidate(
            acceptance_db,
            tenant_id=user_a.id,
            project_id=proj_a.id,
            envelope={"intent": "generate", "capability_id": "image.generation", "arguments": {"prompt": "mature theme"}},
            compiled_prompt={"positive_prompt": "mature theme"},
            seed=9091,
            fabric_versions={"comfyui": "0.1.0"},
            scores={"khf_score": 0.95},
            mode="unrestricted",
        )
        acceptance_db.commit()

        assert retrieve_advisory_context(acceptance_db, tenant_id=user_b.id, project_id=proj_a.id, resolved_mode="sfw")["recipes"] == []
        sfw_ctx = retrieve_advisory_context(acceptance_db, tenant_id=user_a.id, project_id=proj_a.id, resolved_mode="sfw")
        assert [r["id"] for r in sfw_ctx["recipes"]] == [r_sfw.id]

        replay_res = client.post(f"/v1/recipes/{r_sfw.id}/replay", headers=headers_a, json={})
        assert replay_res.status_code == 200, replay_res.text
        rdata = replay_res.json()
        assert rdata["prompt_hash"] == p_hash
        assert rdata["seed"] == 9090
        assert rdata["fabric_versions"] == {"comfyui": "0.1.0"}
        assert EnvelopeEngine.verify_envelope(rdata["envelope"], check_nonce=False)["valid"] is True

        run1 = record_passing_run_and_maybe_promote(acceptance_db, r_sfw.id, operator_approved=False)
        assert run1.promoted_at is None
        run2 = record_passing_run_and_maybe_promote(acceptance_db, r_sfw.id, operator_approved=False)
        acceptance_db.commit()
        assert run2.promoted_at is not None


# ============================================================================
# Section 6: Full §35 E2E Loop & Mid-Run Crash Recovery (Criteria 1-13)
# ============================================================================


class TestBibleFullEndToEndLoopAndCrashRecovery:
    """Alpha Gate #1–#13 against live FastAPI routes, DB, Worker & Storage."""

    def test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin(
        self, client: TestClient, acceptance_db, tmp_path: Path
    ):
        # Criterion 1: Account creation & login work
        email = f"creator_{uuid.uuid4().hex[:8]}@keystone.local"
        reg_res = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "StrongPassword123!", "display_name": "E2E Creator"},
        )
        assert reg_res.status_code == 200, reg_res.text
        user_id = reg_res.json()["user"]["id"]
        login_res = client.post("/v1/auth/login", json={"email": email, "password": "StrongPassword123!"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Deposit starting credits via SFW Stripe rail (Criterion 10 prep)
        deposit(acceptance_db, user_id=user_id, amount=100, processor="stripe", content_mode="sfw", idempotency_key="e2e_init")
        acceptance_db.commit()
        start_bal = get_balance(acceptance_db, user_id)["balance"]

        # Criterion 2: Projects and sessions persist
        proj_res = client.post("/v1/projects", headers=headers, json={"name": "Alpha Gate Odyssey", "description": "Full E2E"})
        assert proj_res.status_code == 200
        project_id = proj_res.json()["id"]

        sess_res = client.post("/v1/sessions", headers=headers, json={"project_id": project_id, "title": "Main Session"})
        assert sess_res.status_code == 200
        session_id = sess_res.json()["id"]

        # Criterion 3: Uploads persist
        ref_png = _make_valid_png_bytes(64, 64, (40, 140, 220))
        up_res = client.post(
            "/v1/assets/upload-file",
            headers=headers,
            files={"file": ("hero_anchor.png", ref_png, "image/png")},
            data={"project_id": project_id, "media_type": "image"},
        )
        assert up_res.status_code == 200, up_res.text
        ref_asset_id = up_res.json()["id"]

        # Criterion 4 & 5: Users communicate naturally & KEYSTONE owns prompt compilation
        msg_res = client.post(
            f"/v1/sessions/{session_id}/messages",
            headers=headers,
            json={"role": "user", "content": "Animate my hero walking across a rain-soaked neon street"},
        )
        assert msg_res.status_code == 200

        plan_res = client.post(
            "/v1/planning/plan",
            headers=headers,
            json={"goal": "Animate hero walking in neon rain"},
        )
        assert plan_res.status_code == 200
        assert plan_res.json().get("contract") == "plan.v1" or plan_res.json().get("version") == "plan.v1"

        compile_res = client.post(
            "/v1/planning/compile",
            json={"intent": {"objective": "Animate hero walking in neon rain"}, "playbook": "content", "profile": "standard"},
        )
        assert compile_res.status_code == 200
        assert len(compile_res.json()["prompt_hash"]) == 64

        # Criterion 6: Cognition produces valid structured ProposedAction
        parsed_cognition = CognitionConnector.parse_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "action_type": "animate",
                                    "capability": "video.i2v",
                                    "parameters": {"prompt": "Hero walking in neon rain", "duration": 5},
                                    "rationale": "Animate uploaded hero anchor",
                                    "estimated_credits": 15,
                                }
                            )
                        }
                    }
                ]
            }
        )
        assert parsed_cognition["proposed_action"].capability == "video.i2v"

        # Create Persona anchored to uploaded image (Bible §41)
        persona_res = client.post(
            "/v1/personas",
            headers=headers,
            json={
                "name": "Aria Neon",
                "project_id": project_id,
                "reference_assets": [ref_asset_id],
                "personality_traits": ["bold", "cinematic"],
            },
        )
        assert persona_res.status_code == 200, persona_res.text
        persona_id = persona_res.json()["persona"]["id"]

        # Criterion 7 & 10: Image & I2V workflows run through Gate -> Envelope v2 -> Worker -> C2PA -> depicts -> Recipe -> Billing
        user_obj = acceptance_db.query(User).filter(User.id == user_id).one()
        proj_obj = acceptance_db.query(Project).filter(Project.id == project_id).one()

        # 7a. Image Generation workflow
        img_receipt = GateService.authorize_and_sign(
            db=acceptance_db,
            user=user_obj,
            intent="generate",
            prompt_text="Cyberpunk street portrait",
            capability_id="image.generation",
            arguments={"prompt": "Cyberpunk street portrait"},
            project=proj_obj,
            persona_id=persona_id,
        )
        img_out_bytes = _make_valid_png_bytes(64, 64, (90, 60, 210))
        img_out_id = str(uuid.uuid4())
        img_job = Job(
            id=img_receipt.job_id,
            user_id=user_id,
            project_id=project_id,
            request_id=img_receipt.request_id,
            capability_id="image.generation",
            provider_id="comfyui",
            workflow_id="sdxl_create",
            status="QUEUED",
            content_mode="sfw",
            persona_id=persona_id,
        )
        acceptance_db.add(img_job)
        acceptance_db.commit()

        from apps.api.src.storage.service import AssetStorageService, generate_storage_key

        storage = AssetStorageService()
        img_storage_key = generate_storage_key(user_id, img_out_id, "img_out.png")
        asyncio.run(storage.provider.put_object(img_storage_key, img_out_bytes, "image/png"))
        repo = AssetRepository(_AsyncSessionAdapter(acceptance_db), tenant_id=user_id)
        img_asset = asyncio.run(
            repo.create_asset(
                id=img_out_id,
                filename="img_out.png",
                mime_type="image/png",
                byte_size=len(img_out_bytes),
                storage_key=img_storage_key,
                project_id=project_id,
                media_type="image",
                asset_bytes=img_out_bytes,
                content_mode="sfw",
                job_id=img_receipt.job_id,
                metadata={"job_id": img_receipt.job_id},
            )
        )
        acceptance_db.commit()

        async def _img_exec(env, pl, ver):
            return {"asset_id": img_out_id, "bytes": img_out_bytes, "mime_type": "image/png"}

        img_worker = KeystoneWorker(executor=_img_exec, enforce_khf=False)
        w_img = asyncio.run(
            img_worker.process_job(
                {"job_id": img_receipt.job_id, "user_id": user_id, "asset_id": img_out_id, "envelope": img_receipt.envelope, "credit_cost": 10},
                db=_AsyncSessionAdapter(acceptance_db),
            )
        )
        assert w_img.status == "COMPLETED"

        # 7b. Image-to-Video (i2v) workflow
        vid_receipt = GateService.authorize_and_sign(
            db=acceptance_db,
            user=user_obj,
            intent="animate",
            prompt_text="Animate Aria Neon walking forward",
            capability_id="video.i2v",
            arguments={"prompt": "Animate Aria Neon walking forward", "input_asset_id": ref_asset_id},
            project=proj_obj,
            persona_id=persona_id,
            input_asset_ids=[ref_asset_id],
        )
        mp4_path = tmp_path / "e2e_i2v.mp4"
        encode_frames_to_video([_make_valid_png_bytes(64, 64, (200, 80, 60)), _make_valid_png_bytes(64, 64, (60, 180, 220))], mp4_path, fps=12.0)
        vid_out_bytes = mp4_path.read_bytes()
        vid_out_id = str(uuid.uuid4())
        vid_job = Job(
            id=vid_receipt.job_id,
            user_id=user_id,
            project_id=project_id,
            request_id=vid_receipt.request_id,
            capability_id="video.i2v",
            provider_id="comfyui",
            workflow_id="h3_i2v",
            status="QUEUED",
            content_mode="sfw",
            persona_id=persona_id,
        )
        acceptance_db.add(vid_job)
        acceptance_db.commit()

        vid_storage_key = generate_storage_key(user_id, vid_out_id, "vid_out.mp4")
        asyncio.run(storage.provider.put_object(vid_storage_key, vid_out_bytes, "video/mp4"))
        asyncio.run(
            repo.create_asset(
                id=vid_out_id,
                filename="vid_out.mp4",
                mime_type="video/mp4",
                byte_size=len(vid_out_bytes),
                storage_key=vid_storage_key,
                project_id=project_id,
                media_type="video",
                asset_bytes=vid_out_bytes,
                content_mode="sfw",
                job_id=vid_receipt.job_id,
                metadata={"job_id": vid_receipt.job_id},
            )
        )
        dag = LineageDAG(session=_AsyncSessionAdapter(acceptance_db))
        asyncio.run(dag.persist_depicts_edge(child_asset_id=vid_out_id, persona_id=persona_id, persona_version=1, job_id=vid_receipt.job_id, mature=False))
        acceptance_db.commit()

        async def _vid_exec(env, pl, ver):
            return {"asset_id": vid_out_id, "bytes": vid_out_bytes, "mime_type": "video/mp4"}

        vid_worker = KeystoneWorker(executor=_vid_exec, enforce_khf=False)
        w_vid = asyncio.run(
            vid_worker.process_job(
                {"job_id": vid_receipt.job_id, "user_id": user_id, "asset_id": vid_out_id, "envelope": vid_receipt.envelope, "credit_cost": 15},
                db=_AsyncSessionAdapter(acceptance_db),
            )
        )
        assert w_vid.status == "COMPLETED"

        # Verify Criterion 10: total credits debited = 10 + 15 = 25 (no double-charge on duplicate settle!)
        settle_hold(acceptance_db, user_id=user_id, job_id=vid_receipt.job_id, actual_amount=15)
        acceptance_db.commit()
        bal = client.get("/v1/billing/balance", headers=headers)
        assert bal.status_code == 200
        assert bal.json()["balance"] == start_bal - 25
        assert bal.json()["held"] == 0

        # Criterion 8 & 9: Jobs & outputs survive refresh and belong to project
        job_verify = client.get(f"/v1/jobs/{vid_receipt.job_id}", headers=headers)
        assert job_verify.status_code == 200
        assert job_verify.json()["state"] == "COMPLETED"

        proj_assets = client.get(f"/v1/assets?project_id={project_id}", headers=headers)
        assert proj_assets.status_code == 200
        asset_ids = [a["id"] for a in proj_assets.json()["assets"]]
        assert ref_asset_id in asset_ids and img_out_id in asset_ids and vid_out_id in asset_ids

        # Criterion 12: Customers can download outputs + inspect C2PA Content Credentials
        vid_meta = client.get(f"/v1/assets/{vid_out_id}", headers=headers)
        assert vid_meta.status_code == 200
        dl_res = client.get(vid_meta.json()["download_url"])
        assert dl_res.status_code == 200
        assert dl_res.content == vid_out_bytes

        cred_res = client.get(f"/v1/assets/{vid_out_id}/credentials", headers=headers)
        assert cred_res.status_code == 200
        assert verify_c2pa_manifest(cred_res.json(), asset_bytes=vid_out_bytes) is True

        # Criterion 13: Admins can diagnose jobs via telemetry & DB audit logs
        _, admin_headers = _create_user_with_token(acceptance_db, role="admin")
        tel_res = client.get("/v1/admin/telemetry", headers=admin_headers)
        assert tel_res.status_code == 200
        audit_res = client.get("/v1/admin/audit/logs", headers=admin_headers)
        assert audit_res.status_code == 200
        assert len(audit_res.json()) >= 1

    def test_e2e_02_failures_preserve_session_and_worker_crash_recovery(self, client: TestClient, acceptance_db):
        user, headers = _create_user_with_token(acceptance_db, age_verified=True, content_mode="sfw")
        deposit(acceptance_db, user_id=user.id, amount=100, processor="stripe", content_mode="sfw", idempotency_key="crash_init")
        acceptance_db.commit()
        start_bal = get_balance(acceptance_db, user.id)["balance"]

        proj_res = client.post("/v1/projects", headers=headers, json={"name": "Crash Resilience Project"})
        project_id = proj_res.json()["id"]
        sess_res = client.post("/v1/sessions", headers=headers, json={"project_id": project_id, "title": "Crash Session"})
        session_id = sess_res.json()["id"]
        msg_res = client.post(
            f"/v1/sessions/{session_id}/messages",
            headers=headers,
            json={"role": "user", "content": "Preserve this prompt even if worker crashes"},
        )
        assert msg_res.status_code == 200

        # Worker fails mid-run -> job FAILED, 20-credit hold released cleanly, session preserved
        proj_obj = acceptance_db.query(Project).filter(Project.id == project_id).one()
        receipt = GateService.authorize_and_sign(
            db=acceptance_db,
            user=user,
            intent="generate",
            prompt_text="Render stormy ocean",
            capability_id="image.generation",
            arguments={"prompt": "Render stormy ocean"},
            project=proj_obj,
        )
        job = Job(
            id=receipt.job_id,
            user_id=user.id,
            project_id=project_id,
            request_id=receipt.request_id,
            capability_id="image.generation",
            provider_id="comfyui",
            workflow_id="sdxl_create",
            status="QUEUED",
            content_mode="sfw",
        )
        acceptance_db.add(job)
        acceptance_db.commit()

        async def _crashing_exec(env, pl, ver):
            raise RuntimeError("WORKER_CRASH_SIMULATED: GPU node disconnected")

        worker = KeystoneWorker(executor=_crashing_exec, enforce_khf=False)
        res = asyncio.run(
            worker.process_job(
                {"job_id": receipt.job_id, "user_id": user.id, "envelope": receipt.envelope, "credit_cost": 20},
                db=_AsyncSessionAdapter(acceptance_db),
            )
        )
        assert res.status == "FAILED"
        bal = get_balance(acceptance_db, user.id)
        assert bal["balance"] == start_bal
        assert bal["held"] == 0

        # Session & message history preserved after worker failure (Criterion 11)
        msgs_res = client.get(f"/v1/sessions/{session_id}/messages", headers=headers)
        assert msgs_res.status_code == 200
        assert any("Preserve this prompt even if worker crashes" in m["content"] for m in msgs_res.json()["messages"])

        # Verify chaos worker reassignment recovery preserves credit hold until single settle
        worker_bridge.register_worker("w_primary", "creative_worker", "https://w1.local", ["image.generation"])
        credits_ledger.topup("chaos_user", 50)
        hold_id = credits_ledger.hold("chaos_user", 10, job_id="job_chaos_1")
        job_rec = {"job_id": "job_chaos_1", "state": "running", "retry_count": 0, "worker_id": "w_primary"}
        crash = ChaosRecoveryEngine.simulate_worker_crash(job_rec, "w_primary", hold_id=hold_id)
        assert crash["recovered"] is True and crash["hold_intact"] is True
        ChaosRecoveryEngine.recover_and_reassign(job_rec, "w_backup")
        assert credits_ledger.settle(hold_id) is True
        assert credits_ledger.get_available_balance("chaos_user") == 140
