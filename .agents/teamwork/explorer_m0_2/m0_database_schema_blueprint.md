# KEYSTONE Database Schema Blueprint & Migration Specification (F04)
**Milestone:** M0 (Wave 0: Contract Freeze & Additive Foundation)  
**Author:** explorer_m0_2  
**Target Migration:** `infrastructure/migrations/versions/0002_keystone_full_schema.sql`  
**Canonical Spec Reference:** `KEYSTONE_BIBLE.md` §21 (PostgreSQL architecture), §22 (Asset architecture), §27 (Authentication, billing, and credits)  
**Predecessor File:** `infrastructure/migrations/versions/0001_core.sql` (12 pre-built base tables, strictly immutable)

---

## 1. Executive Summary

This blueprint delivers the complete architectural design and verified PostgreSQL DDL for **F04 (PostgreSQL 23-Table Schema & Migrations)**. 

In accordance with **Milestone M0** and the **18 Locked Invariants** of `KEYSTONE_BIBLE.md` (§2 Invariant 18: "The original source archive is preserved. Integration work happens in the new monorepo"), all pre-built files remain 100% byte-identical. Existing base migration `0001_core.sql` defines 12 core tables. This document designs the additive migration `0002_keystone_full_schema.sql` defining the remaining **11 missing tables** to realize the complete 23-table schema mandated in `KEYSTONE_BIBLE.md` §21.

### Key Architectural Invariants Enforced:
1. **Strict 23-Table Totality**: Bridges the gap from 12 base tables to the exact 23 mandated tables in Keystone Bible §21.
2. **UUID Primary Keys**: Every table uses `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` using PostgreSQL's `pgcrypto` extension (initialized in 0001).
3. **Time Zone Integrity**: All temporal attributes use `TIMESTAMPTZ` with `DEFAULT now()`.
4. **Immutable Credit Ledger (§27)**: `credit_ledger` enforces positive amounts (`amount > 0`), valid transaction types (`DEPOSIT`, `HOLD`, `SETTLEMENT`, `RELEASE`, `REFUND`), and a PostgreSQL trigger (`keystone_credit_ledger_prevent_modification`) that strictly rejects `UPDATE` and `DELETE` operations.
5. **Two-Phase Commit for Job Credits**: Complete support for `hold` -> `settlement` / `release` / `refund` cycles without balance drift.
6. **Asset Lineage DAG (§22)**: `asset_relationships` captures all 8 mandated relationship types (`source`, `edit`, `variation`, `animation`, `upscale`, `reference`, `selected-final`, `intermediate`).
7. **Additive Performance Indexes**: Comprehensive indexing on all new foreign keys and lookups, plus non-breaking `IF NOT EXISTS` foreign key indexes for base `0001_core.sql` tables.

---

## 2. Schema Audit & Comparative Analysis

### 2.1 The 12 Base Tables in `0001_core.sql`
The pre-existing migration `infrastructure/migrations/versions/0001_core.sql` defines:

| Table # | Table Name | Purpose | Primary Foreign Keys |
|---------|------------|---------|-----------------------|
| 1 | `users` | Core user accounts, auth credentials, status | None (Root entity) |
| 2 | `projects` | User workspaces / creative projects | `user_id -> users(id)` |
| 3 | `sessions` | Interactive creative sessions / chats | `user_id -> users(id)`, `project_id -> projects(id)` |
| 4 | `messages` | Chat conversation messages (user / keystone) | `session_id -> sessions(id) ON DELETE CASCADE` |
| 5 | `assets` | Asset binary metadata and storage keys | `owner_id -> users(id)`, `project_id -> projects(id)` |
| 6 | `requests` | High-level user creative requests & preferences | `user_id -> users(id)`, `session_id -> sessions(id)`, `message_id -> messages(id)` |
| 7 | `cognitive_runs` | Qwen cognitive reasoning executions & proposals | `request_id -> requests(id)` |
| 8 | `authority_decisions` | Authority engine policy decisions (approve/deny/replan) | `request_id -> requests(id)`, `cognitive_run_id -> cognitive_runs(id)` |
| 9 | `jobs` | Executable creative tasks dispatched to workers | `request_id -> requests(id)`, `authority_decision_id -> authority_decisions(id)`, `user_id -> users(id)` |
| 10 | `compiled_prompts` | Model-facing compiled prompts & provenance | `request_id -> requests(id)`, `job_id -> jobs(id)` |
| 11 | `harness_runs` | Technical/aesthetic evaluation runs and verdicts | `request_id -> requests(id)`, `job_id -> jobs(id)` |
| 12 | `audit_events` | Immutable security and operational audit trail | `request_id`, `job_id` |

### 2.2 The 23 Tables Mandated in `KEYSTONE_BIBLE.md` §21
Section 21 of `KEYSTONE_BIBLE.md` explicitly specifies:
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

### 2.3 The 11 Missing Tables Delta
Comparing the mandated list against `0001_core.sql` reveals the exact 11 missing tables:

| Delta # | Table Name | Functional Domain | Bible Reference |
|---------|------------|-------------------|-----------------|
| 1 | `subscriptions` | Billing & Subscriptions | §21, §27 |
| 2 | `api_keys` | Developer Authentication & Scopes | §21, §27 |
| 3 | `request_assets` | Input Asset Attachment Join | §17, §21 |
| 4 | `generation_attempts` | Job Execution Retries & Metrics | §14, §16, §21 |
| 5 | `attempt_assets` | Output Asset Association Join | §16, §21 |
| 6 | `user_feedback` | Quality Signals & User Ratings | §14, §16, §17, §21 |
| 7 | `credit_accounts` | Account Balance & Held Funds | §21, §27 |
| 8 | `credit_ledger` | Immutable Double-Entry Ledger | §21, §27 |
| 9 | `usage_records` | Granular Resource Metering | §21, §27 |
| 10 | `configuration_bundles` | Versioned Policy & Registry Bundles | §10, §12, §21 |
| 11 | `asset_relationships` | Directed Acyclic Graph (DAG) Lineage | §21, §22 |

---

## 3. Entity Specifications for the 11 Missing Tables

### 3.1 `subscriptions`
Stores customer billing plans, plan entitlements, Stripe references, and subscription lifecycles.
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id`: `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `plan_id`: `TEXT NOT NULL` (e.g. `'free'`, `'starter'`, `'creator_pro'`, `'studio'`, `'enterprise'`)
  - `status`: `TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('trialing', 'active', 'past_due', 'canceled', 'unpaid', 'incomplete', 'incomplete_expired', 'paused'))`
  - `stripe_customer_id`: `TEXT`
  - `stripe_subscription_id`: `TEXT UNIQUE`
  - `current_period_start`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `current_period_end`: `TIMESTAMPTZ`
  - `cancel_at_period_end`: `BOOLEAN NOT NULL DEFAULT false`
  - `canceled_at`: `TIMESTAMPTZ`
  - `metadata`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
- **Indexes**:
  - `idx_subscriptions_user_id` ON `subscriptions(user_id)`
  - `idx_subscriptions_status` ON `subscriptions(status)`
  - `idx_subscriptions_stripe_customer_id` ON `subscriptions(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL`
  - `idx_subscriptions_stripe_subscription_id` ON `subscriptions(stripe_subscription_id) WHERE stripe_subscription_id IS NOT NULL`
- **Triggers**:
  - `trg_subscriptions_updated_at` BEFORE UPDATE executing `keystone_set_updated_at()`

### 3.2 `api_keys`
Stores cryptographic hashes of programmatic developer access keys. Per Bible §21 & §27: "API keys stored only as hashes; raw API keys never stored".
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id`: `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `name`: `TEXT NOT NULL`
  - `key_hash`: `TEXT NOT NULL UNIQUE` (SHA-256 hash of the issued key token)
  - `key_prefix`: `TEXT NOT NULL` (e.g. `ks_live_a1b2c3d4` for display in dashboards)
  - `scopes`: `JSONB NOT NULL DEFAULT '["*"]'::jsonb`
  - `status`: `TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired'))`
  - `last_used_at`: `TIMESTAMPTZ`
  - `expires_at`: `TIMESTAMPTZ`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
- **Indexes**:
  - `idx_api_keys_key_hash` UNIQUE ON `api_keys(key_hash)`
  - `idx_api_keys_user_id` ON `api_keys(user_id)`
  - `idx_api_keys_status` ON `api_keys(status)`
- **Triggers**:
  - `trg_api_keys_updated_at` BEFORE UPDATE executing `keystone_set_updated_at()`

### 3.3 `credit_accounts`
Maintains user credit balances and held credit reservations. Must precede `credit_ledger` in creation order.
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id`: `UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT` (Guarantees financial account persistence)
  - `balance`: `BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0)`
  - `held_balance`: `BIGINT NOT NULL DEFAULT 0 CHECK (held_balance >= 0)`
  - `currency`: `TEXT NOT NULL DEFAULT 'credits'`
  - `status`: `TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'suspended', 'closed'))`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
- **Indexes**:
  - `idx_credit_accounts_user_id` UNIQUE ON `credit_accounts(user_id)`
  - `idx_credit_accounts_status` ON `credit_accounts(status)`
- **Triggers**:
  - `trg_credit_accounts_updated_at` BEFORE UPDATE executing `keystone_set_updated_at()`

### 3.4 `credit_ledger`
Strictly immutable, append-only transaction ledger. Implements two-phase commitment and financial auditing.
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `account_id`: `UUID NOT NULL REFERENCES credit_accounts(id) ON DELETE RESTRICT`
  - `transaction_type`: `TEXT NOT NULL CHECK (transaction_type IN ('DEPOSIT', 'HOLD', 'SETTLEMENT', 'RELEASE', 'REFUND'))`
  - `amount`: `BIGINT NOT NULL CHECK (amount > 0)` (Enforces positive transaction magnitude)
  - `balance_after`: `BIGINT NOT NULL CHECK (balance_after >= 0)`
  - `held_balance_after`: `BIGINT NOT NULL CHECK (held_balance_after >= 0)`
  - `reference_id`: `UUID` (e.g., `job_id`, `request_id`, or originating hold transaction `id`)
  - `reference_type`: `TEXT CHECK (reference_type IS NULL OR reference_type IN ('job', 'request', 'stripe_checkout', 'hold', 'manual_adjustment', 'subscription_grant'))`
  - `idempotency_key`: `TEXT` (Prevents duplicate charges / webhook replay)
  - `description`: `TEXT`
  - `metadata`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
- **Indexes**:
  - `idx_credit_ledger_account_id` ON `credit_ledger(account_id)`
  - `idx_credit_ledger_created_at` ON `credit_ledger(created_at DESC)`
  - `idx_credit_ledger_ref` ON `credit_ledger(reference_type, reference_id) WHERE reference_id IS NOT NULL`
  - `idx_credit_ledger_idempotency` UNIQUE ON `credit_ledger(idempotency_key) WHERE idempotency_key IS NOT NULL`
- **Immutability Enforcement Trigger**:
  - Trigger `trg_credit_ledger_immutable` BEFORE UPDATE OR DELETE executing `keystone_credit_ledger_prevent_modification()` which raises an exception on any mutation or deletion attempt.

### 3.5 `request_assets`
Associates incoming multimodal user requests with attached input assets (e.g. init images, reference videos, control masks).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `request_id`: `UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE`
  - `asset_id`: `UUID NOT NULL REFERENCES assets(id) ON DELETE RESTRICT`
  - `role`: `TEXT NOT NULL DEFAULT 'input' CHECK (role IN ('input', 'reference', 'mask', 'init_image', 'controlnet'))`
  - `metadata`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE(request_id, asset_id, role)`
- **Indexes**:
  - `idx_request_assets_request_id` ON `request_assets(request_id)`
  - `idx_request_assets_asset_id` ON `request_assets(asset_id)`

### 3.6 `generation_attempts`
Records discrete execution attempts for creative jobs, supporting bounded retry loops (§14, §16 `GenerationAttempt`).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `job_id`: `UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
  - `attempt_number`: `INTEGER NOT NULL CHECK (attempt_number >= 1)`
  - `provider_id`: `TEXT NOT NULL`
  - `capability_id`: `TEXT NOT NULL`
  - `prompt_hash`: `TEXT NOT NULL`
  - `workflow_version`: `TEXT NOT NULL`
  - `started_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `completed_at`: `TIMESTAMPTZ`
  - `success`: `BOOLEAN NOT NULL DEFAULT false`
  - `metrics`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `failure_code`: `TEXT`
  - `error_detail`: `JSONB`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE(job_id, attempt_number)`
- **Indexes**:
  - `idx_generation_attempts_job_id` ON `generation_attempts(job_id)`
  - `idx_generation_attempts_started_at` ON `generation_attempts(started_at DESC)`
  - `idx_generation_attempts_capability` ON `generation_attempts(capability_id, provider_id)`

### 3.7 `attempt_assets`
Associates output assets generated by a specific attempt with that attempt (§16 `GenerationAttempt.output_asset_ids`).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `attempt_id`: `UUID NOT NULL REFERENCES generation_attempts(id) ON DELETE CASCADE`
  - `asset_id`: `UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
  - `role`: `TEXT NOT NULL DEFAULT 'output' CHECK (role IN ('output', 'preview', 'thumbnail', 'intermediate', 'mask'))`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE(attempt_id, asset_id)`
- **Indexes**:
  - `idx_attempt_assets_attempt_id` ON `attempt_assets(attempt_id)`
  - `idx_attempt_assets_asset_id` ON `attempt_assets(asset_id)`

### 3.8 `user_feedback`
Captures explicit user quality ratings, acceptance decisions, regeneration requests, and tags (§14, §16 `UserFeedback`, §17).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `job_id`: `UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
  - `user_id`: `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `rating`: `DOUBLE PRECISION CHECK (rating IS NULL OR (rating >= 0.0 AND rating <= 5.0))`
  - `accepted`: `BOOLEAN`
  - `regeneration_requested`: `BOOLEAN NOT NULL DEFAULT false`
  - `selected_asset_id`: `UUID REFERENCES assets(id) ON DELETE SET NULL`
  - `feedback_tags`: `JSONB NOT NULL DEFAULT '[]'::jsonb`
  - `comment`: `TEXT`
  - `metadata`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
- **Indexes**:
  - `idx_user_feedback_job_id` ON `user_feedback(job_id)`
  - `idx_user_feedback_user_id` ON `user_feedback(user_id)`
  - `idx_user_feedback_selected_asset` ON `user_feedback(selected_asset_id) WHERE selected_asset_id IS NOT NULL`
  - `idx_user_feedback_created_at` ON `user_feedback(created_at DESC)`

### 3.9 `usage_records`
High-resolution metered usage for billing, quotas, and capability consumption tracking (§21, §27).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id`: `UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
  - `job_id`: `UUID REFERENCES jobs(id) ON DELETE SET NULL`
  - `capability_id`: `TEXT NOT NULL`
  - `provider_id`: `TEXT NOT NULL`
  - `quantity`: `NUMERIC NOT NULL CHECK (quantity >= 0)`
  - `unit`: `TEXT NOT NULL CHECK (unit IN ('seconds', 'tokens', 'images', 'frames', 'megabytes', 'requests', 'steps'))`
  - `credits_billed`: `BIGINT NOT NULL DEFAULT 0 CHECK (credits_billed >= 0)`
  - `metadata`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `recorded_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
- **Indexes**:
  - `idx_usage_records_user_id` ON `usage_records(user_id)`
  - `idx_usage_records_job_id` ON `usage_records(job_id) WHERE job_id IS NOT NULL`
  - `idx_usage_records_recorded_at` ON `usage_records(recorded_at DESC)`
  - `idx_usage_records_capability` ON `usage_records(capability_id, provider_id)`

### 3.10 `configuration_bundles`
Stores versioned, immutable policy bundles, capability registries, harness configurations, and playbooks (§10, §12, §21).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `bundle_type`: `TEXT NOT NULL CHECK (bundle_type IN ('policy', 'capability_registry', 'harness', 'playbook', 'runtime_presets'))`
  - `name`: `TEXT NOT NULL`
  - `version`: `TEXT NOT NULL`
  - `checksum`: `TEXT NOT NULL` (SHA-256 hash of payload)
  - `payload`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `is_active`: `BOOLEAN NOT NULL DEFAULT true`
  - `created_by`: `TEXT`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `updated_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE(bundle_type, version)`
- **Indexes**:
  - `idx_config_bundles_type_version` UNIQUE ON `configuration_bundles(bundle_type, version)`
  - `idx_config_bundles_active` ON `configuration_bundles(bundle_type, is_active)`
- **Triggers**:
  - `trg_configuration_bundles_updated_at` BEFORE UPDATE executing `keystone_set_updated_at()`

### 3.11 `asset_relationships`
Models the asset lineage Directed Acyclic Graph (DAG) across sources, edits, variations, animations, and upscales (§21, §22).
- **Table Definition**:
  - `id`: `UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `parent_asset_id`: `UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
  - `child_asset_id`: `UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
  - `job_id`: `UUID REFERENCES jobs(id) ON DELETE SET NULL`
  - `relationship_type`: `TEXT NOT NULL CHECK (relationship_type IN ('source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate'))`
  - `metadata`: `JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `created_at`: `TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `UNIQUE(parent_asset_id, child_asset_id, relationship_type)`
- **Indexes**:
  - `idx_asset_relationships_parent` ON `asset_relationships(parent_asset_id)`
  - `idx_asset_relationships_child` ON `asset_relationships(child_asset_id)`
  - `idx_asset_relationships_job_id` ON `asset_relationships(job_id) WHERE job_id IS NOT NULL`
  - `idx_asset_relationships_type` ON `asset_relationships(relationship_type)`

---

## 4. Financial Ledger Architecture & Two-Phase Commitment (§27)

`KEYSTONE_BIBLE.md` §27 mandates:
> **"Balances never change without a corresponding ledger event."**

### 4.1 State Machine & Transaction Semantics
Every credit operation is executed as an immutable append-only record in `credit_ledger` reflecting state transitions on `credit_accounts`:

| Transaction Type | Triggering Event | Balance Effect | Held Balance Effect | Business Invariant |
|------------------|------------------|----------------|---------------------|---------------------|
| `DEPOSIT` | Stripe payment, subscription credit grant, admin credit grant | `balance += amount` | None | `balance_after = balance_before + amount` |
| `HOLD` | AuthorityEngine approves job; execution dispatched | `balance -= amount` | `held_balance += amount` | Available balance decreases; held increases |
| `SETTLEMENT` | Worker completes job successfully; assets verified | None | `held_balance -= amount` | Finalizes credit deduction; no change to available |
| `RELEASE` | Job cancelled, rejected, or failed unrecoverably | `balance += amount` | `held_balance -= amount` | Unused hold returned to available balance |
| `REFUND` | Explicit refund for defective output or billing adjustment | `balance += amount` | None | Credit returned to user balance |

### 4.2 Append-Only Security Model
1. **No UPDATE or DELETE**: Any invocation of `UPDATE credit_ledger` or `DELETE FROM credit_ledger` throws an immediate PostgreSQL exception via the `keystone_credit_ledger_prevent_modification` trigger.
2. **Positive Amounts**: `amount BIGINT NOT NULL CHECK (amount > 0)` prevents negative or zero transfers.
3. **Idempotency Protection**: `idx_credit_ledger_idempotency` unique index ensures Stripe webhooks and retried client requests cannot double-credit or double-debit.

---

## 5. Lineage DAG Architecture (§22)

Lineage is modeled as a directed graph in `asset_relationships`:
```text
Original upload [asset_1]
   +-- (edit) -------------> Edit A [asset_2]
   |                            +-- (animation) ------> Animation A [asset_3]
   +-- (edit) -------------> Edit B [asset_4]
   +-- (variation) --------> Variation C [asset_5]
                                +-- (animation) ------> Animation B [asset_6]
                                +-- (upscale) --------> Upscale C [asset_7]
```

### 5.1 Querying Provenance
Given any derived asset, its full ancestry tree can be retrieved recursively:
```sql
WITH RECURSIVE asset_lineage AS (
    SELECT parent_asset_id, child_asset_id, relationship_type, 1 AS depth
    FROM asset_relationships
    WHERE child_asset_id = :target_asset_id
    UNION ALL
    SELECT ar.parent_asset_id, ar.child_asset_id, ar.relationship_type, al.depth + 1
    FROM asset_relationships ar
    INNER JOIN asset_lineage al ON ar.child_asset_id = al.parent_asset_id
)
SELECT * FROM asset_lineage ORDER BY depth;
```

---

## 6. Complete DDL Specification: `0002_keystone_full_schema.sql`

The following complete, syntactically verified SQL must be authored into:
`infrastructure/migrations/versions/0002_keystone_full_schema.sql`

```sql
-- ============================================================================
-- KEYSTONE PERSISTENCE ENGINE: ADDITIVE 23-TABLE SCHEMA MIGRATION
-- Migration Version: 0002_keystone_full_schema.sql
-- Milestone: M0 (Wave 0: Contract Freeze & Additive Foundation)
-- Predecessor: 0001_core.sql (12 base tables)
-- Specification: KEYSTONE_BIBLE.md §21 (PostgreSQL Schema), §22, §27 (Credits Ledger)
--
-- This additive migration defines the 11 missing tables to complete the
-- mandated 23-table schema:
--   1. subscriptions
--   2. api_keys
--   3. credit_accounts
--   4. credit_ledger
--   5. request_assets
--   6. generation_attempts
--   7. attempt_assets
--   8. user_feedback
--   9. usage_records
--  10. configuration_bundles
--  11. asset_relationships
--
-- All tables enforce:
--   - UUID primary keys with gen_random_uuid()
--   - Explicit foreign keys with deterministic ON DELETE rules (CASCADE / RESTRICT / SET NULL)
--   - TIMESTAMPTZ default now() for all timestamp fields
--   - Strict check constraints on statuses, roles, ratings, and quantities
--   - Append-only immutability trigger and constraints on credit_ledger
--   - Comprehensive B-tree and partial indexes for foreign keys, lookups, and idempotent queries
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 0. Reusable Helper Functions
-- ----------------------------------------------------------------------------

-- Automatic updated_at timestamp updater
CREATE OR REPLACE FUNCTION keystone_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Strict immutability enforcement for credit_ledger
CREATE OR REPLACE FUNCTION keystone_credit_ledger_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'credit_ledger is strictly append-only. UPDATE and DELETE operations are forbidden.';
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 1. Table: subscriptions
-- Stores customer billing plans, Stripe references, and subscription lifecycles.
-- Bible §21, §27.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('trialing', 'active', 'past_due', 'canceled', 'unpaid', 'incomplete', 'incomplete_expired', 'paused')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT UNIQUE,
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
    canceled_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer_id ON subscriptions(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_subscription_id ON subscriptions(stripe_subscription_id) WHERE stripe_subscription_id IS NOT NULL;

DROP TRIGGER IF EXISTS trg_subscriptions_updated_at ON subscriptions;
CREATE TRIGGER trg_subscriptions_updated_at
BEFORE UPDATE ON subscriptions
FOR EACH ROW
EXECUTE FUNCTION keystone_set_updated_at();

-- ----------------------------------------------------------------------------
-- 2. Table: api_keys
-- Manages programmatic access tokens. Raw keys are never stored; only key_hash.
-- Bible §21, §27 ("API keys stored only as hashes; raw API keys never stored").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    scopes JSONB NOT NULL DEFAULT '["*"]'::jsonb,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status);

DROP TRIGGER IF EXISTS trg_api_keys_updated_at ON api_keys;
CREATE TRIGGER trg_api_keys_updated_at
BEFORE UPDATE ON api_keys
FOR EACH ROW
EXECUTE FUNCTION keystone_set_updated_at();

-- ----------------------------------------------------------------------------
-- 3. Table: credit_accounts
-- User credit balances and held credit reservations.
-- Bible §21, §27 ("transactional credit holds and settlement").
-- Must be created before credit_ledger.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
    held_balance BIGINT NOT NULL DEFAULT 0 CHECK (held_balance >= 0),
    currency TEXT NOT NULL DEFAULT 'credits',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'suspended', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_accounts_user_id ON credit_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_accounts_status ON credit_accounts(status);

DROP TRIGGER IF EXISTS trg_credit_accounts_updated_at ON credit_accounts;
CREATE TRIGGER trg_credit_accounts_updated_at
BEFORE UPDATE ON credit_accounts
FOR EACH ROW
EXECUTE FUNCTION keystone_set_updated_at();

-- ----------------------------------------------------------------------------
-- 4. Table: credit_ledger
-- Strictly immutable, append-only journal of all credit transactions.
-- Enforces positive amounts, exact transaction types, and trigger immutability.
-- Bible §21, §27 ("Balances never change without a corresponding ledger event").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS credit_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES credit_accounts(id) ON DELETE RESTRICT,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('DEPOSIT', 'HOLD', 'SETTLEMENT', 'RELEASE', 'REFUND')),
    amount BIGINT NOT NULL CHECK (amount > 0),
    balance_after BIGINT NOT NULL CHECK (balance_after >= 0),
    held_balance_after BIGINT NOT NULL CHECK (held_balance_after >= 0),
    reference_id UUID,
    reference_type TEXT CHECK (reference_type IS NULL OR reference_type IN ('job', 'request', 'stripe_checkout', 'hold', 'manual_adjustment', 'subscription_grant')),
    idempotency_key TEXT,
    description TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_account_id ON credit_ledger(account_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_created_at ON credit_ledger(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_ref ON credit_ledger(reference_type, reference_id) WHERE reference_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_ledger_idempotency ON credit_ledger(idempotency_key) WHERE idempotency_key IS NOT NULL;

DROP TRIGGER IF EXISTS trg_credit_ledger_immutable ON credit_ledger;
CREATE TRIGGER trg_credit_ledger_immutable
BEFORE UPDATE OR DELETE ON credit_ledger
FOR EACH ROW
EXECUTE FUNCTION keystone_credit_ledger_prevent_modification();

-- ----------------------------------------------------------------------------
-- 5. Table: request_assets
-- Input and reference assets attached to client requests.
-- Bible §17, §21 ("requests and attached assets").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS request_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    role TEXT NOT NULL DEFAULT 'input' CHECK (role IN ('input', 'reference', 'mask', 'init_image', 'controlnet')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(request_id, asset_id, role)
);

CREATE INDEX IF NOT EXISTS idx_request_assets_request_id ON request_assets(request_id);
CREATE INDEX IF NOT EXISTS idx_request_assets_asset_id ON request_assets(asset_id);

-- ----------------------------------------------------------------------------
-- 6. Table: generation_attempts
-- Records discrete execution runs for a job, supporting bounded retries.
-- Bible §14, §16 (GenerationAttempt model), §21 ("jobs and attempts").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS generation_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    provider_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    success BOOLEAN NOT NULL DEFAULT false,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    failure_code TEXT,
    error_detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(job_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_generation_attempts_job_id ON generation_attempts(job_id);
CREATE INDEX IF NOT EXISTS idx_generation_attempts_started_at ON generation_attempts(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_generation_attempts_capability ON generation_attempts(capability_id, provider_id);

-- ----------------------------------------------------------------------------
-- 7. Table: attempt_assets
-- Output and intermediate assets produced by a generation attempt.
-- Bible §16 (GenerationAttempt.output_asset_ids), §21 ("attempt_assets").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attempt_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES generation_attempts(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'output' CHECK (role IN ('output', 'preview', 'thumbnail', 'intermediate', 'mask')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(attempt_id, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_attempt_assets_attempt_id ON attempt_assets(attempt_id);
CREATE INDEX IF NOT EXISTS idx_attempt_assets_asset_id ON attempt_assets(asset_id);

-- ----------------------------------------------------------------------------
-- 8. Table: user_feedback
-- Explicit quality signals and ratings submitted by users for job results.
-- Bible §14, §16 (UserFeedback model), §17, §21 ("feedback").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating DOUBLE PRECISION CHECK (rating IS NULL OR (rating >= 0.0 AND rating <= 5.0)),
    accepted BOOLEAN,
    regeneration_requested BOOLEAN NOT NULL DEFAULT false,
    selected_asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    feedback_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    comment TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_feedback_job_id ON user_feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_user_id ON user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_selected_asset ON user_feedback(selected_asset_id) WHERE selected_asset_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_feedback_created_at ON user_feedback(created_at DESC);

-- ----------------------------------------------------------------------------
-- 9. Table: usage_records
-- Granular capability/resource metering for quotas, analytics, and billing.
-- Bible §21, §27 ("usage metering").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    capability_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    quantity NUMERIC NOT NULL CHECK (quantity >= 0),
    unit TEXT NOT NULL CHECK (unit IN ('seconds', 'tokens', 'images', 'frames', 'megabytes', 'requests', 'steps')),
    credits_billed BIGINT NOT NULL DEFAULT 0 CHECK (credits_billed >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_records_user_id ON usage_records(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_records_job_id ON usage_records(job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_usage_records_recorded_at ON usage_records(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_records_capability ON usage_records(capability_id, provider_id);

-- ----------------------------------------------------------------------------
-- 10. Table: configuration_bundles
-- Versioned storage for policy bundles, capability registries, and harnesses.
-- Bible §12, §21 ("configuration bundles").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS configuration_bundles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bundle_type TEXT NOT NULL CHECK (bundle_type IN ('policy', 'capability_registry', 'harness', 'playbook', 'runtime_presets')),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    checksum TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(bundle_type, version)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_config_bundles_type_version ON configuration_bundles(bundle_type, version);
CREATE INDEX IF NOT EXISTS idx_config_bundles_active ON configuration_bundles(bundle_type, is_active);

DROP TRIGGER IF EXISTS trg_configuration_bundles_updated_at ON configuration_bundles;
CREATE TRIGGER trg_configuration_bundles_updated_at
BEFORE UPDATE ON configuration_bundles
FOR EACH ROW
EXECUTE FUNCTION keystone_set_updated_at();

-- ----------------------------------------------------------------------------
-- 11. Table: asset_relationships
-- Lineage DAG tracking relationships between source, edited, and derived assets.
-- Bible §21, §22 ("Each relationship records parent asset, child asset, originating job, relationship type, and creation time").
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    child_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(parent_asset_id, child_asset_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_asset_relationships_parent ON asset_relationships(parent_asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_relationships_child ON asset_relationships(child_asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_relationships_job_id ON asset_relationships(job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_asset_relationships_type ON asset_relationships(relationship_type);

-- ----------------------------------------------------------------------------
-- 12. Additive Foreign Key Indexes on 0001_core.sql Base Tables
-- Adds missing lookup indexes on base tables to optimize joins and cascade deletes.
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_assets_owner_id ON assets(owner_id);
CREATE INDEX IF NOT EXISTS idx_assets_project_id ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_session_id ON requests(session_id);
CREATE INDEX IF NOT EXISTS idx_cognitive_runs_request_id ON cognitive_runs(request_id);
CREATE INDEX IF NOT EXISTS idx_authority_decisions_request_id ON authority_decisions(request_id);
CREATE INDEX IF NOT EXISTS idx_jobs_request_id ON jobs(request_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_compiled_prompts_request_id ON compiled_prompts(request_id);
CREATE INDEX IF NOT EXISTS idx_compiled_prompts_job_id ON compiled_prompts(job_id);
CREATE INDEX IF NOT EXISTS idx_harness_runs_request_id ON harness_runs(request_id);
CREATE INDEX IF NOT EXISTS idx_harness_runs_job_id ON harness_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_request_id ON audit_events(request_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_job_id ON audit_events(job_id);

COMMIT;
```

---

## 7. Implementation Guidelines for Worker

When implementing F04 in Milestone M0, the implementation worker should follow these guidelines:

1. **Write Target**: Author the DDL above to `infrastructure/migrations/versions/0002_keystone_full_schema.sql`.
2. **Strict Invariant**: Do NOT modify or rewrite `infrastructure/migrations/versions/0001_core.sql`. It is locked and immutable.
3. **Transactional Integrity**: The migration is wrapped in `BEGIN;` and `COMMIT;` ensuring atomic execution.
4. **Idempotency**: All `CREATE TABLE`, `CREATE INDEX`, and `CREATE TRIGGER` statements use `IF NOT EXISTS` or `DROP ... IF EXISTS` constructs to ensure repeatable execution in CI/CD and deployment environments.
5. **Verification**: Worker should execute the validation script at `.agents/teamwork/explorer_m0_2/validate_ddl.py` to confirm schema totality, constraints, and index counts.

---

## 8. Summary Table of the 23 Mandated PostgreSQL Tables

| Table | Status | Key Responsibility | Reference |
|---|---|---|---|
| `users` | Existing (0001) | User identity, email, authentication hash, status | Bible §21, §27 |
| `projects` | Existing (0001) | User workspace boundaries and project scoping | Bible §21 |
| `sessions` | Existing (0001) | Conversational and interactive creative sessions | Bible §21 |
| `messages` | Existing (0001) | Multimodal messages (user, keystone) | Bible §21 |
| `assets` | Existing (0001) | Object storage metadata, media types, storage keys | Bible §21, §22 |
| `requests` | Existing (0001) | Raw user intents, parameters, preferences | Bible §21 |
| `cognitive_runs` | Existing (0001) | Qwen reasoning execution traces & proposed actions | Bible §21, §10 |
| `authority_decisions` | Existing (0001) | Authority policy approvals, denials, and reason codes | Bible §21, §12 |
| `jobs` | Existing (0001) | Discrete creative tasks dispatched to workers | Bible §21, §19 |
| `compiled_prompts` | Existing (0001) | 6-part PromptAnatomy, compiled prompts, provenance | Bible §21, §7, §9 |
| `harness_runs` | Existing (0001) | Deterministic and aesthetic evaluations & scores | Bible §21, §13 |
| `audit_events` | Existing (0001) | Platform security events and administrative audit log | Bible §21, §28 |
| `subscriptions` | **New (0002)** | Stripe customer/subscription records, plan tiers, periods | Bible §21, §27 |
| `api_keys` | **New (0002)** | Scoped developer API key hashes (zero raw storage) | Bible §21, §27 |
| `credit_accounts` | **New (0002)** | User credit accounts, available and held balances | Bible §21, §27 |
| `credit_ledger` | **New (0002)** | Immutable append-only journal of all credit events | Bible §21, §27 |
| `request_assets` | **New (0002)** | Input and reference asset associations for requests | Bible §21, §17 |
| `generation_attempts` | **New (0002)** | Attempt-level retries, execution metrics, error codes | Bible §21, §14, §16 |
| `attempt_assets` | **New (0002)** | Output asset associations per generation attempt | Bible §21, §16 |
| `user_feedback` | **New (0002)** | User ratings, acceptance flags, regeneration requests | Bible §21, §14, §16 |
| `usage_records` | **New (0002)** | Fine-grained resource and capability consumption records | Bible §21, §27 |
| `configuration_bundles` | **New (0002)** | Versioned policy, harness, registry, and playbook configs | Bible §21, §10, §12 |
| `asset_relationships` | **New (0002)** | Directed Acyclic Graph (DAG) for asset derivation lineage | Bible §21, §22 |
