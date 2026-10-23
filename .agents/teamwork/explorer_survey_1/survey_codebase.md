# Comprehensive Codebase Survey & Additive Architecture Map

**Agent**: `explorer_survey_1` (Teamwork Explorer)  
**Date**: 2026-10-22  
**Target Repository**: `c:\Users\Lesia Eden\Downloads\keystone-cowork`  
**Parent Orchestrator**: `6f59f58e-8034-400a-bd25-c869a10728f4`  
**Canonical Spec**: `KEYSTONE_BIBLE.md` (SHA-256: `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`)  
**Core Invariant**: 100% preservation of all pre-built files; strictly additive architecture.

---

## 1. Executive Summary & Verification Gates Status

An empirical investigation was conducted across the entire repository filesystem, git metadata, Node.js runtime, Python virtual environment, and all test suites.

### Key Findings:
1. **Repository Dual-State Baseline**:
   - The git HEAD commit (`4aaf995 feat: preserve KEYSTONE identity in integrated cowork monorepo`) tracks exactly **21 baseline files** as recorded in `docs/FILE_MANIFEST.txt`.
   - Run 1 and repository staging introduced **48 additional pre-built deliverables** (the `@keystone/intelligence` microservice, BigQuery AI/ML infrastructure, FastAPI `intelligence_router.py`, the 6-target mock fixtures, the 194-test E2E test suite, and environment verification tooling).
   - **Total Pre-Built Files**: Exactly **69 non-cache files** exist across the root. Every file has been inventoried with its byte size and cryptographic SHA-256 checksum.
2. **Canonical Spec Verification**:
   - `KEYSTONE_BIBLE.md` has been verified with SHA-256 checksum:
     `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`.
     This matches the founder-mandated checksum verbatim.
3. **Test Suite Verification**:
   - `npm test`: **3/3 passing (100% green)** in 536ms. Enforces Tier 0 baseline invariant (`tests/identity.test.js`).
   - `node tests/e2e/runner.js`: **132/132 passing (100% green)** in 2270ms across Tiers 1–4.
   - `node --test tests/e2e/*.test.js`: **194/194 passing (100% green)** in 17.5s across Tiers 1–5 (all 62 Tier 5 adversarial tests included).
   - `node tests/adversarial_security_suite.js`: **25/25 passing (100% green)**.
   - `python scripts/verify_environment.py`: **PROBE VERDICT: PASS** (checks all 21 baseline files, sysadmin guardrails, Python 3.14.8 environment, and locked dependencies).
4. **Zero-Destruction Feasibility**:
   - Waves 0 through 6 can be constructed completely additively without modifying or overwriting any of the 69 pre-built files.

---

## 2. Complete Inventory of All Pre-Built Files

The table below catalogs all 69 pre-built files currently present in the repository (excluding `.git/`, `.venv/`, `.pytest_cache/`, `__pycache__/`, and `.agents/teamwork/`).

### A. Original 21 Baseline Scaffold Files (`docs/FILE_MANIFEST.txt`)

| Relative Path | Size (Bytes) | SHA-256 Checksum | Category / Invariant |
| :--- | :---: | :--- | :--- |
| `README.md` | 1,881 | `95FBF20DE30F6894FA94A6AF7C0981CA1E0811409060576D33C339DB7AB8E5BA` | Root Project Overview |
| `apps/admin/README.md` | 164 | `2F6F6F2AD6DFFA4C6AB5C097D85166A5432105F7E44CB7026EBAFDF57F20FC27` | Admin Workspace Spec Stub |
| `apps/api/src/main.py` | 578 | `1EAA72DCC8B1CD383615A2F05FE9C41AA099C6584893419606C96736F170B5DC` | Baseline FastAPI App (`/v1/health`, `/v1/plan` stub) |
| `apps/web/README.md` | 208 | `513E241ABE41D76F5EE89C9C30A2E585B7AE6A70FEA168697AE4AD3AAD48CC8B` | Web Workspace Spec Stub |
| `docs/BUILD_NOW.md` | 1,275 | `D59A31EA09E92AB11B6E869FB09D8EF1A665CB13F0B2C084850F385CBE33C416` | Fastest Production-Shaped Build Plan |
| `docs/FILE_MANIFEST.txt` | 649 | `170E9D94789F66ABA281D425BB3E92C1A063738D1230A441A35B228DD00B1A38` | Baseline Invariant Tracked Manifest |
| `docs/IDENTITY_PRESERVATION.md` | 1,339 | `8AFCD7CAA5BB12B0063A6DE2E6DB2A97FC1ECF0FD3DB8F5DB3A0B8B49DB19926` | Identity Preservation Contract |
| `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb` | 2,149 | `11B010D7C5E378DC956E346C46E12EFF142320E088015E7D4B1FBBA86CAB13CC` | Kaggle T4x2 Bootstrap Notebook Stub |
| `infrastructure/migrations/versions/0001_core.sql` | 4,788 | `F7F0E977CEFD7CACF9D8B20B40BD73F1AC316732FF364E10FFB2287725401186` | PostgreSQL Core Schema (12 baseline tables) |
| `openapi.yaml` | 11,822 | `6D923E48C2117C119AB4B1BE80085EC059E704D2358CE67B7B5DF822B0B03673` | Canonical OpenAPI 3.1.0 Contract |
| `package.json` | 480 | `9AA59FCE6CCAB16012A8521C9B8F7424075182119ECDB047A0903B6FBF11CC96` | Root Monorepo Workspace Config |
| `packages/contracts/src/contracts.json` | 366 | `8AB200CB6524FE7DF2FCCBD5699551CB402815C81BE2C9AC63C136B3B2E251D2` | Common Enum & Contract Definitions |
| `packages/prompt-engine/src/engine.js` | 3,736 | `5DEEFF1380BE1BD546B06FFC82FBA617090F2C0479C0A5D4AF8A1DF16985321A` | Core `generate(goal, options)` Engine |
| `packages/prompt-engine/src/meta-prompt.js` | 562 | `278E4B8E64106B1F89EFE90DB005B7F2B6DB9DCCD40607EB4FB83F667704C3C7` | Meta-prompt Compilation Logic |
| `packages/prompt-engine/src/playbooks.js` | 4,561 | `73CEE77406B403FE20BF4A34EE686A66622350E57EC77494FD21F24383ED0695` | 13 Domain Playbooks Invariant |
| `packages/prompt-engine/src/prompt-compiler.js` | 2,322 | `DB34C93ADF74C465B13CE0AB8A2D1554193D64834A116E2D05BD14B08E53127F` | 6-Part Anatomy Prompt Compiler |
| `services/authority/README.md` | 214 | `860B162B777E4499D5D0143263530DF75AE3F1A59BF364B90B19E02E2DD50019` | Authority Service Spec Stub |
| `services/cognition/README.md` | 329 | `4363EF1A028E5CFE538041C3B08882BA93617B51A7ABC0CB0794CA731A444CC9` | Cognition Service Spec Stub |
| `services/comfy/README.md` | 161 | `0C0E796B5017A52EB5A6AE651C07BC7530719A176236682D725336B15808461B` | Comfy Creative Tool Spec Stub |
| `services/harness/README.md` | 209 | `665BBF9109585DAB9AA296504C15AB2085AD9671FF0219EB5912F9302D69F4D9` | Harness Service Spec Stub |
| `tests/identity.test.js` | 1,314 | `670A0D4549353C215221EA9A7FF326EB7B6B9874E90A703CBDB550782E9738F7` | Baseline Invariant Tests (`npm test`) |

### B. Run 1 Pre-Built Deliverables (48 Files)

#### 1. Specification & Top-Level Documentation
| Relative Path | Size (Bytes) | SHA-256 Checksum | Category |
| :--- | :---: | :--- | :--- |
| `KEYSTONE_BIBLE.md` | 39,681 | `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788` | Canonical Architecture Spec |
| `TEST_INFRA.md` | 16,140 | `EEF150BA70D22B6165722FB20E70ACE9BE3FDA8228BE9E9BC390191A5A5D1CE9` | Verification Framework & Spec |
| `TEST_READY.md` | 10,218 | `D99E9A030CE25E66B52F4D4BA5BB838889F2A5F8B6ACDA4E044447C6D966C0C0` | Test Readiness Report |
| `requirements.txt` | 249 | `09C612F04563EC4F20451E6CB1ABCC4EE41DCA1BF439A2DBD98AD0F9CD7FD30A` | Locked Python Dependencies |
| `Keystone XL/.gitattributes` | 66 | `1A1DBE176BC233B499D35A57DB7513F2941C99AB9759F177830C9149BE99005B` | Git Attributes |
| `keystone-cowork-updated.zip` | 132,075 | `56DACF1BCDD82D5609BD9C984DB24A10336EA6BAE0348CA2F00802482405D4E9` | Baseline Staged Archive |

#### 2. Intelligence Microservice (`services/intelligence/`)
| Relative Path | Size (Bytes) | SHA-256 Checksum | Category |
| :--- | :---: | :--- | :--- |
| `services/intelligence/package.json` | 519 | `8817E3CB1C29C46A881313B24EB00ED57C1B42AA5DDC9D581395FADBC8374541` | Package Config |
| `services/intelligence/README.md` | 10,834 | `EA3BC52D34EAF92AC2428BFEE146570A93308A420E50AA5AE0F9D63418C331E0` | Service Documentation |
| `services/intelligence/src/index.js` | 5,404 | `A0B5A69C51AA49B2D5095B82DF526E786324F95828E4B538C057EABD79DE4B05` | Service Barrel Exports |
| `services/intelligence/src/bridge/capability_manifest.js` | 1,558 | `2FE9C1F6EC666E3D209A354106B7A4A93CF2E558CB2EE58B6C52C84362B332D3` | Capability Manifest Bridge |
| `services/intelligence/src/bridge/prompt_bridge.js` | 2,653 | `74EDB5E99BD4D7F98AF4914D2BD40B9A276C3FC8F21DA5F3E3AD76E4CE07ED30` | PromptAnatomy Bridge |
| `services/intelligence/src/bridge/service_bridge.js` | 10,037 | `D68270F85606FBC07C548B66CC94DC139CACFA476B789878568D11D19A53411C` | Harvest & Bridge Controller |
| `services/intelligence/src/scraper/ast_deconstructor.js` | 10,465 | `B37585CEE137845DBE1B86B88214B66A4AE1041273771F7947F7C9829A1E6A39` | AST Deconstruction Engine |
| `services/intelligence/src/scraper/dedup_cache.js` | 3,947 | `6862C7C7E959C2948EA4EB39771552B08DFC956F70389F2DF07A9B2641CACDB4` | SHA-256 Deduplication Cache |
| `services/intelligence/src/scraper/edge_pii.js` | 2,020 | `3DD6FE55AFB41A6EE1A17D9A3361F60FC7C3C7CD5FC7F836826C95E9634BF99E` | Edge PII Scrubber |
| `services/intelligence/src/scraper/firecrawl_client.js` | 4,251 | `F18070C54E6B8A530853B55C49E15DFFC864ABFD43D32403BCA8F3A5A87D610E` | Firecrawl Streamable Client |
| `services/intelligence/src/security/aikido_defense.js` | 4,503 | `0C782451B5DE576CD9BAB5A1858F8C14F06F41AE033B6B04903DD271F71B1322` | Aikido Prompt-Injection Defense |
| `services/intelligence/src/vault/vault_service.js` | 6,192 | `C7BC6E4FE1A81723BFF4699E0C27B3ABB4E8450E0FCC694934034A71E24C55FB` | AES-256-GCM PII Vault |

#### 3. BigQuery AI/ML Infrastructure (`infrastructure/bigquery/`)
| Relative Path | Size (Bytes) | SHA-256 Checksum | Category |
| :--- | :---: | :--- | :--- |
| `infrastructure/bigquery/README.md` | 11,406 | `8555C908EEDBB2E1C73C9616F3D53483D28F8023CF76C0C89A89BE4BC583E6C4` | BigQuery Architecture Docs |
| `infrastructure/bigquery/mocks/ast_validator.js` | 14,854 | `5472D6BBFCD690F3F1E797612A3D13FB66E03CB6CFE37BD7D4156240DAC65705` | AST In-Memory Simulator |
| `infrastructure/bigquery/queries/ai_procedures.sql` | 10,504 | `D1411CED44801CDA6CA9697FC1CCB6FE3C28C3A76B5D473FF824F752B63E7A52` | Stored Procedures & TVFs |
| `infrastructure/bigquery/schemas/001_intelligence_schema.sql` | 7,550 | `F24AF23BA318E5664D32C58A3857880CB824C1EA6C9B4DDBEE361B3DFEB54887` | Ingestion Tables & Models |
| `infrastructure/bigquery/scripts/deploy_bigquery.ps1` | 6,287 | `6107A8AB155FB6A2578CF2B89E79B51E7E7D1139CDF84836850EA9DCDD8EB78D` | PowerShell Deployment Script |
| `infrastructure/bigquery/scripts/deploy_bigquery.sh` | 5,995 | `642DB963955B1104A41F1B7E155816F6D3C3133D71CD65231B7762D901FDE362` | Bash Deployment Script |

#### 4. API Endpoints & Verification Scripts
| Relative Path | Size (Bytes) | SHA-256 Checksum | Category |
| :--- | :---: | :--- | :--- |
| `apps/api/src/intelligence_router.py` | 21,362 | `350316B4CE9C9A1BE8321003D4842D255A90F0B5A89AEE5EC378868E0776512D` | FastAPI Intelligence Router |
| `scripts/setup_environment.ps1` | 7,664 | `4BCBFB2A6887055E21B396B739BA28790C10170AC23D0D91205C1ADEF43CA765` | PowerShell Environment Setup |
| `scripts/verify_environment.py` | 13,101 | `2161DC800F1B9C0C87DF6096183BAD62CACE59AB15A17DC6DEAED5554EAEF65A` | Composite Environment Probe |

#### 5. Test Suites, Fixtures & Test Harness (`tests/` & `tests/e2e/`)
| Relative Path | Size (Bytes) | SHA-256 Checksum | Category |
| :--- | :---: | :--- | :--- |
| `tests/adversarial_security_suite.js` | 22,016 | `A68D5058C216673ACDD3F0FC71F4523A27901139E4CD1ACC17E5C8417451EC80` | Adversarial Security Suite (25 tests) |
| `tests/e2e/runner.js` | 3,361 | `920D63F106786C5052EFC25D786731C60DF3BBBC018AAE533780344EC0294F6F` | Tiered Test Runner Script |
| `tests/e2e/challenger_stress.js` | 17,757 | `3074FE763273713FFB6D86D02C19EAEF64DD1D489EB376BA06E933DBD9B172B7` | Stress / Boundary Characterization |
| `tests/e2e/tier1_features.test.js` | 23,775 | `2A72BBDD2B1D3C63A710ADCF1DAB8C32D38A683D4B578324B09FCE8C4A05C68B` | Tier 1: F1–F12 Isolation (61 tests) |
| `tests/e2e/tier2_boundaries.test.js` | 20,888 | `B274DB0CFC0EA01EB2D2812FEB6D1489C977ED24E8169F5F677387F9828D36DB` | Tier 2: F1–F12 BVA (60 tests) |
| `tests/e2e/tier3_combinations.test.js` | 6,525 | `39C4BE1AD8AC63B3D7E7E4D7941701377BCAA996B38C573007C4C4FA87CC20E7` | Tier 3: Pairwise Interactions (5 tests) |
| `tests/e2e/tier4_realworld.test.js` | 10,740 | `F4F0C6C5BC3A890E9DBF85C510A0E989457F45390BF6D2C19A38FF7629D5BC96` | Tier 4: 6-Target Scenarios (6 tests) |
| `tests/e2e/tier5_scraping_adversarial.test.js` | 24,467 | `FBCB6C4492C6F37468EE9DECD4D6731E57EE97FDA732655A5DAA7AC07225BC11` | Tier 5: Scraper & BQ Rules (32 tests) |
| `tests/e2e/tier5_security_adversarial.test.js` | 31,947 | `D35FA2BC79D8439F58BC774E1991F9C551DA907945327E1E87B5A7B89133E98B` | Tier 5: AEAD & Injection Rules (30 tests) |
| `tests/e2e/fixtures/adobe_sample.html` | 1,702 | `1AD3420DB825CCF655FF7987166ECBD848CA855C67866B883A69B4F17334A4A7` | Adobe Firefly Mock Fixture |
| `tests/e2e/fixtures/bigquery_ast_mocks.json` | 3,445 | `DC237E29D1E489167B718F5CD7662410B30B1C1722ED842B4AF443C85444FEE9` | BigQuery AST Test Vectors |
| `tests/e2e/fixtures/grok_sample.html` | 1,585 | `025ABB937D259C8B00F111D150035FCD4E29D75AC6C6B54164B25887934FB727` | Grok Reasoning UX Fixture |
| `tests/e2e/fixtures/hf_space_deconstruct.json` | 6,694 | `1E6BCD9FEC6ECDD7A4F9FFDC9688262ABCFDCD6A4BF44871C8D5D6E7955CCDE9` | Hugging Face Reference AST |
| `tests/e2e/fixtures/hf_space_sample.html` | 2,706 | `7CDEDC140940F3C3760304C19AAB1B3855F5638183195FFF3AD2A69FCA93FE4C` | Hugging Face Space Fixture |
| `tests/e2e/fixtures/higgsfield_sample.html` | 1,408 | `5AB21FC98A4B4BA3BD3AEF5AC4EA3274B44F8F95494572900CCDE9387EB530F2` | Higgsfield Cinema AI Fixture |
| `tests/e2e/fixtures/injection_payloads.json` | 1,729 | `7D440AA850A8CC666AE9504935F5410FFA7D88478737307A1688D40851254C68` | Adversarial Injection Vectors |
| `tests/e2e/fixtures/targets_catalog.json` | 2,304 | `8C492E2B75F2C099ACF2903F01DAAA23D52FE5E19D2E8FF671B27E551EAF88BB` | 6-Target Benchmark Spec Catalog |
| `tests/e2e/fixtures/venice_sample.html` | 1,403 | `6115E5BB9D4E2453BFB4CF229B4E95003000458C59EEB6DADE24DEC2302AA672` | Venice AI Zero-Log Fixture |
| `tests/e2e/fixtures/zencreator_sample.html` | 1,375 | `A700C9897A551AAB41580A9680E3DC6752AE061E344E4C32812D3E1607635FC8` | ZenCreator Studio Fixture |
| `tests/e2e/harness/contract_oracle.js` | 28,417 | `2303E176FDF99DA5EBA05A05508B01296633C45C20ED363307FCA74178FB9C97` | Reference Contract Oracle |
| `tests/e2e/harness/loader.js` | 1,319 | `B5D827D236A07169CCCBA06D5316949A1F39E11F421D1D10EDB5D8A6978E627A` | Oracle Loader |
| `tests/e2e/harness/sql_validator.js` | 3,725 | `06BCC7E660A4BAE743877BAD0DB34C051A2D738066D4D512753B35E8B3594880` | BigQuery SQL Syntax Validator |

---

## 3. Existing Test Suites & Commands Verification

### A. Test Commands & Verification Results

| Command | Scope | Test Count | Pass / Fail | Execution Time | Key Invariants Verified |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `npm test` | `tests/identity.test.js` | **3** | **3 Pass / 0 Fail** | 536ms | `plan.v1`, 6-part `PromptAnatomy`, 13 playbooks, compiler profiles |
| `node tests/e2e/runner.js` | Tiers 1–4 E2E Suites | **132** | **132 Pass / 0 Fail** | 2270ms | F1–F12 isolation (61), BVA boundaries (60), pairwise (5), 6 benchmark targets (6) |
| `node --test tests/e2e/*.test.js` | Tiers 1–5 Comprehensive | **194** | **194 Pass / 0 Fail** | ~17.5s | All 132 tests + 62 Tier 5 adversarial tests (DEDUP, SCRAPER, PII, BQ, SEC, VAULT, GDPR, BRIDGE, API) |
| `node tests/adversarial_security_suite.js` | Milestone 2 Security Suite | **25** | **25 Pass / 0 Fail** | ~1.2s | Prompt injection breakout, PII leakage, GDPR Art. 17 idempotency, AES-256-GCM AEAD tamper rejection |
| `python scripts/verify_environment.py` | Composite Environment Probe | N/A | **PROBE PASS** | ~3.5s | Python 3.14.8, active `.venv`, 5 locked pip packages, sysadmin safety guardrails, 21-file manifest |

### B. Detailed Breakdown of Test Suites

#### 1. Baseline Invariant Suite (`tests/identity.test.js` via `npm test`)
- **Test 1**: Verifies `generate('build a web app for creators')` returns `contract: 'plan.v1'`, `domain.id: 'software'`, `path.length: 6`, and ensures each step's prompt includes all 6 parts (`role`, `task`, `context`, `constraints`, `outputFormat`, `reasoning`) and prompt text starts with `## ROLE`.
- **Test 2**: Verifies `playbooks.length === 13`.
- **Test 3**: Verifies `compilePrompt` handles `chat` (returns system role message object) and `reasoning` (returns `## REASONING OBJECTIVE`) profiles in a model-agnostic manner.

#### 2. E2E Intelligence Verification Suite (`tests/e2e/`)
- **Tier 1 (`tier1_features.test.js`, 61 tests)**:
  - F1 (Firecrawl client & watchdog): 5 tests
  - F2 (AST UX deconstruction): 6 tests (Hugging Face, Higgsfield, ZenCreator, Venice, Adobe, Grok)
  - F3 (Edge PII scrubbing): 5 tests
  - F4 (SHA-256 deduplication & TTL cache): 5 tests
  - F5 (AES-256-GCM PII boundary vault): 5 tests
  - F6 (GDPR Article 17 cascading erasure): 5 tests
  - F7 (Aikido prompt injection defense): 5 tests
  - F8 (BigQuery AI/ML schema & DDL): 5 tests
  - F9 (BigQuery TVFs & procedures): 5 tests
  - F10 (Resource attribution labeling): 5 tests
  - F11 (Keystone capability manifest & prompt bridge): 5 tests
  - F12 (Python environment & sysadmin safety): 5 tests
- **Tier 2 (`tier2_boundaries.test.js`, 60 tests)**:
  - Boundary Value Analysis (BVA), maximum lengths, empty payloads, 2,000-level DOM recursion safety, cryptographic bit-flipping detection, case-insensitive delimiters, and idempotency tests across F1–F12.
- **Tier 3 (`tier3_combinations.test.js`, 5 tests)**:
  - TC-PW-01: Scraper + PII Vault (Boundary tokenization of maintainer contacts)
  - TC-PW-02: PII Vault + Aikido Defense (Zero plaintext PII inside `<untrusted_content>`)
  - TC-PW-03: Aikido Defense + Prompt Engine (Injection vector containment)
  - TC-PW-04: Benchmark Extraction + BigQuery AI/ML Schema (Structured vector ingestion)
  - TC-PW-05: Deduplication + BigQuery Ingestion (Idempotent MERGE updates)
- **Tier 4 (`tier4_realworld.test.js`, 6 tests)**:
  - End-to-end integration across all 6 benchmark targets (Hugging Face, Higgsfield, ZenCreator, Venice, Adobe, Grok).
- **Tier 5 Adversarial Hardening (`tier5_scraping_adversarial.test.js` & `tier5_security_adversarial.test.js`, 62 tests)**:
  - White-box boundary characterization, deep object key permutations, IPv4/IPv6 boundary scrubbing, BigQuery TVF clause restrictions (`AI.GENERATE_EMBEDDING` in SELECT prohibited), AES-256-GCM IV and auth tag single-bit tamper rejection, and FastAPI endpoint verification.

---

## 4. Dependencies & Runtime Environment Analysis

### A. Node.js & Workspace Architecture
- **Runtime Version**: Node.js v26.12.0
- **Package Manager**: npm v12.2.0
- **Monorepo Workspaces**: `["apps/*", "packages/*", "services/*"]` defined in root `package.json`.
- **Zero Third-Party Node Dependencies**: The core platform, prompt engine, and intelligence services rely exclusively on Node.js standard library primitives (`node:test`, `node:assert/strict`, `node:crypto`, `node:fs`, `node:path`, `node:http`). This eliminates supply-chain vulnerabilities and guarantees reproducible execution.

### B. Python Virtual Environment (`.venv`)
- **Python Version**: Python 3.14.8 (AMD64 Windows)
- **Virtual Environment Path**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.venv`
- **Dependency Manager Priority**: `venv + pip` (detects `requirements.txt`)
- **Locked Dependencies (`requirements.txt`)**:
  - `fastapi==0.146.0` (ASGI Web API)
  - `uvicorn==0.54.0` (ASGI Production Server)
  - `pydantic==2.14.1` (Schema Validation & Serialization)
  - `pytest==9.1.1` (Python Testing Framework)
  - `cryptography==50.0.2` (AES-256-GCM AEAD Boundary Encryption)
- All 5 locked dependencies are verified present and fully operational inside `.venv`.

---

## 5. Additive Non-Destructive Extension Strategy (Waves 0–6)

The founder directive is absolute: **DO NOT MODIFY OR OVERWRITE ANY PRE-BUILT CODE.**
The 69 pre-built files must remain byte-identical. The table below maps out how every requirement from `KEYSTONE_BIBLE.md` and `docs/BUILD_NOW.md` will be fulfilled cleanly through additive files and modules.

| Subsystem / Area | Pre-Built Files (IMMUTABLE) | Additive Implementation Strategy | Additive Target Files |
| :--- | :--- | :--- | :--- |
| **Specification** | `KEYSTONE_BIBLE.md` (root, SHA-256 pinned) | Provide byte-identical copy in `docs/` per Bible §38. | `docs/KEYSTONE_BIBLE.md` |
| **API Server Entrypoint** | `apps/api/src/main.py` (baseline scaffold), `apps/api/src/intelligence_router.py` | Create a unified application server (`server.py`) that imports `app` from `apps.api.src.main`, mounts `intelligence_router`, and mounts all new domain routers. | `apps/api/src/server.py`, `apps/api/src/routers/*.py` |
| **Database Migrations** | `infrastructure/migrations/versions/0001_core.sql` (12 core tables) | Add additive migration file (`0002_keystone_full_schema.sql`) and Alembic runner implementing the 11 missing Bible §21 tables (`subscriptions`, `api_keys`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `configuration_bundles`, `asset_relationships`). | `infrastructure/migrations/versions/0002_keystone_full_schema.sql`, `infrastructure/migrations/alembic/` |
| **Contracts & Models** | `packages/contracts/src/contracts.json` | Author additive TypeScript types, Pydantic models, and OpenAPI schemas in `packages/contracts/src/`. | `packages/contracts/src/index.ts`, `packages/contracts/src/models.py`, `packages/contracts/src/envelopes.py` |
| **Prompt Engine** | `packages/prompt-engine/src/{engine,meta-prompt,playbooks,prompt-compiler}.js` | Keep existing files 100% untouched. Add cognitive compiler, creative compiler, and hashing modules in `packages/prompt-engine/src/compilers/`. | `packages/prompt-engine/src/compilers/cognitive_compiler.js`, `packages/prompt-engine/src/compilers/creative_compiler.js`, `packages/prompt-engine/src/hashing/provenance.js` |
| **Authority Service** | `services/authority/README.md` | Implement full service logic inside `services/authority/src/` (PolicyRegistry, CapabilityRegistry, HarnessRegistry, AuthorityEngine, ExecutionEnvelope signer). | `services/authority/src/index.js`, `services/authority/src/registry.js`, `services/authority/src/engine.js`, `services/authority/src/envelope.js` |
| **Cognition Service** | `services/cognition/README.md` | Implement full cognition service in `services/cognition/src/` (vLLM adapter, hardware probe, CPU offload calculator, structured proposal parser). | `services/cognition/src/index.py`, `services/cognition/src/vllm_adapter.py`, `services/cognition/src/hardware_probe.py`, `services/cognition/src/offload_planner.py` |
| **Creative Tool Service** | `services/comfy/README.md` | Implement ComfyUI adapter in `services/comfy/src/` (image workflow, Wan video workflow, identity transformation workflow, license gating). | `services/comfy/src/index.py`, `services/comfy/src/workflows/image_gen.py`, `services/comfy/src/workflows/wan_video.py`, `services/comfy/src/workflows/identity.py` |
| **Harness Service** | `services/harness/README.md` | Implement validation harnesses in `services/harness/src/` (MemoryHarness, TechnicalOutputHarness, QualityAggregator, RegressionRunner). | `services/harness/src/index.py`, `services/harness/src/memory_harness.py`, `services/harness/src/quality_aggregator.py` |
| **Job Workers** | (None currently) | Add `services/workers/` for asynchronous job execution, queue listeners, and Kaggle bridge synchronization. | `services/workers/src/job_worker.py`, `services/workers/src/kaggle_gateway.py` |
| **Kaggle Deployment** | `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb` | Leave baseline bootstrap intact. Create `KAGGLE_SETUP/` with the three production notebooks and runbook tooling per Bible §24. | `KAGGLE_SETUP/notebooks/01_keystone_cognition_bootstrap.ipynb`, `KAGGLE_SETUP/notebooks/02_keystone_comfyui_runtime.ipynb`, `KAGGLE_SETUP/notebooks/03_keystone_integrated_gateway.ipynb`, `KAGGLE_SETUP/README.md` |
| **Web Workspace** | `apps/web/README.md` | Author premium creative canvas workspace under `apps/web/src/` (FastAPI/HTML/Tailwind/Lucide or React canvas, composer, lineage, compare mode, mobile review). | `apps/web/src/*`, `apps/web/package.json` |
| **Admin Workspace** | `apps/admin/README.md` | Author admin console under `apps/admin/src/` (job monitoring, GPU/RAM telemetry, credits ledger, audit logs, policy management). | `apps/admin/src/*`, `apps/admin/package.json` |
| **Cloud Deployment** | (None currently) | Add Google Cloud Run, Cloud SQL, and Secret Manager deployment scripts and Dockerfiles under `infrastructure/cloud/` and `infrastructure/docker/`. | `infrastructure/docker/Dockerfile.api`, `infrastructure/docker/Dockerfile.web`, `infrastructure/gcp/deploy_cloudrun.ps1` |
| **Legal Documentation** | (None currently) | Add draft legal documents derived from actual data flows per Bible §30. | `docs/legal/PRIVACY_POLICY_DRAFT.md`, `docs/legal/TERMS_OF_SERVICE_DRAFT.md` |
| **Acceptance Suite** | `tests/identity.test.js`, `tests/e2e/` | Add Bible §35 automated acceptance tests under `tests/acceptance/`. | `tests/acceptance/identity_checks.js`, `tests/acceptance/authority_checks.js`, `tests/acceptance/e2e_live_test.py` |

---

## 6. Recommended Monorepo Directory Layout for New Modules

```text
keystone-cowork/
├── .agents/                               # Agent teamwork metadata (NO source code here)
├── KEYSTONE_BIBLE.md                      # [PRE-BUILT IMMUTABLE] Pinned Canonical Spec (SHA-256: 1D31D909...)
├── README.md                              # [PRE-BUILT IMMUTABLE]
├── TEST_INFRA.md                          # [PRE-BUILT IMMUTABLE]
├── TEST_READY.md                          # [PRE-BUILT IMMUTABLE]
├── openapi.yaml                           # [PRE-BUILT IMMUTABLE]
├── package.json                           # [PRE-BUILT IMMUTABLE]
├── requirements.txt                       # [PRE-BUILT IMMUTABLE]
│
├── apps/
│   ├── api/
│   │   └── src/
│   │       ├── main.py                    # [PRE-BUILT IMMUTABLE] Baseline FastAPI app
│   │       ├── intelligence_router.py     # [PRE-BUILT IMMUTABLE] Run 1 Intelligence router
│   │       ├── server.py                  # [NEW WAVE 1] Unified FastAPI app mounting all routers
│   │       ├── config.py                  # [NEW WAVE 0] Application settings & secrets loader
│   │       ├── database.py                # [NEW WAVE 1] PostgreSQL connection & session manager
│   │       └── routers/                   # [NEW WAVES 1-6] Additive domain routers
│   │           ├── auth.py                # Register, login, refresh, API keys (§17)
│   │           ├── projects.py            # Project CRUD & asset binding (§17)
│   │           ├── sessions.py            # Creative sessions & message history (§17)
│   │           ├── assets.py              # Signed URL upload & lineage tracking (§17, §22)
│   │           ├── jobs.py                # Job submission, status stream, recovery (§17, §19)
│   │           ├── plan.py                # Wired prompt planning endpoint (§17, Wave 2)
│   │           ├── creative.py            # Creative generation actions (§23)
│   │           ├── billing.py             # Stripe webhooks & credits ledger (§27)
│   │           ├── admin.py               # Admin diagnostics & audit logs (§26)
│   │           └── kaggle_bridge.py       # Ephemeral Kaggle worker registration & ping
│   │
│   ├── web/
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   ├── package.json                   # [NEW WAVE 1]
│   │   ├── src/                           # [NEW WAVE 1, 5] Premium Workspace UI
│   │   │   ├── canvas/                    # Creative Canvas, pan/zoom, compare mode
│   │   │   ├── composer/                  # KEYSTONE prompt composer & suggestions
│   │   │   ├── lineage/                   # Asset provenance & relationship graph
│   │   │   ├── progress/                  # §25 Progress language status bar
│   │   │   └── mobile/                    # Mobile review & approval experience
│   │   └── public/                        # Static assets, fonts, icons
│   │
│   └── admin/
│       ├── README.md                      # [PRE-BUILT IMMUTABLE]
│       ├── package.json                   # [NEW WAVE 6]
│       └── src/                           # [NEW WAVE 6] Admin Workspace Console
│           ├── jobs/                      # Real-time job inspection & cancellation
│           ├── workers/                   # Kaggle GPU/RAM telemetry & health
│           ├── credits/                   # Ledger auditing & usage graphs
│           └── audit/                     # Security events & compliance viewer
│
├── packages/
│   ├── contracts/
│   │   └── src/
│   │       ├── contracts.json             # [PRE-BUILT IMMUTABLE] Core enums
│   │       ├── index.ts                   # [NEW WAVE 0] TypeScript contract interfaces
│   │       ├── models.py                  # [NEW WAVE 0] Pydantic models for contracts
│   │       └── envelopes.py               # [NEW WAVE 0] ExecutionEnvelope & ProposedAction schemas
│   │
│   ├── prompt-engine/
│   │   └── src/
│   │       ├── engine.js                  # [PRE-BUILT IMMUTABLE]
│   │       ├── meta-prompt.js             # [PRE-BUILT IMMUTABLE]
│   │       ├── playbooks.js               # [PRE-BUILT IMMUTABLE]
│   │       ├── prompt-compiler.js         # [PRE-BUILT IMMUTABLE]
│   │       ├── compilers/                 # [NEW WAVE 2] Additive specialized compilers
│   │       │   ├── cognitive_compiler.js  # Qwen-targeted structured prompt compiler
│   │       │   └── creative_compiler.js   # ComfyUI/Wan workflow prompt compiler
│   │       └── hashing/                   # [NEW WAVE 2] Prompt hashing & provenance
│   │           └── provenance.js          # Deterministic prompt hash & versioning
│   │
│   ├── sdk/                               # [NEW WAVE 1] Client SDK
│   │   ├── python/                        # Python client library
│   │   └── ts/                            # TypeScript client library
│   │
│   └── ui/                                # [NEW WAVE 1] Shared UI design tokens & primitives
│       ├── tokens.json                    # Colors, typography, spacing scale
│       └── components/                    # Button, Dialog, Slider, Canvas primitives
│
├── services/
│   ├── authority/
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   └── src/                           # [NEW WAVE 4] Authority Engine Implementation
│   │       ├── index.js                   # Authority entrypoint & exports
│   │       ├── policy_registry.js         # Security & content policy bundles
│   │       ├── capability_registry.js     # Tool & worker capability declarations
│   │       ├── harness_registry.js        # Registered validation harnesses
│   │       ├── authority_engine.js        # Proposal authorization & decision logic
│   │       └── envelope_signer.js         # Cryptographic HMAC/RSA envelope signing
│   │
│   ├── cognition/
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   └── src/                           # [NEW WAVE 3] Cognition Service Implementation
│   │       ├── index.py                   # Cognition router & client
│   │       ├── vllm_adapter.py            # vLLM runtime client & retry logic
│   │       ├── hardware_probe.py          # Kaggle T4x2 boot-time hardware discovery
│   │       ├── offload_planner.py         # KHF MemoryHarness offload calculator
│   │       └── proposal_parser.py         # Structured ProposedAction extraction
│   │
│   ├── comfy/
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   └── src/                           # [NEW WAVE 5] Creative Tool Fabric
│   │       ├── index.py                   # Creative adapter entrypoint
│   │       ├── capability_manifest.py     # Image, Wan video, and identity manifests
│   │       ├── workflows/                 # ComfyUI JSON workflows
│   │       │   ├── image_sdturbo.json     # Low-latency draft image generation
│   │       │   ├── image_flux.json        # High-fidelity image workflow
│   │       │   ├── wan_i2v.json           # Wan 2.1 image-to-video workflow
│   │       │   └── identity_portrait.json # Identity-consistent portrait workflow
│   │       └── worker_adapter.py          # Envelope verification & Comfy client
│   │
│   ├── harness/
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   └── src/                           # [NEW WAVE 3, 5] Validation & Quality Harness
│   │       ├── index.py                   # Harness registry & orchestrator
│   │       ├── memory_harness.py          # VRAM & host RAM headroom guard
│   │       ├── technical_harness.py       # Aspect ratio, frame count, codec checks
│   │       └── quality_aggregator.py      # Bounded scoring & retry evaluator
│   │
│   ├── intelligence/                      # [PRE-BUILT IMMUTABLE] Run 1 Service
│   │   ├── package.json                   # [PRE-BUILT IMMUTABLE]
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   └── src/                           # [PRE-BUILT IMMUTABLE] 10 source files
│   │
│   └── workers/                           # [NEW WAVE 1, 5] Background Worker Pool
│       ├── src/
│       │   ├── job_runner.py              # Main queue consumer & state transitions
│       │   ├── asset_processor.py         # Asset download, hashing, and storage
│       │   └── kaggle_bridge_worker.py    # Remote tunnel / webhook listener
│       └── requirements.txt
│
├── infrastructure/
│   ├── kaggle/
│   │   └── keystone_kaggle_bootstrap.ipynb# [PRE-BUILT IMMUTABLE] Baseline Notebook Stub
│   │
│   ├── bigquery/                          # [PRE-BUILT IMMUTABLE] Run 1 Infrastructure
│   │   ├── README.md                      # [PRE-BUILT IMMUTABLE]
│   │   ├── schemas/                       # [PRE-BUILT IMMUTABLE]
│   │   ├── queries/                       # [PRE-BUILT IMMUTABLE]
│   │   ├── scripts/                       # [PRE-BUILT IMMUTABLE]
│   │   └── mocks/                         # [PRE-BUILT IMMUTABLE]
│   │
│   ├── migrations/
│   │   └── versions/
│   │       ├── 0001_core.sql              # [PRE-BUILT IMMUTABLE] 12 Baseline Tables
│   │       └── 0002_keystone_full_schema.sql # [NEW WAVE 0] 11 Missing Bible Tables
│   │
│   ├── docker/                            # [NEW WAVE 1] Container Definitions
│   │   ├── Dockerfile.api                 # Cloud Run container for FastAPI API
│   │   ├── Dockerfile.web                 # Cloud Run container for Web Workspace
│   │   └── Dockerfile.worker              # Background worker container
│   │
│   └── gcp/                               # [NEW WAVE 1, 6] Google Cloud Provisioning
│       ├── deploy_cloudrun.ps1            # Cloud Run deployment script
│       ├── setup_cloudsql.ps1             # PostgreSQL setup script
│       └── setup_storage.ps1              # GCS buckets & signed URL permissions
│
├── KAGGLE_SETUP/                          # [NEW WAVE 3] Dedicated Kaggle Repo (§24)
│   ├── README.md                          # Kaggle setup runbook and instructions
│   ├── notebooks/                         # All 3 production notebooks
│   │   ├── 01_keystone_cognition_bootstrap.ipynb # Qwen 27B abliterated + CPU offload
│   │   ├── 02_keystone_comfyui_runtime.ipynb     # ComfyUI + Wan models + ngrok/localtunnel
│   │   └── 03_keystone_integrated_gateway.ipynb  # Self-registering Kaggle gateway
│   ├── configs/                           # vLLM and Comfy launch profiles
│   ├── scripts/                           # Tunnel creation & heartbeat ping
│   ├── logs/                              # Execution & memory telemetry logs
│   └── checklists/                        # Founder manual startup checklists
│
├── docs/
│   ├── BUILD_NOW.md                       # [PRE-BUILT IMMUTABLE]
│   ├── FILE_MANIFEST.txt                  # [PRE-BUILT IMMUTABLE]
│   ├── IDENTITY_PRESERVATION.md           # [PRE-BUILT IMMUTABLE]
│   ├── KEYSTONE_BIBLE.md                  # [NEW WAVE 0] Byte-identical copy per §38
│   ├── UX_RESEARCH_SYNTHESIS.md           # [NEW WAVE 1] Live 6-target Firecrawl analysis
│   ├── PII_VAULT_AUDIT.md                 # [NEW WAVE 6] R6 Compliance audit report
│   ├── RUNBOOK.md                         # [NEW WAVE 6] Founder start/stop instructions
│   └── legal/                             # [NEW WAVE 6] Draft Legal Documents (§30)
│       ├── PRIVACY_POLICY_DRAFT.md
│       └── TERMS_OF_SERVICE_DRAFT.md
│
├── scripts/
│   ├── setup_environment.ps1              # [PRE-BUILT IMMUTABLE]
│   ├── verify_environment.py              # [PRE-BUILT IMMUTABLE]
│   └── run_all_checks.ps1                 # [NEW WAVE 0] Master verification runner
│
└── tests/
    ├── identity.test.js                   # [PRE-BUILT IMMUTABLE] Baseline tests (npm test)
    ├── adversarial_security_suite.js      # [PRE-BUILT IMMUTABLE] Run 1 Security tests
    ├── e2e/                               # [PRE-BUILT IMMUTABLE] 194-test Run 1 Suite
    │   ├── runner.js                      # [PRE-BUILT IMMUTABLE]
    │   ├── challenger_stress.js           # [PRE-BUILT IMMUTABLE]
    │   ├── tier1_features.test.js         # [PRE-BUILT IMMUTABLE]
    │   ├── tier2_boundaries.test.js       # [PRE-BUILT IMMUTABLE]
    │   ├── tier3_combinations.test.js     # [PRE-BUILT IMMUTABLE]
    │   ├── tier4_realworld.test.js        # [PRE-BUILT IMMUTABLE]
    │   ├── tier5_scraping_adversarial.test.js # [PRE-BUILT IMMUTABLE]
    │   ├── tier5_security_adversarial.test.js # [PRE-BUILT IMMUTABLE]
    │   ├── fixtures/                      # [PRE-BUILT IMMUTABLE] 9 mock fixture files
    │   └── harness/                       # [PRE-BUILT IMMUTABLE] 3 harness files
    │
    └── acceptance/                        # [NEW WAVES 1-6] Automated §35 Acceptance Tests
        ├── identity_acceptance.test.js    # All 6 identity bullets from Bible §35
        ├── authority_acceptance.test.js   # All 7 authority bullets from Bible §35
        └── live_pipeline_e2e.py           # 6-step live Cloud Run + Kaggle verification
```

---

## 7. Strategic Recommendations for Orchestrator & Workstream Leads

1. **Gate Verification Rule**:
   Every worker PR / task completion must run both:
   ```bash
   npm test
   node --test tests/e2e/*.test.js
   ```
   and confirm 3/3 baseline tests and 194/194 E2E tests remain 100% green.
2. **Byte-Identical Preservation Check**:
   Before and after any workstream commits, run a checksum validation against the 69 pre-built files inventoried in Section 2. Any checksum mutation to any of these files is an immediate build failure.
3. **Additive Copy of `KEYSTONE_BIBLE.md`**:
   Bible §38 explicitly states: *"Where §38 calls for docs/KEYSTONE_BIBLE.md, provide a byte-identical copy."* This should be created immediately during Wave 0.
4. **Database Expansion**:
   `0001_core.sql` only has 12 tables. The remaining 11 tables required by Bible §21 (`subscriptions`, `api_keys`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `configuration_bundles`, `asset_relationships`) should be written to `infrastructure/migrations/versions/0002_keystone_full_schema.sql`.
5. **FastAPI Extension**:
   `apps/api/src/main.py` is immutable and only has `/v1/health` and `/v1/plan`. The unified FastAPI application should be created as `apps/api/src/server.py` which mounts `apps.api.src.main:app` and includes `intelligence_router` plus all new domain routers (`auth`, `projects`, `sessions`, `jobs`, `assets`, `billing`, etc.).

---
*Report produced by explorer_survey_1 on 2026-10-22.*
