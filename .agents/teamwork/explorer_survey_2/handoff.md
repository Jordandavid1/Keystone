# Handoff Report: Explorer 2 (Firecrawl & PII/Aikido Security Investigator)

**From**: Explorer 2 (`7b0c9ec0-43ff-4e33-b9cd-9083917fc7ca`)  
**To**: Orchestrator (`60572d58-20e5-4b73-8f9a-70a7a40329ec`)  
**Date**: 2026-10-22  
**Type**: Hard Handoff (Investigation & Architecture Survey Complete)  

---

## 1. Observation

1. **`package.json`**:
   - Lines 8-13:
     ```json
     "workspaces": ["apps/*", "packages/*", "services/*"],
     "scripts": {
       "test": "node --test tests/*.test.js",
       "test:identity": "node --test tests/identity.test.js",
       "dev:api": "python -m uvicorn apps.api.src.main:app --reload --port 8000"
     }
     ```
   - Running `npm test` synchronously completed with code 0:
     ```
     ✔ KEYSTONE preserves plan.v1 and six-part PromptAnatomy (8.1668ms)
     ✔ KEYSTONE preserves all 13 domain playbooks (1.1228ms)
     ✔ compiler remains model-agnostic with chat and reasoning profiles (0.9622ms)
     ℹ tests 3, suites 0, pass 3, fail 0
     ```

2. **`ORIGINAL_REQUEST.md` Requirements R1 & R2**:
   - Lines 20-27:
     - R1: "Build an additive service/module (e.g., under `services/intelligence` or `packages/signal-scraper`) utilizing Firecrawl skills (`firecrawl-scrape`, `firecrawl-build`, `firecrawl-website-design-clone`) to extract frontend component trees, design systems, API contracts, and workflow patterns from benchmark applications (such as Hugging Face Spaces/Hub). Enforce edge-level PII scrubbing (`redactPII: true`) and SHA-256 signal deduplication."
     - R2: "Implement boundary encryption using AES-256-GCM for any extracted contact or personal references, passing only tokenized references. Implement Aikido prompt-injection defense: structural delimiter containment (`<untrusted_content>`), tag escaping, and post-generation sanitization so untrusted scraped markup never hijacks downstream LLM generation. Implement GDPR Article 17 cascading erasure logic with idempotency."

3. **`pii-vault-compliance` Skill**:
   - Lines 20-25: Mandates context minimization via AES-256-GCM vault tokenization, passing only tokenized references (`prospectId` / `vault_token`) to LLM contexts, with rehydration only at the final authorized boundary.
   - Lines 37-44: Mandates 5-step GDPR Article 17 cascading erasure (Vault erasure, signal purge > 30 days, queue purge, immutable audit logging with zero PII, and idempotent returns).
   - Lines 45-55: Mandates Aikido prompt-injection defense: structural delimiter containment (`<untrusted_content>`), tag scrubbing/escaping (`</untrusted_content>`), and post-generation sanitization.

4. **`firecrawl-signal-scraper` Skill**:
   - Lines 24-35: Mandates `redactPII: true` on all scrape requests and watchdog timeout (20-25s) with failover.
   - Lines 45-53: Mandates SHA-256 deduplication hashing: `sha256(canonicalUrl + ":" + entityType + ":" + date/payload)` with sliding TTL cache.

5. **`packages/prompt-engine` Existing Contracts**:
   - `prompt-compiler.js` (lines 15-52) compiles prompts into Markdown, Chat, or Reasoning models from `PromptAnatomy` containing `role`, `task`, `context`, `constraints`, `outputFormat`, and `reasoning`.
   - `engine.js` (line 29) already uses XML delimiter containment syntax (`<previous_step_output>...</previous_step_output>`) in prompt contexts.

---

## 2. Logic Chain

1. From **Observation 1**, `package.json` configures `"workspaces": ["apps/*", "packages/*", "services/*"]` and `"test": "node --test tests/*.test.js"`. Any new module placed under `services/intelligence` automatically participates in the workspace without modifying `package.json`.
2. From **Observation 2**, R1 and R2 require additive implementation without overwriting pre-built code. By creating `services/intelligence` (containing `scraper/`, `vault/`, `security/`, and `bridge/`), we fulfill all R1 and R2 requirements in a self-contained module.
3. From **Observation 3**, to ensure zero plain PII enters downstream models or BigQuery tables, the PII Vault must encrypt sensitive personal fields at the boundary with authenticated `AES-256-GCM` using unique 12-byte IVs, emitting `vault_tok_<uuid>`. For GDPR Article 17 erasure, the 5-step cascade must be implemented with audit logging to `audit_events` (from `infrastructure/migrations/versions/0001_core.sql`) strictly omitting plain PII, and returning HTTP 200 with `erasedVaultRecords: 0` on duplicate calls.
4. From **Observation 4**, Firecrawl scrape requests must include `redactPII: true` at the edge, supplemented by local regex scrubbing, and use canonical SHA-256 deduplication with a 30-day sliding TTL cache to skip redundant processing.
5. From **Observation 5**, when benchmark intelligence is passed into Keystone's `PromptAnatomy.context`, wrapping it with Aikido `<untrusted_content>` delimiters and escaping nested closing tags (`</untrusted_content>`) ensures that untrusted HTML/markdown cannot hijack the prompt compiler or cognitive runtime.
6. From **Observation 1**, implementing `services/intelligence` in Node.js and placing test suites in `tests/*.test.js` guarantees that `npm test` executes the complete verification suite while leaving baseline identity tests untouched and green.

---

## 3. Caveats

1. **Live Network Credentials**: In offline CI/CD or development environments without an active `FIRECRAWL_API_KEY`, the scraper client must automatically fall back to mock benchmark fixtures (e.g., pre-recorded Hugging Face Space payloads) so test suites execute deterministically without external dependencies.
2. **Master Key Storage**: In development, `PII_VAULT_KEY` can be derived from an environment variable or local PBKDF2 default, but in production, it should be retrieved from a secure secret store or KMS.
3. **BigQuery AI/ML Boundary**: Embeddings and SQL transformations over benchmark intelligence are scoped to Explorer 3 and the subsequent implementation phase; this report specifies the exact JSON schemas and sanitized inputs provided to that layer.

---

## 4. Conclusion

Requirements R1 and R2 can be completely and cleanly satisfied through an additive module in `services/intelligence`:
1. `services/intelligence/src/scraper/`: Firecrawl client with watchdog timer, `redactPII: true`, Hugging Face Space deconstruction (component trees, design tokens, API contracts, workflow patterns), and SHA-256 deduplication.
2. `services/intelligence/src/vault/`: Enterprise PII Vault using AES-256-GCM authenticated encryption, context minimization, client masking, and 5-step GDPR Article 17 cascading erasure with idempotency.
3. `services/intelligence/src/security/`: Aikido prompt injection defense with structural delimiter containment (`<untrusted_content>`), tag escaping, post-generation sanitization, and heuristic threat detection.
4. Baseline tests (`npm test`) remain 100% green without modifying any existing files.

Detailed architecture specifications, schemas, interfaces, and test strategies are fully documented in `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_survey_2\survey_report.md`.

---

## 5. Verification Method

To independently verify the findings and specifications:
1. **Verify Baseline Non-Regression**:
   ```bash
   npm test
   ```
   Must pass 3/3 tests in `tests/identity.test.js`.
2. **Inspect Survey Report**:
   Read `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_survey_2\survey_report.md` to verify complete schema definitions, AES-256-GCM parameters, GDPR Article 17 flow, and Aikido delimiter containment logic.
3. **Invalidation Conditions**:
   - Any modification to `packages/prompt-engine/src/*` or `packages/contracts/src/*` invalidates the additive architecture guarantee.
   - Any leakage of raw unencrypted emails or phone numbers into `PromptAnatomy.context` invalidates the zero-PII compliance invariant.
   - Any failure of `npm test` invalidates baseline integrity.
