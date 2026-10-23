## 2026-10-22T16:30:06Z

You are explorer_m0_2, a teamwork_preview_explorer subagent for Milestone M0 (Wave 0: Contract Freeze & Additive Foundation).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (§21 PostgreSQL schema, §27 credits ledger)
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md
- Inspect existing migration: `c:\Users\Lesia Eden\Downloads\keystone-cowork\infrastructure\migrations\versions\0001_core.sql`

OBJECTIVE:
Investigate and design the exact DDL schema and migration blueprint for PostgreSQL 23-Table Schema (F04):
1. Compare `0001_core.sql` (12 existing tables) against the 23 mandated tables in Bible §21.
2. Design the complete additive migration `infrastructure/migrations/versions/0002_keystone_full_schema.sql` that defines the 11 missing tables:
   - `subscriptions`, `api_keys`, `request_assets`, `generation_attempts`, `attempt_assets`, `user_feedback`, `credit_accounts`, `credit_ledger`, `usage_records`, `configuration_bundles`, `asset_relationships`.
3. Ensure every table has: UUID primary keys (`gen_random_uuid()`), appropriate foreign keys (`ON DELETE CASCADE` or `RESTRICT`), timestamps with time zone (`TIMESTAMPTZ DEFAULT now()`), indexes on lookups/joins, and checks.
4. Ensure `credit_ledger` has strict append-only constraints (positive amount, valid transaction types: `DEPOSIT`, `HOLD`, `SETTLEMENT`, `RELEASE`, `REFUND`).
5. Provide complete, syntactically valid PostgreSQL DDL in your report ready for the Worker to author.
6. Write your report to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2\m0_database_schema_blueprint.md`.
7. Write your handoff to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_2\handoff.md`.
8. Send a message to parent when done. Do NOT modify source files.
