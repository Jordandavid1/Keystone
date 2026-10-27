# Milestone M3 Review and Adversarial Audit Report: Cognition & Authority

**Reviewer Agent:** reviewer_m3_1  
**Archetype:** teamwork_preview_reviewer (reviewer, critic)  
**Parent:** Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Target Deliverable:** Milestone M3 (Wave 3: Cognition & Authority)  
**Date:** 2026-10-23T11:39:00Z  
**Verdict:** **APPROVE**  

---

## 1. Executive Summary

Milestone M3 (Wave 3: Cognition & Authority) implements the complete sovereign authority engine, cryptographic envelope issuance and verification, ephemeral Kaggle worker registration and routing, and Tier 0 hardware memory probe math.

Every requirement from `KEYSTONE_BIBLE.md` (§12, §13, §14, §24) and the Project Orchestrator dispatch instructions was independently scrutinized, executed, stress-tested, and verified:
- **Integrity Audit**: Checked for hardcoded test results, facade logic, bypassed tasks, and self-certifying shortcuts. **ZERO integrity violations found**. The code executes real multi-gate sequential evaluation, canonical HMAC-SHA256 cryptographic signatures, replay cache eviction, and dynamic worker heartbeat tracking.
- **Pre-Built Invariant Audit**: Verified that `apps/api/src/main.py` has **zero modifications** (`git diff apps/api/src/main.py` is empty). All 69 pre-built files remain byte-identical.
- **Canonical Bible Checksum**: Verified that `KEYSTONE_BIBLE.md` remains unchanged with exact SHA-256 hash `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`.
- **Full Verification Suite**: 35/35 M3 tests pass, 47/47 M2 tests pass, 23/23 M1 tests pass, 373/373 E2E v2 tests pass, 3/3 identity invariant tests pass, 132/132 Run 1 E2E tests pass, and 100% of invariant checks pass.

---

## 2. Review Dimensions & Detailed Findings

### A. Correctness & Implementation Quality

1. **Action Types & Capability Namespaces (F14)**:
   - `services/authority/src/rules.py` accurately defines the 6 mandated action types: `generate`, `edit`, `variate`, `animate`, `upscale`, `analyze`.
   - Accurately defines the 6 capability namespaces: `image.generation`, `image.editing`, `video.i2v`, `video.t2v`, `identity.flux_pulid`, `upscale.clarity` (with backward compatibility for `analysis.inspect` and `creative.generation`).
   - Aspect ratio whitelist strictly enforced: `{"1:1", "16:9", "9:16", "4:3", "3:4", "21:9"}`. Out-of-bounds aspect ratios are safely clamped to defaults and flagged with `OUT_OF_BOUNDS_PARAMETER`.
   - Resolution ceilings enforced: 2048x2048 for images, 1080p for video, duration clamped to 1-10s.
   - Required asset IDs enforced: `input_asset_id` for editing/video/upscale, `identity_asset_id` for PuLID.

2. **Deterministic Authority Enforcement (F15)**:
   - `AuthorityEngine` in `services/authority/src/engine.py` executes a sequential 5-stage gate pipeline:
     1. `SafetyPolicyEvaluator`: Scans rationale and parameter text for forbidden terms (`FORBIDDEN_TERMS`), destructive SQL commands (`DROP TABLE`, `TRUNCATE`, etc.), destructive shell operations (`rm -rf`, `chmod -R 777`), and Aikido closing delimiter breakouts (`</untrusted_content>`).
     2. `ParameterBoundaryEvaluator`: Clamps and validates parameter bounds, whitelists, and asset dependencies.
     3. Cost Estimation: Deterministic base credits + resolution/duration/step modifiers.
     4. `CreditBalanceEvaluator`: Validates `available_credits = balance - held >= required_credits`.
     5. Confirmation Policy: Operations exceeding `CONFIRMATION_CREDIT_THRESHOLD` (10 credits) mandate `REQUIRE_CONFIRMATION` (`replan`).
   - Audit Event Emission: Emits structured immutable audit records on every evaluation.

3. **Kaggle Tier 0 Memory Math & Retry Profiles (F16)**:
   - `KAGGLE_SETUP/scripts/probe_hardware.py` implements the exact mathematical proof for Qwen-27B BF16 (51.7 GiB weights) on 2x T4 GPUs ($TP=2$):
     - Total GPU VRAM: 30.0 GiB (2x 15.0 GiB usable address space)
     - CUDA reserve: 5.0 GiB
     - Usable GPU VRAM: $30.0 - 5.0 = 25.0 \text{ GiB}$
     - Required CPU weight offload: $51.7 - 25.0 = \mathbf{26.7 \text{ GiB}}$
     - Max safe host offload ceiling: $80.0 - 12.0 = 68.0 \text{ GiB}$
     - Safe host RAM headroom: $68.0 - 26.7 = \mathbf{41.3 \text{ GiB}}$ ($>40.0\text{ GiB}$).
   - All 7 controlled retry profiles codified: `baseline_tp2`, `memory_conserve`, `context_truncate`, `single_sequence`, `batch_token_conserve`, `swap_heavy`, and `stop_and_report` (Profile 7 enforces `HALT_AND_ESCALATE` and `allow_quantization: False`).
   - Quantization prohibition strictly codified in `PROHIBITED_QUANTIZATIONS`: `["AWQ", "GPTQ", "GGUF", "BitsAndBytes", "FP8", "INT8", "INT4"]`.

4. **Dynamic Ephemeral Worker Handshake (F17)**:
   - `WorkerBridge` in `services/harness/src/worker_bridge.py`:
     - Dynamically registers ephemeral Cloudflare/ngrok tunnels via `register_worker`.
     - 30s heartbeat interval tracking via `heartbeat`.
     - 90s offline detection timeout via `detect_offline_workers`.
     - Capability routing (`route_for_capability`) strictly matches healthy, active workers and filters out offline or draining workers.
     - Graceful session draining via `drain_worker`.

5. **Cryptographic Envelope Security (F18)**:
   - `services/harness/src/envelope.py`:
     - `canonical_serialize` deterministically sorts dictionary keys and formats compact JSON separators `(",", ":")`.
     - HMAC-SHA256 signature generation and constant-time verification (`hmac.compare_digest`).
     - `NonceReplayCache` with TTL guarantees single-use nonces and defends against replay attacks.
     - 300s envelope expiration and $\pm 30$s clock skew tolerance.

6. **Additive REST Router Architecture**:
   - `apps/api/src/routers/authority.py`: Mounts `/v1/authority/evaluate`, `/v1/authority/policies`, `/v1/authority/envelope/issue`, and `/v1/authority/envelope/verify`.
   - `apps/api/src/routers/workers.py`: Mounts `/internal/workers/register`, `/internal/workers/heartbeat`, `/internal/workers`, and `/internal/workers/drain`.
   - `apps/api/src/server.py`: Mounts both routers additively without modifying `apps/api/src/main.py`.

---

## 3. Adversarial Stress-Test Results

Independent adversarial stress tests were constructed and executed against the implementation:

| Test Scenario | Attack / Stress Vector | Expected Outcome | Actual Result | Status |
|:---|:---|:---|:---|:---:|
| **Replay Attack** | Resubmission of identical valid signed envelope | `REPLAY_ATTACK_DETECTED` ValueError on 2nd attempt | Correctly raised `REPLAY_ATTACK_DETECTED` | **PASS** |
| **Payload Tampering (Args)** | Mutation of prompt inside arguments payload after signing | `INVALID_SIGNATURE` HMAC verification failure | Correctly raised `INVALID_SIGNATURE` | **PASS** |
| **Payload Tampering (Capability)**| Elevation of capability to `admin.root_access` after signing | `INVALID_SIGNATURE` HMAC verification failure | Correctly raised `INVALID_SIGNATURE` | **PASS** |
| **Signature Forgery** | Replacement of signature with dummy 64-char hex string | `INVALID_SIGNATURE` HMAC verification failure | Correctly raised `INVALID_SIGNATURE` | **PASS** |
| **Clock Skew (Future)** | Envelope issued 35s in future (exceeding 30s tolerance) | `ENVELOPE_FUTURE_ISSUED` rejection | Correctly raised `ENVELOPE_FUTURE_ISSUED` | **PASS** |
| **Clock Skew (Expired)** | Envelope verified 335s after issuance (exceeding 300s + 30s) | `ENVELOPE_EXPIRED` rejection | Correctly raised `ENVELOPE_EXPIRED` | **PASS** |
| **Aikido Delimiter Breakout** | Injection of `</untrusted_content>` and case variants | DENY decision with `AIKIDO_DELIMITER_BREAKOUT_ATTEMPT` | Blocked all delimiter breakout attempts | **PASS** |
| **SQL Injection** | Injection of `DROP TABLE users;` and `DELETE FROM accounts` | DENY decision with `DESTRUCTIVE_SQL_OPERATION` | Blocked all SQL injection attempts | **PASS** |
| **Command Injection** | Injection of `rm -rf /` and `chmod -R 777 /` | DENY decision with `DESTRUCTIVE_SYSTEM_OPERATION` | Blocked all command injection attempts | **PASS** |
| **Missing Dependency** | Requesting `video.i2v` without `input_asset_id` | DENY decision with `MISSING_REQUIRED_ASSET` | Blocked execution and flagged missing asset | **PASS** |
| **Credit Exhaustion** | Requesting action with credit balance of 0 | DENY decision with `INSUFFICIENT_CREDITS` | Blocked execution and reported deficit | **PASS** |
| **Worker Timeout** | Worker without heartbeat for 95 seconds | Worker marked `OFFLINE`, excluded from routing | Worker marked `OFFLINE`, excluded from routing | **PASS** |

---

## 4. Verification Commands & Independent Test Evidence

All 8 mandatory verification commands were executed and passed 100%:

1. `pytest tests/e2e_v2/test_m3_cognition_authority.py -v`
   - **Result**: `35 passed, 3 warnings in 24.55s`
2. `pytest tests/e2e_v2/test_m2_prompt_cognition.py -v`
   - **Result**: `47 passed, 3 warnings in 22.12s`
3. `pytest tests/e2e_v2/test_m1_core_shell.py -v`
   - **Result**: `23 passed, 3 warnings in 42.88s`
4. `node tests/e2e_v2/runner.js`
   - **Result**: `Total Tests Executed: 373, Total Passed: 373, Total Failed: 0 (11.32s)`
5. `npm test`
   - **Result**: `3 passed, 0 failed (1.57s)`
6. `node tests/e2e/runner.js`
   - **Result**: `Total Tests Executed: 132, Total Passed: 132, Total Failed: 0 (7.41s)`
7. `python scripts/verify_invariants.py --require-docs-bible`
   - **Result**: `100% INVARIANTS SATISFIED (69/69 pre-built files byte-identical)`
8. `git status --porcelain`
   - **Result**: Confirms zero baseline modifications; `apps/api/src/main.py` untouched.

---

## 5. Minor Observations & Recommendations

1. **FastAPI Event Deprecation Warning (Minor, Non-blocking)**:
   - FastAPI emits a deprecation warning regarding `@app.on_event("startup")` in `apps/api/src/server.py`. In future refactoring (e.g., M5 or M6), this can be updated to the modern FastAPI lifespan context manager.
2. **Persistent Audit Event Persistence (Informational)**:
   - `AuthorityEngine` currently stores audit events in its in-memory buffer `self.audit_log` and returns them in the decision metadata. In Milestone M5/M6 when database repositories are integrated with live execution, ensure a worker task flushes these records directly to the `audit_events` PostgreSQL table.

---

## 6. Verdict

**Verdict:** **APPROVE**  
Milestone M3 satisfies all functional, architectural, cryptographic, and invariant requirements. It is certified for production handoff to Milestone M4 (Wave 4: Creative Tool Fabric).
