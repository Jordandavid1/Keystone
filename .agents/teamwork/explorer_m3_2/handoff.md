# Milestone M3 Handoff Report: Cognition & Authority Blueprint

**Agent:** explorer_m3_2  
**Role:** teamwork_preview_explorer  
**Parent:** Project Orchestrator (Conversation ID: `6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Target Milestone:** M3 (Wave 3: Cognition & Authority)  
**Date:** 2026-10-23T11:05:00Z  
**Primary Deliverable:** `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_2\m3_cognition_authority_blueprint.md`  

---

## 1. Observation

1. **Contracts (`packages/contracts/src/models.py`)**:
   - `ProposedAction` is defined at lines 201–220 with fields: `action_type: str`, `capability: str`, `parameters: Dict[str, Any]`, `rationale: str`, `estimated_credits: int`.
   - `AuthorityDecision` is defined at lines 233–253 with fields: `decision_id: str`, `request_id: str`, `decision: Literal["approve", "deny", "replan"]`, `capability_id: Optional[str]`, `provider_id: Optional[str]`, `sanitized_arguments: Dict[str, Any]`, `reason_codes: List[str]`, `policy_bundle_version: str`, `capability_registry_version: str`, `harness_bundle_version: str`.
   - `ExecutionEnvelope` is defined at lines 255–275 with fields: `envelope_id`, `decision_id`, `job_id`, `user_id`, `capability_id`, `provider_id`, `workflow_id`, `workflow_version`, `compiled_prompt_id`, `arguments`, `input_asset_ids`, `issued_at`, `expires_at`, `nonce`, `signature`.

2. **Cognition Client (`services/cognition/src/client.py`)**:
   - Line 21 pins `PINNED_CHECKPOINT = "huihui-ai/Huihui-Qwen3.8-27B-abliterated"`.
   - Lines 53–56 strictly reject any checkpoint mutation attempt:
     ```python
     if requested_model != cls.PINNED_CHECKPOINT:
         raise ValueError(f"PROHIBITED_CHECKPOINT_MUTATION: Only pinned checkpoint '{cls.PINNED_CHECKPOINT}' is permitted")
     ```
   - Lines 120–135 handle markdown code fences and JSON extraction with fallback.

3. **Database Models & Tables (`apps/api/src/db/models.py`)**:
   - `AuditEvent` (lines 300–311): mapped to `audit_events` table with `id`, `actor_type`, `actor_id`, `event_type`, `request_id`, `job_id`, `data` (JSON), `created_at`.
   - `CreditAccount` (lines 359–374): mapped to `credit_accounts` table with `balance: BigInteger`, `held_balance: BigInteger`. Available balance is `balance - held_balance`.
   - `CreditLedger` (lines 379–397): mapped to `credit_ledger` table with transaction types `DEPOSIT`, `HOLD`, `SETTLEMENT`, `RELEASE`, `REFUND`.

4. **Kaggle Hardware Verification (`KAGGLE_SETUP/scripts/probe_hardware.py`)**:
   - Lines 11–14 define: `MODEL_WEIGHTS_GIB = 51.7`, `GPU_RESERVE_GIB = 5.0`, `HOST_RESERVE_GIB = 12.0`, `TOTAL_GPU_VRAM_GIB = 30.0`.
   - Calculates `usable_gpu_vram = 25.0 GiB` and `required_cpu_offload = 26.7 GiB`.
   - `KAGGLE_SETUP/configs/vllm_config.json` configures: `"tensor_parallel_size": 2`, `"cpu_offload_gb": 27`, `"dtype": "bfloat16"`, `"max_model_len": 2048`, `"max_num_seqs": 4`, `"gpu_memory_utilization": 0.90`.

5. **Server Additive Architecture (`apps/api/src/server.py`)**:
   - Lines 18–30 import `apps.api.src.main: app` byte-identically, mounting routers for M1 (`auth`, `projects`, `sessions`, `assets`, `jobs`) and M2 (`planning`).
   - M3 endpoints can be mounted additively via `cognition_router`, `authority_router`, and `workers_router`.

6. **Current Test Suite Execution**:
   - `pytest tests/e2e_v2/test_m2_prompt_cognition.py`: 47 passed in 14.25s.
   - `pytest tests/e2e_v2/test_m1_core_shell.py`: 23 passed in 22.95s.
   - Zero test regressions.

---

## 2. Logic Chain

1. **Structured Output & Capability Typing (F14)**:
   - *From Observation 1 & 2*: `ProposedAction` in `contracts` allows flexible dictionaries. However, Bible §12 and M3 requirements dictate strict typing across 6 action types (`generate`, `edit`, `variate`, `animate`, `upscale`, `analyze`) and 6 capability namespaces (`image.generation`, `image.editing`, `video.i2v`, `video.t2v`, `identity.flux_pulid`, `upscale.clarity`).
   - *Therefore*: Designed strict validation schemas enforcing parameter boundary constraints (aspect ratio whitelist, 2048x2048 ceiling, 1080p video ceiling, step ranges) and a deterministic formula for `estimated_credits` with capability-specific multipliers.
   - *Fallback Logic*: Built multi-stage error recovery that strips markdown wrappers, repairs syntax, and falls back to a deterministic safe proposal if Qwen emits corrupt output, ensuring the pipeline never crashes.

2. **Authority Decision Engine (F15)**:
   - *From Observation 1 & 3*: The authority engine must be the sole gatekeeper approving execution envelopes (§2 Invariant 9).
   - *Therefore*: Designed `AuthorityEngine` with three sequential evaluators:
     1. `SafetyPolicyEvaluator`: Prohibits forbidden terms (CSAM, malware) and destructive SQL/system commands, verifying Aikido delimiter quarantine.
     2. `CreditBalanceEvaluator`: Checks `CreditAccount.balance - CreditAccount.held_balance >= estimated_credits`. If deficient, emits `DENY` with `INSUFFICIENT_CREDITS`.
     3. `ParameterBoundaryEvaluator`: Clamps or rejects out-of-bounds parameters.
   - *Decisions*: Maps `ALLOW` $\to$ `approve`, `DENY` $\to$ `deny`, and `REQUIRE_CONFIRMATION` $\to$ `replan` (for actions > 10 credits or destructive overrides). Emits structured audit records to `audit_events`.

3. **Kaggle Memory Harness & 7 Retry Profiles (F16)**:
   - *From Observation 4 & User Directives*: The 27B model in BF16 requires 51.7 GiB. 2x T4 GPUs provide 32 GB raw VRAM, yielding 25.0 GiB usable for weights under $TP=2$ with 5.0 GiB reserved for CUDA runtime and KV scratchpad.
   - *Therefore*: The remaining $51.7 - 25.0 = 26.7 \text{ GiB}$ must be CPU-offloaded into the ~80GB Kaggle host RAM pool. After preserving 12.0 GiB host reserve, 68.0 GiB is available, leaving 41.3 GiB headroom.
   - *Retry Invariant*: Model quantization is strictly prohibited (§2 Invariant 10, §11). Defined all 7 controlled retry profiles from baseline $TP=2$ to single-sequence execution, down to profile 7 (`stop_and_report`).

4. **Kaggle Worker Bridge & Ephemeral Registration (F17)**:
   - *From Observation 4 & System Context*: Kaggle sessions are ephemeral (~9-12h lifespan) and assign dynamic tunnel hostnames (Cloudflare / ngrok).
   - *Therefore*: Designed `POST /internal/workers/register` for dynamic registration, with challenge health check ping, 30s heartbeat loop (`POST /internal/workers/heartbeat`), and 90s timeout for offline worker detection and automated job requeuing.

5. **Signed Execution Envelope Engine (F18)**:
   - *From Observation 1*: `ExecutionEnvelope` carries HMAC-SHA256 signature, nonce, and expiration.
   - *Therefore*: Designed `EnvelopeEngine` with canonical JSON serialization (sorted keys, compact delimiters), HMAC-SHA256 signature generation/verification, in-memory TTL nonce cache for single-use replay defense, and 300s expiration with $\pm 30$s clock skew tolerance.

---

## 3. Caveats

1. **Read-Only Invariant**: As an explorer subagent, I have strictly preserved all existing source files. No source code was modified during this turn.
2. **Kaggle GPU Availability**: Actual Kaggle GPU execution depends on the founder launching the notebooks with active Cloudflare tunnels. The architecture provides full local mock fallbacks for offline testing and development.
3. **BF16 vs FP16 Comparative Benchmark**: The founder directive specifies that BF16 remains the pinned production default, and the comparative FP16 benchmark will be executed post-build during Milestone M7.

---

## 4. Conclusion

The comprehensive architectural blueprint for Milestone M3 (Wave 3: Cognition & Authority) is complete and recorded in `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_2\m3_cognition_authority_blueprint.md`.

All 5 core features (F14, F15, F16, F17, F18) are fully designed, with:
- Strictly-typed ProposedAction schemas for all 6 action types across 6 capability namespaces.
- Deterministic credit calculation rules and parameter boundary validation.
- Multi-gate Authority Decision Engine with audit event logging.
- Exact 26.7 GiB CPU weight offload math and 7 controlled retry profiles.
- Dynamic ephemeral worker handshake with 30s heartbeat loop.
- Cryptographically signed ExecutionEnvelopes with replay attack prevention.
- Additive REST router mounting plan for `apps/api/src/server.py`.
- Complete test matrix for `tests/e2e_v2/test_m3_cognition_authority.py`.

The downstream implementation worker (`worker_m3`) can immediately execute implementation following this blueprint.

---

## 5. Verification Method

1. **Inspect Blueprint Deliverable**:
   - View `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_2\m3_cognition_authority_blueprint.md`
   - Confirm sections 1 through 9 cover all required aspects of F14–F18, API routing, and test suite design.
2. **Inspect Working Directory Artifacts**:
   - `DISPATCH.md`: Record of dispatch prompt.
   - `BRIEFING.md`: Working memory and state tracking.
   - `progress.md`: Liveness heartbeat and milestone checklist.
   - `handoff.md`: This 5-component handoff report.
3. **Verify Baseline Non-Regression**:
   ```powershell
   pytest tests/e2e_v2/test_m2_prompt_cognition.py
   pytest tests/e2e_v2/test_m1_core_shell.py
   ```
   Both commands must exit with code 0 (100% green).
