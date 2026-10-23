# Project: KEYSTONE Phase 1

## Architecture

KEYSTONE is a sovereign, deterministic generative creative engine built around a model-agnostic prompt compiler, cognitive reasoning backend, authority enforcement, and ephemeral GPU workers.

### 1. Invariant System Boundaries & Trust Model
- **Prompt Authority (§2 Invariant 1, §5)**: KEYSTONE alone compiles prompts. Workers cannot mutate compiled prompts. Models cannot dispatch tools directly.
- **Cognition Checkpoint (§2 Invariant 6, §11, §24)**: Pinned checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated` running on Kaggle 2x Nvidia T4 (tensor parallel 2) with remaining weights CPU-offloaded into host RAM (~80 GB host memory pool). Default precision BF16. No quantized or substitute checkpoint is ever permitted.
- **Aikido Prompt Injection Defense (§5 Precedence 7, ORIGINAL_REQUEST)**: All untrusted user content, uploaded metadata, and scraped HTML/markdown are isolated within `<untrusted_content>` structural delimiters, escaped, and scrubbed.
- **Execution Envelopes (§2 Invariant 5, §14)**: Workers receive cryptographically signed execution envelopes with HMAC-SHA256 signatures and single-use nonces. Workers return deterministic `HarnessResult` outputs.
- **Database & Ledger (§21, §27)**: 23 PostgreSQL tables with Alembic migrations. Immutable, append-only credit ledger enforcing two-phase commitment (`hold` -> `settlement` / `release` / `refund`). Zero balance change without a ledger transaction.
- **Additive Architecture**: All 69 pre-built files (Scaffold + Run 1 deliverables) remain strictly byte-identical. New endpoints are mounted via additive API server extensions (`apps/api/src/server.py`), additive migrations (`0002_keystone_full_schema.sql`), and additive packages.

### 2. Core Data Flow & Execution Loop
1. User submits intent via Premium Canvas Workspace or REST API.
2. Prompt Engine compiles intent with relevant playbook (13 domain playbooks) into 6-part `PromptAnatomy`.
3. Cognition Engine (`huihui-ai/Huihui-Qwen3.8-27B-abliterated` on Kaggle T4x2) reasons over compiled prompt, generating a strictly typed `ProposedAction`.
4. Authority Engine evaluates `ProposedAction` against project policies, safety invariants, and credit balance, producing an `AuthorityDecision` (`ALLOW`, `DENY`, or `REQUIRE_CONFIRMATION`).
5. On approval, a hold is placed on user credit balance, and a signed `ExecutionEnvelope` is issued.
6. Ephemeral Kaggle Creative Worker (ComfyUI / Wan / FaceFusion) executes job and returns `HarnessResult`.
7. Lineage DAG is recorded in `asset_relationships`, assets are stored with short-expiry signed URLs, credit hold settles, and UI updates via WebSocket / Server-Sent Events.

---

## Feature Inventory

Every feature surveyed from `KEYSTONE_BIBLE.md` (§1–§38) and `ORIGINAL_REQUEST.md` is inventoried below with an assigned milestone.

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F01 | Invariant Verification & Change-Control | 18 locked invariants, Bible SHA-256 verification, and change control gates | M0 | Bible §2, §37 |
| F02 | Canonical Contracts & Schema Freeze | Typed schemas for PromptIntent, CapabilityManifest, ExecutionEnvelope, HarnessResult, ProposedAction | M0 | Bible §6–§19 |
| F03 | Additive API Server Extension | Additive FastAPI server wiring baseline app and intelligence router without modifying main.py | M0 | Bible §18, Explorer Survey |
| F04 | PostgreSQL 23-Table Schema & Migrations | Complete DDL for 23 mandated tables and Alembic additive migration 0002 | M0 | Bible §21 |
| F05 | Relational Data Models & Repositories | SQLAlchemy / asyncpg data access models for Users, Projects, Sessions, Messages, Assets, Jobs | M1 | Bible §21 |
| F06 | Authentication & Tenant Isolation | Session / API key authentication with strict tenant isolation and workspace scoping | M1 | Bible §27, §28 |
| F07 | Asset Storage & Short-Expiry URLs | Asset binary persistence in Cloud Storage / local store with 15-minute short-expiry signed URLs | M1 | Bible §22 |
| F08 | Lineage DAG Tracking | Directed acyclic graph tracking in `asset_relationships` covering 8 relationship types | M1 | Bible §22 |
| F09 | Job State Machine Engine | 13-state deterministic job state machine with state transition validation | M1 | Bible §19 |
| F10 | Prompt Compiler & Playbook Engine | Prompt compiler integrating 13 domain playbooks and 6-part PromptAnatomy | M2 | Bible §6, §7, §8 |
| F11 | Aikido Prompt-Injection Defense | Structural delimiter containment (`<untrusted_content>`), tag escaping, and post-generation sanitization | M2 | Bible §5, ORIGINAL_REQUEST |
| F12 | PII Scrubbing & Tokenization | Boundary edge-level PII scrubbing and AES-256-GCM tokenization for personal references | M2 | ORIGINAL_REQUEST |
| F13 | Cognition Connector & Client | vLLM OpenAI-compatible client for huihui-ai/Huihui-Qwen3.8-27B-abliterated | M3 | Bible §11, §24 |
| F14 | ProposedAction Structured Output | Guaranteed JSON schema generation for ProposedAction with strict schema validation | M3 | Bible §12 |
| F15 | Authority Engine & Evaluation Rules | Authority decision engine validating proposed actions, parameter boundaries, and credit balance | M3 | Bible §13 |
| F16 | Kaggle Memory Harness & Hardware Probe | Dynamic VRAM/RAM measurement, 26.7GB CPU offload calculation into ~80GB host RAM, 7 retry profiles | M3 | Bible §24, Directives |
| F17 | Kaggle Worker Bridge & Ephemeral Registration | Dynamic worker handshake, heartbeat monitoring, and ephemeral tunnel discovery | M4 | Bible §24 |
| F18 | Signed Execution Envelope Engine | HMAC-SHA256 envelope signing, single-use nonce validation, and tamper prevention | M4 | Bible §14 |
| F19 | Creative Tool Fabric Adapters | Standardized adapters for ComfyUI, Image Gen, Image Edit, Wan I2V, Wan T2V, FaceFusion, Upscale | M4 | Bible §23 |
| F20 | KAGGLE_SETUP Production Workspace | 3 production notebooks (Cognition, ComfyUI, Integrated Gateway) with automated scripts and checklists | M4 | Bible §24 |
| F21 | Firecrawl 6-Target UX Benchmark | Real web scrapes of Hugging Face, Higgsfield, ZenCreator Pro, Venice AI, Adobe Firefly, Grok | M5 | ORIGINAL_REQUEST |
| F22 | UX Research Synthesis Report | Analytical report comparing benchmark architectures, layout systems, and motion patterns | M5 | ORIGINAL_REQUEST |
| F23 | Canvas-First Premium Workspace | 5-region creative workspace with standardized progress language, compare mode, and mobile review | M5 | Bible §25 |
| F24 | Operator Admin Console | Operational dashboard for system health, Kaggle worker status, and audit logs | M5 | Bible §26 |
| F25 | Credits Ledger Engine & Two-Phase Commit | Append-only credit ledger supporting hold, settlement, release, and refund operations | M5 | Bible §27 |
| F26 | Stripe Test-Mode Billing & Webhooks | Stripe checkout integration, subscription management, and idempotent webhook handling | M5 | Bible §27 |
| F27 | Proprietary Policy & Guarded Publication | Pre-push secret scanning, closed-source enforcement, and guarded export tools | M6 | Bible §29, §38 |
| F28 | Legal Documentation Suite | 10 commercial legal policies drafted from actual data flows pending legal review | M6 | Bible §30 |
| F29 | Cloud Run & Infrastructure Deployment | Containerization, Cloud Run service configs, Cloud SQL, Secret Manager, Cloud Storage setup | M6 | Bible §3, §24 |
| F30 | PII Vault Compliance Audit | Independent audit of live system for zero plain PII in model context and GDPR Art. 17 erasure | M6 | ORIGINAL_REQUEST |
| F31 | Bible §35 Acceptance Test Automation | Runnable test suite for 6 Identity tests, 7 Authority tests, and live Cloud Run E2E script | M7 | Bible §35 |
| F32 | Bible §34 Alpha Gate Verification | Full evidence demonstration against all 13 Alpha Gate criteria | M7 | Bible §34 |
| F33 | Opaque-Box E2E Test Suite (Tiers 1–4) | Dual-track comprehensive E2E tests: Tier 1 Feature, Tier 2 BVA, Tier 3 Pairwise, Tier 4 Workloads | M7 | Dual Track Protocol |
| F34 | Tier 5 Adversarial Coverage Hardening | White-box stress testing, chaos worker termination, and coverage hardening | M7 | Dual Track Protocol |
| F35 | Post-Build BF16 vs FP16 Comparative Benchmark | Rigorous Kaggle T4x2 benchmark comparing BF16 default vs FP16 on latency, memory, tokens/sec | M7 | Founder Directive |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Wave 0: Contract Freeze & Additive Foundation | OpenAPI specs, schemas, 23-table DDL migration (0002), additive server shell | none | DONE |
| M1 | Wave 1: Creative Tool Fabric & Core Shell (F05–F09) | Database models, Auth, Asset Storage & URLs, Lineage DAG, Job State Machine | M0 | DONE |
| M2 | Wave 2: Kaggle Tier 0 & Prompt Reasoning (F10–F13) | Playbook runtime, PromptCompiler, Aikido delimiter defense, PII scrubbing, Cognition client | M0, M1 | IN_PROGRESS |
| M3 | Wave 3: Workspaces & Authority (F14–F18) | ProposedAction output, Authority Decision Engine, Kaggle hardware probe, Worker bridge, Signed envelopes | M1, M2 | PLANNED |
| M4 | Wave 4: Auth, Billing & Creative Tool Fabric (F19–F23) | ComfyUI/Wan adapters, KAGGLE_SETUP notebooks, Firecrawl 6-app UX benchmark, Canvas Workspace | M1, M3 | PLANNED |
| M5 | Wave 5: Security, Policies, Legal & Credits (F24–F28) | Admin console, Credits ledger two-phase commit, Stripe billing, Proprietary policies, 10 legal drafts | M1, M4 | PLANNED |
| M6 | Wave 6: Cloud Run Deployment & Live Integration (F29–F31) | Cloud Run manifests, PII compliance audit, Bible §35 acceptance test automation | M4, M5 | PLANNED |
| M7 | Final Milestone: Validation, Hardening & Benchmarks (F32–F35) | §34 Alpha Gate, Dual-track E2E (100% pass), Tier 5 adversarial hardening, BF16 vs FP16 comparative benchmark | M6 | PLANNED |

---

## Interface Contracts

### 1. PromptCompiler ↔ Cognition Engine
- **Input**: `PromptCompilationRequest` { `intent`: `PromptIntent`, `playbook`: `string`, `parameters`: `dict`, `context`: `dict` }
- **Output**: `CompiledPrompt` { `compiled_prompt`: `string`, `system_instructions`: `string`, `anatomy`: `PromptAnatomy`, `structural_delimiters`: `list[str]` }
- **Precedence**: Delimiter tags (`<untrusted_content>`) are strictly enforced around user inputs and web scrape data.

### 2. Cognition Engine ↔ Authority Engine
- **Input**: `CompiledPrompt`
- **Output**: `CognitiveResult` { `raw_text`: `string`, `proposed_action`: `ProposedAction` }
- **ProposedAction Schema**:
  ```json
  {
    "action_type": "string",
    "capability": "string",
    "parameters": "object",
    "rationale": "string",
    "estimated_credits": "integer"
  }
  ```

### 3. Authority Engine ↔ Job State Machine
- **Input**: `ProposedAction`, `user_id`: UUID, `project_id`: UUID, `credit_balance`: integer
- **Output**: `AuthorityDecision` { `decision`: `"ALLOW" | "DENY" | "REQUIRE_CONFIRMATION"`, `reason`: `string`, `required_credits`: `integer`, `policy_violations`: `list[str]` }

### 4. Job State Machine ↔ ExecutionEnvelope Engine
- **Input**: `job_id`: UUID, `capability`: string, `parameters`: dict, `worker_id`: string
- **Output**: `ExecutionEnvelope` { `envelope_id`: UUID, `job_id`: UUID, `capability`: string, `payload`: dict, `nonce`: string, `timestamp`: integer, `hmac_signature`: string }

### 5. ExecutionEnvelope ↔ Kaggle Worker Bridge
- **Worker Handshake**: `POST /internal/workers/register` { `worker_id`: string, `capabilities`: list, `public_key`: string, `tunnel_url`: string }
- **Job Dispatch**: Cloud Run dispatches signed `ExecutionEnvelope` to worker tunnel.
- **Job Return**: Worker returns `HarnessResult` { `job_id`: UUID, `status`: `"SUCCESS" | "FAILED"`, `output_assets`: list[dict], `execution_metrics`: dict, `error`: string | null }.

### 6. Credits Ledger Engine
- **Operations**:
  - `hold(account_id, amount, job_id)` -> creates `HOLD` entry, decreases available balance.
  - `settle(hold_id)` -> creates `SETTLEMENT` entry, finalizes deduction.
  - `release(hold_id)` -> creates `RELEASE` entry, restores available balance.
  - `refund(account_id, amount, reason)` -> creates `REFUND` entry.

---

## Code Layout

To ensure absolute preservation of all pre-built files and clear write ownership across milestones:

```
c:\Users\Lesia Eden\Downloads\keystone-cowork\
├── apps/
│   ├── api/
│   │   └── src/
│   │       ├── main.py                     # [PRE-BUILT IMMUTABLE]
│   │       ├── intelligence_router.py      # [PRE-BUILT IMMUTABLE]
│   │       ├── server.py                   # [M0 OWNER: Additive API entrypoint]
│   │       └── routers/                    # [M1/M5 OWNER: Domain REST routers]
│   ├── web/                                # [M5 OWNER: Canvas-First Premium Workspace]
│   └── admin/                              # [M5 OWNER: Operator Admin Console]
├── packages/
│   ├── contracts/                          # [M0 OWNER: Frozen schemas and TypeScript/Python types]
│   ├── prompt-engine/                      # [M2 OWNER: Compiler runtime & 13 playbooks]
│   └── security/                           # [M2/M6 OWNER: PII Vault & Aikido defense]
├── services/
│   ├── authority/src/                      # [M3 OWNER: Authority Decision Engine]
│   ├── cognition/src/                      # [M3 OWNER: vLLM Client & ProposedAction validator]
│   ├── comfy/src/                          # [M4 OWNER: Creative Fabric Adapters]
│   ├── harness/src/                        # [M4 OWNER: Signed Envelope & Execution Harness]
│   └── intelligence/                       # [PRE-BUILT IMMUTABLE: Run 1 Scraper & BigQuery]
├── infrastructure/
│   ├── bigquery/                           # [PRE-BUILT IMMUTABLE]
│   ├── kaggle/                             # [PRE-BUILT IMMUTABLE]
│   ├── migrations/versions/
│   │   ├── 0001_core.sql                   # [PRE-BUILT IMMUTABLE]
│   │   └── 0002_keystone_full_schema.sql   # [M0 OWNER: Additive 23-table DDL migration]
│   └── cloudrun/                           # [M6 OWNER: Google Cloud Run deployment manifests]
├── KAGGLE_SETUP/                           # [M4 OWNER: 3 Notebooks, scripts, checklists]
├── docs/
│   ├── KEYSTONE_BIBLE.md                   # [M0 OWNER: Byte-identical copy of root spec]
│   └── legal/                              # [M6 OWNER: 10 commercial legal drafts]
├── tests/
│   ├── e2e/                                # [PRE-BUILT IMMUTABLE: Run 1 E2E tests]
│   ├── identity.test.js                    # [PRE-BUILT IMMUTABLE]
│   ├── acceptance/                         # [M7 OWNER: Bible §35 Acceptance Test Suite]
│   └── e2e_v2/                             # [E2E Testing Track OWNER: Opaque-Box Tiers 1-4]
└── PROJECT.md                              # Living project architecture and milestone index
```
