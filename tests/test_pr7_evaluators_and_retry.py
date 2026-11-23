"""PR7 (ADR-005): Tier-B 5-family KHF evaluator tank, mode-aware VLM critique rubrics, and bounded retry escalation."""

from __future__ import annotations

import asyncio
import struct
import uuid
import zlib
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.db.models import (
    Asset,
    AuditEvent,
    Base,
    GenerationAttempt,
    HarnessRun,
    Job,
    Project,
    User,
)
from packages.prompt_engine.compiler import H3PromptCompiler, PromptCompiler
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.evaluators.deterministic import validate_asset_bytes
from services.harness.src.evaluators.identity import (
    DEFAULT_IDENTITY_THRESHOLD,
    PERSONA_IDENTITY_DRIFT,
    create_synthetic_portrait_fixture,
    evaluate_identity,
)
from services.harness.src.evaluators.ocr import (
    OCR_BACKEND_UNAVAILABLE,
    OCR_TEXT_MISMATCH,
    evaluate_ocr,
    render_synthetic_text_image,
)
from services.harness.src.evaluators.temporal import (
    compute_extend_boundary_drift,
    compute_frame_ssim,
    compute_luminance_flicker,
    evaluate_temporal_consistency,
)
from services.harness.src.evaluators.vlm_critique import (
    PROHIBITED_EXTERNAL_VENDOR,
    SFW_EXPLICIT_CONTENT_FLAGGED,
    LocalQwenVLCognitiveProvider,
    create_explicit_test_fixture,
    evaluate_vlm_critique,
)
from services.harness.src.khf_quality import KHFQualityHarness, should_run_vlm_critique
from services.workers.src.worker import KeystoneWorker


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
    """Adapts a synchronous SQLAlchemy Session for async KeystoneWorker execution."""

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


def _make_valid_png_bytes(
    width: int = 32,
    height: int = 32,
    color: Tuple[int, int, int] = (40, 120, 200),
) -> bytes:
    """Build a valid RGB PNG image in pure Python."""

    def _chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            r = (color[0] + x * 3 + y * 2) % 256
            g = (color[1] + x * 2 + y * 3) % 256
            b = (color[2] + x + y * 4) % 256
            raw.extend((r, g, b))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + _chunk(b"IEND", b"")
    )


def _signed_envelope(
    *,
    job_id: str,
    user_id: str,
    content_mode: str = "sfw",
    age_verified: bool = True,
    capability_id: str = "image.generation",
    intent: str = "generate",
):
    decision = SimpleNamespace(
        decision_id=f"dec_{uuid.uuid4().hex[:12]}",
        decision="ALLOW",
        reason_code="OK",
        capability_id=capability_id,
        provider_id="comfyui",
        sanitized_arguments={},
    )
    return EnvelopeEngine.create_envelope(
        decision=decision,
        job_id=job_id,
        user_id=user_id,
        intent=intent,
        content_mode=content_mode,
        age_verified=age_verified,
        floor_verdict="pass",
    )


# ---------------------------------------------------------------------------
# 1. test_corrupted_file_fails_deterministic_evaluator
# ---------------------------------------------------------------------------
def test_corrupted_file_fails_deterministic_evaluator():
    """
    Truncated PNG, empty MP4, corrupted MP4 container, and un-evaluated dict-only
    inputs ({'x': 1}) must all fail deterministic.py and KHFQualityHarness.
    """
    valid_png = _make_valid_png_bytes(32, 32)
    assert validate_asset_bytes(valid_png, "image", "image/png").verdict == "pass"

    # 1) Truncated PNG bytes -> verdict == "fail"
    truncated_png = valid_png[:16]
    res_trunc_png = validate_asset_bytes(truncated_png, "image", "image/png")
    assert res_trunc_png.verdict == "fail"
    assert res_trunc_png.score == 0.0
    assert any("CORRUPT_IMAGE" in code for code in res_trunc_png.reason_codes)

    # 2) Empty MP4 bytes -> verdict == "fail"
    res_empty_mp4 = validate_asset_bytes(b"", "video", "video/mp4")
    assert res_empty_mp4.verdict == "fail"
    assert res_empty_mp4.score == 0.0
    assert "EMPTY_ASSET_BYTES" in res_empty_mp4.reason_codes

    # 3) Corrupted / truncated MP4 header -> verdict == "fail"
    corrupt_mp4 = b"\x00\x00\x00\x18corrupt_mp4_container_bytes"
    res_corrupt_mp4 = validate_asset_bytes(corrupt_mp4, "video", "video/mp4")
    assert res_corrupt_mp4.verdict == "fail"
    assert res_corrupt_mp4.score == 0.0
    assert res_corrupt_mp4.reason_codes

    # 4) KHFQualityHarness rejects truncated PNG and un-evaluated dict-only inputs ({"x": 1})
    khf_trunc = KHFQualityHarness.evaluate_output(
        {"bytes": truncated_png, "mime_type": "image/png"},
        prompt="A crisp architectural render",
    )
    assert khf_trunc.verdict == "fail"
    assert khf_trunc.score == 0.0

    khf_unevaluated = KHFQualityHarness.evaluate_output({"x": 1}, prompt="Self-reported stub")
    assert khf_unevaluated.verdict == "fail"
    assert khf_unevaluated.score == 0.0
    assert "UNEVALUATED_INPUT" in khf_unevaluated.reason_codes
    assert "SELF_REPORTED_INPUT_REJECTED" in khf_unevaluated.reason_codes


# ---------------------------------------------------------------------------
# 2. test_ocr_mismatch_fixture_fails_text_fidelity
# ---------------------------------------------------------------------------
def test_ocr_mismatch_fixture_fails_text_fidelity(monkeypatch):
    """
    Synthetic text-image fixture rendering 'HELO WRLD' vs requested 'HELLO WORLD'
    fails ocr.py with OCR_TEXT_MISMATCH, while exact rendered text passes.
    """
    misspelled_img = render_synthetic_text_image("HELO WRLD")
    mismatch_res = evaluate_ocr(misspelled_img, requested_text="HELLO WORLD")

    assert mismatch_res.verdict == "fail"
    assert OCR_TEXT_MISMATCH in mismatch_res.reason_codes
    assert mismatch_res.score is not None and mismatch_res.score < 0.88
    assert mismatch_res.evidence["normalized_extracted_text"] == "HELO WRLD"
    assert mismatch_res.evidence["edit_distance"] == 2

    # Exact match fixture passes OCR text fidelity
    exact_img = render_synthetic_text_image("HELLO WORLD")
    exact_res = evaluate_ocr(exact_img, requested_text="HELLO WORLD")
    assert exact_res.verdict == "pass"
    assert exact_res.score == pytest.approx(1.0)
    assert OCR_TEXT_MISMATCH not in exact_res.reason_codes

    # Orchestrated through KHFQualityHarness
    khf_ocr_fail = KHFQualityHarness.evaluate_output(
        {"bytes": misspelled_img, "mime_type": "image/png", "requested_text": "HELLO WORLD"},
        prompt='Render a neon sign reading "HELLO WORLD"',
    )
    assert khf_ocr_fail.verdict == "fail"
    assert OCR_TEXT_MISMATCH in khf_ocr_fail.reason_codes
    assert "ocr" in khf_ocr_fail.evidence["executed_families"]

    # Clean error when binary OCR is strictly required and absent
    monkeypatch.setattr("services.harness.src.evaluators.ocr._resolve_tesseract_binary", lambda: None)
    strict_res = evaluate_ocr(misspelled_img, requested_text="HELLO WORLD", require_binary=True)
    assert strict_res.verdict == "fail"
    assert OCR_BACKEND_UNAVAILABLE in strict_res.reason_codes


# ---------------------------------------------------------------------------
# 3. test_persona_drift_fixture_fails_identity_threshold
# ---------------------------------------------------------------------------
def test_persona_drift_fixture_fails_identity_threshold():
    """
    Two distinct synthetic portrait fixtures score below DEFAULT_IDENTITY_THRESHOLD (0.72)
    in identity.py and fail with PERSONA_IDENTITY_DRIFT.
    """
    persona_a_ref = create_synthetic_portrait_fixture("persona_a")
    persona_a_pose2 = create_synthetic_portrait_fixture("persona_a_pose2")
    persona_b_drift = create_synthetic_portrait_fixture("persona_b")

    # Mismatched persona identity -> fails below 0.72 with PERSONA_IDENTITY_DRIFT
    drift_res = evaluate_identity(
        candidate=persona_b_drift,
        reference_assets=[persona_a_ref],
        allow_cpu_fallback=True,
    )
    assert drift_res.verdict == "fail"
    assert PERSONA_IDENTITY_DRIFT in drift_res.reason_codes
    assert drift_res.score is not None and drift_res.score < DEFAULT_IDENTITY_THRESHOLD
    assert drift_res.evidence["cosine_similarity"] < DEFAULT_IDENTITY_THRESHOLD

    # Same persona across poses -> passes >= 0.72 threshold (and is computed, not hardcoded 0.90)
    match_res = evaluate_identity(
        candidate=persona_a_pose2,
        reference_assets=[persona_a_ref],
        allow_cpu_fallback=True,
    )
    assert match_res.verdict == "pass"
    assert PERSONA_IDENTITY_DRIFT not in match_res.reason_codes
    assert match_res.score is not None and match_res.score >= DEFAULT_IDENTITY_THRESHOLD
    assert match_res.score != 0.90 and match_res.score != 0.85

    # Orchestrated through KHFQualityHarness with persona reference assets
    khf_drift = KHFQualityHarness.evaluate_output(
        {"bytes": persona_b_drift, "mime_type": "image/png"},
        prompt="Close-up studio portrait of Persona A",
        persona_id=str(uuid.uuid4()),
        reference_assets=[persona_a_ref],
        allow_cpu_fallback=True,
        run_vlm=False,
    )
    assert khf_drift.verdict == "fail"
    assert PERSONA_IDENTITY_DRIFT in khf_drift.reason_codes
    assert "identity" in khf_drift.evidence["executed_families"]


# ---------------------------------------------------------------------------
# 4. test_mode_aware_vlm_rubric_sfw_vs_unrestricted
# ---------------------------------------------------------------------------
def test_mode_aware_vlm_rubric_sfw_vs_unrestricted():
    """
    Explicit fixture passes the UNRESTRICTED VLM critique rubric (which evaluates craft,
    adherence, and composition without penalizing requested explicit/gore/dark content)
    while being flagged by the SFW VLM critique rubric with SFW_EXPLICIT_CONTENT_FLAGGED.
    """
    explicit_intent = {
        "objective": "Explicit nude gothic portrait with visceral crimson gore and dark shadows",
        "subject": "Gothic figure in dramatic chiaroscuro",
        "visual_style": "Dark visceral fine art photography",
        "composition": "Centered three-quarter portrait",
    }
    persona_sheet = {"name": "Nyx", "traits": {"style": "dark gothic"}, "mature": True}

    # Verify PromptCompiler.critique_rubric and H3PromptCompiler.critique_rubric mode discipline (§13.4)
    sfw_rubric = PromptCompiler.critique_rubric(
        mode="sfw",
        intent=explicit_intent,
        persona_sheet=persona_sheet,
    )
    unrestricted_rubric = H3PromptCompiler.critique_rubric(
        mode="unrestricted",
        intent=explicit_intent,
        persona_sheet=persona_sheet,
    )

    assert sfw_rubric["mode"] == "sfw"
    assert sfw_rubric["penalize_explicit_content"] is True
    assert sfw_rubric["flag_explicit_adult_content"] is True

    assert unrestricted_rubric["mode"] == "unrestricted"
    assert unrestricted_rubric["penalize_explicit_content"] is False
    assert unrestricted_rubric["allow_requested_explicit"] is True

    explicit_fixture = create_explicit_test_fixture(
        intent=explicit_intent["objective"],
    )

    # 1) Under UNRESTRICTED mode: explicit fixture is evaluated on craft/adherence/composition and PASSES
    res_unrestricted = evaluate_vlm_critique(
        explicit_fixture,
        intent=explicit_intent,
        content_mode="unrestricted",
        persona_sheet=persona_sheet,
    )
    assert res_unrestricted.verdict == "pass"
    assert res_unrestricted.score is not None and res_unrestricted.score >= 0.70
    assert res_unrestricted.evidence["explicit_content_detected"] is True
    assert res_unrestricted.evidence["explicit_content_penalized"] is False
    assert res_unrestricted.evidence["flagged_explicit"] is False
    assert SFW_EXPLICIT_CONTENT_FLAGGED not in res_unrestricted.reason_codes

    # 2) Under SFW mode: identical explicit fixture is FLAGGED and FAILS
    res_sfw = evaluate_vlm_critique(
        explicit_fixture,
        intent=explicit_intent,
        content_mode="sfw",
        persona_sheet=persona_sheet,
    )
    assert res_sfw.verdict == "fail"
    assert SFW_EXPLICIT_CONTENT_FLAGGED in res_sfw.reason_codes
    assert res_sfw.evidence["flagged_explicit"] is True
    assert res_sfw.evidence["explicit_content_penalized"] is True

    # 3) External aligned vendors are strictly rejected (Invariant 6 / §10)
    with pytest.raises(ValueError, match=PROHIBITED_EXTERNAL_VENDOR):
        LocalQwenVLCognitiveProvider(model="gpt-4o-mini")


# ---------------------------------------------------------------------------
# 5. test_retry_exhaustion_flags_operator_review_and_persists_harness_runs
# ---------------------------------------------------------------------------
def test_retry_exhaustion_flags_operator_review_and_persists_harness_runs(db_session, monkeypatch):
    """
    Force 3 consecutive failing KHF evaluation attempts in KeystoneWorker:
      - Worker stops at KEYSTONE_EVAL_RETRY_MAX=3 budget (3 attempts total).
      - Asset is marked status='needs_review' and metadata_['review_required']=True.
      - 3 durable HarnessRun rows and 3 GenerationAttempt rows are persisted in DB.
      - Temporal evaluator also validates frame sequences & extend boundaries.
    """
    monkeypatch.setenv("KEYSTONE_EVAL_RETRY_MAX", "3")
    monkeypatch.setenv("KEYSTONE_EVAL_BUDGET_VLM_PCT", "100")

    # Verify temporal consistency evaluator on smooth vs strobing frames before worker run
    frame_a = _make_valid_png_bytes(32, 32, (60, 120, 180))
    frame_b = _make_valid_png_bytes(32, 32, (62, 122, 182))
    assert compute_frame_ssim(frame_a, frame_b) > 0.85
    temp_pass = evaluate_temporal_consistency(frames=[frame_a, frame_b, frame_a, frame_b])
    assert temp_pass.verdict == "pass"
    boundary_info = compute_extend_boundary_drift([frame_a, frame_b], [frame_b, frame_a])
    assert boundary_info["boundary_ssim"] > 0.85
    assert compute_luminance_flicker([frame_a, frame_b, frame_a])["flicker_score"] < 0.20

    # Set up User, Project, Job, and initial Asset in DB
    user = User(
        id=str(uuid.uuid4()),
        email="pr7-retry@example.com",
        password_hash="hashed",
        role="user",
        age_verified=True,
        content_mode="sfw",
    )
    project = Project(id=str(uuid.uuid4()), user_id=user.id, name="PR7 Retry Escalation")
    job_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())

    job = Job(
        id=job_id,
        user_id=user.id,
        project_id=project.id,
        capability_id="image.generation",
        provider_id="comfyui",
        workflow_id="flux_dev_t2i",
        workflow_version="1.0.0",
        status="QUEUED",
        content_mode="sfw",
    )
    asset = Asset(
        id=asset_id,
        user_id=user.id,
        project_id=project.id,
        asset_type="image",
        storage_key=f"tenants/{user.id}/assets/{asset_id}/banner.png",
        filename="banner.png",
        mime_type="image/png",
        size_bytes=512,
        status="ready",
        metadata_={"initial": True},
    )
    db_session.add_all([user, project, job, asset])
    db_session.commit()

    envelope = _signed_envelope(
        job_id=job_id,
        user_id=user.id,
        content_mode="sfw",
        capability_id="image.generation",
        intent="generate",
    )

    # Executor returns a misspelled OCR image ("HELO WRLD") on all 3 attempts while "HELLO WORLD" is requested
    misspelled_png = render_synthetic_text_image("HELO WRLD")
    attempt_calls: List[Dict[str, Any]] = []

    async def _failing_executor(env_obj, payload_dict, verified_dict):
        attempt_calls.append(
            {
                "attempt_number": payload_dict.get("attempt_number", 1),
                "is_retry": payload_dict.get("is_retry", False),
                "seed": payload_dict.get("seed"),
                "guidance_multiplier": payload_dict.get("guidance_multiplier"),
            }
        )
        return {
            "asset_id": asset_id,
            "bytes": misspelled_png,
            "mime_type": "image/png",
            "requested_text": "HELLO WORLD",
        }

    worker = KeystoneWorker(executor=_failing_executor)
    async_db = _AsyncSessionAdapter(db_session)

    result = asyncio.run(
        worker.process_job(
            {
                "job_id": job_id,
                "user_id": user.id,
                "asset_id": asset_id,
                "requested_text": "HELLO WORLD",
                "prompt": 'Render a studio banner reading "HELLO WORLD"',
                "envelope": envelope,
            },
            db=async_db,
        )
    )

    # 1) Stopped at retry budget of 3 consecutive failing attempts
    assert len(attempt_calls) == 3
    assert attempt_calls[0]["is_retry"] is False
    assert attempt_calls[1]["is_retry"] is True
    assert attempt_calls[2]["is_retry"] is True
    assert attempt_calls[1]["guidance_multiplier"] == pytest.approx(1.20)
    assert should_run_vlm_critique(is_retry=True, has_persona=False, vlm_budget_pct=0.0) is True

    assert result.accepted is True
    assert result.attempt_count == 3
    assert result.review_required is True
    assert result.status == "needs_review"
    assert result.asset_status == "needs_review"
    assert result.reason_code == OCR_TEXT_MISMATCH

    # 2) Asset in DB is marked status="needs_review" and metadata_["review_required"] = True
    db_session.expire_all()
    updated_asset = db_session.get(Asset, asset_id)
    assert updated_asset is not None
    assert updated_asset.status == "needs_review"
    assert updated_asset.deleted_at is None
    assert isinstance(updated_asset.metadata_, dict)
    assert updated_asset.metadata_.get("review_required") is True
    assert updated_asset.metadata_.get("eval_attempts") == 3
    assert OCR_TEXT_MISMATCH in (updated_asset.metadata_.get("review_reason_codes") or [])

    # 3) 3 durable HarnessRun rows and 3 GenerationAttempt rows persisted in DB
    harness_runs = (
        db_session.execute(
            select(HarnessRun).where(HarnessRun.job_id == job_id).order_by(HarnessRun.created_at)
        )
        .scalars()
        .all()
    )
    assert len(harness_runs) == 3
    for hr in harness_runs:
        assert hr.verdict == "fail"
        assert OCR_TEXT_MISMATCH in (hr.reason_codes or [])
        assert hr.attempt_id is not None

    attempts = (
        db_session.execute(
            select(GenerationAttempt).where(GenerationAttempt.job_id == job_id)
        )
        .scalars()
        .all()
    )
    assert len(attempts) == 3
    assert all(a.success is False for a in attempts)
    assert all(a.failure_code == OCR_TEXT_MISMATCH for a in attempts)

    # 4) Operator review escalation AuditEvent persisted
    audit_events = (
        db_session.execute(
            select(AuditEvent).where(
                AuditEvent.job_id == job_id,
                AuditEvent.event_type == "worker.operator_review_required",
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_events) == 1
    assert audit_events[0].payload["review_required"] is True
    assert audit_events[0].payload["asset_status"] == "needs_review"
