# KEYSTONE Test Infrastructure & Verification Architecture (TEST_INFRA.md)

## 1. Overview & Testing Philosophy

This document defines the authoritative test infrastructure, verification methodology, and execution framework for the **KEYSTONE Multimodal Creative Orchestration Platform (Phase 1)** under the Dual-Track Engineering Protocol defined in `PROJECT.md`.

The test architecture enforces four foundational principles:
1. **Zero-Regression & Identity Preservation**: All pre-built files remain strictly immutable. Baseline regression tests (`npm test` invoking `tests/identity.test.js`) must remain 100% green (3/3 passing) across all milestones. `KEYSTONE_BIBLE.md` checksum (`1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`) is cryptographically verified on every run.
2. **Dual-Track Requirement-Driven Verification**: Every test case is derived directly from authoritative requirements (`KEYSTONE_BIBLE.md` §1–§38, `ORIGINAL_REQUEST.md`, and `PROJECT.md`). Tests verify behavioral contracts, schema freezes, and invariant boundaries opaque-box style rather than internal implementation details.
3. **Comprehensive Feature Coverage (F01–F35)**: Complete coverage spanning the full 35-feature inventory across all 6 build milestones:
   - Wave 0: Contract Freeze & Additive Foundation (F01–F04)
   - Wave 1: Vertical Shell & Repositories (F05–F09)
   - Wave 2: Prompt Engine & Security Barrier (F10–F12)
   - Wave 3: Cognition & Authority (F13–F16)
   - Wave 4: Creative Tool Fabric & Kaggle Workers (F17–F20)
   - Wave 5: Creative Workspaces & Billing (F21–F26)
   - Wave 6: Security, Legal, Guarded Pub & Deploy (F27–F30)
   - Wave 7: Validation, Hardening & Benchmarks (F31–F35)
4. **Deterministic & Isolated Execution**: All tests execute locally without requiring live external network access, paid cloud credentials, or live Kaggle GPU sessions. Contract oracles and realistic synthetic fixtures provide reproducible, isolated execution under Node.js native test runner.

---

## 2. Test Framework & Execution Engine

- **Test Runner**: Node.js Native Test Runner (`node:test` and `node:assert/strict`), native to Node.js v26.12.0.
- **Zero External Test Dependencies**: No third-party runner dependencies (such as Jest or Mocha) are required, preventing supply chain drift and dependency pollution.
- **Pre-Built Test Isolation**: Pre-existing test suites (`tests/identity.test.js`, `tests/e2e/runner.js`) remain untouched and run independently.
- **Execution Commands**:
  - Run complete E2E v2 suite with structured markdown report:
    ```bash
    node tests/e2e_v2/runner.js
    ```
  - Run all E2E v2 tests with native runner:
    ```bash
    node --test tests/e2e_v2/*.test.js
    ```
  - Run baseline immutable identity tests:
    ```bash
    npm test
    ```
  - Run Run 1 intelligence pipeline tests:
    ```bash
    node tests/e2e/runner.js
    ```

---

## 3. Directory Layout & Test Artifacts

```
keystone-cowork/
├── tests/
│   ├── identity.test.js                   # Baseline immutable identity test (3/3 passing, Invariant)
│   ├── e2e/                               # Run 1 E2E Verification Suite (132 tests, Immutable)
│   │   ├── runner.js                      # Run 1 test runner
│   │   └── ...
│   └── e2e_v2/                            # Phase 1 Full E2E Verification Suite (373 tests)
│       ├── runner.js                      # Multi-tier test runner with structured markdown reporting
│       ├── tier1_features.test.js         # Tier 1: Feature Coverage (F01–F35, >=5 tests/feature = 175 tests)
│       ├── tier2_boundaries.test.js       # Tier 2: Boundary & Corner Cases (F01–F35, >=5 tests/feature = 175 tests)
│       ├── tier3_combinations.test.js     # Tier 3: Cross-Feature Combinations & State Transitions (15 tests)
│       ├── tier4_realworld.test.js        # Tier 4: Real-World Creative Workflows (8 tests)
│       └── harness/                       # Verification harness & reference contract oracle
│           ├── loader.js                  # Dynamic implementation / reference oracle resolver
│           └── keystone_oracle.js         # Canonical specification reference oracle for F01–F35
├── TEST_INFRA.md                          # This test infrastructure specification
└── TEST_READY.md                          # Test suite readiness certification & checklist
```

---

## 4. Multi-Tiered Verification Architecture

```
+-----------------------------------------------------------------------------------+
|                        TIER 5: ADVERSARIAL HARDENING                              |
|           White-box stress testing, chaos worker crash, memory exhaustion         |
+-----------------------------------------------------------------------------------+
                                          ^
+-----------------------------------------------------------------------------------+
|                     TIER 4: REAL-WORLD CREATIVE WORKFLOWS                         |
|   End-to-End Scenarios: §35 Animation, Text-to-Video, FaceFusion Identity,         |
|   Bounded Quality Retry, Replan Adaptation, Crash Recovery, Multi-Tenant GDPR     |
+-----------------------------------------------------------------------------------+
                                          ^
+-----------------------------------------------------------------------------------+
|                     TIER 3: CROSS-FEATURE PAIRWISE COMBINATIONS                   |
|   PromptCompiler + Aikido + Vault | Cognition + Action + Authority Engine         |
|   Authority + Ledger + Envelope   | Worker Bridge + ComfyUI Creative Adapter      |
|   Stripe Webhook + Ledger Idempotency | Chaos Worker Crash + Credit Safety        |
+-----------------------------------------------------------------------------------+
                                          ^
+-----------------------------------------------------------------------------------+
|                     TIER 2: BOUNDARY VALUE ANALYSIS (BVA)                         |
|   Empty inputs, max lengths, malformed JSON, delimiter breakouts, bit-flips,      |
|   illegal state transitions, expired signatures (>=5 tests/feat across F01-F35)   |
+-----------------------------------------------------------------------------------+
                                          ^
+-----------------------------------------------------------------------------------+
|                        TIER 1: FEATURE COVERAGE (ISOLATION)                       |
|   Happy-path isolation, parameter validation, schema compliance for F01-F35        |
|               (>=5 test cases per feature = 175 test cases)                       |
+-----------------------------------------------------------------------------------+
                                          ^
+-----------------------------------------------------------------------------------+
|                     TIER 0: BASELINE INVARIANT PRESERVATION                       |
|   npm test (tests/identity.test.js) -> plan.v1, 13 playbooks, compiler => 100%    |
+-----------------------------------------------------------------------------------+
```

---

## 5. Feature Inventory & Coverage Mapping (F01–F35)

| Feature ID | Feature Name | Tier 1 Tests | Tier 2 Tests | Tier 3 Pairwise | Tier 4 Workflows | Milestone | Source Reference |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **F01** | Invariant Verification & Change-Control | 5 | 5 | Yes | Yes | M0 | Bible §2, §37 |
| **F02** | Canonical Contracts & Schema Freeze | 5 | 5 | Yes | Yes | M0 | Bible §6–§19 |
| **F03** | Additive API Server Extension | 5 | 5 | N/A | Yes | M0 | Bible §18, Explorer Survey |
| **F04** | PostgreSQL 23-Table Schema & Migrations | 5 | 5 | Yes | Yes | M0 | Bible §21 |
| **F05** | Relational Data Models & Repositories | 5 | 5 | Yes | Yes | M1 | Bible §21 |
| **F06** | Authentication & Tenant Isolation | 5 | 5 | Yes | Yes | M1 | Bible §27, §28 |
| **F07** | Asset Storage & Short-Expiry URLs | 5 | 5 | Yes | Yes | M1 | Bible §22 |
| **F08** | Lineage DAG Tracking | 5 | 5 | Yes | Yes | M1 | Bible §22 |
| **F09** | Job State Machine Engine | 5 | 5 | Yes | Yes | M1 | Bible §19 |
| **F10** | Prompt Compiler & Playbook Engine | 5 | 5 | Yes | Yes | M2 | Bible §6, §7, §8 |
| **F11** | Aikido Prompt-Injection Defense | 5 | 5 | Yes | Yes | M2 | Bible §5, ORIGINAL_REQUEST |
| **F12** | PII Scrubbing & Tokenization | 5 | 5 | Yes | Yes | M2 | ORIGINAL_REQUEST |
| **F13** | Cognition Connector & Client | 5 | 5 | Yes | Yes | M3 | Bible §11, §24 |
| **F14** | ProposedAction Structured Output | 5 | 5 | Yes | Yes | M3 | Bible §12 |
| **F15** | Authority Engine & Evaluation Rules | 5 | 5 | Yes | Yes | M3 | Bible §13 |
| **F16** | Kaggle Memory Harness & Hardware Probe | 5 | 5 | Yes | N/A | M3 | Bible §24, Directives |
| **F17** | Kaggle Worker Bridge & Registration | 5 | 5 | Yes | Yes | M4 | Bible §24 |
| **F18** | Signed Execution Envelope Engine | 5 | 5 | Yes | Yes | M4 | Bible §14 |
| **F19** | Creative Tool Fabric Adapters | 5 | 5 | Yes | Yes | M4 | Bible §23 |
| **F20** | KAGGLE_SETUP Production Workspace | 5 | 5 | Yes | N/A | M4 | Bible §24 |
| **F21** | Firecrawl 6-Target UX Benchmark | 5 | 5 | Yes | Yes | M5 | ORIGINAL_REQUEST |
| **F22** | UX Research Synthesis Report | 5 | 5 | Yes | Yes | M5 | ORIGINAL_REQUEST |
| **F23** | Canvas-First Premium Workspace | 5 | 5 | N/A | Yes | M5 | Bible §25 |
| **F24** | Operator Admin Console | 5 | 5 | Yes | N/A | M5 | Bible §26 |
| **F25** | Credits Ledger Engine & Two-Phase Commit | 5 | 5 | Yes | Yes | M5 | Bible §27 |
| **F26** | Stripe Test-Mode Billing & Webhooks | 5 | 5 | Yes | N/A | M5 | Bible §27 |
| **F27** | Proprietary Policy & Guarded Publication | 5 | 5 | Yes | N/A | M6 | Bible §29, §38 |
| **F28** | Legal Documentation Suite | 5 | 5 | N/A | N/A | M6 | Bible §30 |
| **F29** | Cloud Run & Infrastructure Deployment | 5 | 5 | N/A | N/A | M6 | Bible §3, §24 |
| **F30** | PII Vault Compliance Audit | 5 | 5 | N/A | Yes | M6 | ORIGINAL_REQUEST |
| **F31** | Bible §35 Acceptance Test Automation | 5 | 5 | N/A | Yes | M7 | Bible §35 |
| **F32** | Bible §34 Alpha Gate Verification | 5 | 5 | N/A | Yes | M7 | Bible §34 |
| **F33** | Opaque-Box E2E Test Suite (Tiers 1–4) | 5 | 5 | N/A | N/A | M7 | Dual Track Protocol |
| **F34** | Tier 5 Adversarial Coverage Hardening | 5 | 5 | Yes | Yes | M7 | Dual Track Protocol |
| **F35** | Post-Build BF16 vs FP16 Comparative Benchmark | 5 | 5 | N/A | N/A | M7 | Founder Directive |
| **Total** | **All 35 Features across 4 Tiers** | **175** | **175** | **15** | **8** | — | **373 Tests** |

---

## 6. Coverage Thresholds & Quality Gates

1. **Gate 1: Baseline Preservation Gate**:
   - `npm test` must be 100% passing (3/3 passing) at all times.
   - Zero modifications to baseline files (`tests/identity.test.js`, `tests/e2e/runner.js`, `tests/e2e/*.test.js`).
2. **Gate 2: Bible SHA-256 Invariant Gate**:
   - `KEYSTONE_BIBLE.md` checksum must match `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`.
3. **Gate 3: Feature Completeness Gate**:
   - Every feature (F01–F35) must maintain >=5 Tier 1 isolation tests and >=5 Tier 2 boundary tests (>=10 tests/feature).
4. **Gate 4: Cross-Feature Integration Gate**:
   - Minimum 15 pairwise interaction tests covering state transitions, credit safety, and execution envelope cryptographic verification.
5. **Gate 5: Real-World Workflow Gate**:
   - Minimum 8 end-to-end creative workflows covering complete lifecycle from natural language intent to asset delivery, lineage DAG recording, and browser refresh state recovery.
6. **Gate 6: Zero Regression & Defect Escalation**:
   - Any test failure in implementation code must be escalated to the responsible implementation agent. QA role applies only to test defects.

---

## 7. How to Execute Tests

### Complete E2E v2 Test Suite (Recommended)
```bash
node tests/e2e_v2/runner.js
```
*Expected output: 373/373 passed (100% green) in ~3 seconds.*

### Individual Tiers
```bash
# Tier 1: Feature Coverage (Isolation)
node --test tests/e2e_v2/tier1_features.test.js

# Tier 2: Boundary & Corner Cases (BVA)
node --test tests/e2e_v2/tier2_boundaries.test.js

# Tier 3: Cross-Feature Combinations & State Transitions
node --test tests/e2e_v2/tier3_combinations.test.js

# Tier 4: Real-World Creative Workflows
node --test tests/e2e_v2/tier4_realworld.test.js
```

### Baseline Tests
```bash
npm test
node tests/e2e/runner.js
```
