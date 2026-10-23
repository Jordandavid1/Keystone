"""
Adversarial Stress Test Script for M0 Deliverables
Executed by reviewer_m0_1
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from packages.contracts.src.models import (
    PromptIntent, ParameterSpec, CapabilityManifest,
    PromptCompilationRequest, CompiledPrompt, ProposedAction,
    CognitiveResult, AuthorityDecision, ExecutionEnvelope,
    HarnessResult, QualityDimensions, QualityScore, RetryPolicy,
    GenerationAttempt, PromptAnatomy, UserFeedback,
    PromptRevisionRequest, PromptRevisionProposal
)
from apps.api.src.server import app, get_contracts
from fastapi.testclient import TestClient

def test_models_adversarial():
    print("[1] Testing models.py constraints & validation...")
    
    # 1. PromptIntent min_length=1
    try:
        PromptIntent(objective="")
        assert False, "Should fail on empty objective"
    except ValidationError:
        print("  - PromptIntent rejected empty objective: PASS")

    # 2. ProposedAction non-negative credits
    try:
        ProposedAction(action_type="gen", capability="cap", estimated_credits=-1)
        assert False, "Should fail on negative credits"
    except ValidationError:
        print("  - ProposedAction rejected negative credits: PASS")

    # 3. AuthorityDecision Literal validation
    try:
        AuthorityDecision(
            decision_id="d1", request_id="r1", decision="INVALID_DECISION",
            policy_bundle_version="1.0", capability_registry_version="1.0", harness_bundle_version="1.0"
        )
        assert False, "Should fail on invalid decision literal"
    except ValidationError:
        print("  - AuthorityDecision rejected invalid literal: PASS")

    # 4. HarnessResult score range [0.0, 1.0]
    try:
        HarnessResult(harness_id="h1", harness_version="1.0", phase="input", verdict="pass", score=1.5)
        assert False, "Should fail on score > 1.0"
    except ValidationError:
        print("  - HarnessResult rejected score > 1.0: PASS")

    try:
        HarnessResult(harness_id="h1", harness_version="1.0", phase="input", verdict="pass", score=-0.1)
        assert False, "Should fail on score < 0.0"
    except ValidationError:
        print("  - HarnessResult rejected score < 0.0: PASS")

    # 5. RetryPolicy bounds
    try:
        RetryPolicy(max_attempts=0)
        assert False, "Should fail on max_attempts < 1"
    except ValidationError:
        print("  - RetryPolicy rejected max_attempts=0: PASS")

    try:
        RetryPolicy(max_attempts=11)
        assert False, "Should fail on max_attempts > 10"
    except ValidationError:
        print("  - RetryPolicy rejected max_attempts=11: PASS")

    # 6. UserFeedback rating range [0.0, 5.0]
    try:
        UserFeedback(job_id="j1", user_id="u1", rating=5.5)
        assert False, "Should fail on rating > 5.0"
    except ValidationError:
        print("  - UserFeedback rejected rating > 5.0: PASS")

    # 7. CognitiveResult min_length=1 for proposed_actions
    try:
        CognitiveResult(
            reasoning_id="r1",
            intent=PromptIntent(objective="test"),
            proposed_actions=[],
            confidence=0.9
        )
        assert False, "Should fail on empty proposed_actions"
    except ValidationError:
        print("  - CognitiveResult rejected empty proposed_actions: PASS")

    print("[1] models.py validation: ALL CHECKS PASSED")

def test_server_adversarial():
    print("[2] Testing apps/api/src/server.py under adversarial requests...")
    client = TestClient(app)

    # 1. Health check GET vs POST
    res = client.get("/v1/health")
    assert res.status_code == 200, f"Expected 200 got {res.status_code}"
    res = client.post("/v1/health")
    assert res.status_code == 405, f"Expected 405 Method Not Allowed, got {res.status_code}"
    print("  - /v1/health Method Not Allowed check: PASS")

    # 2. /v1/plan invalid payload (empty body)
    res = client.post("/v1/plan", json={})
    assert res.status_code == 422, f"Expected 422 Unprocessable Entity, got {res.status_code}"
    print("  - /v1/plan 422 on empty body: PASS")

    # 3. /v1/plan with valid body
    res = client.post("/v1/plan", json={"goal": "test goal"})
    assert res.status_code == 501, f"Expected 501 Not Implemented, got {res.status_code}"
    assert res.json()["status"] == "contract_scaffolded"
    print("  - /v1/plan 501 contract scaffolded preserved: PASS")

    # 4. /v1/contracts structure
    res = client.get("/v1/contracts")
    assert res.status_code == 200
    data = res.json()
    assert "schemas" in data
    assert len(data["schemas"]) == 15, f"Expected 15 schemas in server endpoint, got {len(data['schemas'])}"
    print(f"  - /v1/contracts returned {len(data['schemas'])} schemas: PASS")

    # 5. Non-existent route
    res = client.get("/v1/non_existent_route")
    assert res.status_code == 404
    print("  - 404 for unknown route: PASS")

    # 6. CORS options request
    res = client.options("/v1/contracts", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    print("  - CORS options preflight headers: PASS")

    print("[2] server.py adversarial: ALL CHECKS PASSED")

def test_canonical_json_consistency():
    print("[3] Testing canonical_contracts.json consistency with models.py...")
    json_path = REPO_ROOT / "packages" / "contracts" / "src" / "canonical_contracts.json"
    assert json_path.exists(), "canonical_contracts.json missing"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    
    assert data["plan"] == "plan.v1"
    assert len(data["promptAnatomy"]) == 6
    assert len(data["jobStates"]) == 13
    assert set(data["authorityDecisions"]) == {"approve", "deny", "replan"}
    assert len(data["schemas"]) == 18

    # Compare schema for PromptIntent
    gen_schema = PromptIntent.model_json_schema()
    file_schema = data["schemas"]["PromptIntent"]
    assert gen_schema["properties"]["objective"]["type"] == file_schema["properties"]["objective"]["type"]
    print("  - JSON schema registry matches models.py: PASS")

if __name__ == "__main__":
    test_models_adversarial()
    test_server_adversarial()
    test_canonical_json_consistency()
    print("\nALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY!")
