## 2026-10-22T14:35:54Z
You are the Intelligence Core Worker (teamwork_preview_worker) for Milestone 2.
Working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m2
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative Request: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Authoritative Plan: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_1\PROJECT.md
Test Infra: c:\Users\Lesia Eden\Downloads\keystone-cowork\TEST_INFRA.md
Test Ready: c:\Users\Lesia Eden\Downloads\keystone-cowork\TEST_READY.md

Authoritative Specifications to Implement:
1. Firecrawl & 6-Target AST Spec: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m2\spec_report.md
2. PII Vault & GDPR Erasure Spec: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_1\vault_spec.md
3. Aikido Prompt Injection & Packaging Spec: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_2\aikido_spec.md

CRITICAL USER DIRECTIVE:
"use firecrawl when coding use the skills"
You MUST read and utilize the Firecrawl skills at:
- C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-build\SKILL.md
- C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-build-scrape\SKILL.md
- C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-website-design-clone\SKILL.md
- C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-scrape\SKILL.md
- C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-developer-index\SKILL.md
- C:\Users\Lesia Eden\.gemini\config\skills\pii-vault-compliance\SKILL.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

EXCLUSIVE WRITE OWNERSHIP:
You own files under `services/intelligence/` ONLY:
- `services/intelligence/package.json`
- `services/intelligence/src/scraper/firecrawl_client.js`
- `services/intelligence/src/scraper/ast_deconstructor.js`
- `services/intelligence/src/scraper/edge_pii.js`
- `services/intelligence/src/scraper/dedup_cache.js`
- `services/intelligence/src/vault/vault_service.js`
- `services/intelligence/src/security/aikido_defense.js`
- `services/intelligence/src/bridge/capability_manifest.js`
- `services/intelligence/src/bridge/prompt_bridge.js`
- `services/intelligence/src/index.js`
DO NOT modify any of the 21 pre-built baseline tracked files or files under `tests/identity.test.js`.

TASKS:
1. Implement the complete `services/intelligence` package and all modules matching the specifications in `spec_report.md`, `vault_spec.md`, and `aikido_spec.md`. Ensure compatibility with `tests/e2e/harness/loader.js` and all 132 tests.
2. Run baseline verification: `npm test` (must pass 3/3, 100% green).
3. Run E2E test suite: `node --test tests/e2e/*.test.js` and `node tests/e2e/runner.js` (must pass 132/132 tests, 100% green).
4. Write your handoff report to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m2\handoff.md` with full execution evidence and command results, and notify the orchestrator.
