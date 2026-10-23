# Project: Keystone Additive Architectural & UX Intelligence Pipeline

## Architecture

Keystone is an authoritative creative orchestration and prompt-intelligence platform. The repository contains 21 baseline tracked files (all IMMUTABLE). All new capabilities are built strictly additively.

```
keystone-cowork/
├── apps/
│   └── api/                  # FastAPI app (baseline immutable, routes extended via sub-router)
├── packages/
│   ├── contracts/            # Contracts JSON (immutable, extended via manifest)
│   └── prompt-engine/        # Core prompt engine (immutable 13 playbooks & 6-part PromptAnatomy)
├── services/
│   └── intelligence/         # [ADDITIVE R1 & R2]
│       ├── package.json      # Workspace package for intelligence service
│       └── src/
│           ├── scraper/      # Firecrawl client, watchdog, AST deconstruction, SHA-256 deduplication
│           ├── vault/        # AES-256-GCM encryption, tokenization, GDPR Art 17 erasure
│           ├── security/     # Aikido prompt injection defense (<untrusted_content> quarantine)
│           └── bridge/       # Keystone PromptAnatomy adapter & OpenAPI capability manifest
├── infrastructure/
│   └── bigquery/             # [ADDITIVE R3]
│       ├── schemas/          # Dataset DDL, benchmark tables, vector embeddings
│       ├── queries/          # AI.GENERATE, AI.SIMILARITY, AI.CLASSIFY procedures
│       ├── scripts/          # Attribution-labeled deploy scripts (--label datacloud:antigravity)
│       └── mocks/            # Query AST validator & offline execution harness
└── tests/                    # [ADDITIVE VERIFICATION]
    ├── identity.test.js      # Baseline immutable test (3/3 passing)
    ├── e2e_intelligence.test.js # Tier 1-4 comprehensive opaque-box test suite
    └── adversarial_hardening.test.js # Tier 5 white-box coverage hardening
```

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Firecrawl Streamable Client & Watchdog | HTTP/FastMCP client with 25s timeout, mock fixture fallback for 6 benchmark targets | M2 | R1 |
| F2 | Benchmark UX Deconstruction | AST parser for component trees, design systems, API contracts, workflows across 6 targets (Hugging Face, Higgsfield, ZenCreator Pro, Venice AI, Adobe Creative Cloud/Firefly, Grok) | M2 | R1 |
| F3 | Edge-Level PII Redaction | `redactPII: true` enforced on all scraping, regex edge scrubbing | M2 | R1 |
| F4 | SHA-256 Signal Deduplication | Canonical hash with 30-day sliding TTL cache | M2 | R1 |
| F5 | Enterprise PII Boundary Vault | AES-256-GCM encryption (12-byte IV, 16-byte tag), `vault_tok_<uuid>` | M2 | R2 |
| F6 | GDPR Article 17 Cascading Erasure | 5-step idempotent erasure, audit log without plain PII | M2 | R2 |
| F7 | Aikido Prompt-Injection Defense | `<untrusted_content>` containment, tag escaping, post-gen sanitization | M2 | R2 |
| F8 | BigQuery AI/ML Schema & DDL | Scraped architecture tables, remote models, vector embeddings | M3 | R3 |
| F9 | BigQuery AI/ML Analysis Procedures | `AI.GENERATE`, `AI.SIMILARITY`, `AI.CLASSIFY`, TVF `VECTOR_SEARCH` in FROM | M3 | R3 |
| F10 | Mandatory Resource Attribution | Mutating `bq` commands with `--label datacloud:antigravity` | M3 | R3 |
| F11 | Additive Keystone Capability Manifest | OpenAPI `PublicCapability` manifest and PromptAnatomy context bridge | M4 | R4 |
| F12 | Python Environment & Sysadmin Safety | Isolated `.venv`, requirements verification, non-interactive execution | M4 | R4 |
| F13 | Complete Baseline Preservation | 21 tracked files immutable, `npm test` remains 100% green | M1-M5 | Invariant |
| F14 | Comprehensive E2E Test Suite | Tiers 1-4 (>=60 tests) opaque-box test runner, `TEST_READY.md` | M1 | Verification |
| F15 | Adversarial Coverage Hardening | Tier 5 white-box challenger test generation | M5 | Hardening |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Test Infrastructure Track | TEST_INFRA.md, opaque-box test definitions (Tiers 1-4), runner, TEST_READY.md | none | DONE |
| 2 | Intelligence Core (R1 & R2) | Firecrawl scraper, UX deconstruction, PII Vault (AES-256-GCM), Aikido defense | M1 | DONE |
| 3 | BigQuery AI/ML Layer (R3) | SQL schemas, TVFs in FROM clause, attribution labeling, procedures | M2 | DONE |
| 4 | Additive Keystone Integration (R4) | Capability manifest, PromptAnatomy bridge, Python venv checks | M2, M3 | DONE |
| 5 | Final Milestone: 100% E2E Pass & Hardening | Pass all Tier 1-4 tests, Tier 5 adversarial hardening, forensic audit | M1, M2, M3, M4 | DONE |

## Interface Contracts

### Scraper ↔ PII Vault
- `extractBenchmark(url, options) -> RawBenchmarkPayload`
- `vault.tokenize(RawBenchmarkPayload) -> SanitizedBenchmarkPayload`
  - Replaces all email/phone/name with `vault_tok_<uuid>`
  - Generates AES-256-GCM ciphertext in vault store

### PII Vault ↔ Aikido Defense
- `sanitizeForPrompt(SanitizedBenchmarkPayload) -> UntrustedPromptContext`
  - Wraps in `<untrusted_content>` tags
  - Escapes nested `</untrusted_content>` tags
  - Verifies zero plain PII reaches LLM prompt context

### Intelligence ↔ Keystone Prompt Engine
- `buildIntelligencePromptContext(SanitizedBenchmarkPayload) -> PromptAnatomyContext`
  - Attaches to `PromptAnatomy.context` conforming to `packages/contracts/src/contracts.json`

### Intelligence ↔ BigQuery AI/ML Layer
- Ingestion table: `keystone_intelligence.scraped_benchmarks`
- Schema fields: `benchmark_id STRING, source_url STRING, component_tree JSON, design_tokens JSON, api_contracts JSON, workflow_patterns JSON, content_hash STRING, ingested_at TIMESTAMP`
- Embeddings TVF: `FROM AI.GENERATE_EMBEDDING(TABLE keystone_intelligence.scraped_benchmarks, 'component_tree', connection => 'DEFAULT')`
- Search TVF: `FROM VECTOR_SEARCH(TABLE keystone_intelligence.benchmark_embeddings, 'embedding', TABLE query_table, top_k => 5)`

## Code Layout

- `services/intelligence/`: All R1/R2 source and unit tests
- `infrastructure/bigquery/`: All R3 SQL DDL, queries, procedures, attribution scripts, and mock validation
- `tests/e2e_intelligence.test.js`: Additive E2E test suite (Tiers 1-4)
- `tests/identity.test.js`: Untouched baseline test file (3/3 passing)
