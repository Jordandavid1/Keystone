# Handoff Report — spec_miner_survey_2

**Date:** 2026-10-22T16:26:00Z  
**Agent:** `spec_miner_survey_2`  
**Parent Agent:** Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Mission:** Deep specification mining survey of `KEYSTONE_BIBLE.md` Part 2 (§21 through §38) and related requirements in `ORIGINAL_REQUEST.md`.  
**Artifact Produced:** `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_2\survey_specs_part2.md`  

---

## 1. Observation

1. **Canonical Specification Integrity & Lines:**
   - File: `c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md`
   - Verified SHA-256 Checksum: `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788` (measured via `Get-FileHash -Algorithm SHA256`).
   - Line numbers for Part 2 sections observed directly via PowerShell line matcher:
     - §21 PostgreSQL architecture: Line 905
     - §22 Asset architecture: Line 966
     - §23 Creative tool fabric: Line 988
     - §24 Kaggle bootstrap deployment: Line 1016
     - §25 Premium creative workspace: Line 1098
     - §26 Admin workspace: Line 1163
     - §27 Authentication, billing, and credits: Line 1187
     - §28 Security and reliability: Line 1214
     - §29 Proprietary source policy: Line 1255
     - §30 Legal documentation stage: Line 1281
     - §31 Monorepo: Line 1302
     - §32 Implementation epics: Line 1336
     - §33 Fastest production-shaped build order: Line 1441
     - §34 MVP and full-app position: Line 1514
     - §35 Acceptance tests: Line 1551
     - §36 Canonical product statement: Line 1595
     - §37 Change-control rules: Line 1605
     - §38 Current canonical deliverables: Line 1621
     - Total file lines: 1637.

2. **Database Schema State (§21):**
   - File `infrastructure/migrations/versions/0001_core.sql` currently contains 12 tables (`users`, `projects`, `sessions`, `messages`, `assets`, `requests`, `cognitive_runs`, `authority_decisions`, `jobs`, `compiled_prompts`, `harness_runs`, `audit_events`).
   - Bible §21 explicitly mandates **23 tables**. Missing from `0001_core.sql` are: `subscriptions`, `api_keys`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `configuration_bundles`, `asset_relationships`.
   - Core data models in §16 (`GenerationAttempt`, `UserFeedback`, `PromptRevisionRequest`, `PromptRevisionProposal`) and §27 define the schemas for these tables.

3. **Cognition & Kaggle Configuration (§24):**
   - Pinned checkpoint: `huihui-ai/Huihui-Qwen3.8-27B-abliterated` (Bible §11, §24).
   - Notebook `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb` defines:
     `MODEL_ID='huihui-ai/Huihui-Qwen3.8-27B-abliterated'`, `GPU_RESERVE_GIB=5.0`, `HOST_RESERVE_GIB=12.0`, `MODEL_ESTIMATE_GIB=51.7`.
   - Host RAM Directive (ORIGINAL_REQUEST.md, 16:11:55Z): Founder stated verbatim: *"kaggle has around 80gb of system memory so offload the rest of the model into ram"*.
   - Post-Build Benchmark Directive (ORIGINAL_REQUEST.md, 16:13:56Z): *"when its done in it's entirety, test bf16 vs fp16 and see what happens"*. BF16 is default during build; comparison test runs as a benchmark after completion.

4. **Baseline Test Suite Status:**
   - Command: `npm test` -> 3 tests passed (`tests/identity.test.js`), 0 failed.
   - Command: `node --test tests/e2e/runner.js` -> 100% green across all tiers (Tier 1-5, 61 feature tests in `tier1_features.test.js`).

---

## 2. Logic Chain

1. **From Observation 1 & 2 to Schema Architecture:**
   - `KEYSTONE_BIBLE.md` §21 specifies the full set of 23 required relational tables, UUID primary keys, `TIMESTAMPTZ` timestamps, and an immutable ledger.
   - Comparing `0001_core.sql` against §21 reveals that 11 required tables must be added via additive Alembic migrations (`0002_*.py` / `.sql`), specifically addressing credit accounting (`credit_accounts`, `credit_ledger`), subscriptions, asset relationships (`asset_relationships`), prompt compilation attempts, and feedback.
   - The table definitions, foreign keys, indexes, and constraints are fully detailed in `survey_specs_part2.md` Section 4.1.

2. **From Observation 3 to Kaggle Execution Strategy:**
   - On 2x Nvidia T4 (15GB usable VRAM each = 30GB total), unquantized 27B weights (51.7GB) cannot fit without offloading.
   - With 5GB reserved for GPU activations and 12GB reserved for host OS/buffers, exactly 26.7GB of weights are offloaded into host RAM.
   - Kaggle's ~80GB host RAM safely accommodates this 26.7GB offload + 12GB reserve (38.7GB total footprint).
   - If memory fragmentation occurs, the 7 controlled retry profiles (§24) must be followed sequentially. Automatic substitution of quantized checkpoints is strictly prohibited.

3. **From §22, §23, §25, §26 to Vertical Slice & Workspaces:**
   - Asset binaries are kept in object storage with 15-minute signed URLs, while the lineage DAG is tracked in `asset_relationships`.
   - The 7 creative adapters (ComfyUI, Image Gen, Image Edit, Wan I2V, Wan T2V, FaceFusion, Upscale) are gated behind signed `ExecutionEnvelope`s.
   - The UI is canvas-first with 5 desktop regions and standardized progress language ("Understanding your request" -> "Creating" -> "Finishing").
   - The admin workspace provides operational observability and request-to-result tracing without requiring SSH access.

4. **From §27, §28, §30 to Release Security & Legal Readiness:**
   - Financial ledger enforces two-phase commit: `hold` on job creation, `settlement` on success, `release` on failure, preventing double charges.
   - Webhook idempotency protects against duplicate Stripe events.
   - Pre-push tooling and secret scanning guard the closed-source repository.
   - 10 legal commercial drafts must be derived from actual data flows.

5. **From §32, §33, §34, §35 to Execution Order & Acceptance:**
   - Implementation follows Waves 0 through 6 to systematically build contracts, vertical shell, prompt engine, cognition, authority, creative fabric, and release mechanics.
   - Acceptance relies on the 13-point Alpha Gate (§34) and automated §35 acceptance tests (6 identity checks, 7 authority checks, and live Cloud Run E2E script with worker termination recovery).

---

## 3. Caveats

1. **Hardware Verification:** The Kaggle T4x2 environment is tested via mock and offline script logic in this survey. Live execution of notebooks requires the founder to launch the Kaggle sessions with provided credentials.
2. **PostgreSQL Migration Path:** The existing `0001_core.sql` was authored as a raw SQL script rather than an Alembic migration script. Wave 0/1 must ensure Alembic environment (`env.py`, `versions/`) tracks this baseline cleanly without dropping existing schema.
3. **No Other Caveats:** All specifications in §21–§38 and `ORIGINAL_REQUEST.md` have been fully documented.

---

## 4. Conclusion

The specification mining survey of Part 2 (§21 through §38) of `KEYSTONE_BIBLE.md` and related requirements in `ORIGINAL_REQUEST.md` is complete and fully documented in `survey_specs_part2.md`. 
The findings provide an exhaustive blueprint for:
- Implementing the 23 PostgreSQL tables, constraints, and indexes.
- Managing assets and the lineage DAG via short-expiry signed URLs.
- Gating the 7 creative tool fabric adapters behind cryptographic execution envelopes.
- Deploying the Tier 0 Kaggle bootstrap (Qwen 27B vLLM TP=2 + ~80GB RAM CPU offload) and executing the post-build BF16 vs FP16 benchmark.
- Constructing the 5-region premium creative workspace and operator admin console.
- Operating the immutable credits ledger with Stripe test mode.
- Enforcing tenant isolation, proprietary repository guards, and drafting the 10 legal policies.
- Executing Epics A–I across Waves 0–6 and passing the §34 Alpha Gate and §35 Acceptance Test Suite.

---

## 5. Verification Method

1. **Bible Invariant Verification:**
   ```powershell
   (Get-FileHash -Algorithm SHA256 KEYSTONE_BIBLE.md).Hash
   # Must return: 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788
   ```

2. **Baseline Non-Regression Verification:**
   ```powershell
   npm test
   node --test tests/e2e/runner.js
   # Both commands must exit with code 0 and 100% pass rates
   ```

3. **Artifact Review:**
   - Inspect `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_2\survey_specs_part2.md`
   - Verify that all 10 objective domains, the 31 discovered features table, the 10 edge cases table, the 23-table schema specification, and the invariant cross-cutting matrix are fully present.
