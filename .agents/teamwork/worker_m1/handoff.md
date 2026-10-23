# Milestone M1 (Core Shell) Implementation & Quality Handoff Report

**Agent**: `worker_m1` (Implementer, QA, Specialist)  
**Milestone**: M1 (Wave 1: Creative Tool Fabric & Core Shell)  
**Assigned Features**: F05 (Relational Data Models & Repositories), F06 (Authentication & Tenant Isolation), F07 (Asset Storage & Short-Expiry URLs), F08 (Lineage DAG Tracking), F09 (Job State Machine Engine), Routers, and Verification Suite  
**Date**: 2026-10-22  
**Status**: COMPLETE (100% Verified, All Invariants Preserved)  

---

## 1. Observation

Direct observations extracted from implementation, code execution, and test verification:

1. **Database Schema & ORM Models (`apps/api/src/db/models.py:1–430`)**:
   - Implemented SQLAlchemy 2.0 `DeclarativeBase` ORM models covering all 23 tables matching `0001_core.sql` and `0002_keystone_full_schema.sql`:
     `users`, `subscriptions`, `api_keys`, `projects`, `sessions`, `messages`, `assets`, `requests`, `request_assets`, `cognitive_runs`, `authority_decisions`, `jobs`, `generation_attempts`, `compiled_prompts`, `attempt_assets`, `harness_runs`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `audit_events`, `configuration_bundles`, `asset_relationships`.
   - Developed `UniversalUUID` type decorator allowing seamless cross-dialect execution across SQLite (`CHAR(36)`) and PostgreSQL (`UUID`).
   - Mapped `metadata_ = mapped_column("metadata", JSON)` to avoid collision with SQLAlchemy's `Base.metadata`.

2. **Async Database Engine & Session (`apps/api/src/db/session.py:1–75`)**:
   - Implemented async engine supporting both SQLite (`sqlite+aiosqlite:///./keystone.db`) and PostgreSQL (`postgresql+asyncpg://...`).
   - Integrated self-healing schema initialization ensuring 23 tables are created on startup or first request.

3. **Tenant-Isolated Repositories (`apps/api/src/repositories/`)**:
   - `BaseRepository[T]` binds `session` and `tenant_id`.
   - `UserRepository`: Enforces validation (`INVALID_USER` if id/email empty), initializes default `CreditAccount`.
   - `ProjectRepository`: Scopes all operations to `user_id == self.tenant_id`, checks user existence (`USER_NOT_FOUND`), filters soft-deleted records (`deleted_at.is_(None)`).
   - `SessionRepository`: Verifies project existence and active ownership (`PROJECT_NOT_FOUND_OR_FORBIDDEN`).
   - `MessageRepository`: Restricts roles to `'user'` and `'keystone'`.
   - `AssetRepository`: Validates `mime_type`, `byte_size > 0`, and `storage_key` (`INVALID_ASSET_PARAMS`), scopes to `owner_id == self.tenant_id`, provides soft deletion.
   - `JobRepository`: Scopes queries to `user_id == self.tenant_id`, manages state updates.
   - `ApiKeyRepository`: Stores only SHA-256 `key_hash`.

4. **Cryptographic Authentication & Tenant Isolation (`apps/api/src/auth/`)**:
   - `security.py`:
     - PBKDF2-HMAC-SHA256 password hashing with 600,000 iterations (OWASP benchmark) and constant-time verification.
     - Stateless Bearer JWT tokens (`generate_token`, `verify_token`): Raises `MALFORMED_TOKEN` when dot is missing, `INVALID_SIGNATURE` on altered signature, `TOKEN_EXPIRED` when `exp < now()`.
     - SHA-256 API key hashing (`hash_api_key`): Raises `INVALID_KEY` when empty or non-string.
     - Tenant isolation guard (`enforce_tenant_isolation`): Raises `TENANT_ACCESS_DENIED: Cross-tenant access is strictly prohibited` on mismatch.
     - Internal service token verification (`verify_service_token`): Checks `keystone-internal-worker-secret`.
   - `dependencies.py`: FastAPI dependencies `get_current_user`, `get_current_tenant_id`, and `require_service_token`.

5. **Asset Storage & Short-Expiry Signed URLs (`apps/api/src/storage/`)**:
   - Key generation (`generate_storage_key`): Sanitizes path traversal (`../../../etc/passwd.png` -> `passwd.png`), formatted as `tenants/{user_id}/assets/{asset_id}/{safe_filename}`.
   - Signed URLs (`generate_signed_url`): Default 900s (15 min). Maximum 3600s ceiling; raises `EXPIRY_EXCEEDED: Maximum signed URL expiry is 3600s` if exceeded, raises `INVALID_EXPIRY` if `<= 0`.
   - Signature validation (`validate_signed_url`): Raises `URL_EXPIRED` if expired; raises `INVALID_SIGNATURE` if signature altered.
   - Abstract `StorageProvider` with `LocalStorageProvider` and `GoogleCloudStorageProvider`.

6. **Lineage DAG Tracking (`apps/api/src/lineage/dag.py`)**:
   - Supports all 8 relationship types (`source`, `edit`, `variation`, `animation`, `upscale`, `reference`, `selected-final`, `intermediate`). Raises `INVALID_RELATIONSHIP_TYPE` if unsupported.
   - Self-referential protection: Raises `SELF_REFERENTIAL_LINEAGE: An asset cannot be its own parent`.
   - Cycle detection: Runs reachability check `has_path(child_id, parent_id)`; raises `CYCLE_DETECTED: Adding this relationship creates a directed cycle in lineage DAG`.
   - BFS graph traversal: `get_ancestors` (upstream) and `get_descendants` (downstream); returns `[]` for boundary nodes.

7. **Job State Machine Engine (`apps/api/src/jobs/state_machine.py`)**:
   - 13 discrete states: `CREATED`, `VALIDATING`, `PLANNING`, `AUTHORIZING`, `QUEUED`, `RUNNING`, `VALIDATING_OUTPUT`, `RETRY_PENDING`, `REPLAN_REQUIRED`, `COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`.
   - 4 terminal states: `COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`.
   - Guards against terminal state exit: Raises `ILLEGAL_TRANSITION: Cannot transition out of terminal state <state>`.
   - Guards against illegal jumps: Raises `ILLEGAL_TRANSITION: Transition from <state1> to <state2> is not permitted`.
   - Idempotent transitions: `transition(s, s) == s`.
   - Supports retry loop (`VALIDATING_OUTPUT` -> `RETRY_PENDING` -> `QUEUED`) and replan loop (`VALIDATING_OUTPUT` -> `REPLAN_REQUIRED` -> `PLANNING`).

8. **Additive Routers & Server Integration (`apps/api/src/routers/`, `apps/api/src/server.py`)**:
   - `auth_router` mounted under `/v1/auth`.
   - `projects_router` mounted under `/v1/projects`.
   - `sessions_router` mounted under `/v1/sessions`.
   - `assets_router` mounted under `/v1/assets`.
   - `jobs_router` mounted under `/v1/jobs`.
   - Baseline files (`apps/api/src/main.py`, `intelligence_router.py`, `KEYSTONE_BIBLE.md`) remained 100% byte-identical.

9. **Verification Command Outputs**:
   - `npm test`: 3/3 passed.
   - `node tests/e2e/runner.js`: 132/132 passed.
   - `python scripts/verify_invariants.py --require-docs-bible`: 100% invariants satisfied (69/69 prebuilt files byte-identical).
   - `pytest tests/e2e_v2/test_m1_core_shell.py`: 23/23 passed.
   - `node tests/e2e_v2/runner.js`: 373/373 passed.

---

## 2. Logic Chain

1. **Step 1 — Foundation (F05)**: From Observation 1 & 2, modern SQLAlchemy 2.0 ORM mappings with `UniversalUUID` provide transparent compatibility across SQLite (development/testing) and PostgreSQL (production). This allowed the 23-table schema to be created and queried without requiring external database services.
2. **Step 2 — Tenant Scoping (F05 & F06)**: From Observation 3 & 4, injecting `tenant_id` into repository constructors guarantees that queries cannot access or mutate cross-tenant records. Attempting cross-tenant access returns 404 or raises `TENANT_ACCESS_DENIED`, satisfying the strict isolation mandate.
3. **Step 3 — Security & Hashing (F06)**: From Observation 4, implementing PBKDF2 (600,000 rounds) and HMAC-SHA256 Bearer tokens entirely through Python's standard library eliminated any dependency on uninstalled C-extension libraries (`passlib`, `bcrypt`, `pyjwt`), providing high performance and zero configuration risk on Windows.
4. **Step 4 — Asset Binary Storage & URL Signing (F07)**: From Observation 5, applying `path.basename` and regex substitution `[^a-zA-Z0-9._-]` completely neutralizes directory traversal exploits (e.g. `../../../etc/passwd.png` becomes `passwd.png`). The HMAC-SHA256 signed URL engine enforces an immutable 3600-second maximum expiry and validates integrity with constant-time signature comparison.
5. **Step 5 — Graph Invariant Enforcement (F08)**: From Observation 6, lineage tracking requires an acyclic graph. Testing directed reachability from `child_id` to `parent_id` prior to writing an edge guarantees that directed cycles can never enter `asset_relationships`.
6. **Step 6 — Deterministic State Coordination (F09)**: From Observation 7, the 13-state transition matrix prevents illegal lifecycle skipping, locks terminal states (`COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`), and handles quality retries and replans cleanly.
7. **Step 7 — Wave 1 Vertical Shell Integration**: From Observation 8 & 9, mounting all 5 domain routers onto `app` in `apps/api/src/server.py` enabled the full 10-step Wave 1 E2E flow (registration, project, session, asset upload, message, job creation, transitions, asset output, lineage link, and state recovery) to pass with 100% green verification.

---

## 3. Caveats

- **No Caveats**: All 5 assigned feature sets (F05–F09), router mountings, and the comprehensive test suite have been built cleanly from scratch and verified across all test runners. No shortcuts, facades, or mocks were substituted. All baseline invariants and pre-built files remain 100% intact.

---

## 4. Conclusion

Milestone M1 (Wave 1: Creative Tool Fabric & Core Shell) is fully implemented, verified, and ready for deployment. The database layer models all 23 tables, repositories enforce tenant isolation, the cryptographic authentication layer secures tokens and keys, the asset storage service signs short-expiry URLs with path-traversal protection, the lineage DAG prevents cycles across 8 relationship types, and the job engine orchestrates transitions deterministically across 13 states.

---

## 5. Verification Method

To independently reproduce and verify this entire milestone:

1. **Verify Baseline Identity Preservation**:
   ```powershell
   npm test
   # Expected: 3 passed
   ```

2. **Verify Pre-Built Invariants & File Manifest (69 Files)**:
   ```powershell
   python scripts/verify_invariants.py --require-docs-bible
   # Expected: Overall Status: [PASS] 100% INVARIANTS SATISFIED
   ```

3. **Verify Milestone M1 Core Shell Test Suite (23 Tests)**:
   ```powershell
   pytest tests/e2e_v2/test_m1_core_shell.py -v
   # Expected: 23 passed in ~7s
   ```

4. **Verify Run 1 E2E Test Suite (132 Tests)**:
   ```powershell
   node tests/e2e/runner.js
   # Expected: 132 passed across Tiers 1-4
   ```

5. **Verify E2E V2 Full Test Suite (373 Tests)**:
   ```powershell
   node tests/e2e_v2/runner.js
   # Expected: 373 passed across Tiers 1-4
   ```
