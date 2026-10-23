# Handoff Report: Firecrawl Specification Mining for Milestone 2

**Agent**: Firecrawl Specification Miner (`teamwork_preview_spec_miner`)  
**Workspace**: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m2`  
**Recipient**: Parent Orchestrator (`60572d58-20e5-4b73-8f9a-70a7a40329ec`)  
**Date**: 2026-10-22  
**Type**: Hard Handoff (Task Complete)  

---

## 1. Observation

1. **Authoritative Request & Directives**:
   - `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md` (lines 57–81): Mandates Option A (Full-Pipeline Integration) across 6 leading benchmark applications:
     1. Hugging Face Spaces/Hub
     2. Higgsfield (video/motion AI)
     3. ZenCreator Pro (creator studio workflows)
     4. Venice AI (privacy-first generative AI)
     5. Adobe Creative Cloud / Firefly (creative tooling pipelines)
     6. Grok (multimodal reasoning UX)
   - Line 78 explicitly directs: `"use firecrawl when coding use the skills"`.
2. **Project Plan & Architecture**:
   - `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_1\PROJECT.md` (lines 14–21, 36–44): Defines Milestone 2 scope:
     - `services/intelligence/`: All R1/R2 source and unit tests.
     - Features F1 to F7: Firecrawl Streamable Client & Watchdog (25s), Benchmark UX Deconstruction (6 targets), Edge-Level PII Redaction (`redactPII: true`), SHA-256 Signal Deduplication (sliding 30-day TTL), Enterprise PII Boundary Vault (`AES-256-GCM`, `vault_tok_<uuid>`), GDPR Article 17 Cascading Erasure, Aikido Prompt-Injection Defense (`<untrusted_content>`).
3. **Test Infrastructure & Verified Oracles**:
   - `tests/e2e/harness/contract_oracle.js` (lines 20–579): Fully implements executable reference classes (`ScraperService`, `EdgePiiScrubber`, `SignalDeduplicator`, `PiiVaultService`, `AikidoDefenseService`, `KeystoneBridgeService`) against which 132 tests in `tests/e2e/*.test.js` pass with 100% green status.
   - `tests/e2e/harness/loader.js` (lines 12–20): Seamlessly detects `services/intelligence/src` and binds production implementations once built.
   - `tests/e2e/fixtures/targets_catalog.json` (lines 1–58): Defines exact target schemas, sample HTML fixtures, and domain categories.
   - `tests/e2e/fixtures/hf_space_deconstruct.json` (lines 1–217): Authoritative AST schema for Hugging Face Space deconstruction.
4. **Firecrawl Skill Methodology**:
   - `firecrawl-build/SKILL.md`: SDK vs REST selection, environment setup (`FIRECRAWL_API_KEY`).
   - `firecrawl-build-scrape/SKILL.md`: Page-level extraction primitives, formats, `maxAge`, `onlyMainContent`.
   - `firecrawl-website-design-clone/SKILL.md`: Extraction of semantic color roles, typography, spacing scales, component patterns.
   - `firecrawl-scrape/SKILL.md`: Scraper parameters, JSON schemas, timeout handling.
   - `firecrawl-developer-index/SKILL.md`: API contract querying and verification.
5. **Specification Report Deliverable**:
   - Written to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m2\spec_report.md` (465 lines) with 26 discovered features in table format, 34 edge cases with observed behaviors, full TypeScript interfaces, regex patterns, cryptographic algorithms, and production layout blueprint.

---

## 2. Logic Chain

1. **Deriving Implementation Boundaries from System Invariants**:
   - Observation 1 & 2 establish that pre-built code is strictly immutable (21 baseline files).
   - Therefore, all Milestone 2 code must be placed additively in `services/intelligence/` under the npm workspace glob defined in root `package.json`.
2. **Deriving Exact Class & Method Contracts from Active Test Oracles**:
   - `tests/e2e/tier1_features.test.js`, `tier2_boundaries.test.js`, `tier3_combinations.test.js`, and `tier4_realworld.test.js` contain 132 assertions that specifically check:
     - `scraper.buildScrapeRequest(url, options)` enforcing `redactPII: true`, 25,000ms timeout, and throwing `INVALID_URL`, `INVALID_PROTOCOL`, `INVALID_TIMEOUT`.
     - `scraper.deconstructBenchmark(html, url)` producing AST with `rootNodeId`, `nodes`, `hierarchy`, and `designTokens` matching CSS variables or falling back cleanly.
     - `edgePii.scrub(content)` scrubbing emails, obfuscated emails, phone numbers, API keys, IPv4 while preserving CSS and technical words.
     - `dedup.computeHash(url, entityType, payload)` hashing `${normalizedUrl}:${entityType}:${sortedJson}` to 64-char hex, with 30-day sliding TTL.
     - `vault.tokenize(plaintext, subjectId, entityType)` encrypting via `AES-256-GCM` with a 12-byte IV and 16-byte tag, producing `vault_tok_<uuid>`, and `detokenize()` rejecting tampered ciphertexts.
     - `vault.purgeSubject(subjectId)` executing 5-step cascading erasure (vault shredding, job queue cancellation, zero-PII audit ledger, detokenize blocking, and idempotency).
     - `aikido.quarantine(content)` wrapping in `<untrusted_content>`, escaping `</untrusted_content>` to `&lt;/untrusted_content&gt;`, scrubbing scripts/comments, scoring threat levels (`SAFE`, `SUSPICIOUS`, `MALICIOUS`), and sanitizing output.
     - `bridge.getCapabilityManifest()` conforming to OpenAPI `PublicCapability`, and `compilePlanWithBenchmark()` compiling plans via Keystone's prompt engine.
   - Because `loader.js` binds to `services/intelligence/src` if present, matching these exact method signatures guarantees that the test suite will immediately validate the production code upon implementation.
3. **Harmonizing Firecrawl Skills with Project Contracts**:
   - Official Firecrawl skills (`firecrawl-website-design-clone`, `firecrawl-build-scrape`) emphasize extracting semantic color roles, typography, spacing scales, and layout trees.
   - These map directly to the `DesignSystemTokens` and `ComponentTree` interfaces specified in `spec_report.md`.

---

## 3. Caveats

1. **Network vs Offline Fixtures**: Live Firecrawl API calls require network access and a valid `FIRECRAWL_API_KEY`. When offline or without an API key, the client must seamlessly use the 25s watchdog fallback to load the realistic HTML fixtures in `tests/e2e/fixtures/`.
2. **Read-Only Invariant**: As Spec Miner, no production application files in `services/intelligence/` or elsewhere were created or modified during this turn. All outputs are strictly confined to metadata files in `.agents/teamwork/spec_miner_m2/`.

---

## 4. Conclusion

The authoritative technical specification for Milestone 2 has been thoroughly mined, verified, and documented in:
`c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m2\spec_report.md`.

All required interfaces, parameters (`redactPII: true`), watchdog timeout logic (25,000ms), 6-target AST patterns (Hugging Face, Higgsfield, ZenCreator Pro, Venice AI, Adobe Creative Cloud / Firefly, Grok), SHA-256 composite hashing, AES-256-GCM vault tokenization, GDPR Art 17 erasure, and Aikido prompt defense have been documented in complete detail.

Downstream implementers for Milestone 2 (`intelligence_lead` / `implementer_m2`) can immediately consume `spec_report.md` and implement `services/intelligence/src/` to turn the E2E test suite green against real production code.

---

## 5. Verification Method

To verify the findings and specifications:
1. **Inspect Specification Report**:
   - View `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m2\spec_report.md`.
2. **Verify Baseline Invariant**:
   ```bash
   npm test
   ```
   *Pass criteria: 3/3 tests passing in `tests/identity.test.js`.*
3. **Verify E2E Test Suite Alignment**:
   ```bash
   node tests/e2e/runner.js
   ```
   *Pass criteria: 132/132 tests passing across Tiers 1–4.*
