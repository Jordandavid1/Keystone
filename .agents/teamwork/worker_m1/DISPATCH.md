## 2026-10-22T19:12:54Z
Your identity: worker_m1
Your working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m1
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative requests: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Scope document: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_3\PROJECT.md
Canonical specification: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md

MANDATORY FIRST STEP:
Read c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md before starting any work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY BLUEPRINTS & REPORTS TO CONSULT:
1. c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m1_1\handoff.md (Exact specifications, transition matrices, schemas, edge cases, error codes)
2. c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1\handoff.md (Complete SQLAlchemy 2.0 ORM across 23 tables, tenant repositories, crypto auth, routers)
3. c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_2\handoff.md (StorageProvider, short-expiry signed URLs, Lineage DAG cycle detection, 13-state Job State Machine)

YOUR WRITE OWNERSHIP:
You own exclusively:
- apps/api/src/db/*
- apps/api/src/auth/*
- apps/api/src/repositories/*
- apps/api/src/storage/*
- apps/api/src/lineage/*
- apps/api/src/jobs/*
- apps/api/src/routers/*
- apps/api/src/server.py (additive modifications only)
- tests/e2e_v2/test_m1_core_shell.py

STRICT PROHIBITION:
DO NOT modify or overwrite any pre-built baseline work (such as apps/api/src/main.py, apps/api/src/intelligence_router.py, KEYSTONE_BIBLE.md, etc.). All 69 baseline files must remain 100% byte-identical.

TASKS TO IMPLEMENT:
1. F05: SQLAlchemy 2.0 ORM & Tenant Repositories:
   - `apps/api/src/db/models.py`: Modern DeclarativeBase models for all 23 tables matching migration 0002.
   - `apps/api/src/db/session.py`: Async engine supporting SQLite (local dev/test) and PostgreSQL (production).
   - `apps/api/src/repositories/`: Tenant-scoped repositories for Users, Projects (with soft delete), Sessions, Messages, Assets (with soft delete), Jobs.
2. F06: Authentication & Tenant Isolation:
   - `apps/api/src/auth/security.py`: PBKDF2 password hashing, HMAC-SHA256 Bearer JWT tokens, API key hashing, service token check.
   - `apps/api/src/auth/dependencies.py`: FastAPI security dependencies (`get_current_user`, `get_current_tenant_id`, `enforce_tenant_isolation`).
3. F07: Asset Storage & Short-Expiry URLs:
   - `apps/api/src/storage/`: `LocalStorageProvider`, `GoogleCloudStorageProvider`, `AssetStorageService`. Tenant storage key `tenants/{user_id}/assets/{asset_id}/{safe_filename}` with path traversal sanitization. HMAC-SHA256 signed URLs (default 900s, max 3600s).
4. F08: Lineage DAG Tracking:
   - `apps/api/src/lineage/dag.py`: Support for all 8 relationship types (`source`, `edit`, `variation`, `animation`, `upscale`, `reference`, `selected-final`, `intermediate`). Self-referential protection (`SELF_REFERENTIAL_LINEAGE`). Cycle detection (`CYCLE_DETECTED`). BFS/DFS ancestor and descendant traversal.
5. F09: Job State Machine Engine:
   - `apps/api/src/jobs/state_machine.py`: 13 discrete states, 4 terminal states, transition matrix, terminal state mutation protection, idempotent transitions, retry/replan loops.
6. API Routers & Additive Mounting:
   - `apps/api/src/routers/auth.py`, `projects.py`, `sessions.py`, `assets.py`, `jobs.py`.
   - Additively mount in `apps/api/src/server.py`.
7. Comprehensive Test Suite:
   - Create `tests/e2e_v2/test_m1_core_shell.py` exercising all F05-F09 functionalities.

VERIFICATION REQUIRED:
Execute and verify:
1. `npm test` (3/3 passing)
2. `node tests/e2e/runner.js` (132/132 passing)
3. `python scripts/verify_invariants.py --require-docs-bible` (100% invariants satisfied)
4. `pytest tests/e2e_v2/test_m1_core_shell.py` (All passing)
5. `node tests/e2e_v2/runner.js` (373/373 passing)
