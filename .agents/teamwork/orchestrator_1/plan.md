# Keystone Architectural & UX Intelligence Pipeline Plan

## Goal
Implement requirements R1-R4 additively, keeping pre-built code intact and existing tests green, with full verification and audit pass before victory claim.

## Execution Plan

### Phase 0: Survey & Codebase Baseline (Current)
- Dispatch 3 Explorers:
  - Explorer 1: Inspect existing Keystone codebase architecture, package.json, python environment, existing tests (`npm test`), directory layout, and conventions.
  - Explorer 2: Analyze R1 (Firecrawl UX extraction & component tree scraping) and R2 (AES-256-GCM PII Vault, GDPR Art 17 erasure, Aikido prompt injection containment) requirements and domain skills.
  - Explorer 3: Analyze R3 (BigQuery AI/ML SQL procedures, embeddings, similarity) and R4 (Keystone integration manifests, sysadmin guardrails, dependency management).
- Synthesize survey findings into `PROJECT.md`.

### Phase 1: Test Infrastructure & Verification Suite Setup
- Setup E2E testing track (`TEST_INFRA.md`).
- Define requirement-driven test cases (Tiers 1-4).

### Phase 2: Implementation of R1 & R2 (Intelligence, Scraping & Security)
- Build Firecrawl UX extraction service (`services/intelligence` or `packages/signal-scraper`).
- Build Enterprise PII Vault (AES-256-GCM tokenization, GDPR erasure) & Aikido prompt injection defense.

### Phase 3: Implementation of R3 (BigQuery AI/ML & Embeddings Layer)
- Author BigQuery schemas, queries, embeddings generation, and similarity procedures with mandatory resource attribution labeling.

### Phase 4: Implementation of R4 (Additive Keystone Integration & Manifests)
- Wire new capabilities cleanly into Keystone without touching existing contracts.
- Validate Python dependencies and virtual environments.

### Phase 5: Verification & Gate Audit
- Run full verification suite (Tiers 1-4).
- Adversarial coverage hardening (Tier 5).
- Run forensic integrity audit (`teamwork_preview_auditor`).
- Confirm baseline `npm test` remains 100% green.
- Report victory to Sentinel.
