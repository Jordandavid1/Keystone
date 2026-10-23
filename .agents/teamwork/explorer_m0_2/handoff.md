# Handoff Report: PostgreSQL 23-Table Schema & Migration Blueprint (F04)

**Agent:** explorer_m0_2  
**Milestone:** M0 (Wave 0: Contract Freeze & Additive Foundation)  
**Recipient:** Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Deliverable Document:** `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2\m0_database_schema_blueprint.md`  
**Handoff Type:** Hard (Task complete)

---

## 1. Observation

1. **Pre-Existing Base Migration**: Inspected `infrastructure/migrations/versions/0001_core.sql` (lines 1–16). It creates extension `pgcrypto` and defines 12 base tables:
   - `users` (line 3)
   - `projects` (line 4)
   - `sessions` (line 5)
   - `messages` (line 6)
   - `assets` (line 7)
   - `requests` (line 8)
   - `cognitive_runs` (line 9)
   - `authority_decisions` (line 10)
   - `jobs` (line 11)
   - `compiled_prompts` (line 12)
   - `harness_runs` (line 13)
   - `audit_events` (line 14)
2. **Canonical Schema Mandate in Keystone Bible**: Inspected `KEYSTONE_BIBLE.md` §21 (lines 924–950). It mandates exactly 23 tables:
   ```text
   users
   subscriptions
   api_keys
   projects
   sessions
   messages
   assets
   requests
   request_assets
   cognitive_runs
   authority_decisions
   jobs
   generation_attempts
   compiled_prompts
   attempt_assets
   harness_runs
   user_feedback
   credit_accounts
   credit_ledger
   usage_records
   audit_events
   configuration_bundles
   asset_relationships
   ```
3. **Credit Ledger Invariants**: Inspected `KEYSTONE_BIBLE.md` §27 (lines 1187–1211). It mandates:
   - "Balances never change without a corresponding ledger event."
   - "transactional credit holds and settlement;"
   - "refunds and reversals through ledger entries;"
   - "API keys stored only as hashes; raw API keys never stored".
4. **Asset Lineage Invariants**: Inspected `KEYSTONE_BIBLE.md` §22 (lines 982–985). It mandates:
   - "Each relationship records parent asset, child asset, originating job, relationship type, and creation time."
   - "Supported relationship types include source, edit, variation, animation, upscale, reference, selected-final, and intermediate."
5. **Generation Attempts & Feedback Data Models**: Inspected `KEYSTONE_BIBLE.md` §16 (lines 620–650). It defines `GenerationAttempt` (attempt_id, job_id, provider_id, capability_id, prompt_hash, workflow_version, started_at, completed_at, success, output_asset_ids, metrics, failure_code) and `UserFeedback` (job_id, user_id, rating, accepted, regeneration_requested, selected_asset_id, feedback_tags, comment).
6. **Baseline Test Suite Execution**:
   - `npm test` executed and passed 3/3 identity tests cleanly (duration 365.8ms).
   - `node --test tests/e2e/` executed and passed 194/194 tests cleanly (duration 10,380ms).
7. **DDL Validation Script Execution**:
   - Developed and ran `python .agents/teamwork/explorer_m0_2/validate_ddl.py`.
   - Result: Confirmed 11 missing tables, 17 foreign keys targeting existing tables, `amount > 0` check, 5 valid transaction types (`DEPOSIT`, `HOLD`, `SETTLEMENT`, `RELEASE`, `REFUND`), `TIMESTAMPTZ` data types, and 53 indexes.

---

## 2. Logic Chain

1. **Delta Derivation**: Subtracting the 12 base tables in `0001_core.sql` (Observation 1) from the 23 mandated tables in `KEYSTONE_BIBLE.md` §21 (Observation 2) produces the exact 11 missing tables: `subscriptions`, `api_keys`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `configuration_bundles`, and `asset_relationships`.
2. **Pre-Built Preservation Invariant**: `0001_core.sql` is part of the locked pre-built work (Observation 1, `ORIGINAL_REQUEST.md` line 16, `PROJECT.md` line 13). Therefore, all new table definitions must be authored into an additive migration file `infrastructure/migrations/versions/0002_keystone_full_schema.sql` without modifying `0001_core.sql`.
3. **Ledger Integrity & Immutability**: Bible §27 dictates that balances never change without a ledger event and that transactions are immutable (Observation 3). To guarantee that no bug or rogue query can mutate or delete historical ledger records, the DDL implements both:
   - Check constraints: `amount > 0`, `transaction_type IN ('DEPOSIT', 'HOLD', 'SETTLEMENT', 'RELEASE', 'REFUND')`, `balance_after >= 0`, `held_balance_after >= 0`.
   - A PL/pgSQL function `keystone_credit_ledger_prevent_modification()` and trigger `trg_credit_ledger_immutable` on `credit_ledger` that immediately raises an exception on `UPDATE` or `DELETE`.
4. **Referential Integrity Ordering**:
   - `credit_accounts` must be created prior to `credit_ledger` because `credit_ledger.account_id` references `credit_accounts(id)`.
   - `generation_attempts` must be created prior to `attempt_assets` because `attempt_assets.attempt_id` references `generation_attempts(id)`.
   - Foreign key to users on `credit_accounts` uses `ON DELETE RESTRICT` to ensure financial accounts cannot be deleted if transactions exist.
   - Foreign key to accounts on `credit_ledger` uses `ON DELETE RESTRICT` to preserve immutable audit trails.
5. **Asset Lineage DAG Modeling**: Mapping Observation 4 into `asset_relationships` requires:
   - `parent_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
   - `child_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
   - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
   - `relationship_type TEXT NOT NULL CHECK (relationship_type IN ('source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate'))`
   - `UNIQUE(parent_asset_id, child_asset_id, relationship_type)`.
6. **Additive Performance Indexing**: `0001_core.sql` did not define explicit indexes on foreign keys (Observation 1). Adding non-blocking `CREATE INDEX IF NOT EXISTS` for all foreign keys across both `0001_core.sql` and the new 11 tables optimizes join traversal and prevents table-level locking during cascade operations.

---

## 3. Caveats

1. **Alembic Wrapper vs Raw SQL**: The migration directory currently contains raw SQL version files (`0001_core.sql`). In Python/Alembic environments, migrations may either be executed via an async raw SQL runner (`connection.execute(text(sql))`) or wrapped inside Alembic's `upgrade()` function (`op.execute(...)`). The blueprint provides pure, standard PostgreSQL DDL so it is completely agnostic and compatible with either Alembic `op.execute()` or direct PostgreSQL migration runners.
2. **PostgreSQL Server Extensions**: The DDL relies on `gen_random_uuid()` from `pgcrypto` (which was enabled in `0001_core.sql`) or built-in PostgreSQL 13+. In modern PostgreSQL (13+), `gen_random_uuid()` is a native core function.
3. **No Code Modification Undertaken**: In strict adherence to Explorer read-only duties, no files outside `.agents/teamwork/explorer_m0_2/` were written or modified.

---

## 4. Conclusion

1. The architectural gap between `0001_core.sql` and the full Keystone specification has been completely analyzed, resolved, and documented.
2. The 11 missing tables (`subscriptions`, `api_keys`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `configuration_bundles`, `asset_relationships`) have been exhaustively specified with strict typing, check constraints, foreign key actions, indexes, and immutability triggers.
3. The complete, production-ready DDL has been synthesized and verified in `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2\m0_database_schema_blueprint.md`.
4. Milestone M0 Worker can author `infrastructure/migrations/versions/0002_keystone_full_schema.sql` directly from the DDL in Section 6 of the blueprint without architectural uncertainty.

---

## 5. Verification Method

To independently verify this blueprint:
1. **Verify Table Delta & Constraints**:
   Run the automated DDL verification test script:
   ```powershell
   python .agents/teamwork/explorer_m0_2/validate_ddl.py
   ```
   *Expected Output:* `ALL TESTS PASSED SUCCESSFULLY!` (confirms 23-table totality, `amount > 0`, transaction types, triggers, and foreign keys).
2. **Verify Non-Regression of Pre-Built Tests**:
   Run the project test suites:
   ```powershell
   npm test
   node --test tests/e2e/
   ```
   *Expected Output:* 3/3 identity tests pass and 194/194 E2E tests pass.
3. **Inspect the Blueprint Document**:
   View `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2\m0_database_schema_blueprint.md`.
   Verify Section 6 contains the full PostgreSQL DDL ready for authoring into `0002_keystone_full_schema.sql`.

---
*End of Handoff Report.*
