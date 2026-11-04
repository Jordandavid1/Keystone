"""
Milestone M4 E2E Test Suite: Creative Tool Fabric & Quality Harnesses (F19–F23)
Empirical verification of adapters, KHF quality measurement, bounded retry loops,
and provider routing.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.server import app
from services.comfy.src.adapters import (
    ADAPTER_REGISTRY,
    get_adapter,
    list_capabilities,
    validate_adapter_request,
    SUPPORTED_ADAPTERS
)
from services.comfy.src.routing import provider_router
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.khf_quality import KHFQualityHarness
from services.harness.src.retry_loop import BoundedRetryManager
from services.harness.src.worker_bridge import worker_bridge
from packages.contracts.src.models import (
    AuthorityDecision,
    CapabilityManifest,
    ExecutionEnvelope,
    HarnessResult,
    QualityScore,
    RetryPolicy
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# Section 1: Creative Tool Fabric Adapters (F19)
# ============================================================================

class TestCreativeFabricAdapters:
    """Verifies all 7 creative tool fabric adapters and parameter validations."""

    def test_all_seven_adapters_registered(self):
        assert len(ADAPTER_REGISTRY) >= 7
        for ad_name in SUPPORTED_ADAPTERS:
            assert ad_name in ADAPTER_REGISTRY
            adapter = get_adapter(ad_name)
            assert adapter.adapter_name == ad_name
            manifest = adapter.get_manifest()
            assert isinstance(manifest, CapabilityManifest)
            assert manifest.capability_id.startswith(("creative", "image", "video", "identity", "upscale"))

    def test_wan_i2v_parameter_validation(self):
        # Missing source_image_asset_id must fail
        with pytest.raises(ValueError, match="MISSING_ASSET"):
            validate_adapter_request("wan_i2v", {"prompt": "A cat leaping in slow motion"})

        # Valid payload succeeds and returns workflow graph
        res = validate_adapter_request("wan_i2v", {
            "source_image_asset_id": "asset_img_001",
            "prompt": "gentle ocean waves",
            "duration_seconds": 5,
            "resolution": "720p"
        })
        assert res["status"] == "READY"
        assert res["adapter"] == "wan_i2v"
        assert "graph" in res
        assert "WanVideoSampler" in str(res["graph"])

    def test_wan_t2v_parameter_validation(self):
        # Missing prompt must fail
        with pytest.raises(ValueError, match="MISSING_PROMPT"):
            validate_adapter_request("wan_t2v", {})

        with pytest.raises(ValueError, match="MISSING_PROMPT"):
            validate_adapter_request("wan_t2v", {"prompt": "   "})

        res = validate_adapter_request("wan_t2v", {"prompt": "cinematic drone flight over mountains"})
        assert res["status"] == "READY"
        assert "WanVideoModelLoader" in str(res["graph"])

    def test_facefusion_parameter_validation(self):
        # Missing source or target asset must fail
        with pytest.raises(ValueError, match="MISSING_ASSETS"):
            validate_adapter_request("facefusion", {"source_face_asset_id": "face_01"})

        with pytest.raises(ValueError, match="MISSING_ASSETS"):
            validate_adapter_request("facefusion", {"target_asset_id": "target_01"})

        res = validate_adapter_request("facefusion", {
            "source_face_asset_id": "face_01",
            "target_asset_id": "target_01"
        })
        assert res["status"] == "READY"
        assert "FaceFusionSwap" in str(res["graph"])

    def test_upscale_parameter_validation(self):
        with pytest.raises(ValueError, match="MISSING_ASSET"):
            validate_adapter_request("upscale", {})

        res = validate_adapter_request("upscale", {
            "source_image_asset_id": "img_low_res",
            "upscale_factor": 4
        })
        assert res["status"] == "READY"
        assert "ImageUpscaleWithModel" in str(res["graph"])

    def test_unknown_adapter_raises_error(self):
        with pytest.raises(ValueError, match="UNKNOWN_ADAPTER"):
            get_adapter("nonexistent_adapter_xyz")


# ============================================================================
# Section 2: KHF Quality Harness (F20)
# ============================================================================

class TestKHFQualityHarness:
    """Verifies multi-phase output evaluation and dimensional scoring."""

    def test_empty_output_fails_evaluation(self):
        res = KHFQualityHarness.evaluate_output({}, prompt="portrait of a cyberpunk warrior")
        assert res.verdict == "fail"
        assert res.score == 0.0
        assert "EMPTY_OUTPUT_PAYLOAD" in res.reason_codes

    def test_high_quality_output_passes(self):
        output_data = {
            "prompt_adherence": 0.95,
            "technical_quality": 0.92,
            "composition": 0.90,
            "visual_consistency": 0.88,
            "user_satisfaction": 0.90,
            "artifact_score": 0.05,
            "resolution": "1024x1024",
            "format": "png"
        }
        res = KHFQualityHarness.evaluate_output(output_data, prompt="test prompt")
        assert res.verdict == "pass"
        assert res.score >= 0.70
        assert res.runtime_ms is not None and res.runtime_ms >= 0

    def test_high_artifact_density_triggers_rejection_or_warning(self):
        output_data = {
            "prompt_adherence": 0.80,
            "technical_quality": 0.40,
            "composition": 0.50,
            "visual_consistency": 0.50,
            "user_satisfaction": 0.40,
            "artifact_score": 0.65  # Heavy artifacts
        }
        res = KHFQualityHarness.evaluate_output(output_data, prompt="test prompt")
        assert "HIGH_ARTIFACT_DENSITY" in res.reason_codes
        assert res.verdict in ("warn", "fail")

    def test_compute_quality_score_all_dimensions(self):
        qs = KHFQualityHarness.compute_quality_score({
            "prompt_adherence": 0.90,
            "technical_quality": 0.88,
            "composition": 0.85,
            "visual_consistency": 0.87,
            "identity_consistency": 0.86,
            "temporal_consistency": 0.80,
            "artifact_score": 0.08,
            "user_satisfaction": 0.90
        })
        assert isinstance(qs, QualityScore)
        assert 0.0 <= qs.overall <= 1.0
        assert qs.confidence > 0.80
        assert len(qs.evidence.get("strengths", [])) > 0


# ============================================================================
# Section 3: Bounded Retry Loop & Replanning (F21)
# ============================================================================

class TestBoundedRetryLoop:
    """Verifies bounded retry limits on attempts, runtime, and cost budgets."""

    def test_successful_attempt_returns_pass(self):
        manager = BoundedRetryManager()
        manager.record_attempt(
            job_id="job_pass",
            provider_id="comfy.flux",
            capability_id="image.generation",
            prompt_hash="h1",
            success=True,
            cost=1.0
        )
        decision = manager.evaluate_retry()
        assert decision.action == "PASS"
        assert decision.reason == "GENERATION_SUCCEEDED"

    def test_retry_permitted_within_budget(self):
        manager = BoundedRetryManager(policy=RetryPolicy(max_attempts=3, max_estimated_cost=10.0))
        manager.record_attempt(
            job_id="job_retry",
            provider_id="comfy.flux",
            capability_id="image.generation",
            prompt_hash="h1",
            success=False,
            cost=2.0
        )
        decision = manager.evaluate_retry()
        assert decision.action == "RETRY"
        assert decision.attempt_number == 2
        assert "seed" in decision.recommended_adjustments

    def test_max_attempts_exceeded_triggers_replan_or_abort(self):
        manager = BoundedRetryManager(policy=RetryPolicy(max_attempts=2, max_estimated_cost=20.0))
        for _ in range(2):
            manager.record_attempt(
                job_id="job_exhausted",
                provider_id="comfy.flux",
                capability_id="image.generation",
                prompt_hash="h1",
                success=False,
                cost=1.0
            )
        decision = manager.evaluate_retry()
        assert decision.action in ("REPLAN", "ABORT")
        assert "MAX_ATTEMPTS_EXCEEDED" in decision.reason

    def test_cost_ceiling_exceeded_aborts(self):
        manager = BoundedRetryManager(policy=RetryPolicy(max_attempts=5, max_estimated_cost=5.0))
        manager.record_attempt(
            job_id="job_costly",
            provider_id="comfy.flux",
            capability_id="image.generation",
            prompt_hash="h1",
            success=False,
            cost=6.0  # Immediately exceeds 5.0 cost ceiling
        )
        decision = manager.evaluate_retry()
        assert decision.action == "ABORT"
        assert "COST_CEILING_EXCEEDED" in decision.reason


# ============================================================================
# Section 4: Provider Routing Engine (F22)
# ============================================================================

class TestProviderRouting:
    """Verifies capability-based worker routing and fallback handling."""

    def test_select_worker_when_none_registered(self):
        worker_bridge.clear()
        selected = provider_router.select_worker("video.i2v")
        assert selected is None

        dispatch = provider_router.dispatch_envelope({"capability_id": "video.i2v", "job_id": "j1"})
        assert dispatch["status"] == "QUEUED_NO_WORKER"

    def test_select_worker_matches_active_capable_worker(self):
        worker_bridge.clear()
        worker_bridge.register_worker(
            worker_id="w_kaggle_wan",
            worker_type="creative_worker",
            tunnel_url="https://tunnel-wan.ngrok-free.app",
            capabilities=["video.i2v", "video.t2v"]
        )
        selected = provider_router.select_worker("video.i2v")
        assert selected is not None
        assert selected.worker_id == "w_kaggle_wan"

        dispatch = provider_router.dispatch_envelope({"capability_id": "video.i2v", "job_id": "j_wan_01"})
        assert dispatch["status"] == "DISPATCHED"
        assert dispatch["worker_id"] == "w_kaggle_wan"


# ============================================================================
# Section 5: REST API Integration (F23)
# ============================================================================

class TestCreativeApiEndpoints:
    """Verifies /v1/creative endpoints."""

    def test_get_capabilities(self, client: TestClient):
        res = client.get("/v1/creative/capabilities")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 7

    def test_execute_creative_adapter(self, client: TestClient):
        payload = {
            "adapter": "image_gen",
            "parameters": {
                "prompt": "majestic mountain peak at sunset",
                "width": 1024,
                "height": 1024
            }
        }
        res = client.post("/v1/creative/execute", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["adapter"] == "image_gen"
        assert data["status"] == "READY"
        assert "graph" in data

    def test_execute_creative_adapter_invalid_param(self, client: TestClient):
        payload = {
            "adapter": "wan_i2v",
            "parameters": {}  # Missing source_image_asset_id
        }
        res = client.post("/v1/creative/execute", json=payload)
        assert res.status_code == 400
        assert "MISSING_ASSET" in res.json()["detail"]

    def test_quality_evaluate_endpoint(self, client: TestClient):
        payload = {
            "prompt": "a futuristic flying car",
            "output_data": {
                "prompt_adherence": 0.90,
                "technical_quality": 0.85
            }
        }
        res = client.post("/v1/creative/quality/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["verdict"] in ("pass", "warn")
        assert "score" in data

    def test_retry_evaluate_endpoint(self, client: TestClient):
        payload = {
            "attempt_count": 3,
            "cumulative_cost": 3.0,
            "latest_success": False,
            "failure_code": "RENDER_TIMEOUT"
        }
        res = client.post("/v1/creative/retry/evaluate", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["action"] in ("REPLAN", "ABORT", "RETRY")
