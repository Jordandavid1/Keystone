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
