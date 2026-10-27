# Handoff Report: Milestone M1 (Wave 1: Vertical Shell) Blueprint

**Agent ID:** explorer_m1_1  
**Role:** teamwork_preview_explorer  
**Parent:** Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Working Directory:** `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1`  
**Handoff Type:** Hard (Task Complete)  

---

## 1. Observation

1. **Canonical Invariants & Requirements in `KEYSTONE_BIBLE.md`**:
   - §19 (Lines 776–792): Mandates 13 discrete job states: `CREATED`, `VALIDATING`, `PLANNING`, `AUTHORIZING`, `QUEUED`, `RUNNING`, `VALIDATING_OUTPUT`, `RETRY_PENDING`, `REPLAN_REQUIRED`, `COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`.
   - §21 (Lines 905–950): Mandates 23 database tables: `users`, `subscriptions`, `api_keys`, `projects`, `sessions`, `messages`, `assets`, `requests`, `request_assets`, `cognitive_runs`, `authority_decisions`, `jobs`, `generation_attempts`, `compiled_prompts`, `attempt_assets`, `harness_runs`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `audit_events`, `configuration_bundles`, `asset_relationships`.
   - §21 (Lines 954–960): Enforces UUID primary keys, `TIMESTAMPTZ` timestamps, immutable credit ledger, raw API keys never stored (hashes only), media binaries kept in object storage, and tenant ownership checked on every query.
   - §22 (Lines 966–985): Mandates 8 canonical asset relationship types: `source`, `edit`, `variation`, `animation`, `upscale`, `reference`, `selected-final`, and `intermediate`.
   - §27 (Lines 1187–1198): Requires PBKDF2 password hashing, short-lived tokens, API keys stored as hashes, and transactional credit account initialization.
   - §28 (Lines 1214–1224): Requires tenant isolation, storage-key scoping, signed URLs with short expiration (15 minutes), and directory traversal defenses.
   - §33 (Lines 1457–1470): Specifies the 10-step Wave 1 Vertical Shell build order.

2. **Database Migrations Status**:
   - `infrastructure/migrations/versions/0001_core.sql` defines the first 12 base tables (`users`, `projects`, `sessions`, `messages`, `assets`, `requests`, `cognitive_runs`, `authority_decisions`, `jobs`, `compiled_prompts`, `harness_runs`, `audit_events`).
   - `infrastructure/migrations/versions/0002_keystone_full_schema.sql` additively creates the remaining 11 tables (`subscriptions`, `api_keys`, `credit_accounts`, `credit_ledger`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `usage_records`, `configuration_bundles`, `asset_relationships`) plus indexes and immutability triggers.

3. **Current API Server Architecture**:
   - `apps/api/src/server.py`: Additively mounts `auth_router`, `projects_router`, `sessions_router`, `assets_router`, `jobs_router`, and `planning_router` onto the baseline `app` while leaving `apps/api/src/main.py` 100% byte-identical.
   - Existing modules currently exist under `apps/api/src/db/`, `apps/api/src/repositories/`, `apps/api/src/auth/`, `apps/api/src/storage/`, `apps/api/src/lineage/`, and `apps/api/src/jobs/`.

4. **Empirical Verification Results**:
   - Executed: `python -m pytest tests/e2e_v2/test_m1_core_shell.py`
     Result: `23 passed, 2 warnings in 8.25s` (Exit code 0).
   - Executed: `python -m pytest tests/e2e_v2/test_m1_challenger_adversarial.py tests/e2e_v2/test_m1_retest_vulnerabilities.py`
     Result: `48 passed, 2 warnings in 52.03s` (Exit code 0).
   - Total M1 test suite: 71/71 tests passing with zero failures.

---

## 2. Logic Chain

1. **Step 1: Invariant & Specification Alignment**:
   - By cross-referencing Bible §19, §21, §22, §27, §28, and §33 against `ORIGINAL_REQUEST.md` and `PROJECT.md`, the five core capability features for Milestone M1 (F05 Relational Data Models & Repositories, F06 Authentication & Tenant Isolation, F07 Asset Storage & Signed URLs, F08 Lineage DAG Tracking, F09 Job State Machine Engine) have exact, deterministic constraints that must be preserved.

2. **Step 2: Clean Monorepo Modularization vs. Non-Regression**:
   - The project architectural blueprint defines modular packages (`packages/database`, `packages/security`, `services/assets`, `services/jobs`).
   - Meanwhile, pre-existing tests in `tests/e2e_v2/` import from `apps.api.src.db`, `apps.api.src.repositories`, etc.
   - To achieve both clean architectural modularity AND 100% non-regression, the blueprint establishes a unified re-export bridge pattern: `apps/api/src/db`, `apps/api/src/repositories`, etc., cleanly import and re-export from `packages/database`, `packages/security`, `services/assets`, and `services/jobs`. This ensures any consumer or worker container can import from the standalone packages, while existing test harnesses continue running without breakage.

3. **Step 3: Security & Adversarial Defense Rigor**:
   - Empirical adversary testing confirmed 5 critical vulnerability vectors that the architecture must continue strictly guarding:
     a) LocalStorageProvider must reject sibling traversal outside `base_dir` using `target.relative_to(base_dir)` (raising `ILLEGAL_STORAGE_PATH`).
     b) Filenames must sanitize `..`, `\`, and null bytes, falling back to `asset.bin` for dot-only filenames.
     c) Caller-supplied `storage_key` values in `POST /v1/assets` must match `^tenants/{caller_tenant_id}/assets/{asset_id}/{safe_filename}$` to prevent arbitrary tenant path injection.
     d) Lineage relationship creation must verify that the `child_asset_id` belongs to the calling tenant (returning HTTP 404 rather than permitting cross-tenant linkage).
     e) PBKDF2 must maintain 600,000 iterations with constant-time `secrets.compare_digest`.

4. **Step 4: End-to-End Wave 1 Shell Feasibility**:
   - The 10-step vertical shell flow (`Register -> Create project -> Create session -> Upload asset -> Send message -> Create fake job -> Stream status -> Return persistent fake asset -> Display asset on canvas -> Refresh and recover state`) is verified end-to-end through the HTTP REST API, proving the system is ready for Wave 2 prompt engine integration.

---

## 3. Caveats

1. **SQLite vs PostgreSQL Concurrency**:
   - In local tests, `sqlite+aiosqlite` is used with `check_same_thread=False` and in-memory tables. In production Google Cloud Run with Cloud SQL PostgreSQL, connection pooling (`pool_size=20, max_overflow=10, pool_recycle=1800`) and the `asyncpg` driver must be configured via `DATABASE_URL`.
2. **Kaggle Ephemeral Tunnels**:
   - The job execution endpoints in M1 simulate worker progression via `POST /v1/jobs/{job_id}/transition`. Live worker envelope signing (HMAC-SHA256) and dynamic Kaggle worker tunnel discovery belong to Milestone M4.
3. **Credit Ledger Settlement**:
   - Welcome credits (100 credits) are automatically seeded upon user registration in `credit_accounts`. The transactional hold and settlement ledger engine (Bible §27) is scoped to Milestone M5.

---

## 4. Conclusion

The technical architecture and implementation blueprint for Milestone M1 (Wave 1: Vertical Shell) is fully completed, verified against existing empirical test harnesses (71/71 tests passing), and documented in `m1_vertical_shell_blueprint.md`.

The blueprint provides:
- Complete database connection manager and 23-table SQLAlchemy 2.0 ORM model specifications with cross-dialect `UniversalUUID`.
- Tenant-scoped repository interfaces enforcing soft-deletion filtering on all queries.
- PBKDF2-HMAC-SHA256 (600k work factor) authentication, stateless JWT tokens, SHA-256 API key hashing, and zero-trust tenant dependencies.
- Multi-tenant asset storage with path traversal sanitization and 15-minute HMAC-SHA256 signed URLs.
- Lineage DAG engine enforcing all 8 canonical relationship types, anti-self-parenting, cycle prevention, and ancestor/descendant graph traversal.
- Deterministic 13-state Job State Machine engine with terminal locks and bounded retry budgets.
- Additive REST API router definitions and server mounting strategy.
- Complete verification test suite blueprint for `tests/e2e_v2/test_m1_vertical_shell.py`.

---

## 5. Verification Method

To independently verify the architecture and existing test coverage:

1. **Run M1 Core Shell Test Suite**:
   ```powershell
   python -m pytest tests/e2e_v2/test_m1_core_shell.py -v
   ```
   *Expected outcome:* 23 passed in ~8 seconds.

2. **Run M1 Adversarial Challenger & Vulnerability Retest Suites**:
   ```powershell
   python -m pytest tests/e2e_v2/test_m1_challenger_adversarial.py tests/e2e_v2/test_m1_retest_vulnerabilities.py -v
   ```
   *Expected outcome:* 48 passed in ~52 seconds.

3. **Verify Baseline Tests & Invariant Integrity**:
   ```powershell
   npm test
   ```
   *Expected outcome:* 3 baseline identity tests pass.

4. **Verify Bible SHA-256 Checksum**:
   ```powershell
   python -c "import hashlib; print(hashlib.sha256(open('KEYSTONE_BIBLE.md', 'rb').read()).hexdigest().upper())"
   ```
   *Expected output:* `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`

5. **Inspect Blueprint Deliverables**:
   - Blueprint: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1\m1_vertical_shell_blueprint.md`
   - Handoff: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m1_1\handoff.md`
