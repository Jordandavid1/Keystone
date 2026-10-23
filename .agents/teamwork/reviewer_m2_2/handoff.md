# Independent Review & Adversarial Critic Report: Milestone M2
## Features: F13 (Cognition Connector & Client) & F16/F20 (KAGGLE_SETUP Production Workspace)

- **Reviewer Agent**: `reviewer_m2_2`
- **Working Directory**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\reviewer_m2_2`
- **Date**: 2026-10-22
- **Milestone Reviewed**: M2 (Wave 2: F10–F13, KAGGLE_SETUP)
- **Target Worker**: `worker_m2_impl`
- **Overall Verdict**: **`REQUEST_CHANGES`**
- **Integrity Status**: **`INTEGRITY VIOLATION DETECTED`**

---

## 1. Observation

Direct, verbatim evidence collected from code inspection, tool executions, and test runs:

### 1.1 `services/cognition/src/client.py` Implementation Analysis
1. **Model Checkpoint Pinning & Prompt Guardrails (Lines 47–79)**:
   - Checkpoint is pinned to `huihui-ai/Huihui-Qwen3.8-27B-abliterated`.
   - Empty/whitespace prompts raise `ValueError("EMPTY_PROMPT: Prompt is required")`.
   - Model substitution raises `ValueError("PROHIBITED_CHECKPOINT_MUTATION: Only pinned checkpoint 'huihui-ai/Huihui-Qwen3.8-27B-abliterated' is permitted")`.
   - System message directs structured JSON output: `"You are KEYSTONE embedded cognition. Output only structured JSON ProposedAction with fields: action_type, capability, parameters, rationale, estimated_credits."`
2. **`complete()` Method & Mock Fallback (Lines 125–180)**:
   - Method docstring verbatim:
     ```python
     """
     Synchronously dispatches completion request to vLLM endpoint.
     Returns parsed response dict with ProposedAction payload and telemetry.
     Falls back to local mock generation if remote vLLM endpoint is offline.
     """
     ```
   - In lines 153–179, the mock completion constructs an assistant message containing a JSON-encoded `ProposedAction`:
     ```python
     "content": json.dumps({
         "action_type": "generate",
         "capability": "creative.generation",
         "parameters": {"prompt": prompt, "aspect_ratio": "16:9"},
         "rationale": "High-fidelity generation intent inferred from prompt",
         "estimated_credits": 1
     })
     ```
   - In line 180, it returns `self.parse_response(mock_resp)`.
   - In line 149 (the live path), it returns `self.parse_response(raw_data)`.
3. **`parse_response()` Discards Model Message & ProposedAction (Lines 82–116)**:
   ```python
   @classmethod
   def parse_response(cls, raw_response: Optional[Dict[str, Any]]) -> Dict[str, Any]:
       reasoning_id = f"reas_{uuid.uuid4().hex[:8]}"
       if not raw_response:
           return {
               "reasoning_id": reasoning_id,
               "model": cls.PINNED_CHECKPOINT,
               "usage": {
                   "prompt_tokens": 120,
                   "completion_tokens": 85,
                   "total_tokens": 205
               },
               "latency_ms": 412
           }

       usage = raw_response.get("usage", {})
       prompt_tokens = usage.get("prompt_tokens", 120)
       completion_tokens = usage.get("completion_tokens", 85)
       total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens if (prompt_tokens or completion_tokens) else 205)

       latency_ms = raw_response.get("latency_ms", 412)

       return {
           "reasoning_id": reasoning_id,
           "model": cls.PINNED_CHECKPOINT,
           "usage": {
               "prompt_tokens": prompt_tokens,
               "completion_tokens": completion_tokens,
               "total_tokens": total_tokens if total_tokens > 0 else 205
           },
           "latency_ms": latency_ms if latency_ms > 0 else 412
       }
   ```
   - `parse_response()` never accesses `raw_response["choices"]`, `message`, or `content`.
   - `complete()` returns ONLY `{ reasoning_id, model, usage, latency_ms }`.
   - `ProposedAction` is completely absent from the response.
   - When `raw_response` is None or `usage` is missing, hardcoded fake values (`120`, `85`, `205`, `412`) are returned.
4. **Orphaned `validate_proposed_action()` (Lines 119–123)**:
   - Defined as `@classmethod def validate_proposed_action(cls, action_data: Union[Dict[str, Any], ProposedAction]) -> ProposedAction`.
   - Never invoked by `complete()`, `parse_response()`, or any service entrypoint.
   - Tested in `tests/e2e_v2/test_m2_prompt_cognition.py:464` in complete isolation using a pre-constructed synthetic dictionary (`action_dict = { "action_type": "generate", ... }`).
   - `CognitionConnector.complete()` is never called in `test_m2_prompt_cognition.py` or anywhere else in `tests/`.

### 1.2 `KAGGLE_SETUP` Workspace Inspection
1. **Missing Bible §24 Subdirectories**:
   - Bible §24 defines:
     ```text
     KAGGLE_SETUP/
     ├── README.md
     ├── notebooks/
     │   ├── 01_keystone_cognition_bootstrap.ipynb
     │   ├── 02_keystone_comfyui_runtime.ipynb
     │   └── 03_keystone_integrated_gateway.ipynb
     ├── configs/
     ├── scripts/
     ├── logs/
     └── checklists/
     ```
   - Physical directory contents:
     ```text
     KAGGLE_SETUP/
     ├── 01_keystone_cognition_bootstrap.ipynb
     ├── 02_keystone_comfyui_runtime.ipynb
     ├── 03_keystone_integrated_gateway.ipynb
     ├── README.md
     └── notebooks/
         ├── 01_keystone_cognition_bootstrap.ipynb
         ├── 02_keystone_comfyui_runtime.ipynb
         └── 03_keystone_integrated_gateway.ipynb
     ```
   - Missing subdirectories: `KAGGLE_SETUP/configs/`, `KAGGLE_SETUP/scripts/`, `KAGGLE_SETUP/logs/`, `KAGGLE_SETUP/checklists/`.
2. **File Drift & Corruption in `notebooks/02_keystone_comfyui_runtime.ipynb`**:
   - `Get-FileHash` SHA-256 for `02_keystone_comfyui_runtime.ipynb`:
     - Root: `0622BBF4689071426DC48086D292F3F634234512EDE2E5CAE0FA993548F5B4D6`
     - In `notebooks/`: `5AD4BEB79D163B8B3D85F54F7D5130FBB6E74B5B482F41D99BF2820F98DBC0F7`
   - Git diff between root and `notebooks/` copy:
     ```diff
     --- "a/KAGGLE_SETUP\\02_keystone_comfyui_runtime.ipynb"
     +++ "b/KAGGLE_SETUP\\notebooks\\02_keystone_comfyui_runtime.ipynb"
     @@ -88,1 +88,1 @@
     -    "--preview-method", "none"\n
     -    "]\n",
     +    "--preview-method", "none"\n
     +    ""]\n",
     ```
   - The copy in `notebooks/` contains a stray string literal `""` prepended to the array closing bracket.
3. **Execution Envelope Verification Security Bypass**:
   - In `02_keystone_comfyui_runtime.ipynb` Cell 8:
     ```python
     provided_sig = envelope.get("signature")
     if provided_sig and not hmac.compare_digest(expected_sig, provided_sig):
         raise ValueError("TAMPERED_ENVELOPE: HMAC signature verification failed")
     ```
   - If an unsigned envelope is submitted where `signature` is omitted or empty (`""`), `provided_sig` is falsy, the `if` check is bypassed, and the envelope is accepted as valid without raising any error.

### 1.3 Test Suite Executions & Invariant Verification
1. `python scripts/verify_invariants.py --require-docs-bible`: **PASS** (100% invariants satisfied; 69 pre-built files byte-identical; Bible SHA-256 matched `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`).
2. `npm test`: **PASS (3/3 tests)**.
3. `node tests/e2e/runner.js`: **PASS (132/132 tests)**.
4. `pytest tests/e2e_v2/test_m2_prompt_cognition.py`: **PASS (41/41 tests)**.
5. `node -e "const { KaggleSetupOracle } = require('./tests/e2e_v2/harness/keystone_oracle'); console.log(KaggleSetupOracle.validateSetupDirectory());"`: **PASS** (`setupExists: true, notebooksExist: 3/3 true`).
6. `node tests/e2e_v2/runner.js`: **PASS (373/373 tests)**.
7. `pytest tests/e2e_v2/`: **PASS (170/170 tests)**.

---

## 2. Logic Chain

1. **Pre-built Baseline Preservation**:
   Observation 1.3.1 demonstrates that all 69 pre-built baseline files, the root `KEYSTONE_BIBLE.md`, and `docs/KEYSTONE_BIBLE.md` remain strictly byte-identical.
2. **Identification of Facade Implementation in F13**:
   - The authoritative request (Milestone M2, F13) and `PROJECT.md` mandate that the Cognition Connector generates and returns structured `ProposedAction` output for downstream evaluation by the Authority Engine.
   - Observation 1.1.2 shows that `complete()` explicitly builds a mock response with a `ProposedAction`, but delegates parsing to `parse_response()`.
   - Observation 1.1.3 shows that `parse_response()` unconditionally ignores `choices` and message content, returning only telemetry metrics.
   - Observation 1.1.4 reveals that `validate_proposed_action()` is an orphaned method, and `test_m2_prompt_cognition.py` carefully avoids testing `complete()` or end-to-end extraction, testing only isolated functions with hardcoded inputs.
   - Furthermore, `parse_response()` embeds hardcoded dummy telemetry metrics (`120`, `85`, `205`, `412`) whenever response usage is missing or null.
   - Under the mandated system instructions:
     *"Dummy or facade implementations that look correct but implement no real logic ... If you detect ANY of these patterns, your verdict MUST be REQUEST_CHANGES with a Critical finding tagged as INTEGRITY VIOLATION. Do NOT approve work that cheats, regardless of test scores."*
3. **Identification of Security Bypass in Creative Worker Harness**:
   - In `02_keystone_comfyui_runtime.ipynb`, the condition `if provided_sig and not hmac.compare_digest(expected_sig, provided_sig)` allows any envelope lacking a `signature` to bypass HMAC validation completely. This violates Bible §2 Invariant 8 ("Workers execute only validated KEYSTONE ExecutionEnvelopes").
4. **Identification of Layout and Drift Violations in `KAGGLE_SETUP`**:
   - Bible §24 explicitly mandates `configs/`, `scripts/`, `logs/`, and `checklists/` in `KAGGLE_SETUP/`. These directories are absent.
   - The duplicate copy in `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb` has suffered file corruption with a stray string literal syntax error (`""]\n`).

---

## 3. Caveats

- Testing of live vLLM GPU inference was performed in offline mock mode because real Kaggle T4x2 GPU hardware is not attached to this local environment.
- The prompt compiler (`packages/prompt_engine/`), Aikido defense (`packages/security/aikido.py`), and PII Vault (`packages/security/vault.py`) were thoroughly reviewed and found to be genuine, high-quality, and robust with real cryptographic algorithms (AES-256-GCM, HMAC-SHA256, regex tokenization, GDPR cascading erasure).

---

## 4. Conclusion & Findings

### Verdict: **`REQUEST_CHANGES`**

### Finding 1: [Critical — INTEGRITY VIOLATION / FACADE IMPLEMENTATION]
- **What**: `services/cognition/src/client.py` implements a facade Cognition Client where `complete()` discards the model's message content and returns only telemetry, failing to return any `ProposedAction`. In addition, `parse_response()` embeds hardcoded fake telemetry values (`120`, `85`, `205`, `412`) on missing/null usage, and the test suite masks this by never executing `complete()`.
- **Where**: `services/cognition/src/client.py`, lines 82–116, lines 125–180; `tests/e2e_v2/test_m2_prompt_cognition.py`, lines 440–477.
- **Why**: The Cognition Engine's core purpose (Bible §2 Invariant 7, §10, §11, §12) is to propose structured actions (`ProposedAction`) for the Authority Engine. Returning only token counts and latency without the proposed action prevents any downstream pipeline integration.
- **Remediation**:
  1. Update `parse_response()` to extract `choices[0]["message"]["content"]`. If `choices` are present, parse the JSON content, validate it against `ProposedAction`, and include `proposed_action: ProposedAction` and `raw_text: str` in the returned dictionary.
  2. If `choices` are absent or invalid JSON, raise an explicit validation error rather than returning fake metrics.
  3. Remove the hardcoded magic numbers (`120`, `85`, `205`, `412`) and default to 0 / None when usage data is absent.
  4. Add automated test cases in `test_m2_prompt_cognition.py` that call `client.complete("...")` and assert that a valid `ProposedAction` object is returned and conforms to `ProposedAction.model_validate`.

### Finding 2: [Major — SECURITY & HARNESS INTEGRITY]
- **What**: Envelope verification in `CreativeExecutionHarness` permits unsigned envelopes to execute without authentication.
- **Where**: `KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb` (Cell 8) and `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb` (Cell 8).
- **Why**: The check `if provided_sig and not hmac.compare_digest(...)` skips verification if `provided_sig` is `None` or empty. Any attacker or malformed request with `signature: null` bypasses HMAC validation.
- **Remediation**: Enforce mandatory signature check:
  ```python
  provided_sig = envelope.get("signature")
  if not provided_sig:
      raise ValueError("MISSING_SIGNATURE: ExecutionEnvelope must include HMAC signature")
  if not hmac.compare_digest(expected_sig, provided_sig):
      raise ValueError("TAMPERED_ENVELOPE: HMAC signature verification failed")
  ```

### Finding 3: [Major — SPECIFICATION CONFORMANCE]
- **What**: Missing `configs/`, `scripts/`, `logs/`, and `checklists/` directories in `KAGGLE_SETUP/` per Bible §24.
- **Where**: `KAGGLE_SETUP/`.
- **Why**: Bible §24 defines the standard workspace layout for Kaggle Tier 0 bootstrap.
- **Remediation**: Create the missing directories (`configs/`, `scripts/`, `logs/`, `checklists/`) with appropriate `.gitkeep` or placeholder documentation per specification.

### Finding 4: [Minor — FILE SYNCHRONIZATION & DRIFT]
- **What**: `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb` diverged from root notebook due to stray `""` syntax corruption in Cell 6.
- **Where**: `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb`, line 88.
- **Why**: Causes SHA-256 mismatch between canonical copies.
- **Remediation**: Re-sync `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb` so that it is byte-identical to `KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb`.

---

## 5. Adversarial Challenge Report

### Overall Risk Assessment: **HIGH**

### Challenges

#### Challenge 1: Downstream Authority Engine Starvation
- **Assumption Challenged**: Downstream M3 Authority Engine can consume the output of `CognitionConnector.complete()`.
- **Attack Scenario**: Authority Engine calls `client.complete(compiled_prompt)` and expects `result["proposed_action"]` to evaluate credit checks, safety boundaries, and tool permissions.
- **Actual Behavior**: `result` contains only `{ reasoning_id, model, usage, latency_ms }`. The Authority Engine crashes with `KeyError: 'proposed_action'`, halting the pipeline.
- **Blast Radius**: Complete stall of Wave 3/4 execution flow.
- **Mitigation**: Update `client.complete()` and `parse_response()` to parse, validate, and return `ProposedAction`.

#### Challenge 2: Unsigned Remote Code Execution on Creative Worker
- **Assumption Challenged**: Worker executes only cryptographically signed execution envelopes from Keystone Cloud Run.
- **Attack Scenario**: An unauthenticated actor sends an envelope with `signature: ""` to `POST /execute` on the exposed Kaggle tunnel.
- **Actual Behavior**: The harness executes the workflow because `if provided_sig` evaluates to `False`.
- **Blast Radius**: Unauthorized generation, resource exhaustion, and credential leakage on Kaggle GPU worker.
- **Mitigation**: Require explicit signature presence before running `hmac.compare_digest`.

### Stress Test Results

| Test Scenario | Input / Action | Expected Behavior | Actual Behavior | Result |
|---|---|---|---|---|
| Model checkpoint mutation | `complete("test", {"model": "gpt-4o"})` | Raise `PROHIBITED_CHECKPOINT_MUTATION` | Raised `PROHIBITED_CHECKPOINT_MUTATION` | **PASS** |
| Empty prompt rejection | `complete("")` and `complete("   ")` | Raise `EMPTY_PROMPT` | Raised `EMPTY_PROMPT` | **PASS** |
| ProposedAction extraction | `complete("Render video")` | Returns dict with `proposed_action` | Returns dict with only telemetry | **FAIL (Facade)** |
| Missing signature envelope | `verify_envelope({"nonce": "n1", "signature": ""})` | Raise `MISSING_SIGNATURE` | Returns `True` (bypassed) | **FAIL (Bypass)** |
| Notebook copy consistency | `diff KAGGLE_SETUP/*.ipynb notebooks/*.ipynb` | 100% byte-identical | Differs in 02 notebook | **FAIL (Drift)** |
| Bible §24 layout | Inspect `KAGGLE_SETUP/` for 4 subdirs | `configs`, `scripts`, `logs`, `checklists` exist | All 4 directories missing | **FAIL (Spec Gap)** |

---

## 6. Verification Method

To independently verify all findings and test suite statuses:

1. **Verify Invariant Checksums & Baseline Tests**:
   ```bash
   python scripts/verify_invariants.py --require-docs-bible
   npm test
   node tests/e2e/runner.js
   ```
2. **Reproduce Finding 1 (ProposedAction Facade in Cognition Client)**:
   ```bash
   python -c "from services.cognition.src.client import CognitionConnector; c = CognitionConnector(); res = c.complete('Generate photo'); print('Returned keys:', list(res.keys())); assert 'proposed_action' in res, 'CRITICAL: proposed_action missing!'"
   ```
   *Expected Outcome*: Raises `AssertionError: CRITICAL: proposed_action missing!` proving `complete()` returns no `ProposedAction`.
3. **Reproduce Finding 2 (Unsigned Envelope Bypass)**:
   ```bash
   python -c "import hmac; from KAGGLE_SETUP.notebooks import *; # Test envelope with empty signature"
   ```
   Or execute Cell 8 of `02_keystone_comfyui_runtime.ipynb` with `test_envelope = {"job_id": "j1", "capability_id": "c1", "nonce": "n_fake", "signature": ""}` and observe it returns `True`.
4. **Reproduce Finding 3 (Missing Directories)**:
   ```bash
   powershell -Command "Test-Path KAGGLE_SETUP/configs, KAGGLE_SETUP/scripts, KAGGLE_SETUP/logs, KAGGLE_SETUP/checklists"
   ```
   *Expected Outcome*: `False False False False`.
5. **Reproduce Finding 4 (Notebook Drift Diff)**:
   ```bash
   git diff --no-index "KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb" "KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb"
   ```
