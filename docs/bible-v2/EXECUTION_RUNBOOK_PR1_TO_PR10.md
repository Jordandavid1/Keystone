# KEYSTONE Bible v2 — End-to-End Execution Runbook (`PR1` → `PR10` + Phase D)

**Status:** Canonical step-by-step build blueprint for low-effort / mechanical orchestration (no open architectural decisions).  
**Authority:** `KEYSTONE_BIBLE.md` (v2, SHA-256 synced with `docs/KEYSTONE_BIBLE.md`), `docs/change_control/ADR_004_*`, `docs/change_control/ADR_005_*`, `docs/bible-v2/APPLICATION_PROTOCOL.md`, and `specs/{SPEC_GATE,SPEC_EVALUATORS,SPEC_MEMORY,UX_PARITY,DEPENDENCY_MANIFEST}.md`.  
**Starting Baseline Commit:** `517285d` (`Pre-PR1 Cleanup` complete; Phase 0 `O0–O17` + Pre-PR1 done; `alembic 1.20.1` already installed in `.venv`; 345/345 pytest green; 5/5 blocking checks in `scripts/verify_invariants.py` green).

---

## 0. Mandatory Executor Operating Rules (Read First — Apply to Every PR)

1. **Shell & Tooling Environment (Windows PowerShell 5.1):**
   - Chain commands with `;` (NEVER `&&` or `||`).
   - Python binary: `.venv\Scripts\python.exe` (NEVER system `python`).
   - Alembic CLI: `.venv\Scripts\alembic.exe` (`1.20.1` already installed).
   - Node tests (root): `npm test` (runs `tests/identity.test.js` — must remain 3/3 pass).
   - Next.js typecheck: `Set-Location apps\web; npx tsc --noEmit`.
2. **Hard Invariants (NEVER Violate):**
   - **One PR = One Atomic Commit** citing `PR# (ADR-005): ...` (PR3 may split into `PR3a` and `PR3b`). Never mix changes from later PRs into an earlier PR.
   - **Never modify `KEYSTONE_BIBLE.md` without identically updating `docs/KEYSTONE_BIBLE.md`** (`bible_sync` is BLOCKING).
   - **Never edit or delete historical `infrastructure/migrations/versions/0001_core.sql` or `0002_keystone_full_schema.sql`** (`tests/e2e_v2/test_m0_challenger_adversarial.py:29-73` asserts their union equals 23 tables). All new Alembic files live under `infrastructure/migrations/alembic/`.
   - **Never commit `.env*`, `keystone.db`, `*.zip`, or real credentials.** Check `git status --short` before every `git commit`.
   - **Never use mock-oracle tests or hardcoded PASS dicts** (Bible v2 §2 Invariant 12). Every PR adds real FastAPI/DB/module tests under `tests/test_pr#_*.py`.
   - **No banned placeholder strings** (e.g. `TODO`, `placeholder`, `mock_data`, `lorem ipsum`, `sample_image` in runtime files) — enforced as BLOCKING by `scripts/verify_invariants.py` (`banned_strings`).
   - **Browser default rule (global user rule):** If any browser verification is performed, always target **Microsoft Edge** (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`), never Chrome.
3. **Structural Lint Promotion Schedule (`scripts/verify_invariants.py` → `BLOCKING_CHECKS`):**
   | Check Name | Current Mode | Flips to BLOCKING In | Condition Before Flipping |
   |---|---|---|---|
   | `bible_sync` | BLOCKING | `O2` (done) | Both Bible copies byte-identical |
   | `license_policy` | BLOCKING | `O17` (done) | Proprietary notice in `LICENSE` & `package.json` |
   | `banned_strings` | BLOCKING | `O0.5` (done) | Zero placeholders/mocks in live code |
   | `change_control` | BLOCKING | `O0.5` (done) | All ADRs have 7 numbered §37 headings |
   | `npm_test_identity` | BLOCKING | `O0.5` (done) | `npm test` 3/3 pass |
   | `no_duplicate_engines` | advisory | **PR6** (sub-checks cleared in PR4 & PR6) | 1 Python compiler + 1 Comfy client (PR4) + legacy SPA retired (PR6) |
   | `manifest_accounting` | advisory | **PR8** | Local Qwen-embedding registered in `CapabilityManifest` + zero closed vendors |
   | `--strict` (all 7 checks) | Phase D | **PR10** | Zero blocking AND zero advisory warnings |
4. **Owner Operational Action (Out-of-Band From Code PRs — Do NOT Automate Without Owner):**
   - Historical git commits `419740e` and `6218d7a` contain an exposed `sk-atomic-*` key (untracked `.agents/teamwork/ORIGINAL_REQUEST.md` is already redacted and `.env` bundling is already stripped from `keystone-desktop.spec`).
   - Owner operational order: `(1) generate new key at provider -> (2) update local .env -> (3) verify live service -> (4) revoke old key at provider -> (5) rebuild desktop exe without .env`.
5. **Standard End-of-PR Verification Gate (Run Before Every Commit):**
   ```powershell
   .venv\Scripts\python.exe scripts/verify_invariants.py
   .venv\Scripts\python.exe -m pytest tests/test_pr<N>_*.py -v
   .venv\Scripts\python.exe -m pytest -q
   git status --short
   ```

---

## PR1 — Alembic Setup & 27-Table Bible v2 Schema + ORM Sync

**Goal:** Establish Alembic as sole schema migration engine supporting PostgreSQL (`+pgvector`) and SQLite dev/test, synchronize all 27 Bible v2 §21 tables in both Alembic revisions and SQLAlchemy 2.0 ORM, and verify upgrade/downgrade/round-trip + Postgres SQL generation.

**STRICT DO-NOT-TOUCH LIST (PR1):**
- Do NOT edit `infrastructure/migrations/versions/0001_core.sql` or `0002_keystone_full_schema.sql`.
- Do NOT edit `apps/api/src/lineage/dag.py` (`test_m1_core_shell.py:362` asserts `len(VALID_RELATIONSHIPS) == 8` until PR6).
- Do NOT edit any router or service logic (purely DB/Alembic/ORM/tests).

### Exact Files to Create / Edit
1. **CREATE `alembic.ini`** (repo root):
   - `script_location = infrastructure/migrations/alembic`
   - `prepend_sys_path = .`
   - `sqlalchemy.url = sqlite:///./keystone.db` (overridden by `DATABASE_URL` env in `env.py`)
2. **CREATE `infrastructure/migrations/alembic/script.py.mako`**: standard Alembic revision template.
3. **CREATE `infrastructure/migrations/alembic/env.py`**:
   - Import `Base` from `apps.api.src.db.models` (`target_metadata = Base.metadata`).
   - Read URL from `os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")`.
   - Normalize async drivers for sync Alembic: replace `postgresql+asyncpg://` → `postgresql://` and `sqlite+aiosqlite:///` → `sqlite:///`.
   - Support offline mode (`--sql`, used to verify PostgreSQL DDL without a live Postgres server) with `literal_binds=True`, `dialect_opts={"paramstyle": "named"}`, and `render_as_batch=(dialect == "sqlite")`.
   - Support online mode with `render_as_batch=(connection.dialect.name == "sqlite")`.
4. **CREATE `infrastructure/migrations/alembic/versions/0001_baseline_v1_23_tables.py`**:
   - `revision = "0001_baseline_v1_23_tables"`, `down_revision = None`.
   - Creates all 23 v1 baseline tables matching `0001_core.sql` + `0002_keystone_full_schema.sql` cross-dialect (`UUID`/`CHAR(36)`, `JSONB`/`JSON`, `TIMESTAMPTZ`/`DATETIME`):
     `users`, `projects`, `sessions`, `messages`, `assets`, `requests`, `cognitive_runs`, `authority_decisions`, `jobs`, `compiled_prompts`, `harness_runs`, `audit_events`, `subscriptions`, `api_keys`, `credit_accounts`, `credit_ledger`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `usage_records`, `configuration_bundles`, `asset_relationships`.
   - On PostgreSQL (`bind.dialect.name == "postgresql"`): run `CREATE EXTENSION IF NOT EXISTS pgcrypto;`, create `keystone_set_updated_at()` and `keystone_credit_ledger_prevent_modification()` functions + triggers (`trg_subscriptions_updated_at`, `trg_api_keys_updated_at`, `trg_credit_accounts_updated_at`, `trg_configuration_bundles_updated_at`, `trg_credit_ledger_immutable`).
   - On SQLite: create `BEFORE UPDATE` and `BEFORE DELETE` triggers on `credit_ledger` (`SELECT RAISE(ABORT, 'credit_ledger is strictly append-only');`).
   - Full `downgrade()` dropping triggers/functions and all 23 tables in reverse FK order.
5. **CREATE `infrastructure/migrations/alembic/versions/0002_bible_v2_schema_expansion.py`**:
   - `revision = "0002_bible_v2_schema_expansion"`, `down_revision = "0001_baseline_v1_23_tables"`.
   - `EMBEDDING_DIM = int(os.getenv("KEYSTONE_EMBEDDING_DIM", "1024"))` (local Qwen-embedding Matryoshka default).
   - On PostgreSQL: `CREATE EXTENSION IF NOT EXISTS vector;`.
   - **Table 24 — `personas` (missing from v1 SQL; Bible v2 §41):**
     - Columns: `id` PK, `owner_id` FK `users(id)` CASCADE NOT NULL, `project_id` FK `projects(id)` SET NULL, `parent_persona_id` FK `personas(id)` SET NULL, `name` VARCHAR(128) NOT NULL, `description` TEXT, `avatar_asset_id` FK `assets(id)` SET NULL, `reference_assets` JSON/JSONB NOT NULL default `'[]'`, `identity_adapter` VARCHAR(32) NOT NULL default `'reference-set'` CHECK IN `('ip','reference-set')`, `voice_provider` VARCHAR(32) default `'elevenlabs'`, `voice_id` VARCHAR(128), `voice_name` VARCHAR(128), `voice_settings` JSON/JSONB NOT NULL default `'{}'`, `personality_traits` JSON/JSONB NOT NULL default `'[]'`, `system_prompt` TEXT, `version` INTEGER NOT NULL default `1` CHECK `version >= 1`, `mature` BOOLEAN NOT NULL default `false`, `metadata` JSON/JSONB NOT NULL default `'{}'`, `created_at` TIMESTAMPTZ NOT NULL default now(), `updated_at` TIMESTAMPTZ NOT NULL default now(), `deleted_at` TIMESTAMPTZ NULL.
     - Indexes: `idx_personas_owner_id`, `idx_personas_project_id`, `idx_personas_owner_mature(owner_id, mature)`, `idx_personas_deleted_at`.
   - **Alter existing v1 tables (use `op.batch_alter_table(...)` so SQLite works cleanly; on SQLite drop & recreate `credit_ledger` immutability triggers around batch alter if needed):**
     - `users`: add `role` VARCHAR(32) NOT NULL default `'user'` CHECK IN `('user','admin','operator')`, `content_mode` VARCHAR(16) NOT NULL default `'sfw'` CHECK IN `('sfw','unrestricted')`, `age_verified` BOOLEAN NOT NULL default `false`, `age_verified_at` TIMESTAMPTZ NULL, `age_verification_method` VARCHAR(64) NULL; indexes `idx_users_role`, `idx_users_content_mode`.
     - `projects`: add `deleted_at` TIMESTAMPTZ NULL (v1 gap fix!), `content_mode` VARCHAR(16) NULL CHECK `IS NULL OR IN ('sfw','unrestricted')`.
     - `sessions`: add `content_mode` VARCHAR(16) NULL CHECK `IS NULL OR IN ('sfw','unrestricted')`.
     - `messages`: replace `role` CHECK with `role IN ('user','keystone','assistant','system')`.
     - `assets`: add `mature` BOOLEAN NOT NULL default `false`, `c2pa_manifest` JSON/JSONB NULL; index `idx_assets_owner_mature(owner_id, mature)`.
     - `authority_decisions`: add `content_mode` VARCHAR(16) NOT NULL default `'sfw'` CHECK IN `('sfw','unrestricted')`, `age_verified` BOOLEAN NOT NULL default `false`, `floor_verdict` VARCHAR(16) NOT NULL default `'pass'` CHECK IN `('pass','fail','uncertain')`.
     - `generation_attempts`: add `resource_cost` JSON/JSONB NOT NULL default `'{}'`.
     - `credit_ledger`: add `processor` VARCHAR(32) NOT NULL default `'internal'` CHECK IN `('internal','stripe','adult_rail','crypto')`, `content_mode` VARCHAR(16) NOT NULL default `'sfw'` CHECK IN `('sfw','unrestricted')`; expand `reference_type` CHECK to include `'adult_rail_checkout'` & `'crypto_checkout'`; index `idx_credit_ledger_processor_mode(processor, content_mode)`. Re-verify `trg_credit_ledger_immutable` (Postgres) / SQLite triggers stay active!
     - `usage_records`: expand `unit` CHECK to add `'vram_minutes'` and `'eval_seconds'`.
     - `asset_relationships`: make `parent_asset_id` nullable; add `persona_id` FK `personas(id)` SET NULL, `persona_version` INTEGER NULL, `mature` BOOLEAN NOT NULL default `false`; expand `relationship_type` CHECK to add `'depicts'`; add CHECK `parent_asset_id IS NOT NULL OR (relationship_type = 'depicts' AND persona_id IS NOT NULL)`; index `idx_asset_relationships_persona_child(persona_id, child_asset_id)`.
   - **Table 25 — `recipes` (Bible v2 §42 / `SPEC_MEMORY.md`):**
     - `id` PK, `tenant_id` FK `users(id)` CASCADE NOT NULL, `project_id` FK `projects(id)` CASCADE NOT NULL, `persona_id` FK `personas(id)` SET NULL, `envelope` JSON/JSONB NOT NULL, `compiled_prompt` JSON/JSONB NOT NULL, `seed` BIGINT NOT NULL, `fabric_versions` JSON/JSONB NOT NULL default `'{}'`, `scores` JSON/JSONB NOT NULL default `'{}'`, `mode` VARCHAR(16) NOT NULL CHECK IN `('sfw','unrestricted')`, `vendor` BOOLEAN NOT NULL default `false`, `passing_runs` INTEGER NOT NULL default `0` CHECK `>= 0`, `promoted_at` TIMESTAMPTZ NULL, `created_at` TIMESTAMPTZ NOT NULL default now().
     - Indexes: `idx_recipes_tenant_project_mode(tenant_id, project_id, mode)`, `idx_recipes_persona_id(persona_id)`, `idx_recipes_promoted_at(promoted_at)`.
   - **Table 26 — `recipe_embeddings` (Bible v2 §42.3 / `SPEC_MEMORY.md`):**
     - `recipe_id` PK FK `recipes(id)` CASCADE, `embedding` (`VECTOR(1024)` on PostgreSQL via `PGVectorColumn`, `JSON` on SQLite) NOT NULL, `embedding_model` VARCHAR(128) NOT NULL default `'qwen-embedding-local'`, `created_at` TIMESTAMPTZ NOT NULL default now().
     - On PostgreSQL: `CREATE INDEX IF NOT EXISTS idx_recipe_embeddings_hnsw ON recipe_embeddings USING hnsw (embedding vector_cosine_ops);`.
   - **Table 27 — `style_rules` (Bible v2 §42.2 / `SPEC_MEMORY.md`):**
     - `id` PK, `tenant_id` FK `users(id)` CASCADE NOT NULL, `project_id` FK `projects(id)` CASCADE NOT NULL, `text` TEXT NOT NULL, `weight` FLOAT NOT NULL default `1.0`, `active` BOOLEAN NOT NULL default `true`, `created_at` TIMESTAMPTZ NOT NULL default now().
     - Index: `idx_style_rules_tenant_project_active(tenant_id, project_id, active)`.
   - Full `downgrade()` reversing every single table, column, constraint, and index cleanly back to `0001_baseline_v1_23_tables`.
6. **EDIT `apps/api/src/db/models.py`**:
   - Add `UniversalJSON` (PostgreSQL `JSONB` / SQLite `JSON`), `PGVectorColumn(UserDefinedType)` emitting `VECTOR(dim)`, `UniversalVector` (PostgreSQL string vector `"[...]"` / SQLite float list).
   - Synchronize all 27 ORM models (`User`, `Project`, `Session`, `Message`, `Asset`, `AuthorityDecision`, `GenerationAttempt`, `CreditLedger`, `UsageRecord`, `Persona`, `AssetRelationship`, plus new `Recipe`, `RecipeEmbedding`, `StyleRule`) with exact columns, server defaults, and check constraints above.
7. **EDIT `apps/api/src/db/__init__.py`**: export all 27 models (`Persona`, `Recipe`, `RecipeEmbedding`, `StyleRule` added) + `UniversalUUID`, `UniversalJSON`, `UniversalVector`.
8. **EDIT `apps/api/src/db/session.py`**:
   - Add SQLite `PRAGMA foreign_keys=ON` connect listener gated by `os.getenv("KEYSTONE_SQLITE_ENFORCE_FK", "0") == "1"` (keep default `"0"` in PR1 so legacy `test_m1_core_shell.py:549` calling `POST /v1/jobs` without `action` keeps passing until PR3; PR3 flips default to `"1"`).
   - Add helper `sync_legacy_sqlite_columns(sync_conn)` invoked inside `init_db()` ONLY for SQLite: inspects `PRAGMA table_info(<table>)` for any pre-Alembic local `keystone.db` and executes additive `ALTER TABLE ADD COLUMN` for missing v2 columns so existing local `keystone.db` files never throw `OperationalError: no such column`.
   - Add helper `run_alembic_upgrade(database_url: str, revision: str = "head")` wrapping `alembic.command.upgrade`.
9. **EDIT `requirements.txt`**: add `alembic==1.20.1` and `sqlalchemy==2.1.6` (keep existing 5 lines intact).

### Pre-Known Pitfalls (PR1)
- Existing local untracked `./keystone.db` may hold v1 tables without `users.role` / `users.content_mode`. `sync_legacy_sqlite_columns` in `init_db()` ensures existing tests (`test_m1_core_shell.py`) run cleanly without deleting local data.
- On SQLite, `batch_alter_table("credit_ledger")` recreates the table — re-create the SQLite `BEFORE UPDATE`/`BEFORE DELETE` immutability triggers right after `batch_alter_table` finishes in `0002_bible_v2_schema_expansion.py`!
- In `alembic --sql` offline mode for PostgreSQL, `op.get_bind().dialect.name` works cleanly — verify with `DATABASE_URL=postgresql://localhost/keystone .venv\Scripts\alembic.exe upgrade head --sql`.

### Required Test File: `tests/test_pr1_migrations.py`
1. `test_alembic_upgrade_head_creates_all_27_tables`: run `alembic upgrade head` on a fresh temp SQLite DB, assert `set(inspector.get_table_names()) - {"alembic_version"}` equals exact 27 §21 tables, verify all new columns on `users`, `projects`, `sessions`, `assets`, `authority_decisions`, `generation_attempts`, `credit_ledger`, `asset_relationships`, `personas`, `recipes`, `recipe_embeddings`, `style_rules`.
2. `test_orm_roundtrip_all_v2_entities_and_constraints`: enable `PRAGMA foreign_keys=ON`, insert & read back `User` (role/content_mode/age_verified), `Project` (deleted_at/content_mode), `Session` (content_mode), `Message` (`role="assistant"` & `role="system"`), `Asset` (mature/c2pa_manifest), `Persona` (version/reference_assets/identity_adapter/mature/deleted_at), `AssetRelationship` (`depicts` with `parent_asset_id=None`, `persona_id`, `persona_version`, `mature=True`), `CreditLedger` (`processor="adult_rail"`, `content_mode="unrestricted"`), `UsageRecord` (`unit="vram_minutes"`), `Recipe`, `RecipeEmbedding` (1024-dim float vector round-trip), `StyleRule`. Assert invalid `content_mode="invalid"` fails CHECK constraint; assert orphan FK fails FK constraint; assert `UPDATE`/`DELETE` on `credit_ledger` fails trigger!
3. `test_alembic_downgrade_and_reupgrade_roundtrip`: `upgrade head` → `downgrade 0001_baseline_v1_23_tables` (verify 23 tables remain & v2 tables dropped) → `downgrade base` (verify 0 tables remain) → `upgrade head` (verify 27 tables restored).
4. `test_postgres_offline_ddl_generation`: run `alembic upgrade head --sql` with `DATABASE_URL=postgresql://localhost/keystone` via subprocess; assert exit 0 and output contains `CREATE EXTENSION IF NOT EXISTS pgcrypto`, `CREATE EXTENSION IF NOT EXISTS vector`, `VECTOR(1024)`, `USING hnsw`, `JSONB`, `TIMESTAMPTZ`, `trg_credit_ledger_immutable`, and all 27 `CREATE TABLE` statements.

### Commit Message
`PR1 (ADR-005): Alembic harness, 27-table Bible v2 PostgreSQL+pgvector migrations, and SQLAlchemy ORM sync`

---

## PR2 — `ExecutionEnvelope` v2, Env-Held Secrets & Redis-Backed Nonce Replay Cache

**Goal:** Upgrade `ExecutionEnvelope` to v2 schema (embedding `content_mode`, `age_verified`, `floor_verdict`, `intent`, `playbook`, `envelope_version="2.0"`), delete every hardcoded secret default across the repo, and back nonce replay cache with Redis (with clean in-process TTL fallback when `REDIS_URL` is unset in local dev/unit tests).

**STRICT DO-NOT-TOUCH LIST (PR2):**
- Do NOT implement `gate.py` or route RBAC yet (that is PR3).
- Do NOT break existing `AuthorityEngine.evaluate` callers; keep backwards-compatible optional args with safe defaults (`content_mode="sfw"`, `age_verified=False`, `floor_verdict="pass"`).

### Exact Files to Create / Edit
1. **EDIT `packages/contracts/src/models.py`**:
   - Update `ExecutionEnvelope` model (lines ~260–315) to v2 per `specs/SPEC_GATE.md` §4:
     - Add fields: `envelope_version: Literal["2.0"] = "2.0"`, `intent: str = "generate"`, `playbook: Optional[str] = None`, `content_mode: Literal["sfw", "unrestricted"] = "sfw"`, `age_verified: bool = False`, `floor_verdict: Literal["pass", "fail", "uncertain"] = "pass"`.
   - Update `AuthorityDecision` to include optional `content_mode: Literal["sfw", "unrestricted"] = "sfw"`, `age_verified: bool = False`, `floor_verdict: Literal["pass", "fail", "uncertain"] = "pass"`.
   - Update `GenerationAttempt` to include `resource_cost: Dict[str, float] = Field(default_factory=dict)` (Bible v2 §16).
2. **EDIT `services/harness/src/envelope.py`**:
   - **DELETE** line 20 hardcoded default `"keystone_master_secret_2026_authority_key"`.
   - Implement `get_envelope_secret(override: Optional[str] = None) -> str`: reads `override` or `os.getenv("KEYSTONE_ENVELOPE_SECRET")`; if missing/empty, raise `RuntimeError("KEYSTONE_ENVELOPE_SECRET_MISSING: Must set KEYSTONE_ENVELOPE_SECRET in environment")` (in dev/pytest, explicitly set `KEYSTONE_ENVELOPE_SECRET` via fixture/env — never silently fall back to a hardcoded string!).
   - Replace `NonceReplayCache` with `RedisBackedNonceCache`: uses `redis.from_url(os.getenv("REDIS_URL"))` with `SET nx=True ex=ttl` atomic consume if `REDIS_URL` is configured (and `redis` package installed), falling back cleanly to thread-safe in-memory TTL dict when `REDIS_URL` is unset.
   - Update `EnvelopeEngine.create_envelope(...)` to accept `intent`, `playbook`, `content_mode`, `age_verified`, `floor_verdict`, include ALL v2 fields inside `payload_to_sign` before HMAC-SHA256 signing, and reject issuing an envelope if `floor_verdict != "pass"` or (`content_mode == "unrestricted"` and not `age_verified`).
   - Update `EnvelopeEngine.verify_envelope(..., expected_mode: Optional[str] = None)`:
     - Verify `envelope_version == "2.0"`.
     - Verify `floor_verdict == "pass"`.
     - If `content_mode == "unrestricted"`, verify `age_verified is True`.
     - If `expected_mode` is provided and `data.get("content_mode") != expected_mode`: raise `ValueError("ENVELOPE_MODE_MISMATCH: ...")` (prevents SFW envelope replayed on UNRESTRICTED path!).
     - Verify HMAC-SHA256 signature BEFORE consuming nonce (so forged requests cannot poison nonce cache; wait — keep replay check before signature OR check replay → verify signature → consume nonce!).
3. **EDIT `apps/api/src/auth/security.py`**:
   - **DELETE** line 20 hardcoded `INTERNAL_SERVICE_TOKEN = "keystone-internal-worker-secret"`.
   - Implement `get_service_token() -> Optional[str]` reading `os.getenv("KEYSTONE_INTERNAL_SERVICE_TOKEN")` dynamically at call time; `verify_service_token(token)` returns `False` if env var is unset/empty or mismatch (constant-time `secrets.compare_digest`).
   - Update `JWT_SECRET_KEY` resolution to read `os.getenv("KEYSTONE_SECRET_KEY")`; if unset in production (`KEYSTONE_ENV == "production"`), raise `RuntimeError`; in dev/test, generate ephemeral per-process secret cleanly without a static literal.
4. **EDIT `services/billing/src/stripe_client.py`** (or grep `DEFAULT_STRIPE_WEBHOOK_SECRET` across `services/billing/`):
   - Delete hardcoded webhook secret literal; read strictly from `os.getenv("STRIPE_WEBHOOK_SECRET")`.
5. **GREP & REMOVE** hardcoded `"keystone-live-key"` fallbacks in `apps/api/src/` & `services/` (replace with `os.getenv("OPENAI_API_KEY", "")`).
6. **UPDATE affected legacy unit test fixtures** (`tests/e2e_v2/test_m1_core_shell.py:279`, `test_m3_cognition_authority.py`, `test_m4_creative_fabric.py`, `tests/acceptance/test_bible_acceptance.py`, `tests/conftest.py`) so tests set `KEYSTONE_ENVELOPE_SECRET` and `KEYSTONE_INTERNAL_SERVICE_TOKEN` in `monkeypatch` / `os.environ` at test startup rather than relying on deleted hardcoded secrets!

### Required Test File: `tests/test_pr2_envelope_v2.py`
1. `test_missing_envelope_secret_fails_closed`: unset `KEYSTONE_ENVELOPE_SECRET`, assert `create_envelope` and `verify_envelope` raise `RuntimeError("KEYSTONE_ENVELOPE_SECRET_MISSING")`.
2. `test_envelope_v2_sign_and_verify_roundtrip`: valid SFW and age-verified UNRESTRICTED envelopes sign & verify cleanly.
3. `test_unverified_unrestricted_or_failed_floor_cannot_sign`: `content_mode="unrestricted", age_verified=False` raises `ValueError`; `floor_verdict="fail"` raises `ValueError`.
4. `test_tampered_content_mode_rejected`: sign SFW envelope, mutate `content_mode` to `"unrestricted"` → `INVALID_SIGNATURE`.
5. `test_sfw_envelope_on_unrestricted_path_rejected`: sign valid SFW envelope, call `verify_envelope(env, expected_mode="unrestricted")` → `ENVELOPE_MODE_MISMATCH`.
6. `test_replay_and_expiry_rejected`: verify once succeeds; second verify raises `REPLAY_ATTACK_DETECTED`; expired timestamp raises `ENVELOPE_EXPIRED`.
7. `test_service_token_env_only`: unset `KEYSTONE_INTERNAL_SERVICE_TOKEN` → `verify_service_token("keystone-internal-worker-secret")` returns `False`; set env var → matching token returns `True`.

### Commit Message
`PR2 (ADR-005): ExecutionEnvelope v2, env-held secrets, and Redis-backed nonce replay cache`

---

## PR3 — The Gate, Stage-1 Age Verification, Tier-A Floor & P0/P1 Security Wall

*(May be committed as **PR3a** Security Wall + **PR3b** Gate & Stage-1 Age Verification, or single clean PR3 commit.)*

**Goal:** Eliminate every P0/P1 security vulnerability from `KEYSTONE_CODEBASE_AUDIT.md §4`, implement the single authoritative Gate (`apps/api/src/services/gate.py`), add Stage-1 age verification & content-mode endpoints (`POST /v1/account/age-verification`, `PATCH /v1/account/content-mode`), persist `authority_decisions` and `audit_events` to DB (never process RAM), and enforce `envelope=null -> 400` on execution routes.

### Exact Files to Create / Edit

#### Part PR3a — Security Wall (Closes ALL P0/P1 Exploits)
1. **EDIT `apps/api/src/auth/dependencies.py`**:
   - Add `require_admin(current_user: User = Depends(get_current_user)) -> User`: raises HTTP `403` unless `current_user.role == "admin"`.
   - Harden `dev_bypass_applies(...)`: **disable unconditionally** if `os.getenv("KEYSTONE_ENV", "development").lower() == "production"`; require BOTH socket client AND `X-Forwarded-For` (and reject if proxied without explicit trusted header).
2. **EDIT `apps/web/lib/backendProxy.ts` (lines 24–36)**:
   - Always forward real client IP in `X-Forwarded-For` header when proxying to FastAPI so remote traffic through `:3000` can NEVER spoof loopback!
3. **EDIT `apps/api/src/routers/admin.py`**:
   - Attach `dependencies=[Depends(require_admin)]` to the entire router!
   - Update admin audit/decisions reads to query real DB `AuditEvent` and `AuthorityDecision` tables (not process-RAM lists).
4. **EDIT `apps/api/src/routers/workers.py`**:
   - Attach `dependencies=[Depends(require_service_token)]` to ALL `/internal/workers/*` and `/internal/jobs/*` endpoints!
   - Fix `services/harness/src/kaggle_daemon.py:199-200` (`ComfyUIClient` instantiation & `system_stats()` method name).
5. **EDIT `apps/api/src/routers/creative.py`**:
   - Line 74 (`POST /v1/creative/execute`): **REQUIRE** `request.envelope` — if `request.envelope is None`, immediately raise HTTP `400` (`MISSING_ENVELOPE: ExecutionEnvelope v2 is required`)! Also require authenticated caller or service token, and call `EnvelopeEngine.verify_envelope(request.envelope, expected_mode=...)`.
   - Line 208 (`POST /v1/creative/comfy/configure`): attach `Depends(require_admin)`, sanitize all values against `\r`/`\n` (reject newline injection with HTTP `400`), validate URL scheme (`http`/`https`) + SSRF blocklist (reject `169.254.169.254`, metadata IPs, private RFC1918 unless explicitly allowlisted via `KEYSTONE_ALLOW_PRIVATE_WORKERS=1`).
6. **EDIT `apps/api/src/routers/audio.py` (lines 63–88)**:
   - Attach `Depends(require_admin)` to `/configure` and reject `\r`/`\n` injection before writing `.env`.
7. **EDIT `apps/api/src/routers/authority.py`**:
   - Lock `POST /v1/authority/envelope/issue` with `require_admin` OR `require_service_token` (never a public signing oracle!).
   - Require authentication (`Depends(get_current_user)`) on `/evaluate` and `/verify`.
8. **EDIT `apps/api/src/server.py`**:
   - Lock `/v1/config/remote` (`POST`/`PUT`) with `Depends(require_admin)` (lines 304–327).
   - Fix CORS (lines 334–340): replace `allow_origins=["*"]` with explicit allowlist from `os.getenv("KEYSTONE_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000").split(",")`.
   - Do NOT mount raw `apps/web/` root over `/workspace` exposing `package.json`/`.next`/`node_modules` (serve only explicit static build or redirect to Next.js Studio).
9. **Close ALL 4 Cross-Tenant IDORs + SSRF + Stored XSS + MIME Sniffing:**
   - `apps/api/src/routers/zencreator.py` (lines 160–173): require `get_current_user` and filter `Asset` lookup by `Asset.owner_id == tenant_id` and `Asset.deleted_at.is_(None)`.
   - `apps/api/src/routers/personas.py` (lines 100, 150, 174, 223): filter `Asset` lookup by `Asset.owner_id == tenant_id` AND `Asset.deleted_at.is_(None)` before minting avatar signed URL!
   - `apps/api/src/routers/cognition.py` (lines 485–501): verify `Session.user_id == tenant_id` before appending/reading messages; fix `live_url_scrape` (lines 111–149) with strict SSRF IP blocklist (`ipaddress.ip_address`: block loopback, private, link-local `169.254.0.0/16`, multicast, reserved, non-http/https schemes).
   - `apps/api/src/routers/billing.py` (lines 160–185): require `get_current_user`, enforce `account.user_id == tenant_id` (unless `admin`), remove unauthenticated self-topup.
   - `apps/api/src/routers/assets.py` (lines 730–737): enforce upload MIME allowlist (`image/png`, `image/jpeg`, `image/webp`, `video/mp4`, `video/webm`, `audio/mpeg`, `audio/wav`, `audio/ogg`), enforce max upload size (`KEYSTONE_MAX_UPLOAD_BYTES`, default 250MB), add `X-Content-Type-Options: nosniff` & `Content-Disposition: attachment` for non-safe types, never render uploaded `text/html` or `image/svg+xml` inline!
   - `apps/admin/index.html` (lines 596–623): replace unsafe `innerHTML` interpolations with `textContent` / DOM builders + add admin auth login gate sending `Authorization: Bearer <token>`.
   - `services/authority/src/evaluator.py` (lines 186–191) & `apps/api/src/routers/jobs.py` (lines 94–130): stop honoring caller-supplied `unlock_max_bounds=True` unless `user.role == "admin"`; remove auto-refill of 100,000 credits in `jobs.py:129`; flip `KEYSTONE_SQLITE_ENFORCE_FK` default to `"1"` after ensuring `jobs.py` always persists real `Request` + `AuthorityDecision` rows!

#### Part PR3b — The Gate (`apps/api/src/services/gate.py`), Tier-A Watchdog & Stage-1 Age Verification
1. **CREATE `services/harness/src/evaluators/__init__.py` & `services/harness/src/evaluators/deterministic.py`** (Tier-A per `specs/SPEC_EVALUATORS.md`):
   - `validate_asset_bytes(data: bytes, expected_media_type: str, expected_mime: str, source_dimensions: Optional[Tuple[int,int]] = None, require_upscale_delta: bool = False) -> HarnessResult`:
     - Images: inspect via `PIL.Image` (`verify()` + `load()`), check non-zero bytes, valid dimensions, and if `require_upscale_delta`, assert output width/height strictly exceeds source AND Laplacian sharpness delta check (rejects corrupted/empty/zero-delta fakes).
     - Videos: inspect via `ffprobe` (or header validation fallback if `ffprobe` absent in minimal CI), verify non-zero duration & valid container/streams.
     - Audio: verify non-empty valid WAV/MP3/OGG header.
2. **CREATE `apps/api/src/services/floor_watchdog.py`** (Non-configurable lawful-content floor per Bible v2 §40.5):
   - Local deterministic + optional local classifier (`Qwen-Guard`-class behind `CognitiveProvider` when configured) check at the Gate.
   - Non-configurable hard floor rules (CSAM/minors sexualization, non-consensual intimate imagery of real identifiable persons, actionable CBRN/terrorism/self-harm instructions, cyber-exploitation targeting critical infrastructure); configurable upward-only via `KEYSTONE_EXTRA_FLOOR_RULES` env; **never** flags lawful adult sexual content, consensual erotica, dark fiction, or graphic violence under `unrestricted` mode!
   - Returns `FloorVerdict(verdict="pass"|"fail"|"uncertain", reason_codes=[...], rule_version="1.0.0")`.
3. **CREATE `apps/api/src/services/gate.py`** (Exact 10-step flow per `specs/SPEC_GATE.md` §3):
   - `resolve_content_mode(user: User, project: Optional[Project], session: Optional[Session]) -> Literal["sfw", "unrestricted"]`: exact cascade `session.content_mode -> project.content_mode -> user.content_mode -> "sfw"`.
   - `GateService.authorize_and_sign(db, user, intent, prompt_text, capability_id, arguments, project=None, session=None, persona_id=None, input_asset_ids=None, playbook=None) -> GateReceipt`:
     1. Resolve `content_mode`.
     2. If `content_mode == "unrestricted"` and not `user.age_verified` → raise HTTP `403` (`AGE_VERIFICATION_REQUIRED`).
     3. If `persona_id` provided → verify `Persona.owner_id == user.id` and `deleted_at is None`; if `persona.mature` and `content_mode == "sfw"` → reject/hide (`MATURE_PERSONA_BLOCKED_IN_SFW`).
     4. Scope playbooks (1–13 in `sfw`, 1–16 in `unrestricted`; refuse 14–16 in `sfw` with HTTP `403`).
     5. Compile prompt via canonical PromptCompiler (embedding mode-aware system prompt template from `specs/SPEC_GATE.md` §5 for cognition routes).
     6. Run `floor_watchdog.evaluate(prompt_text, compiled_prompt, content_mode)`. On `fail` → persist `AuthorityDecision(decision="deny", floor_verdict="fail", ...)` + `AuditEvent(event_type="gate.floor_violation", ...)` in DB and raise HTTP `422` (`LAWFUL_CONTENT_FLOOR_VIOLATION`) with **zero** worker dispatch!
     7. Run `AuthorityEngine.evaluate(...)` → persist `Request`, `CompiledPrompt`, `AuthorityDecision`, and `AuditEvent` rows to PostgreSQL/SQLite DB (never RAM!). On `deny` → raise HTTP `403`/`400`.
     8. Sign `ExecutionEnvelope` v2 via `EnvelopeEngine.create_envelope(...)` embedding `content_mode`, `age_verified`, `floor_verdict="pass"`, `intent`, `playbook`.
     9. Return `GateReceipt(request_id, decision_id, compiled_prompt_id, job_id, envelope, content_mode, mature=(content_mode == "unrestricted"))`.
4. **CREATE `apps/api/src/routers/account.py`** (and mount in `apps/api/src/server.py`):
   - `GET /v1/account` — returns authenticated user profile (`id`, `email`, `display_name`, `role`, `content_mode`, `age_verified`, `age_verified_at`, `age_verification_method`).
   - `POST /v1/account/age-verification` — **Stage-1 age verification** (refined per user decision #1!): body `{ "confirmed_adult_18_plus": true, "method": "attestation" }`; requires `confirmed_adult_18_plus is True` (else HTTP `400`), writes `user.age_verified = True`, `user.age_verified_at = now(UTC)`, `user.age_verification_method = "attestation"` to DB + durable `AuditEvent(event_type="account.age_verified")`.
   - `PATCH /v1/account/content-mode` — body `{ "content_mode": "sfw" | "unrestricted", "project_id"?: str, "session_id"?: str }`: if setting `"unrestricted"` and not `user.age_verified` → HTTP `403` (`AGE_VERIFICATION_REQUIRED`); otherwise updates target (`session`, `project` owned by user, or `user`) and writes durable `AuditEvent`.
5. **EDIT `apps/api/src/routers/assets.py`**:
   - Filter `GET /v1/assets` by resolved content mode: under `sfw`, exclude `Asset.mature == True` unless caller explicitly resolved `unrestricted` (and `user.age_verified == True`).
   - Stamp `Asset.mature = gate_receipt.mature` on newly generated assets.
6. **WIRE Gate into `cognition.py`, `assets.py`, `zencreator.py`, `audio.py`, `jobs.py`**: every generation/cognition-execution route acquires a `GateReceipt` before dispatching any work.

### Required Test File: `tests/test_pr3_gate_and_security.py`
1. `test_age_unverified_cannot_set_or_invoke_unrestricted_403`: new user calls `PATCH /v1/account/content-mode {"content_mode": "unrestricted"}` → `403`.
2. `test_stage1_age_verification_enables_unrestricted_mode`: call `POST /v1/account/age-verification {"confirmed_adult_18_plus": true}` → `200`, DB `age_verified=True`, `age_verified_at` set, `AuditEvent` written; then `PATCH /v1/account/content-mode {"content_mode": "unrestricted"}` → `200`.
3. `test_mode_resolution_cascade`: verify `session > project > user > "sfw"` resolution order.
4. `test_floor_violation_returns_422_writes_db_audit_and_zero_dispatch`: floor-violation fixture → `422`, durable `authority_decisions` (`floor_verdict="fail"`) + `audit_events` rows in DB, worker mock asserts `call_count == 0`.
5. `test_lawful_unrestricted_passes_floor_and_signs_v2_envelope`: lawful adult/explicit fixture under age-verified `unrestricted` user → passes floor, compiles with `content_mode="unrestricted"`, signs valid Envelope v2.
6. `test_creative_execute_null_envelope_returns_400`: `POST /v1/creative/execute` with `envelope=None` → `400`.
7. `test_admin_worker_configure_auth_wall`: unauthenticated & non-admin user calling `/v1/admin/*`, `/v1/creative/comfy/configure`, `/v1/audio/configure`, `/v1/config/remote`, `/v1/authority/envelope/issue` → `401`/`403`; unauthenticated `/internal/workers/register` → `403`; newline injection on `/configure` → `400`.
8. `test_idor_ssrf_mime_and_mature_gallery_isolation`: cross-tenant `Persona` avatar/session/asset access → `404`/`403`; SSRF to `169.254.169.254` / `127.0.0.1` → blocked; `text/html` upload → rejected; `mature=True` asset excluded from SFW `GET /v1/assets` and visible in `unrestricted`.
9. `test_tier_a_deterministic_corrupt_binary_fails`: truncated PNG bytes fail `deterministic.py`.

### Commit Message
`PR3 (ADR-005): Single Gate service, Tier-A floor watchdog, Stage-1 age verification, and P0/P1 security wall`

---

## PR4 — Image Core Live Wiring, Bug Fixes & Compiler/Client Consolidation

**Goal:** Fix the image generation crash (`assets.py:478`), consolidate the 3 competing prompt engines into 1 authoritative Python compiler (`packages/prompt_engine/compiler.py`) and the 3 ComfyUI/H3 clients into 1 canonical fabric adapter (`services/comfy/src/client.py`), stage real ComfyUI image workflows (`create`, `edit`, `vary`, neural ESRGAN `upscale`), and eliminate HTTP 503 traps for all image tools in `zencreator.py`.

### Exact Files to Create / Edit / Delete
1. **FIX `apps/api/src/routers/assets.py`**:
   - Line 478: fix `AttributeError: 'GenerateAssetRequest' object has no attribute 'media_type'` → derive `media_type` cleanly from `intent` / `output_mime` (`"image"` vs `"video"`).
   - Line 409: do NOT override `DEFAULT_NEGATIVE_PROMPT` when `req.negative_prompt is None`.
   - Replace bicubic Pillow resize in `/v1/assets/upscale` with real neural ESRGAN ComfyUI workflow dispatch via Gate (reject bicubic fallback per Bible v2 §23.2!).
2. **CONSOLIDATE Prompt Compiler (One Python Compiler Rule — ADR-005):**
   - Enhance canonical `packages/prompt_engine/compiler.py` to absorb `H3PromptCompiler` (mode-scoped playbooks 1–13 SFW / 1–16 UNRESTRICTED, `PromptIntent` + `PromptAnatomy`, deterministic SHA-256 `prompt_hash`, `critique_rubric(mode)` stub ready for PR7, `memory_context` advisory block ready for PR8, persona sheet injection ready for PR6).
   - **DELETE** duplicate `apps/api/src/keystone/prompting.py` (including its incompatible raw-`sqlite3` `compiled_prompts` table!) and update all imports across `apps/api/src/` and `tests/` to import from `packages.prompt_engine.compiler`.
   - *(Keep `packages/prompt-engine/src/engine.js` strictly for the preserved `npm test` `plan.v1` JS identity contract — `verify_invariants.py:93` explicitly allows JS compat + 1 Python compiler.)*
3. **CONSOLIDATE ComfyUI / H3 Client (One Fabric Client Rule — ADR-005):**
   - Merge `apps/api/src/creative/h3.py` and `services/comfy/src/adapters.py` capability manifests into a single canonical `services/comfy/src/client.py` + `services/comfy/src/workflows/` directory (JSON workflow templates for `sdxl_create.json`, `sdxl_edit.json`, `sdxl_vary.json`, `esrgan_upscale.json`, plus existing MiniMax H3 workflow).
   - Require a verified `ExecutionEnvelope` v2 on `ComfyUIClient.execute_workflow(envelope, ...)` — worker/client verifies signature & mode before calling ComfyUI HTTP API!
   - **DELETE** duplicate `apps/api/src/creative/h3.py` and `services/comfy/src/adapters.py` (update imports in `routers/creative.py`, `routers/zencreator.py`, `routers/assets.py`, `scripts/verify_invariants.py:152-155` manifest path list).
4. **WIRE `apps/api/src/routers/zencreator.py`** image intents (`by_prompt` → `create`, `by_ref` → `create` with ref, `image_editor` → `edit`, `variation` → `vary`, `upscaler` → neural ESRGAN `upscale`):
   - Remove the unconditional `503 NO_ENGINE_CONFIGURED` blocks for image tools!
   - Route every tool through `GateService.authorize_and_sign` → `ComfyUIClient.execute_workflow` → `deterministic.py` Tier-A validation → persist `Asset` (with `project_id` and `mature`) + `GenerationAttempt` + `AttemptAsset` + `HarnessRun` + `AssetRelationship` lineage edge!
5. **FIX `services/cognition/src/client.py` & `apps/api/src/routers/cognition.py`**:
   - Convert blocking `urllib.request` calls to async `httpx.AsyncClient` (or `run_in_threadpool` cleanly) so cognition never blocks the FastAPI event loop.
   - Fix `apps/api/src/repositories/sessions.py:80` to allow `("user", "keystone", "assistant", "system")` matching PR1 migration so chat persistence stops failing!

### Required Test File: `tests/test_pr4_image_core_consolidation.py`
1. `test_single_python_compiler_and_mode_playbook_scoping`: verify `apps/api/src/keystone/prompting.py` is deleted; verify playbooks 14–16 rejected in `sfw` and allowed in `unrestricted`.
2. `test_single_comfy_client_rejects_unsigned_envelope`: verify `h3.py` and `adapters.py` consolidated; calling `execute_workflow` with missing/tampered envelope fails closed.
3. `test_image_create_edit_vary_upscale_through_gate_and_db`: hit FastAPI `/v1/assets/generate`, `/v1/assets/upscale`, and `/v1/zencreator/*` image routes against local mock ComfyUI HTTP server (`tests/fixtures/mock_comfy.py`); assert zero `AttributeError` at `assets.py:478`, HTTP 200, real `CompiledPrompt`, `AuthorityDecision`, `GenerationAttempt`, `Asset`, `AttemptAsset`, `HarnessRun`, and `AssetRelationship` rows written to DB, and neural upscale delta verified by `deterministic.py`!
4. `test_cognition_chat_persists_assistant_messages`: `POST /v1/cognition/chat` with `session_id` persists both `user` and `assistant` messages to `messages` table.

### Commit Message
`PR4 (ADR-005): Fix image-gen crash, consolidate compiler & ComfyUI client, wire live image workflows through Gate`

---

## PR5 — Full Video Suite (`t2v`/`i2v`/`ref2v`/`v2v`/`extend`/`video-upscale`) & Deterministic Grade Lane

**Goal:** Wire all remaining video & audio intents from Bible v2 §23.3 through the Gate, add `ffmpeg` last-frame extraction & segment stitching for `extend`, add the deterministic post-process grade lane (`exposure`, `contrast`, `saturation`, `warmth`) executed before neural ESRGAN upscale, replace Windows-only SAPI TTS fallback with POSIX-compatible local fallback, and add HTTP `Range` support for video playback.

### Exact Files to Create / Edit
1. **CREATE `services/comfy/src/workflows/` video templates**: `h3_t2v.json`, `h3_i2v.json`, `h3_ref2v.json`, `h3_v2v.json`, `video_esrgan_upscale.json`.
2. **CREATE `services/comfy/src/grade.py`** (Deterministic Grade Lane — Bible v2 §23.2):
   - Pure Pillow/NumPy deterministic image/frame grading function `apply_grade(image_bytes, exposure=0.0, contrast=1.0, saturation=1.0, warmth=0.0) -> bytes` (strictly clamped bounds, deterministic output hash, runs before neural ESRGAN upscale when grade params are non-neutral).
3. **CREATE `services/comfy/src/video_ops.py`**:
   - `extract_last_frame(video_path: Path) -> bytes` via `ffmpeg`.
   - `stitch_video_segments(segment_paths: List[Path], output_path: Path) -> Path` via `ffmpeg` concat demuxer (re-encoded to matching codec/fps/resolution).
   - `probe_video_metadata(video_path: Path) -> Dict[str, Any]` via `ffprobe` (duration, width, height, fps, codec).
4. **WIRE `apps/api/src/routers/zencreator.py` & `services/comfy/src/client.py`**:
   - Wire `text_to_video` (`t2v`), `image_to_video` (`i2v`), `ref2v` (`videogen`), `video2video` (`v2v` / `re-render`), `extend` (last-frame extract → `i2v` through Gate → `stitch_video_segments` → `AssetRelationship(relationship_type="animation")`), and `video_upscaler` (frame-wise neural ESRGAN upscale).
   - Honor `camera_motion`, `motion_speed`, `duration`, `aspect_ratio`, and Look grade parameters (`exposure`, `contrast`, `saturation`, `warmth`) inside compiled prompt + ComfyUI workflow graph!
5. **EDIT `apps/api/src/routers/assets.py`**:
   - Add proper HTTP `Range` (`206 Partial Content`, `Accept-Ranges: bytes`, `Content-Range`) support on `GET /v1/assets/{asset_id}/content` so video timeline seeking works in browsers.
6. **EDIT `services/audio/src/elevenlabs.py`**:
   - Replace Windows-only `powershell` SAPI subprocess fallback with POSIX-compatible fallback (`espeak-ng` / `piper` / pure-Python deterministic PCM WAV synthesis error or clean configured local TTS provider — never `powershell.exe` on Linux!).
7. **CREATE real async worker package `services/workers/src/worker.py`** (replacing empty `services/workers/`):
   - Redis-backed async job queue consumer (with in-process `asyncio.Queue` fallback when `REDIS_URL` is unset in local dev) that verifies `ExecutionEnvelope` v2 signature + mode before running any ComfyUI/video job, updates `Job` state machine transitions in DB, and persists job events (removing process-RAM `_JOB_EVENTS` and `generation_progress` dicts!).

### Required Test File: `tests/test_pr5_video_grade_workers.py`
1. `test_grade_lane_deterministic_and_runs_before_upscale`: apply non-zero exposure/contrast/saturation/warmth, assert pixel stats change deterministically and identical inputs produce identical SHA-256 bytes.
2. `test_video_variants_and_extend_chain_through_gate`: hit `t2v`, `i2v`, `ref2v`, `v2v`, `extend`, and `video_upscaler` with Gate + mock ComfyUI + synthetic MP4 fixture; verify `camera_motion`/`motion_speed` reach workflow params and lineage edges persist.
3. `test_asset_content_http_range_206`: request `Range: bytes=0-1023` on a persisted video asset → HTTP `206` with exact `Content-Range` and 1024 bytes.
4. `test_worker_refuses_unsigned_or_mode_mismatched_job`: push unsigned or SFW-on-UNRESTRICTED payload to worker → refused, job transitions to `REJECTED`, audit row written.

### Commit Message
`PR5 (ADR-005): Live video suite (t2v/i2v/ref2v/v2v/extend/upscale), grade lane, Range streaming, and envelope-verifying worker`

---

## PR6 — Cross-Modal Personas (§41), Full UX Parity (§25.9) & Legacy SPA Retirement

**Goal:** Make Personas first-class across chat/image/video/voice (`as: persona_id`, immutable versioning, `depicts` lineage, soft delete, `mature` inheritance), fix EVERY row in `specs/UX_PARITY.md` to `PORTED-WIRED`, retire the legacy HTML/JS SPA (`apps/web/index.html`, `apps/web/app.js`, `apps/web/styles.css`, `apps/web/legacy/`), and flip `no_duplicate_engines` in `scripts/verify_invariants.py` to **BLOCKING**!

### Exact Files to Create / Edit / Delete
1. **EDIT `apps/api/src/lineage/dag.py`**:
   - Add `"depicts"` to `VALID_RELATIONSHIPS` (9 total types per Bible v2 §22).
   - Add `persist_depicts_edge(child_asset_id, persona_id, persona_version, job_id, mature)` writing `AssetRelationship(parent_asset_id=None, child_asset_id=..., persona_id=..., persona_version=..., relationship_type="depicts", mature=...)`.
   - Update `tests/e2e_v2/test_m1_core_shell.py:362` from `== 8` to `== 9`.
2. **EDIT `apps/api/src/routers/personas.py`**:
   - Support full §41 fields on `POST /v1/personas`, `GET /v1/personas`, `GET /v1/personas/{id}`, `PATCH /v1/personas/{id}` (keep `PUT` alias if needed), `DELETE /v1/personas/{id}`:
     - Creation inherits `mature = (resolved_mode == "unrestricted")`, starts at `version = 1`, stores `reference_assets`, `identity_adapter`, `voice_provider`.
     - `PATCH` creates a **new immutable version** (`version + 1`, `parent_persona_id = old.id`) rather than mutating history in place (Bible v2 §41.5)!
     - `DELETE` performs **soft delete** (`deleted_at = now(UTC)`) so historical `depicts` lineage edges remain intact (§41.5).
     - `GET /v1/personas` excludes `deleted_at IS NOT NULL`, and under `sfw` mode excludes `mature == True` (§41.6).
     - `POST /v1/personas/{id}/speak` routes through Gate; if persona has no bound voice, returns compile-time warning header/field (§41.3).
3. **WIRE `as` (`persona_id`) Parameter Across All Intents (`gate.py`, `cognition.py`, `zencreator.py`, `assets.py`, `audio.py`):**
   - Accept optional `as` (alias `persona_id`) on chat/plan, image create/edit, video animate/v2v/extend, speak, and analyze.
   - Gate resolves persona, injects sheet into cognition prompt / descriptor tags + `reference_assets` into image/video conditioning, binds voice for `speak`, and writes `depicts(persona_id, persona.version)` edge with `mature` propagation on every generated asset!
4. **NEXT.JS STUDIO UX PARITY (`apps/web/**`) — Clear ALL 12 Rows of `specs/UX_PARITY.md`:**
   - `apps/web/components/Modals/PersonasModal.tsx:92-104`: fix response unwrap crash (`const created = res.persona ?? res;`), wire full CRUD + version display + voice bind + `as: persona_id` composer selector.
   - `apps/web/components/Composer/MotionPad.tsx`: send `camera_motion` & `motion_speed` to backend animate endpoints.
   - `apps/web/components/Inspector/RightInspector.tsx`: send Look sliders (`exposure`, `contrast`, `saturation`, `warmth`) to backend grade lane before upscale.
   - `apps/web/components/Modals/SettingsModal.tsx`: wire all 5 settings flags to real backend `/v1/account` / project preferences (`content_mode` toggle + Stage-1 18+ age-verification modal calling `POST /v1/account/age-verification` & `PATCH /v1/account/content-mode`, quality tier, eval budget, default seed, output prefs).
   - `apps/web/components/Modals/SessionsModal.tsx`: wire `onSelectSession` to load active session + persisted message history.
   - `apps/web/components/Canvas/StageFrame.tsx`: key by `asset.id`, reset broken image/video error state cleanly on asset switch, add retry button.
   - `apps/web/components/Canvas/AnalysisPane.tsx`: send selected `asset_id` to `POST /v1/cognition/analyze` (real multimodal Qwen-VL via Gate).
   - `apps/web/components/Modals/AgentChatModal.tsx`: send active `session_id`, render returned `created_assets`, citations, and errors inline, dispatch `ASSETS_ADDED` into canvas state.
   - `apps/web/lib/toolsCatalog.ts`: remove raw model-picker dropdowns (Bible v2 §25: customer UI exposes intents only, never raw model names!).
   - Persist `project_id` & display lineage DAG + mature badge/filter cleanly across browser refresh.
5. **RETIRE LEGACY SPA & FLIP STRUCTURAL LINT:**
   - Update `specs/UX_PARITY.md` marking every row `PORTED-WIRED` (or `OWNER-DROPPED` with reason).
   - **DELETE** `apps/web/index.html`, `apps/web/app.js`, `apps/web/styles.css`, and `apps/web/legacy/`.
   - Update `apps/desktop/launcher.py` to launch Next.js Studio URL (instead of deleted legacy HTML).
   - **EDIT `scripts/verify_invariants.py`**: add `"no_duplicate_engines"` to `BLOCKING_CHECKS`!

### Required Test File: `tests/test_pr6_personas_and_parity.py`
1. `test_persona_versioning_soft_delete_and_mature_isolation`: create persona under `unrestricted` (`mature=True, v=1`) → invisible in `sfw` `GET /v1/personas`; `PATCH` creates `v=2` leaving `v=1` immutable; `DELETE` sets `deleted_at` without breaking `depicts` edges.
2. `test_as_persona_cross_modal_and_depicts_lineage`: generate image/video with `as=persona_id` → persists `AssetRelationship(relationship_type="depicts", persona_id=..., persona_version=..., mature=...)`.
3. `test_nextjs_typecheck_and_legacy_spa_retired`: assert `apps/web/index.html` and `apps/web/legacy/` do not exist; run `npx tsc --noEmit` in `apps/web` (exit 0); verify `verify_invariants.py` passes with `no_duplicate_engines` BLOCKING!

### Commit Message
`PR6 (ADR-005): Cross-modal Personas, full UX Parity pass, legacy SPA retirement, and no_duplicate_engines blocking`

---

## PR7 — Tier-B Evaluator Tank (`services/harness/src/evaluators/`) & Bounded Retry Wiring

**Goal:** Replace the fake float-averaging stub in `services/harness/src/khf_quality.py` with the 5 real evaluator families per Bible v2 §13 & `specs/SPEC_EVALUATORS.md`, wire mode-aware VLM critique rubrics, persist every evaluation to `harness_runs` in DB, and connect `retry_loop.py` bounded retries + operator-review escalation.

### Exact Files to Create / Edit
1. **CREATE `services/harness/src/evaluators/ocr.py`**:
   - Extract rendered text from image bytes via local OCR (`pytesseract` / `easyocr` / lightweight fallback with clean error if binary missing; deterministic test hook for synthetic PIL-rendered text images) and compute normalized edit-distance fidelity against requested text strings.
2. **CREATE `services/harness/src/evaluators/vlm_critique.py`**:
   - Build evaluation prompt via `PromptCompiler.critique_rubric(mode=content_mode, intent=..., persona_sheet=...)` (Bible v2 §13.4):
     - `UNRESTRICTED` rubric evaluates craft/adherence/composition and **never** penalizes requested explicit sexual content, gore, or dark themes.
     - `SFW` rubric flags explicit/unrequested adult content.
   - Invoke local Qwen-VL behind `CognitiveProvider` (zero external aligned vendors!).
3. **CREATE `services/harness/src/evaluators/temporal.py`**:
   - Sample `KEYSTONE_EVAL_VIDEO_SAMPLE_FRAMES` (default `8`) frames via `ffmpeg`, compute adjacent-frame SSIM + luminance/optical-flow flicker score and drift across `extend` segment boundaries.
4. **CREATE `services/harness/src/evaluators/identity.py`**:
   - Compute cosine similarity between generated asset face/subject embedding and the persona's `reference_assets` embeddings (local face/CLIP-class embedding extractor; deterministic pixel/histogram fallback ONLY if explicitly configured for CPU-only unit tests, never hardcoded `0.90`!). Scores below threshold (`0.72`) fail with `PERSONA_IDENTITY_DRIFT`.
5. **REWRITE `services/harness/src/khf_quality.py`**:
   - Delete all hardcoded `0.85`/`0.90` default scores!
   - Orchestrate Tier A (`deterministic.py`, ALWAYS) + Tier B (`ocr`, `vlm_critique`, `temporal`, `identity`) gated by `KEYSTONE_EVAL_BUDGET_VLM_PCT`, retry flag, and persona presence (`specs/SPEC_EVALUATORS.md` §2).
   - Reject un-evaluated or self-reported dict-only inputs (`{"x": 1}` MUST fail, never pass!).
   - Persist every evaluator verdict as a `HarnessRun` row in PostgreSQL/SQLite.
6. **WIRE `services/harness/src/retry_loop.py` into worker post-execution hook (`services/workers/src/worker.py`)**:
   - Below threshold → invoke bounded revision/retry up to `KEYSTONE_EVAL_RETRY_MAX` (default 3) & cost/runtime budget.
   - On budget exhaustion → set `Asset.metadata_["review_required"] = True` + `Asset.status = "needs_review"` (NEVER silent accept, NEVER silent drop!).

### Required Test File: `tests/test_pr7_evaluators_and_retry.py`
1. `test_corrupted_file_fails_deterministic_evaluator`: truncated PNG / empty MP4 → `verdict == "fail"`.
2. `test_ocr_mismatch_fixture_fails_text_fidelity`: PIL-generated image rendering `"HELO WRLD"` vs requested `"HELLO WORLD"` → fails `ocr.py` with `OCR_TEXT_MISMATCH`.
3. `test_persona_drift_fixture_fails_identity_threshold`: two distinct synthetic portrait fixtures → scores below threshold in `identity.py` with `PERSONA_IDENTITY_DRIFT`.
4. `test_mode_aware_vlm_rubric_sfw_vs_unrestricted`: explicit fixture passes `UNRESTRICTED` rubric while flagged by `SFW` rubric.
5. `test_retry_exhaustion_flags_operator_review_and_persists_harness_runs`: force 3 consecutive failing attempts → job stops at budget, asset marked `status="needs_review"`, 3 `harness_runs` rows persisted in DB.

### Commit Message
`PR7 (ADR-005): Real 5-family KHF evaluator tank, mode-aware VLM rubrics, and bounded retry escalation`

---

## PR8 — Memory & Recipe Library (`pgvector`, Local Qwen Embeddings, Replay, 2-Run Promotion)

**Goal:** Implement the project-scoped creative memory flywheel (Bible v2 §42 & `specs/SPEC_MEMORY.md`), register local Qwen-embedding in `CapabilityManifest` (closing Invariant 2 with zero external embedding vendors), wire `GET /v1/recipes`, `POST /v1/recipes/{id}/replay`, `style_rules` CRUD, and two-run auto-promotion, and flip `manifest_accounting` in `scripts/verify_invariants.py` to **BLOCKING**!

### Exact Files to Create / Edit
1. **CREATE `services/cognition/src/embeddings.py`**:
   - `LocalEmbeddingProvider` calling local Qwen-embedding endpoint (`/v1/embeddings` beside the Qwen reasoning core behind `CognitiveProvider`; dimension `KEYSTONE_EMBEDDING_DIM=1024`).
   - Register `cognition.local_embeddings` inside `CapabilityManifest` (recording model id, quantization, dimension, license) so `manifest_accounting` accounts for every active model!
2. **CREATE `apps/api/src/services/memory.py`**:
   - `record_recipe_candidate(db, tenant_id, project_id, persona_id, envelope, compiled_prompt, seed, fabric_versions, scores, mode, embedding)`: writes `Recipe` + `RecipeEmbedding`.
   - `retrieve_advisory_context(db, tenant_id, project_id, resolved_mode, query_embedding, persona_id=None, k=5)`:
     - **Mandatory SQL scope invariant (`SPEC_MEMORY.md` §3):**
       - `Recipe.tenant_id == tenant_id`
       - `Recipe.project_id == project_id`
       - `Recipe.mode == "sfw"` when `resolved_mode == "sfw"` (NEVER returns `unrestricted` recipes in `sfw`!)
     - Ranks by cosine similarity (`<=>` on PostgreSQL `pgvector`, exact Python cosine on SQLite) × quality score × score-per-credit × recency decay × persona affinity.
     - Loads active `StyleRule`s for `(tenant_id, project_id, active=True)`.
     - Returns token-budgeted advisory context block injected non-authoritatively into `PromptCompiler.compile(intent, mode, memory=context)`.
   - `record_passing_run_and_maybe_promote(db, recipe_id, operator_approved=False)`:
     - Operator review promotes immediately (`promoted_at = now(UTC)`).
     - Automatic promotion increments `passing_runs`; sets `promoted_at` ONLY when `passing_runs >= 2` (never after 1 run!).
3. **CREATE `apps/api/src/routers/recipes.py`** (mount in `apps/api/src/server.py`):
   - `GET /v1/recipes` (tenant + project + mode-filtered; never leaks mature recipes under SFW).
   - `POST /v1/recipes/{recipe_id}/replay` — loads stored `envelope`, `compiled_prompt`, `seed`, `fabric_versions`, runs through **normal `GateService.authorize_and_sign`** (re-checking mode, age gate, and lawful floor!) and dispatches deterministic staging!
   - `POST /v1/projects/{project_id}/style-rules`, `GET /v1/projects/{project_id}/style-rules`, `DELETE /v1/projects/{project_id}/style-rules/{rule_id}`.
4. **WIRE into `gate.py` & Next.js Studio**:
   - Step 4 of `gate.py` fetches advisory memory context and passes it to `PromptCompiler`.
   - Surface "Similar proven recipe" + Replay button in Studio inspector (`UX_PARITY.md` row 12).
5. **FLIP STRUCTURAL LINT (`scripts/verify_invariants.py`)**:
   - Update `verify_manifest_accounting` to verify `cognition.local_embeddings` is registered in `CapabilityManifest`.
   - Add `"manifest_accounting"` to `BLOCKING_CHECKS`!

### Required Test File: `tests/test_pr8_memory_and_recipes.py`
1. `test_cross_tenant_retrieval_returns_zero_rows`: tenant A saves recipe → tenant B queries same project/embedding → `[]`.
2. `test_sfw_compile_never_retrieves_unrestricted_recipe`: save `mode="unrestricted"` recipe → query under `resolved_mode="sfw"` → `[]`; query under `resolved_mode="unrestricted"` → returns recipe.
3. `test_recipe_replay_reproduces_deterministic_staging_through_gate`: `POST /v1/recipes/{id}/replay` matches stored `prompt_hash`, `seed`, `fabric_versions`, and still enforces age gate + floor!
4. `test_two_run_promotion_rule`: 1 passing run → `promoted_at is None`; 2nd independent passing run → `promoted_at is not None`.
5. `test_manifest_accounting_blocking_passes`: `verify_invariants.py` reports `[PASS] (blocking) manifest_accounting`.

### Commit Message
`PR8 (ADR-005): Memory & Recipe Library (pgvector + local Qwen embeddings), replay, 2-run promotion, and manifest_accounting blocking`

---

## PR9 — Immutable DB Billing Ledger, Dual-Rail Processor Provenance, Stage-2 Age Gate & C2PA Credentials

**Goal:** Eliminate the in-memory `credits_ledger` split-brain, execute transactional DB `HOLD → SETTLEMENT / RELEASE` on every job with VRAM-minute & evaluator-second metering (`usage_records`), enforce dual-rail processor provenance (`stripe` for SFW ONLY; `adult_rail`/`crypto` for UNRESTRICTED ONLY), add Stage-2 card/processor age verification, and stamp every generated asset with a C2PA Content Credentials manifest (§43).

### Exact Files to Create / Edit
1. **CREATE `apps/api/src/services/credits.py`** (Replaces in-memory `credits_ledger` singleton):
   - Transactional DB methods with `SELECT ... FOR UPDATE` (on Postgres) / atomic transaction (on SQLite):
     - `deposit(db, user_id, amount, processor, content_mode, idempotency_key, reference_type, reference_id)` — enforces **dual-rail invariant**: rejects `processor == "stripe"` with `content_mode == "unrestricted"` (HTTP `400` `PROCESSOR_MODE_VIOLATION`); requires `user.age_verified == True` for any `unrestricted` deposit (unless Stage-2 adult processor webhook simultaneously verifies age!).
     - `hold_for_job(db, user_id, job_id, amount, content_mode, idempotency_key)` — deducts available into `held_balance`, appends `CreditLedger(transaction_type="HOLD")`, idempotent on `idempotency_key` (never double-charges!).
     - `settle_hold(db, user_id, job_id, actual_amount, vram_minutes, eval_seconds, capability_id, provider_id)` — settles hold (refunding excess if `actual < held`), appends `CreditLedger(transaction_type="SETTLEMENT")`, writes `UsageRecord` rows with `unit="vram_minutes"` and `unit="eval_seconds"`.
     - `release_hold(db, user_id, job_id, reason)` — releases full hold on job failure/cancel, appends `CreditLedger(transaction_type="RELEASE")`.
2. **EDIT `apps/api/src/routers/billing.py` & `services/billing/src/stripe_client.py`**:
   - Delete in-memory `credits_ledger` dict references; wire all endpoints to `apps/api/src/services/credits.py` + DB `CreditAccount`/`CreditLedger`/`Subscription`.
   - Implement real Stripe webhook signature verification (`t=...,v1=...` HMAC-SHA256 with `STRIPE_WEBHOOK_SECRET` + timestamp replay window + DB `idempotency_key`) strictly scoped to `content_mode="sfw"`.
   - Add `POST /v1/billing/webhooks/adult-processor` (HMAC-verified with `ADULT_PROCESSOR_WEBHOOK_SECRET`) for Stage-2 age verification + `unrestricted` credit deposit (`processor="adult_rail"`, sets `user.age_verified=True`, `user.age_verification_method="card_adult_processor"`, writes `AuditEvent`).
3. **CREATE `apps/api/src/services/c2pa_credentials.py`** (Bible v2 §43):
   - Reads dedicated `KEYSTONE_C2PA_SIGNING_KEY` from env (asserts `KEYSTONE_C2PA_SIGNING_KEY != KEYSTONE_ENVELOPE_SECRET`!).
   - Stamps every generated asset at persist time with a signed C2PA-compatible JSON-LD/JUMBF manifest (`platform="KEYSTONE"`, `timestamp`, `fabric`, `recipe_id`, `content_mode`, `asset_sha256`, `signature`), persists into `assets.c2pa_manifest`, and exposes `GET /v1/assets/{asset_id}/credentials` + UI badge toggle (`UX_PARITY.md` row 12).
4. **WIRE `hold → settle / release` + C2PA stamping into `gate.py` & `services/workers/src/worker.py`**.

### Required Test File: `tests/test_pr9_billing_age2_c2pa.py`
1. `test_credit_hold_settle_release_idempotent_no_double_charge`: duplicate hold with same `idempotency_key` charges exactly once; failure releases full hold; settlement writes `usage_records` (`vram_minutes`, `eval_seconds`) and immutable `credit_ledger` rows.
2. `test_dual_rail_blocks_stripe_for_unrestricted`: attempting `processor="stripe"` with `content_mode="unrestricted"` raises `PROCESSOR_MODE_VIOLATION`.
3. `test_stage2_adult_processor_webhook_verifies_age_and_deposits`: valid signed adult-processor webhook marks `age_verified=True` (`method="card_adult_processor"`), credits account, and is idempotent on replay.
4. `test_c2pa_manifest_stamped_with_separate_key`: generated asset stores signed `c2pa_manifest` with verifiable SHA-256 + signature; reusing `KEYSTONE_ENVELOPE_SECRET` as C2PA key is rejected!

### Commit Message
`PR9 (ADR-005): Immutable DB billing ledger, dual-rail processor provenance, Stage-2 age gate, and C2PA credentials`

---

## PR10 & Phase D — Real Acceptance Suite, Live `verify_alpha_gate.py`, Cloud Run Fix & Final OpenAPI

**Goal:** Replace the retired v1 verification theater with real HTTP + DB + worker acceptance tests covering every Bible v2 §34 & §35 criterion, make `scripts/verify_alpha_gate.py` run those real tests (exit 0 only when all real boundaries pass), fix Docker/Cloud Run packaging & legal docs, regenerate the final `openapi.yaml` matching all PR1–PR9 routes, and pass `scripts/verify_invariants.py --strict`!

### Exact Files to Create / Edit
1. **REWRITE `tests/acceptance/test_bible_acceptance.py`**:
   - Delete any remaining mock/stub shortcuts. Implement full end-to-end real FastAPI + Alembic-migrated DB + worker tests covering EVERY §35 category:
     - **Identity:** `plan.v1`, 16 playbooks (14–16 UNRESTRICTED-only), `PromptAnatomy`, prompt provenance.
     - **Authority:** raw user/model bypass fails, `envelope=null -> 400`, expired/replayed/tampered/SFW-on-UNRESTRICTED rejected, worker refuses unsigned/mutated prompt.
     - **Content Modes:** unverified 403, Stage-1 & Stage-2 age gate, floor violation 422 + audit row + 0 dispatch, lawful UNRESTRICTED passes, mature asset gallery exclusion.
     - **Evaluators:** corrupt binary, OCR mismatch, persona drift, UNRESTRICTED vs SFW rubric divergence, retry exhaustion → `needs_review`.
     - **Memory:** cross-tenant 0 rows, SFW excludes mature recipes, replay determinism, 2-run promotion.
     - **Full E2E Loop (§35):** Register → Create project → Verify age & set mode → Create persona → Upload image → Animate as persona → Gate + Envelope v2 → Worker execute → Evaluate → Persist video + `depicts` lineage + C2PA + recipe → Debit credits once with processor provenance → Refresh & recover complete state → Simulate mid-run worker crash & verify recovery!
2. **REBUILD `scripts/verify_alpha_gate.py`** (replacing the `RETIRED_PENDING_PR10` stub):
   - Executes real subprocess `pytest tests/acceptance/test_bible_acceptance.py` + `scripts/verify_invariants.py --strict` + `npm test` + `apps/web` `npx tsc --noEmit`. Zero hardcoded `"PASS"` dicts! Exits `0` ONLY if all real checks exit `0`.
3. **FIX Cloud Run & Packaging (`requirements.txt`, `infrastructure/cloudrun/Dockerfile`, `docs/legal/*`, `packages/security/gdpr_erasure.py`):**
   - Complete `requirements.txt` with all runtime dependencies (`sqlalchemy`, `alembic`, `aiosqlite`, `asyncpg`, `greenlet`, `python-multipart`, `httpx`, `pillow`, `redis`, `google-cloud-storage`, etc.).
   - Fix `infrastructure/cloudrun/Dockerfile` (single-worker or Redis-safe multi-worker, runs `alembic upgrade head` in entrypoint, verified cleanly against `.dockerignore`).
   - Wire `packages/security/gdpr_erasure.py` to actually soft-delete/erase user DB rows + storage objects (remove hardcoded `assets_deleted: True`).
   - Update `docs/legal/` to accurately match dual-mode SFW/UNRESTRICTED acceptable use, age verification, C2PA records posture, and real subprocessors (Bible v2 §30).
4. **REGENERATE FINAL `openapi.yaml`** from the live FastAPI `app.openapi()` schema (now including `/v1/account/*`, `/v1/recipes/*`, updated `/v1/personas/*`, `/v1/billing/webhooks/*`, `/v1/assets/{id}/credentials`, etc.).
5. **UPDATE `docs/FILE_MANIFEST.txt` & `TEST_READY.md`** to reflect final shipped repository state.

### Phase D Final Verification Gate (ALL Must Exit 0)
```powershell
.venv\Scripts\python.exe scripts/verify_invariants.py --strict
.venv\Scripts\python.exe scripts/verify_change_control.py --root .
.venv\Scripts\python.exe scripts/verify_alpha_gate.py
.venv\Scripts\python.exe -m pytest -q
npm test
Set-Location apps\web; npx tsc --noEmit
```

### Commit Message
`PR10 (ADR-005): Real acceptance suite, live verify_alpha_gate, Cloud Run/GDPR fixes, final openapi.yaml, and Phase D strict pass`

---

## Copy-Paste Handoff Prompt for Low-Cost Orchestrator (Hydrogen 4 on Low)

When switching models, start the prompt with:

> Read `docs/bible-v2/EXECUTION_RUNBOOK_PR1_TO_PR10.md` and `docs/bible-v2/APPLICATION_PROTOCOL.md`. Execute **PR<N>** strictly as specified — obey Section 0 rules and the DO-NOT-TOUCH list, write the exact required test file `tests/test_pr<N>_*.py`, run the Section 0 end-of-PR verification commands, and commit with the exact commit message template once all checks exit 0. Do not redesign architecture or skip tests.
