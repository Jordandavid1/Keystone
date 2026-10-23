# KEYSTONE Codebase Baseline & Architecture Survey Report

**Explorer**: Explorer 1 (Codebase Baseline & Architecture Investigator)  
**Date**: 2026-10-22  
**Working Directory**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_survey_1`  
**Target Repository**: `c:\Users\Lesia Eden\Downloads\keystone-cowork`  
**Authoritative Request**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md`  

---

## 1. Executive Summary

A comprehensive, non-destructive forensic baseline survey of the KEYSTONE repository was performed. 

KEYSTONE is structured as a monorepo leveraging npm workspaces (`apps/*`, `packages/*`, `services/*`) with a JavaScript prompt-intelligence core and a Python/FastAPI application shell. Exactly **21 baseline tracked files** exist in version control, cataloged in `docs/FILE_MANIFEST.txt` and verified via `git ls-files`.

The baseline test suite (`npm test`) executes native Node.js tests against `tests/identity.test.js`. It validates the 13 domain playbooks, the 6-part PromptAnatomy schema, and the `generate(goal, options) -> plan.v1` contract. The baseline test suite is **100% green (3/3 passing, 0 failures)**.

All new work (R1–R4: Firecrawl UX scraping, PII Vault, Aikido prompt injection defense, BigQuery AI/ML SQL layer, and Keystone integration) must be built strictly additively. Under no circumstances may any of the 21 pre-existing tracked files or established contracts be modified.

---

## 2. Repository Layout & Tracked File Catalog

The repository is organized into cleanly delineated workspaces. As confirmed by `git ls-files` and `docs/FILE_MANIFEST.txt`, the repository contains exactly 21 tracked files:

| # | File Path | Workspace / Module | Purpose | Modification Status |
|---|---|---|---|---|
| 1 | `README.md` | Root | Product identity, invariants, structure, getting started | **IMMUTABLE** |
| 2 | `package.json` | Root | Monorepo workspace configuration & npm scripts | **IMMUTABLE** |
| 3 | `openapi.yaml` | Root | OpenAPI 3.1.0 public/internal REST contract (v0.1.0-alpha) | **IMMUTABLE** |
| 4 | `docs/BUILD_NOW.md` | Docs | Production build roadmap (Waves 0 through 6) | **IMMUTABLE** |
| 5 | `docs/FILE_MANIFEST.txt` | Docs | Complete authoritative manifest of tracked files | **IMMUTABLE** |
| 6 | `docs/IDENTITY_PRESERVATION.md` | Docs | Identity preservation invariants contract | **IMMUTABLE** |
| 7 | `packages/contracts/src/contracts.json` | Contracts | Core contract definitions (`plan.v1`, `promptAnatomy`, states) | **IMMUTABLE** |
| 8 | `packages/prompt-engine/src/engine.js` | Prompt Engine | Core `generate()`, heuristic domain classifier, signal extractor | **IMMUTABLE** |
| 9 | `packages/prompt-engine/src/meta-prompt.js` | Prompt Engine | `META_PROMPT_CORE` prompt guidance definitions | **IMMUTABLE** |
| 10 | `packages/prompt-engine/src/playbooks.js` | Prompt Engine | The 13 canonical domain playbooks | **IMMUTABLE** |
| 11 | `packages/prompt-engine/src/prompt-compiler.js` | Prompt Engine | Multi-profile prompt compiler (`standard`, `chat`, `reasoning`) | **IMMUTABLE** |
| 12 | `apps/api/src/main.py` | API App | FastAPI application entrypoint (`/v1/health`, `/v1/plan`) | **IMMUTABLE BASELINE** |
| 13 | `apps/admin/README.md` | Admin App | Operator workspace documentation | **IMMUTABLE** |
| 14 | `apps/web/README.md` | Web App | Creative workspace documentation | **IMMUTABLE** |
| 15 | `services/authority/README.md` | Authority Service | Authority engine & policy registry documentation | **IMMUTABLE** |
| 16 | `services/cognition/README.md` | Cognition Service | vLLM/Qwen runtime adapter documentation | **IMMUTABLE** |
| 17 | `services/comfy/README.md` | Comfy Service | Creative tool adapter documentation | **IMMUTABLE** |
| 18 | `services/harness/README.md` | Harness Service | Quality/validation harness documentation | **IMMUTABLE** |
| 19 | `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb` | Infrastructure | T4 x2 BF16 Kaggle bootstrap notebook | **IMMUTABLE** |
| 20 | `infrastructure/migrations/versions/0001_core.sql` | Database | Core PostgreSQL schema with 12 baseline tables | **IMMUTABLE** |
| 21 | `tests/identity.test.js` | Tests | Native Node.js identity preservation test suite | **IMMUTABLE** |

### Existing Directory Tree & Scaffolded Slots
- `packages/`:
  - `prompt-engine/`: Active core JS engine (`engine.js`, `meta-prompt.js`, `playbooks.js`, `prompt-compiler.js`).
  - `contracts/`: Core contract JSON (`contracts.json`).
  - `sdk/`: Empty scaffolded directory.
  - `ui/`: Empty scaffolded directory.
- `services/`:
  - `authority/`: Documentation only (`README.md`).
  - `cognition/`: Documentation only (`README.md`).
  - `comfy/`: Documentation only (`README.md`).
  - `harness/`: Documentation only (`README.md`).
  - `workers/`: Empty scaffolded directory.
  - *(Target for R1/R2)*: `services/intelligence/` (new additive directory).
- `apps/`:
  - `api/`: FastAPI backend (`src/main.py`).
  - `admin/`: Documentation only (`README.md`).
  - `web/`: Documentation only (`README.md`).
- `infrastructure/`:
  - `docker/`: Empty scaffolded directory.
  - `kaggle/`: Kaggle notebook (`keystone_kaggle_bootstrap.ipynb`).
  - `migrations/versions/`: Initial SQL migration (`0001_core.sql`).
  - *(Target for R3)*: `infrastructure/bigquery/` (new additive directory).
- `tests/`:
  - `identity.test.js`: Identity preservation regression test.
- Untracked / Auxiliary:
  - `.agents/`: Agent metadata and survey outputs.
  - `Keystone XL/`: Untracked legacy git metadata.
  - `archive/`: Quarantined legacy assets.

---

## 3. Package Configuration, Frameworks & Entrypoints

### NPM Root Configuration (`package.json`)
```json
{
  "name": "keystone",
  "version": "2.0.0-alpha.0",
  "private": true,
  "description": "KEYSTONE prompt-intelligence and authoritative creative orchestration platform.",
  "author": "Jordan Maxwell",
  "license": "MIT",
  "workspaces": ["apps/*", "packages/*", "services/*"],
  "scripts": {
    "test": "node --test tests/*.test.js",
    "test:identity": "node --test tests/identity.test.js",
    "dev:api": "python -m uvicorn apps.api.src.main:app --reload --port 8000"
  }
}
```

- **Workspace Globs**: `apps/*`, `packages/*`, `services/*`. Any newly added package under these globs will automatically be recognized as a workspace member.
- **Node Test Script**: `npm test` runs `node --test tests/*.test.js`.
  - **Important finding**: Because the glob is `tests/*.test.js`, any `.test.js` file placed in the top level of `tests/` will automatically be executed by `npm test`.

### API Entrypoint (`apps/api/src/main.py`)
- Framework: **FastAPI 0.146.0** with **Uvicorn 0.54.0** and **Pydantic 2.14.1**.
- Current endpoints:
  - `GET /v1/health`: Returns `{"status": "ok", "product": "KEYSTONE"}`.
  - `POST /v1/plan`: Accepts `PlanRequest(goal, answers, options)` and returns HTTP 501 `{"status": "contract_scaffolded", "detail": "Wire the preserved JS prompt-engine through the service bridge."}`.
- New capability routers for intelligence, scraping, and PII Vault can be integrated additively without disrupting existing endpoints.

### OpenAPI Contract (`openapi.yaml`)
- Version: OpenAPI 3.1.0 (`KEYSTONE API`, v0.1.0-alpha).
- Server prefix: `/v1`.
- Defined resource groups: `Auth`, `Account`, `Projects`, `Sessions`, `Assets`, `Jobs`, `Feedback`, `Capabilities`, `System`.

---

## 4. Runtime Environment & Tooling Verification

An audit of the host environment reveals:

| Component | Detected Version | Executable Path / Details |
|---|---|---|
| **Node.js** | `v26.12.0` | Node.js native test runner (`node:test`) supported |
| **npm** | `12.2.0` | Native workspaces supported |
| **Python** | `3.14.8` | `C:\Python314\python.exe` |
| **pip** | `26.2.1` | Python package installer |
| **pytest** | `9.1.1` | Installed with `pytest-asyncio 1.4.0` |
| **FastAPI** | `0.146.0` | With `uvicorn 0.54.0`, `starlette 1.9.0` |
| **Pydantic** | `2.14.1` | Core v2 schema validation |
| **Cryptography** | `50.0.2` | High-performance OpenSSL bindings (AES-256-GCM ready) |
| **HTTP Clients** | `httpx 0.28.1`, `httpcore 1.0.9` | Async/sync HTTP client libraries |
| **Playwright** | `1.63.0` | Headless automation / web driver |
| **SQLAlchemy** | `2.1.5` | Relational SQL ORM & query builder |

---

## 5. Baseline Test Suite Verification

### Verification Command
```bash
npm test
```

### Execution Log (Exact Output)
```
npm notice run keystone@2.0.0-alpha.0 test
npm notice run node --test tests/*.test.js
✔ KEYSTONE preserves plan.v1 and six-part PromptAnatomy (8.8829ms)
✔ KEYSTONE preserves all 13 domain playbooks (0.2837ms)
✔ compiler remains model-agnostic with chat and reasoning profiles (0.7828ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 245.7724
```
**Exit Code**: 0  
**Status**: 100% Green.

### Detailed Test Assertions in `tests/identity.test.js`
1. **Test 1**: `KEYSTONE preserves plan.v1 and six-part PromptAnatomy`
   - Generates plan using `generate('build a web app for creators')`.
   - Asserts `contract === 'plan.v1'`.
   - Asserts `domain.id === 'software'`.
   - Asserts `path.length === 6`.
   - For every step in `path`, asserts presence of all six anatomy keys: `role`, `task`, `context`, `constraints`, `outputFormat`, `reasoning`.
   - Asserts generated markdown includes `## ROLE`.
2. **Test 2**: `KEYSTONE preserves all 13 domain playbooks`
   - Asserts `playbooks.length === 13`.
3. **Test 3**: `compiler remains model-agnostic with chat and reasoning profiles`
   - Compiles prompt with standard, chat (`profile: 'chat'`), and reasoning (`profile: 'reasoning'`) profiles.
   - Asserts markdown headings, chat message array formatting (`role: 'system'`), and reasoning objective headers.

---

## 6. Core Preserved Contracts & Domain Playbooks

### Canonical Contracts (`packages/contracts/src/contracts.json`)
```json
{
  "plan": "plan.v1",
  "promptAnatomy": ["role", "task", "context", "constraints", "outputFormat", "reasoning"],
  "authorityDecisions": ["approve", "deny", "replan"],
  "jobStates": [
    "created", "validating", "planning", "authorizing",
    "queued", "running", "validating_output",
    "retry_pending", "replan_required", "completed",
    "failed", "cancelled", "rejected"
  ]
}
```

### The 13 Domain Playbooks (`packages/prompt-engine/src/playbooks.js`)
1. `software`: "Build software" (keywords: `app`, `software`, `website`, `code`, `api`, `saas`)
2. `writing`: "Write something" (keywords: `write`, `book`, `novel`, `essay`, `story`)
3. `marketing`: "Market and grow" (keywords: `market`, `growth`, `ads`, `seo`, `campaign`)
4. `business`: "Start or grow a business" (keywords: `business`, `startup`, `revenue`, `sales`, `offer`)
5. `learning`: "Learn a skill" (keywords: `learn`, `study`, `course`, `skill`, `exam`)
6. `career`: "Career move" (keywords: `job`, `career`, `resume`, `interview`, `promotion`)
7. `content`: "Create content or a channel" (keywords: `podcast`, `youtube`, `newsletter`, `channel`, `content`)
8. `research`: "Research and analysis" (keywords: `research`, `analysis`, `benchmark`, `study`, `evaluate`)
9. `design`: "Design and visual work" (keywords: `design`, `ui`, `ux`, `branding`, `visual`, `wireframe`)
10. `fitness`: "Health and fitness" (keywords: `workout`, `fitness`, `exercise`, `nutrition`, `gym`)
11. `events`: "Plan an event or trip" (keywords: `event`, `trip`, `travel`, `wedding`, `itinerary`)
12. `finance`: "Personal finance" (keywords: `finance`, `invest`, `budget`, `saving`, `debt`)
13. `general`: "Anything else" (fallback playbook)

Each playbook defines critical slots (with default assumptions and clarifying questions) and a 6-step path (`Define the objective`, `Gather requirements`, `Design the approach`, `Build the core`, `Integrate and test`, `Polish and deliver`).

### Baseline Database Schema (`infrastructure/migrations/versions/0001_core.sql`)
Contains 12 relational tables:
- `users`, `projects`, `sessions`, `messages`, `assets`
- `requests`, `cognitive_runs`, `authority_decisions`, `jobs`
- `compiled_prompts`, `harness_runs`, `audit_events`

---

## 7. Additive Architecture Placement Plan for R1–R4

To ensure **zero regression** and comply with the critical invariant:
> *"DO NOT MODIFY OR OVERWRITE ANY PRE-BUILT CODE. Build strictly additively. All existing files, playbooks, and contracts must remain intact. Existing tests (`npm test`) must remain 100% green at all times."*

The recommended additive placement strategy is:

```
keystone-cowork/
├── services/
│   └── intelligence/                     <-- [NEW ADDITIVE SERVICE for R1 & R2]
│       ├── __init__.py
│       ├── extractor.py                  <-- Firecrawl scraping, component trees & deduplication (R1)
│       ├── vault.py                      <-- AES-256-GCM tokenization & GDPR Art 17 erasure (R2)
│       ├── aikido.py                     <-- Delimiter quarantine & sanitization defense (R2)
│       ├── manifest.json                 <-- Capability manifest exposed to Keystone (R4)
│       └── models.py                     <-- Pydantic data schemas
├── infrastructure/
│   └── bigquery/                         <-- [NEW ADDITIVE LAYER for R3]
│       ├── schemas/                      <-- DDL schemas (architectures, embeddings, telemetry)
│       ├── procedures/                   <-- Stored procedures using AI.GENERATE, AI.SIMILARITY
│       └── queries/                      <-- SQL queries with mandatory resource attribution labels
├── apps/
│   └── api/
│       └── src/
│           ├── routers/                  <-- [NEW ADDITIVE ROUTERS for R4]
│           │   ├── __init__.py
│           │   └── intelligence.py       <-- Mounted routes for intelligence pipeline
│           └── (main.py preserved intact)
└── tests/
    ├── identity.test.js                  <-- (Preserved untouched; tests 1-3 pass)
    ├── intelligence.test.js              <-- [NEW ADDITIVE JS TEST for npm test if desired]
    └── python/                           <-- [NEW ADDITIVE PYTHON TEST SUITE for pytest]
        ├── test_extractor.py
        ├── test_vault.py
        ├── test_aikido.py
        └── test_bigquery.py
```

### Architectural Details by Requirement:
1. **R1: Firecrawl Benchmark App & UX Extraction Service**
   - **Location**: `services/intelligence/extractor.py` (or `packages/signal-scraper/`).
   - **Capabilities**: Component tree extraction, design tokens, API patterns from target benchmarks (such as Hugging Face Spaces/Hub).
   - **Controls**: Edge-level PII scrubbing (`redactPII: true`), SHA-256 content/signal deduplication.
2. **R2: Enterprise PII Vault & Aikido Prompt Injection Defense**
   - **Location**: `services/intelligence/vault.py` & `services/intelligence/aikido.py`.
   - **Vault**: AES-256-GCM encryption with cryptographic key rotation, tokenized replacement (`[PII_UUID_...]`), and GDPR Article 17 cascading erasure (idempotent purge of ciphertext/mappings).
   - **Aikido Defense**: Untrusted content encapsulation using structural delimiters (`<untrusted_content>...</untrusted_content>`), tag escape sequences, and post-generation sanitization ensuring untrusted scraped markup never escapes quarantine.
3. **R3: BigQuery AI/ML SQL Intelligence & Embeddings Layer**
   - **Location**: `infrastructure/bigquery/`.
   - **SQL Primitives**: `AI.GENERATE`, `AI.GENERATE_EMBEDDING`, `AI.SIMILARITY`, `AI.CLASSIFY`.
   - **Compliance**: Resource attribution labels (`resource_type: intelligence_pipeline`, etc.), standard GCP syntax constraints.
4. **R4: Additive Keystone Integration & Clean Dependency Management**
   - **Location**: Expose capability manifest (`services/intelligence/manifest.json`), add router `apps/api/src/routers/intelligence.py` mounted cleanly into FastAPI.
   - **Preservation**: Core `packages/contracts/src/contracts.json`, `packages/prompt-engine/src/*`, and `tests/identity.test.js` remain pristine.
   - **Testing**: `npm test` remains 100% green. Pytest runs comprehensive unit/integration tests for the Python intelligence layer.

---

## 8. Guardrails & Invariants for Subsequent Execution Phases

1. **Strict File Immutability**: None of the 21 tracked files in `docs/FILE_MANIFEST.txt` may be altered or overwritten.
2. **Green Test Gate**: `npm test` must be executed and confirmed passing with exit code 0 before and after every phase.
3. **No Unmanaged Dependencies**: All Python dependencies must be verified against current environment (`Python 3.14.8`) without global non-isolated package modifications.
4. **Sysadmin Guardrails**: Non-interactive command execution, atomic writes, idempotency in scripts and schemas.
5. **Teamwork Artifact Discipline**: Agent metadata and temporary files must reside strictly in `.agents/teamwork/<agent_id>/` and never pollute source packages.

---
*Report compiled by Explorer 1. Ready for synthesis into `PROJECT.md` by Orchestrator.*
