## 2026-10-22T19:02:50Z
Your identity: spec_miner_m1_1
Your working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m1_1
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative requests: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Scope document: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_3\PROJECT.md
Canonical specification: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md

MANDATORY FIRST STEP:
Read c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md before starting any work.

YOUR TASK:
Extract exact, authoritative specification requirements for Milestone M1 (F05–F09 and Wave 1 Vertical Shell / Creative Fabric):
1. Extract all specifications from KEYSTONE_BIBLE.md regarding:
   - §19: Job states, allowed transitions, terminal states, retry limits, cancellation.
   - §21: Relational models, 23 tables, foreign keys, cascade rules, soft deletion.
   - §22: Assets, storage keys, signed URLs, short expiry (15 min), lineage relationships (8 types), DAG acyclicity.
   - §23: Creative tool fabric contracts (ComfyUI, Wan, FaceFusion, Upscale) relevant to execution envelope payloads.
   - §27, §28: Authentication, API keys (hashed), session tokens, tenant isolation.
   - §33: Wave 1 vertical shell sequence.
2. Inspect tests/e2e_v2/harness/keystone_oracle.js and tests/e2e_v2/tier1_features.test.js to extract exact test expectations, parameters, error types, and response schemas for F05–F09.

OUTPUT:
Write your complete specification report to c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m1_1\handoff.md.
Include:
- Exact method signatures and schemas required.
- State machine transition table matrix.
- Lineage relationship types and edge rules.
- Test assertion contracts from Tier 1–4 suites.
Send a completion message back to your parent orchestrator with the file path when done.
