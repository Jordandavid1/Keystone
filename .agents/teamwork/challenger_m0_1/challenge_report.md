# Empirical Adversarial Challenge Report: Milestone M0 Contracts & Additive API Server

**Agent**: `challenger_m0_1` (teamwork_preview_challenger)  
**Target Milestone**: M0 (Wave 0: Contract Freeze & Additive Foundation)  
**Parent Orchestrator**: `6f59f58e-8034-400a-bd25-c869a10728f4`  
**Date**: 2026-10-23  
**Verdict**: **APPROVE**  

---

## 1. Executive Summary

Milestone M0 establishes the canonical contract models (`packages/contracts/src/models.py`), typed exports (`packages/contracts/src/index.ts`, `canonical_contracts.json`), and the additive API server shell (`apps/api/src/server.py`).

An empirical adversarial test harness comprising 29 comprehensive stress test cases (`tests/e2e_v2/test_m0_adversarial_challenge.py`) was constructed and executed against the implementation. The suite subjected the system to:
1. Malformed and invalid inputs across all Pydantic v2 models (`PromptAnatomy`, `PromptIntent`, `ParameterSpec`, `CapabilityManifest`, `HarnessResult`, `QualityDimensions`, `QualityScore`, `RetryPolicy`, `GenerationAttempt`, `PromptCompilationRequest`, `CompiledPrompt`, `ProposedAction`, `CognitiveResult`, `AuthorityDecision`, `ExecutionEnvelope`, `UserFeedback`).
2. Nine aggressive prompt injection vectors and delimiter breakout strings (`</untrusted_content>`, DAN mode jailbreaks, nested scripts, SQL injections, null bytes).
3. Boundary value analysis on `QualityScore` (out-of-range floats <0.0 and >1.0), `RetryPolicy` (zero/excessive attempts, negative budgets), and `ProposedAction` (negative credits).
4. Cryptographic execution envelope verification, including HMAC-SHA256 signature tamper detection, expired timestamp rejection, and single-use nonce replay defense.
5. Direct HTTP route invocation against `apps/api/src/server.py` verifying status codes (200, 501, 404, 405, 422), route preservation (`/v1/health`, `/v1/plan`), and additive endpoint wiring (`/v1/contracts`, `/v1/intelligence/*`).

**Test Execution Results**:
- **Total Adversarial Tests**: 29
- **Passed**: 29 (100%)
- **Failed**: 0 (0% failure rate)
- **Regression Invariant Tests**: 373/373 passed (`node tests/e2e_v2/runner.js`), 3/3 passed (`npm test`), 132/132 passed (`node tests/e2e/runner.js`).
- **Invariant & Immutability Verification**: 100% satisfied (`python scripts/verify_invariants.py --require-docs-bible`).

---

## 2. Challenge Summary

**Overall Risk Assessment**: **LOW**

The M0 implementation exhibits strong typing, robust Pydantic v2 validation constraints, and strict preservation of baseline invariants. Two architectural observations and stress-tested assumptions are noted below with recommended mitigations for subsequent milestones.

---

## 3. Empirical Challenges & Stress-Test Analyses

### [Medium] Challenge 1: Open String Typing for `ProposedAction.action_type`

- **Assumption Challenged**: That `ProposedAction` strictly restricts `action_type` to valid categories (`generate`, `edit`, `animate`, `transform`, `analyze`) at the contract deserialization boundary.
- **Attack Scenario**: An adversarial or unconstrained cognitive model output emits an arbitrary or unexpected action type string (e.g. `action_type="delete_database"` or `action_type="unauthorized_exec"`).
- **Blast Radius**: Pydantic v2 deserialization accepts any non-empty string for `action_type` because the field is defined as `action_type: str = Field(...)` rather than a constrained `Literal[...]`. If downstream systems do not perform admission checks, unexpected action strings could propagate.
- **Empirical Findings**:
  - `models.py` line 205 defines `action_type: str = Field(..., description="Action category: generate, edit, animate, transform, analyze")`.
  - This faithfully reflects the root `KEYSTONE_BIBLE.md` §10 specification snippet where `action_type: str`.
  - The Bible architectural model delegates semantic admission and authorization to the **AuthorityEngine** (Milestone M3) rather than rejecting the schema at the serialization layer.
- **Mitigation / Recommendation**: In Milestone M3 (AuthorityEngine), ensure the policy evaluation engine enforces strict whitelist validation (`["generate", "edit", "animate", "transform", "analyze"]`) and denies any unrecognized action types before generating execution tokens.

---

### [Low] Challenge 2: Temporal Invariant Validation on `ExecutionEnvelope`

- **Assumption Challenged**: That `ExecutionEnvelope` validates that `expires_at > issued_at` internally via Pydantic model validation.
- **Attack Scenario**: A corrupted or forged envelope is constructed where `expires_at` is set to a past timestamp relative to `issued_at` (e.g. expired at creation time).
- **Blast Radius**: `ExecutionEnvelope` model instantiation succeeds even if `expires_at <= issued_at`, because `models.py` defines them as independent `datetime` fields without a `@model_validator`.
- **Empirical Findings**:
  - Model instantiation allows past timestamps, but our cryptographic verification harness (`TestExecutionEnvelopeHarness`) and the Milestone M4 worker bridge (`ExecutionEnvelopeOracle.verify`) evaluate `current_time > env.expires_at` and reject expired envelopes with `ENVELOPE_EXPIRED`.
  - In `tests/e2e_v2/harness/keystone_oracle.js`, `validateExecutionEnvelope` explicitly checks `expires_at > issued_at`.
- **Mitigation / Recommendation**: Add a `@model_validator(mode="after")` to `ExecutionEnvelope` in future contract refinement if strict schema-level temporal validation is desired, though runtime rejection at worker ingestion fully protects the execution boundary.

---

### [Low] Challenge 3: FastAPI Startup Deprecation Warning

- **Assumption Challenged**: That the server lifecycle handlers in `server.py` use modern FastAPI 0.100+ patterns.
- **Observation**: During pytest execution, FastAPI emitted:
  `DeprecationWarning: on_event is deprecated, use lifespan event handlers instead.` (line 130 of `server.py`).
- **Blast Radius**: Cosmetic deprecation warning; zero functional impact on Python 3.14 / FastAPI current release.
- **Mitigation**: Update `@app.on_event("startup")` to the `lifespan` context manager in a subsequent maintenance pass if desired.

---

## 4. Stress Test Results Matrix

| Scenario / Vector | Expected Behavior | Actual Behavior | Result |
|:---|:---|:---|:---:|
| `PromptIntent(objective="")` | Raise `ValidationError` (`min_length=1`) | Raised `ValidationError: String should have at least 1 character` | **PASS** |
| `PromptIntent(constraints="str")` | Raise `ValidationError` (list expected) | Raised `ValidationError: Input should be a valid list` | **PASS** |
| `PromptAnatomy()` missing required fields | Raise `ValidationError` for missing fields | Raised `ValidationError` identifying missing `role`, `task`, `outputFormat`, `reasoning` | **PASS** |
| `HarnessResult(phase="unauthorized")` | Raise `ValidationError` (Literal mismatch) | Raised `ValidationError: Input should be 'input', 'proposal', ...` | **PASS** |
| `HarnessResult(score=-0.01)` / `(score=1.01)` | Raise `ValidationError` (out of range [0.0, 1.0]) | Raised `ValidationError: Input should be greater than or equal to 0` | **PASS** |
| `QualityDimensions(prompt_adherence=1.001)` | Raise `ValidationError` (le=1.0) | Raised `ValidationError: Input should be less than or equal to 1` | **PASS** |
| `QualityScore(overall=-0.1)` / `(confidence=1.1)` | Raise `ValidationError` | Raised `ValidationError` | **PASS** |
| `RetryPolicy(max_attempts=0)` / `(max_attempts=11)` | Raise `ValidationError` (ge=1, le=10) | Raised `ValidationError` | **PASS** |
| `ProposedAction(estimated_credits=-1)` | Raise `ValidationError` (ge=0) | Raised `ValidationError: Input should be greater than or equal to 0` | **PASS** |
| `CognitiveResult(proposed_actions=[])` | Raise `ValidationError` (`min_length=1`) | Raised `ValidationError: List should have at least 1 item` | **PASS** |
| `AuthorityDecision(decision="allow")` | Raise `ValidationError` (Literal mismatch) | Raised `ValidationError: Input should be 'approve', 'deny' or 'replan'` | **PASS** |
| `ExecutionEnvelope()` missing signature/nonce | Raise `ValidationError` | Raised `ValidationError` identifying all required cryptographic fields | **PASS** |
| Delimiter breakout: `</untrusted_content><script>` | Safely preserved in data container without eval | Stored safely, serialized cleanly without crash | **PASS** |
| Hostile injection: DAN mode, instruction override | Escaped & tagged in `/v1/intelligence/sanitize` | `</untrusted_content>` escaped to `&lt;/untrusted_content&gt;`, threat level `MALICIOUS` | **PASS** |
| Execution envelope with tampered capability | Verification fails HMAC signature match | Raised `ValueError: SIGNATURE_MISMATCH` | **PASS** |
| Execution envelope expired timestamp | Verification rejects expired token | Raised `ValueError: ENVELOPE_EXPIRED` | **PASS** |
| Execution envelope nonce replay | Second submission of same nonce fails | Raised `ValueError: REUSED_NONCE` | **PASS** |
| `GET /v1/health` | Returns 200 `{"status": "ok", "product": "KEYSTONE"}` | 200 OK with expected JSON | **PASS** |
| `POST /v1/plan` with valid payload | Returns 501 `contract_scaffolded` (preserved baseline) | 501 Not Implemented with baseline message | **PASS** |
| `POST /v1/plan` with empty goal `""` | Returns 422 Unprocessable Entity | 422 Unprocessable Entity | **PASS** |
| `GET /v1/contracts` | Returns 200 OK with all schemas & invariants | 200 OK, full schema dictionary verified | **PASS** |
| `GET /v1/intelligence/capabilities` | Returns 200 OK with 6 supported targets | 200 OK, `intelligence.ux_harvester` present | **PASS** |
| `POST /v1/intelligence/extract` | Returns 200 OK, SHA-256 dedup hash | 200 OK with valid component tree & 64-char hash | **PASS** |
| `GET /v1/nonexistent_route` | Returns 404 Not Found | 404 Not Found | **PASS** |
| `POST /v1/health` (wrong HTTP method) | Returns 405 Method Not Allowed | 405 Method Not Allowed | **PASS** |
| `POST /v1/intelligence/sanitize` malformed body | Returns 422 Unprocessable Entity | 422 Unprocessable Entity | **PASS** |

---

## 5. Unchallenged Areas

- **PostgreSQL 0002 Migration Execution**: The SQL migration script (`infrastructure/migrations/versions/0002_keystone_full_schema.sql`) defines the 11 missing tables. Live execution against a running PostgreSQL instance was not executed in M0 since the live database service is provisioned in Milestone M6 (Cloud Run & Cloud SQL). The DDL syntax and table schema totality were verified statically.
- **Kaggle GPU vLLM Inference**: Real Qwen-27B cognition generation is provisioned in Milestone M3/M4 via `KAGGLE_SETUP`. M0 reviews the contract definitions only.

---

## 6. Final Verdict

### **Verdict**: **APPROVE**

Milestone M0 satisfies all adversarial challenge criteria:
1. All Pydantic v2 contract models raise validation errors when presented with malformed inputs, out-of-bounds metrics, or unauthorized enum/literal values.
2. Delimiter breakout attempts and prompt injections are quarantined and escaped by Aikido defenses without compromising contract data structures.
3. Cryptographic envelope boundaries reliably reject tampered signatures, expired timestamps, and reused nonces.
4. Additive API server routes correctly preserve baseline endpoints, mount intelligence and contracts routers, and handle 404/405/422 status codes properly.
5. All baseline invariants and pre-built files remain byte-identical.
