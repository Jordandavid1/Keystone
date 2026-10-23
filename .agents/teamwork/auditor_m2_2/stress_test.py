import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
import pytest
from services.cognition.src.client import CognitionConnector, PINNED_CHECKPOINT
from packages.prompt_engine.compiler import PromptCompiler, validate_prompt_anatomy
from packages.contracts.src.models import ProposedAction

print("Starting Auditor Stress Tests...")

# 1. Stress test CognitionConnector.parse_response with various markdown formatting
markdown_cases = [
    '```json\n{"action_type": "generate", "capability": "creative.generation", "parameters": {}, "rationale": "test", "estimated_credits": 1}\n```',
    '```\n{"action_type": "generate", "capability": "creative.generation", "parameters": {}, "rationale": "test", "estimated_credits": 1}\n```',
    '{"action_type": "generate", "capability": "creative.generation", "parameters": {}, "rationale": "test", "estimated_credits": 1}',
    '   \n\n```json\n{"action_type": "generate", "capability": "creative.generation", "parameters": {}, "rationale": "test", "estimated_credits": 1}\n```  \n'
]

for idx, md in enumerate(markdown_cases):
    raw = {
        "choices": [{"message": {"role": "assistant", "content": md}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    }
    parsed = CognitionConnector.parse_response(raw)
    assert parsed["proposed_action"] is not None, f"Failed case {idx}"
    assert parsed["proposed_action"].action_type == "generate"
print("PASS: Markdown code fence stripping in CognitionConnector")

# 2. Stress test invalid ProposedAction schemas
invalid_actions = [
    '{"action_type": "", "capability": "c"}', # missing fields
    '{"action_type": "generate", "capability": "c", "parameters": "not a dict", "rationale": "r", "estimated_credits": 1}',
    'not even json',
    '{"random": 123}'
]

for idx, inv in enumerate(invalid_actions):
    raw = {"choices": [{"message": {"role": "assistant", "content": inv}}]}
    try:
        CognitionConnector.parse_response(raw)
        assert False, f"Expected error on invalid action {idx}"
    except ValueError as e:
        assert "INVALID_PROPOSED_ACTION" in str(e)
print("PASS: Rejection of malformed ProposedAction in parse_response")

# 3. Stress test prompt hash sensitivity in PromptCompiler
c1 = PromptCompiler.compile({"objective": "Test", "constraints": ["A"]}, playbook="general")
c2 = PromptCompiler.compile({"objective": "Test", "constraints": ["B"]}, playbook="general")
assert c1["prompt_hash"] != c2["prompt_hash"]
assert "Constraints: A" in c1["positive_prompt"]
assert "Constraints: B" in c2["positive_prompt"]
print("PASS: Constraints sensitivity in PromptCompiler positive_prompt & hash")

# 4. Stress test non-string playbook inputs in PromptCompiler
for bad_pb in [123, None, [], {}, object(), False, True]:
    res = PromptCompiler.compile({"objective": "Test"}, playbook=bad_pb)
    assert res["provenance"]["playbook"] == "general"
print("PASS: Type resilience for playbook argument in PromptCompiler")

# 5. Stress test notebook HMAC signature verification with invalid signatures
nb = json.load(open("KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb", encoding="utf-8"))
# Find cell with CreativeExecutionHarness definition
harness_cell = None
for cell in nb["cells"]:
    src = "".join(cell.get("source", []))
    if "class CreativeExecutionHarness" in src:
        harness_cell = src
        break

assert harness_cell is not None
exec_scope = {}
exec(harness_cell, exec_scope)
harness = exec_scope["CreativeExecutionHarness"]()

# Test missing signature
try:
    harness.verify_envelope({"nonce": "n1", "job_id": "j1", "capability_id": "cap1"})
    assert False, "Should fail on missing signature"
except ValueError as e:
    assert "MISSING_SIGNATURE" in str(e)

# Test empty signature
try:
    harness.verify_envelope({"nonce": "n2", "job_id": "j1", "capability_id": "cap1", "signature": ""})
    assert False, "Should fail on empty signature"
except ValueError as e:
    assert "MISSING_SIGNATURE" in str(e)

# Test tampered signature
try:
    harness.verify_envelope({"nonce": "n3", "job_id": "j1", "capability_id": "cap1", "signature": "bad_sig_1234567890"})
    assert False, "Should fail on bad signature"
except ValueError as e:
    assert "TAMPERED_ENVELOPE" in str(e)

# Test valid signature
import hmac, hashlib
payload = "j1:cap1:n4"
expected_sig = hmac.new("keystone_dev_secret".encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
valid_env = {"nonce": "n4", "job_id": "j1", "capability_id": "cap1", "signature": expected_sig}
assert harness.verify_envelope(valid_env) is True

# Test nonce replay
try:
    harness.verify_envelope(valid_env)
    assert False, "Should fail on replayed nonce"
except ValueError as e:
    assert "INVALID_NONCE" in str(e)

print("PASS: CreativeExecutionHarness cryptographic HMAC & nonce replay verification")

print("\nALL 5 AUDITOR STRESS TESTS PASSED EMPIRICALLY!")
