## 2026-10-22T16:44:14Z
You are worker_m0, a teamwork_preview_worker subagent implementing Milestone M0 (Wave 0: Contract Freeze & Additive Foundation).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m0

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (STRICTLY READ-ONLY! Checksum 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788).
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md
- Read Explorer Blueprint 1 (Contracts & Server): c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_1\m0_contracts_api_blueprint.md
- Read Explorer Blueprint 2 (23-Table DDL Migration): c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2\m0_database_schema_blueprint.md
- Read Explorer Blueprint 3 (Invariants & Verification): c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_3\m0_invariants_and_verification_blueprint.md

EXCLUSIVE WRITE OWNERSHIP (You may only write to these files):
1. docs/KEYSTONE_BIBLE.md (byte-identical binary copy of root KEYSTONE_BIBLE.md per §38)
2. packages/contracts/src/models.py (Complete Pydantic v2 schemas per Blueprint 1)
3. packages/contracts/src/index.ts (TypeScript interfaces per Blueprint 1)
4. packages/contracts/src/canonical_contracts.json (JSON schemas per Blueprint 1)
5. apps/api/src/server.py (Additive API server importing app from main.py, mounting intelligence router, /v1/contracts, OpenAPI per Blueprint 1)
6. infrastructure/migrations/versions/0002_keystone_full_schema.sql (Complete PostgreSQL DDL for 11 missing tables with constraints, indexes, and immutability trigger per Blueprint 2 §6)
7. scripts/verify_invariants.py (Automated invariant verification script per Blueprint 3 §3.3)
8. scripts/verify_change_control.py (Automated change control audit script per Blueprint 3 §4)
9. docs/change_control/ADR_TEMPLATE.md (ADR template per Blueprint 3 §4)
10. tests/e2e_v2/test_m0_contracts_server.py (Verification test suite per Blueprint 1 §5.2)

FORBIDDEN FILES (DO NOT MODIFY, OVERWRITE, OR TOUCH):
- Root KEYSTONE_BIBLE.md
- Any of the 69 pre-built files (apps/api/src/main.py, apps/api/src/intelligence_router.py, packages/contracts/src/contracts.json, infrastructure/migrations/versions/0001_core.sql, tests/identity.test.js, tests/e2e/*, etc.)

TASK EXECUTION STEPS:
1. Copy root KEYSTONE_BIBLE.md to docs/KEYSTONE_BIBLE.md and verify its SHA-256 is 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788.
2. Implement packages/contracts/src/models.py, index.ts, and canonical_contracts.json using the exact models from Blueprint 1.
3. Implement apps/api/src/server.py using the exact implementation from Blueprint 1.
4. Implement infrastructure/migrations/versions/0002_keystone_full_schema.sql using the exact DDL from Blueprint 2 §6.
5. Implement scripts/verify_invariants.py, scripts/verify_change_control.py, and docs/change_control/ADR_TEMPLATE.md from Blueprint 3.
6. Implement tests/e2e_v2/test_m0_contracts_server.py.
7. Run the verification commands:
   - npm test
   - node tests/e2e/runner.js
   - python scripts/verify_invariants.py --require-docs-bible
   - pytest tests/e2e_v2/test_m0_contracts_server.py
   - git status --porcelain (confirm 0 pre-built files modified)
8. Write comprehensive handoff.md in your dedicated folder.
9. Send completion message to parent (6f59f58e-8034-400a-bd25-c869a10728f4).
