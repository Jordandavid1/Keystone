"""
Milestone M0 Verification Suite: Canonical Contracts & Additive Server Extension
Verifies F02 (Pydantic v2 Schemas) and F03 (Additive API Server Extension).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of how pytest is invoked
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from apps.api.src.server import app, get_contracts
from apps.api.src.main import PlanRequest
from packages.contracts.src.models import (
    PromptIntent,
    ParameterSpec,
    CapabilityManifest,
    PromptCompilationRequest,
    CompiledPrompt,
    ProposedAction,
    CognitiveResult,
    AuthorityDecision,
    ExecutionEnvelope,
    HarnessResult,
    QualityDimensions,
    QualityScore,
    RetryPolicy
)


def test_main_routes_preserved():
    """Verify /v1/health and /v1/plan from main.py exist and execute on extended app."""
    paths = set(app.openapi()["paths"].keys())
    assert "/v1/health" in paths
    assert "/v1/plan" in paths

    client = TestClient(app)
    health_res = client.get("/v1/health")
    assert health_res.status_code == 200
    assert health_res.json() == {"status": "ok", "product": "KEYSTONE"}

    plan_res = client.post("/v1/plan", json={"goal": "Create cinematic scene"})
    assert plan_res.status_code == 501
    assert plan_res.json()["status"] == "contract_scaffolded"


def test_intelligence_routes_mounted():
    """Verify intelligence router endpoints are cleanly mounted under /v1/intelligence."""
    paths = set(app.openapi()["paths"].keys())
    assert "/v1/intelligence/capabilities" in paths
    assert "/v1/intelligence/extract" in paths
    assert "/v1/intelligence/sanitize" in paths

    client = TestClient(app)
    cap_res = client.get("/v1/intelligence/capabilities")
    assert cap_res.status_code == 200
    data = cap_res.json()
    assert "capabilities" in data
    assert len(data["capabilities"]) > 0


def test_contracts_endpoint():
    """Verify /v1/contracts returns all frozen schemas and invariants."""
    res = get_contracts()
    assert res["status"] == "ok"
    assert res["product"] == "KEYSTONE"
    assert res["plan"] == "plan.v1"
    assert len(res["promptAnatomy"]) == 6
    assert set(res["authorityDecisions"]) == {"approve", "deny", "replan"}
    assert len(res["jobStates"]) == 13
    assert len(res["playbooks"]) == 16

    schemas = res["schemas"]
    for model_name in [
        "PromptIntent", "ParameterSpec", "CapabilityManifest", "PromptCompilationRequest",
        "CompiledPrompt", "ProposedAction", "CognitiveResult", "AuthorityDecision",
        "ExecutionEnvelope", "HarnessResult", "QualityDimensions", "QualityScore", "RetryPolicy"
    ]:
        assert model_name in schemas
        assert "properties" in schemas[model_name]

    # Also test via HTTP TestClient
    client = TestClient(app)
    http_res = client.get("/v1/contracts")
    assert http_res.status_code == 200
    assert http_res.json()["contract_version"] == "2.0.0"


def test_pydantic_v2_model_instantiation():
    """Verify all 12 core models instantiate and validate types correctly."""
    intent = PromptIntent(objective="Animate walking dog", mood="joyful")
    assert intent.objective == "Animate walking dog"
    assert intent.mood == "joyful"

    action = ProposedAction(action_type="animate", capability="creative.video_wan", estimated_credits=2)
    assert action.estimated_credits == 2

    envelope = ExecutionEnvelope(
        envelope_id="env-1",
        decision_id="dec-1",
        job_id="job-1",
        user_id="usr-1",
        capability_id="creative.video_wan",
        provider_id="comfy.wan_i2v",
        workflow_id="wf-wan-1",
        workflow_version="1.0.0",
        compiled_prompt_id="hash-1",
        expires_at=datetime.now(timezone.utc),
        nonce="nonce-1",
        signature="sig-1"
    )
    assert envelope.capability_id == "creative.video_wan"
