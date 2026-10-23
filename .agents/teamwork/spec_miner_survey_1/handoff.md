# Specification Mining Survey Handoff Report (Part 1: §1–§20)

**Subagent ID:** `spec_miner_survey_1`  
**Role:** Specification Miner (`teamwork_preview_spec_miner`)  
**Parent Agent:** Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Target Artifact:** `survey_specs_part1.md`  
**Handoff Type:** Hard (Task complete)  

---

## 1. Observation

1. **Canonical Specification Integrity**:
   - `KEYSTONE_BIBLE.md` exists at repository root (`Total Lines: 1637`, `Total Bytes: 39681`).
   - Verified SHA-256 hash using PowerShell `(Get-FileHash -Algorithm SHA256 'KEYSTONE_BIBLE.md').Hash`:
     `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`.
     This matches the mandated hash in `ORIGINAL_REQUEST.md` line 95 verbatim. The file was not modified, touched, or edited.

2. **Baseline Non-Regression**:
   - `npm test` executed cleanly with exit code 0:
     ```text
     ✔ KEYSTONE preserves plan.v1 and six-part PromptAnatomy (10.0498ms)
     ✔ KEYSTONE preserves all 13 domain playbooks (0.4442ms)
     ✔ compiler remains model-agnostic with chat and reasoning profiles (0.8628ms)
     ℹ tests 3, pass 3, fail 0
     ```
   - Native E2E Test Suite (`node tests/e2e/runner.js`) executed with exit code 0:
     ```text
     Tier 1: Feature Coverage (F1-F12 Isolation)        |   61 |    0 |     566ms |   OK   |
     Tier 2: Boundary & Corner Cases (F1-F12 BVA)       |   60 |    0 |     564ms |   OK   |
     Tier 3: Cross-Feature Combinations                 |    5 |    0 |     570ms |   OK   |
     Tier 4: Real-World 6-Target Scenarios              |    6 |    0 |     812ms |   OK   |
     Total Tests Executed: 132 | Total Passed: 132 | Total Failed: 0
     ```

3. **Cognitive Checkpoint & Bootstrap Harness**:
   - `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb` defines:
     - `MODEL_ID = 'huihui-ai/Huihui-Qwen3.8-27B-abliterated'`
     - `GPU_RESERVE_GIB = 5.0`
     - `HOST_RESERVE_GIB = 12.0`
     - `MODEL_ESTIMATE_GIB = 51.7`
     - `offload = max(0.0, MODEL_ESTIMATE_GIB - max(0.0, gpu_total - GPU_RESERVE_GIB))`
     - `assert offload <= max(0.0, host_available - HOST_RESERVE_GIB)`
   - Founder directives in `ORIGINAL_REQUEST.md` (lines 181–206) explicitly mandate:
     - Plan for ~80 GB of host RAM on Kaggle.
     - Keep whatever fits in 2x T4 VRAM (tensor parallel 2), CPU-offload remainder into host RAM.
     - BF16 default remains locked during build.
     - Documented comparison test of BF16 vs FP16 to be conducted post-build.

4. **Locked Architectural Invariants & Trust Architecture**:
   - `KEYSTONE_BIBLE.md` §2 defines 18 locked invariants (lines 27–47).
   - `KEYSTONE_BIBLE.md` §4 defines system context and trust boundaries (lines 73–110).
   - `KEYSTONE_BIBLE.md` §5 defines prompt authority vs contribution, and 7-tier prompt precedence (lines 114–159).
   - `KEYSTONE_BIBLE.md` §6–§19 defines compatibility (`plan.v1`, `PromptAnatomy`), `PromptIntent`, `CapabilityManifest`, `PromptCompiler`, `CognitiveResult`, `ProposedAction`, `AuthorityDecision`, `ExecutionEnvelope`, `HarnessResult`, `QualityDimensions`, `QualityScore`, `RetryPolicy`, public/internal APIs, and the 13-state job state machine.
   - `KEYSTONE_BIBLE.md` §20 defines sequence diagrams for Normal Generation, Quality Retry, Replan, and Capability Discovery.

---

## 2. Logic Chain

1. **Integrity & Compatibility Premise**:
   Because `KEYSTONE_BIBLE.md` is strictly locked (SHA-256 invariant) and all pre-built code must remain untouched, all architectural schemas, contracts, and state transitions must be extracted verbatim without synthetic modification or assumption drift.

2. **Prompt Authority & Sandbox Invariant**:
   Invariants 1, 2, 3, 5, 8, and 9 establish that KEYSTONE alone is the prompt compiler and runtime authority. Workers cannot mutate prompts, models cannot dispatch tools, and untrusted user/scraped data cannot enter model prompts without passing through Aikido structural delimiters (`<untrusted_content>`) at Precedence Level 7.

3. **Cognitive Containment & Memory Remediation**:
   Invariants 6, 7, 10, and 11 establish that `huihui-ai/Huihui-Qwen3.8-27B-abliterated` is an embedded reasoning backend. Because OOM cannot be resolved by silent model quantization or substitution, memory pressure on Kaggle T4x2 (32 GiB total VRAM) is managed mathematically: offloading ~25–30 GiB of weights to measured host RAM (~80 GiB available), reserving 5 GiB GPU and 12 GiB host headroom, and progressing through the 7 controlled retry profiles in §24.

4. **Tier 0 Decoupling**:
   Kaggle workers are ephemeral (12-hour max session, dynamic tunnel URLs). By establishing an outbound dynamic registration contract (`POST /internal/workers/register`) and cryptographically signed, short-lived `ExecutionEnvelope` tokens with single-use nonces, the Cloud Run control plane remains completely decoupled from transient worker restarts and network volatility.

---

## 3. Caveats

1. **Part 2 Scope Boundary**:
   This survey specifically covers KEYSTONE Bible Part 1 (§1 through §20) and related bootstrap directives. Subsequent sections (§21 PostgreSQL schema, §22 Asset lineage, §23 Creative tool fabric, §24 Kaggle setup notebooks, §25 Workspace UX, §26 Admin workspace, §27 Auth & Stripe billing, §28 Security controls, §29 Proprietary source policy, §30 Legal drafting, §31 Monorepo layout, §32 Epics A–I, and §33 Build order Waves 0–6) are surveyed in companion work or downstream milestones.
2. **Kaggle Hardware Variance**:
   While the founder has provided ~80 GB host RAM as the planning figure, actual available host RAM must be measured dynamically at boot time via the hardware probe, and `HOST_RESERVE_GIB=12.0` must be preserved.
3. **No Code Implementation**:
   Per the Specification Miner archetype, this task is 100% read-only and analytical. No production code, tests, or configurations outside `.agents/teamwork/spec_miner_survey_1` were created or altered.

---

## 4. Conclusion

The specification mining survey for KEYSTONE Bible Part 1 is complete, comprehensive, and fully verified. The resulting document, `survey_specs_part1.md`, contains:
- Complete breakdown of all 18 locked invariants and their strict build constraints.
- Detailed trust boundary definitions, prompt contribution rules, and 7-level prompt precedence hierarchy.
- Comprehensive sequence flows for generation, quality retry, replanning, and discovery.
- Fully typed data schemas for `PromptIntent`, `CapabilityManifest`, `ParameterSpec`, `PromptCompilationRequest`, `CompiledPrompt`, `CognitiveResult`, `ProposedAction`, `AuthorityDecision`, `ExecutionEnvelope`, `HarnessResult`, `QualityScore`, `RetryPolicy`, and core data models.
- Complete mapping of public REST endpoints, internal service endpoints, and the 13-state job state machine.
- Precise hardware arithmetic for running `huihui-ai/Huihui-Qwen3.8-27B-abliterated` on Kaggle T4x2 with CPU offload.
- Comprehensive "Features Discovered" (28 distinct features) and "Edge Cases" (18 verified scenarios) tables.

---

## 5. Verification Method

To independently verify this specification survey and its findings:

1. **Verify Bible SHA-256**:
   ```powershell
   powershell -Command "(Get-FileHash -Algorithm SHA256 'KEYSTONE_BIBLE.md').Hash"
   ```
   *Expected Output:* `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`

2. **Verify Baseline Tests**:
   ```bash
   npm test
   ```
   *Expected Output:* 3 passed, 0 failed.

3. **Verify E2E Tests**:
   ```bash
   node tests/e2e/runner.js
   ```
   *Expected Output:* 132 passed, 0 failed.

4. **Inspect Artifacts**:
   - `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_1\survey_specs_part1.md`
   - `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_1\handoff.md`

5. **Invalidation Conditions**:
   - Any modification or hash change of `KEYSTONE_BIBLE.md`.
   - Any regression in `npm test` or `node tests/e2e/runner.js`.
   - Any departure from the pinned checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated` or BF16 default.
