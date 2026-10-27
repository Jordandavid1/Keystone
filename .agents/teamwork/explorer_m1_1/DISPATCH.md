## 2026-10-23T06:39:14Z
From: 6f59f58e-8034-400a-bd25-c869a10728f4 (Project Orchestrator)
Content:
You are explorer_m1_1, a teamwork_preview_explorer subagent for Milestone M1 (Wave 1: Vertical Shell).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (§21 PostgreSQL, §22 Assets & Lineage, §19 Job State Machine, §27 Auth, §28 Tenant Isolation, §33 Wave 1)
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md
- Inspect existing schemas: `infrastructure/migrations/versions/0001_core.sql` and `infrastructure/migrations/versions/0002_keystone_full_schema.sql`
- Inspect existing server: `apps/api/src/server.py` and `packages/contracts/src/models.py`

OBJECTIVE:
Investigate and design the complete implementation blueprint for Milestone M1 (Wave 1: Vertical Shell):
1. F05 Relational Data Models & Repositories:
   - Design database connection manager (`packages/database/src/connection.py`) using asyncpg / SQLAlchemy async engine.
   - Design models & repositories for Users, Projects, Sessions, Messages, Assets, Jobs in `packages/database/src/models/` and `packages/database/src/repositories/`.
2. F06 Authentication & Tenant Isolation:
   - Design authentication middleware and dependency in `packages/security/src/auth.py` supporting session tokens, API keys (hashed), and enforcing tenant isolation where user queries are strictly scoped to project / user boundaries.
3. F07 Asset Storage & Short-Expiry Signed URLs:
   - Design asset storage service in `services/assets/src/storage.py` supporting local persistent disk and Google Cloud Storage fallback, generating 15-minute short-expiry signed URLs.
4. F08 Lineage DAG Tracking:
   - Design asset lineage manager in `services/assets/src/lineage.py` managing `asset_relationships` covering all 8 relationship types (`source`, `edit`, `variation`, `animation`, `upscale`, `reference`, `selected-final`, `intermediate`).
5. F09 Job State Machine Engine:
   - Design deterministic 13-state engine in `services/jobs/src/state_machine.py` with valid transition enforcement:
     `created -> validating -> planning -> authorizing -> queued -> running -> validating_output -> completed`
     plus branches: `retry_pending`, `replan_required`, `failed`, `cancelled`, `rejected`.
6. REST API Routers for M1 under `apps/api/src/routers/`:
   - `auth.py`: `/v1/auth/register`, `/v1/auth/login`, `/v1/auth/api-keys`
   - `projects.py`: `/v1/projects` (CRUD)
   - `sessions.py`: `/v1/projects/{id}/sessions` (CRUD)
   - `messages.py`: `/v1/sessions/{id}/messages` (create, list)
   - `assets.py`: `/v1/assets/upload-url`, `/v1/assets/{id}`, `/v1/assets/{id}/lineage`
   - `jobs.py`: `/v1/jobs` (create, get, transition, list)
   - Design how `apps/api/src/server.py` mounts these routers additively.
7. Verification test suite blueprint for M1 (`tests/e2e_v2/test_m1_vertical_shell.py`).
8. Write comprehensive report to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1\m1_vertical_shell_blueprint.md`.
9. Write handoff to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1\handoff.md`.
10. Send message to parent when complete. Do NOT modify source files.
