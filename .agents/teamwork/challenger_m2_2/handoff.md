# Milestone M2 (Wave 2) Adversarial Challenger Verification Report
## F10 Prompt Compiler, F13 Cognition Connector, and Kaggle Tier 0 Setup

**Agent**: `challenger_m2_2`  
**Working Directory**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\challenger_m2_2`  
**Date**: 2026-10-22  
**Target Milestone**: M2 (Wave 2: F10, F11, F12, F13, F16, F20)  
**Verdict**: **REQUEST_CHANGES** (2 Concrete Vulnerabilities Discovered)  

---

## 1. Observation

Direct empirical observations extracted from test harness execution, command runs, and AST / JSON parsing:

### 1.1 Existing Test Suites Executed
1. `pytest tests/e2e_v2/test_m2_prompt_cognition.py`: **41/41 PASS (100%)**
   ```
   ======================= 41 passed, 2 warnings in 4.18s ========================
   ```
2. `npm test`: **3/3 PASS (100%)**
   ```
   ✔ KEYSTONE preserves plan.v1 and six-part PromptAnatomy (18.0417ms)
   ✔ KEYSTONE preserves all 13 domain playbooks (0.5196ms)
   ✔ compiler remains model-agnostic with chat and reasoning profiles (0.8999ms)
   ```
3. `node tests/e2e/runner.js`: **132/132 PASS (100%)**
   ```
   Total Tests Executed: 132 | Total Passed: 132 | Total Failed: 0
   E2E Suite Verification: 100% GREEN (ALL TIERS PASSING)
   ```
4. `python scripts/verify_invariants.py --require-docs-bible`: **100% INVARIANTS SATISFIED**
   ```
   Root Bible SHA-256 : 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788 [VALID]
   Tracked Pre-Built  : 69 files | Byte-Identical: 69 files | Mismatches: 0
   Pinned Model       : huihui-ai/Huihui-Qwen3.8-27B-abliterated [VERIFIED]
   ```
5. `pytest tests/e2e_v2/test_m2_challenger_adversarial.py -v`: **23/23 PASS (100%)**
   ```
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestModelMutationAdversarial::test_build_completion_request_rejects_all_substitute_models PASSED [  4%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestModelMutationAdversarial::test_complete_method_rejects_substitute_models PASSED [  8%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestModelMutationAdversarial::test_explicit_none_or_empty_model_option_rejected PASSED [ 13%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestModelMutationAdversarial::test_pinned_model_clean_acceptance PASSED [ 17%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestEmptyPromptAdversarial::test_build_completion_request_rejects_empty_prompts PASSED [ 21%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestEmptyPromptAdversarial::test_complete_method_rejects_empty_prompts PASSED [ 26%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_validate_anatomy_missing_each_required_field PASSED [ 30%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_validate_anatomy_whitespace_only_field_values PASSED [ 34%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_validate_anatomy_type_errors PASSED [ 39%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_prompt_compiler_objective_required PASSED [ 43%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_playbook_catalog_and_fallback_resilience PASSED [ 47%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_determinism_stress_1000_iterations PASSED [ 52%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_avalanche_effect_hash_sensitivity_on_positive_prompt_fields PASSED [ 56%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPromptCompilerStress::test_finding_constraints_omission_from_positive_prompt_and_hash PASSED [ 60%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestKaggleHardwareVerification::test_mathematical_cpu_offload_formulas PASSED [ 65%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestKaggleHardwareVerification::test_memory_harness_asserts_failure_on_insufficient_host_ram PASSED [ 69%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestKaggleHardwareVerification::test_finding_notebook_02_json_syntax_corruption PASSED [ 73%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestKaggleHardwareVerification::test_strict_prohibition_of_quantization_in_all_loadable_notebooks PASSED [ 78%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestKaggleHardwareVerification::test_notebook_01_cognition_bootstrap_exact_parameters PASSED [ 82%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPlanningRouterAdversarial::test_plan_empty_goal_returns_400 PASSED [ 86%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPlanningRouterAdversarial::test_compile_empty_objective_returns_400 PASSED [ 91%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPlanningRouterAdversarial::test_compile_unknown_playbook_falls_back_to_general PASSED [ 95%]
   tests/e2e_v2/test_m2_challenger_adversarial.py::TestPlanningRouterAdversarial::test_compile_api_determinism PASSED [100%]
   ======================= 23 passed, 2 warnings in 5.20s ========================
   ```

---

### 1.2 Vulnerability Observations

#### Vulnerability 1 (CRITICAL): `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb` Corrupted JSON Syntax
- **Location**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\KAGGLE_SETUP\notebooks\02_keystone_comfyui_runtime.ipynb` line 88.
- **Verbatim Error**:
  ```bash
  $ python -m json.tool KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb
  Expecting ',' delimiter: line 88 column 8 (char 2958)
  ```
- **Code Inspection**:
  Lines 86–90 of `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb`:
  ```json
  86:     "    \"--gpu-only\",\n",
  87:     "    \"--preview-method\", \"none\"\n",
  88:     ""]\n",
  89:     "print(\"ComfyUI startup command formulated:\")\n",
  ```
  Notice the extra double-quote `""` in `""]\n",` (unlike `KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb` which has `"]\n",`). This breaks JSON syntax, rendering the canonical copy of Notebook 02 unparseable by Jupyter, nbformat, or any automated pipeline.
- **Oracle Blind Spot**: The worker's validation oracle in `tests/e2e_v2/harness/keystone_oracle.js` only checked `fs.existsSync(file)`, never invoking `JSON.parse()` or verifying notebook validity.

#### Vulnerability 2 (HIGH): Constraints Dropped from `positive_prompt` and SHA-256 `prompt_hash`
- **Location**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\packages\prompt_engine\compiler.py` lines 178–184:
  ```python
  # Build positive prompt string for hashing and delivery
  context_str = ", ".join(context_items)
  positive_prompt = f"{anatomy_dict['role']}. Goal: {anatomy_dict['task']}. Context: {context_str}."

  # Compute deterministic SHA-256 prompt hash
  prompt_hash = hashlib.sha256(positive_prompt.encode("utf-8")).hexdigest()
  ```
- **Observation**:
  `PromptCompiler.compile()` accepts `constraints` in `PromptIntent` and puts them into `anatomy_dict["constraints"]`. However, `positive_prompt` is constructed **only** from `role`, `task`, and `context`. `constraints` is completely omitted from `positive_prompt`.
- **Consequence**:
  Because `prompt_hash` is computed strictly from `positive_prompt`, changing or adding constraints in `PromptIntent` produces **identical** `positive_prompt` and **identical** `prompt_hash`.
  ```python
  intent_a = {"objective": "Render villa", "constraints": ["No blur"]}
  intent_b = {"objective": "Render villa", "constraints": ["Strictly no watermarks", "High dynamic range"]}
  assert PromptCompiler.compile(intent_a)["prompt_hash"] == PromptCompiler.compile(intent_b)["prompt_hash"]
  # True! Both produce 64-char hash: c52873ee674ec2f05a963b5168019fe8a14ecb370a5c4ba5d58c89481ec650ff
  ```
  This violates Bible §2 Invariant 3 ("Every model-facing prompt is assembled, compiled, versioned, hashed, and recorded by KEYSTONE") and causes downstream creative workers to never receive the constraints.

#### Vulnerability 3 (MEDIUM): Non-String `playbook` Argument in `PromptCompiler.compile()` Raises `AttributeError`
- **Location**: `packages/prompt_engine/compiler.py` line 155:
  ```python
  pb_lower = (playbook or "").lower()
  ```
- **Observation**: If a caller passes `playbook=123`, `(123 or "")` evaluates to `123`, and calling `123.lower()` raises `AttributeError: 'int' object has no attribute 'lower'`.
- **Mitigation**: Sanitize with `str(playbook or "").lower()`.

---

## 2. Logic Chain

1. **Model Mutation Robustness (PASS)**:
   - Evaluated 29 substitute models across commercial (GPT-4, Claude 3.5), open/aligned (Mistral, Llama, Qwen Instruct), quantized (AWQ, GPTQ, GGUF), and mutated strings.
   - All 29 variants were strictly rejected by both `CognitionConnector.build_completion_request()` and `complete()` with `ValueError("PROHIBITED_CHECKPOINT_MUTATION: ...")`.
   - Pinned checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated` accepted cleanly.
2. **Empty / Whitespace Prompt Robustness (PASS)**:
   - Evaluated 8 empty/whitespace/null variants (`""`, `"   "`, `"\t"`, `"\r\n"`, `None`).
   - All 8 variants were strictly rejected by both `build_completion_request()` and `complete()` with `ValueError("EMPTY_PROMPT: Prompt is required")`.
3. **Kaggle Hardware & CPU Offload Verification (PASS on Math / FAIL on Syntax)**:
   - Mathematical calculations verified: 27B model in BF16 = 51.7 GiB weights. 2x T4 GPUs = 30.0 GiB VRAM. With 5.0 GiB runtime reserve, usable GPU VRAM = 25.0 GiB. Offloaded to host RAM = 26.7 GiB. In an 80 GB host RAM pool with 12.0 GiB host reserve (>= 10 GiB required), available headroom is 68.0 GiB and remaining free memory is 41.3 GiB.
   - All loadable notebooks prohibit quantization (`--quantization`, `load_in_4bit`, `bitsandbytes`, `int4`, `int8`, `awq` absent). `--dtype` is strictly `bfloat16`. 7 retry profiles match Bible §24.
   - **However**, `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb` is syntactically invalid JSON at line 88 (Observation 1.2, Vulnerability 1).
4. **PromptCompiler Anatomy & Hashing (FAIL on Constraints)**:
   - Anatomy validation (`validate_prompt_anatomy`) correctly rejects missing required fields and type mismatches.
   - 1,000 iterations of identical input produces identical SHA-256 prompt hash.
   - **However**, `PromptCompiler.compile()` completely drops `constraints` when generating `positive_prompt` and its SHA-256 hash (Observation 1.2, Vulnerability 2).
5. **Conclusion Derivation**:
   Because Vulnerability 1 breaks the canonical production notebook required for Kaggle deployment and Vulnerability 2 drops prompt constraints and causes hash collisions across different constraint sets, the implementation cannot be approved as complete without remediation.

---

## 3. Caveats

- Live GPU inference on Kaggle was not executed (requires Kaggle GPU session with founder credentials). All hardware checks, calculations, launch scripts, and client adapters were validated statically and via mock fallbacks.
- Baseline 69 files remain 100% byte-identical and unmodified; all findings are located in additive files created during Milestone M2.

---

## 4. Conclusion

**Verdict**: **REQUEST_CHANGES**

The worker must address the following two issues:
1. **Fix JSON syntax in `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb`**:
   At line 88, replace `""]\n",` with `"]\n",` so that the notebook parses as valid JSON.
2. **Incorporate `constraints` into `positive_prompt` and `prompt_hash` in `packages/prompt_engine/compiler.py`**:
   Update `positive_prompt` construction so that constraints are not dropped. For example:
   ```python
   constraints_str = "; ".join(constraints_list) if constraints_list else "None"
   positive_prompt = f"{anatomy_dict['role']}. Goal: {anatomy_dict['task']}. Context: {context_str}. Constraints: {constraints_str}."
   ```
   This ensures that changes to constraints properly modify the compiled model-facing prompt and generate distinct SHA-256 hashes.
3. *(Optional hardening)* In `packages/prompt_engine/compiler.py` line 155, use `str(playbook or "").lower()` to handle non-string playbook inputs gracefully.

---

## 5. Verification Method

To independently verify all findings and test suites:

1. **Verify Corrupted Notebook JSON (Vulnerability 1)**:
   ```bash
   python -m json.tool KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb
   ```
   *Expected result: Exits with code 1 and error `Expecting ',' delimiter: line 88 column 8 (char 2958)`.*

2. **Run Challenger Adversarial Test Suite**:
   ```bash
   pytest tests/e2e_v2/test_m2_challenger_adversarial.py -v
   ```
   *Expected result: 23 passed.*

3. **Run M2 Feature Test Suite**:
   ```bash
   pytest tests/e2e_v2/test_m2_prompt_cognition.py -v
   ```
   *Expected result: 41 passed.*

4. **Run Identity Invariant Tests**:
   ```bash
   npm test
   ```
   *Expected result: 3 passed.*

5. **Run Pre-built Intelligence E2E Suite**:
   ```bash
   node tests/e2e/runner.js
   ```
   *Expected result: 132 passed.*

6. **Verify Immutability & Bible Checksum**:
   ```bash
   python scripts/verify_invariants.py --require-docs-bible
   ```
   *Expected result: 100% INVARIANTS SATISFIED (69/69 files byte-identical).*
