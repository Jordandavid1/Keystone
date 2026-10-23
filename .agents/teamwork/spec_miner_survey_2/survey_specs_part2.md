# KEYSTONE Specification Mining Survey: Part 2 (§21 through §38)

**Document Status:** Authoritative Spec Mining Report  
**Survey Agent:** `spec_miner_survey_2` (Teamwork Specification Miner)  
**Parent Agent:** Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Target Repository:** `c:\Users\Lesia Eden\Downloads\keystone-cowork`  
**Canonical Spec Source:** `KEYSTONE_BIBLE.md` (SHA-256: `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`)  
**Directives Referenced:** `ORIGINAL_REQUEST.md` (Founder Directives through 2026-10-22T16:13:56Z)  

---

## 1. Executive Summary & Verification Context

This specification mining report covers Part 2 of `KEYSTONE_BIBLE.md` (Sections 21 through 38) and the associated founder requirements recorded in `ORIGINAL_REQUEST.md`. 

The canonical specification establishes KEYSTONE as the prompt-intelligence engine, prompting authority, cognition controller, workflow orchestrator, and quality controller for a multimodal creative AI platform. The core invariant remains:
> **Tools contribute. Qwen reasons. Harnesses measure. KEYSTONE prompts and decides.**

### 1.1 Invariant Checksum & Integrity
- **Canonical Bible SHA-256:** `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788` (Verified unmodified).
- **Pre-built Baseline:** `npm test` (3 identity tests) and `tests/e2e/runner.js` (Run 1 benchmark intelligence test suite) verified passing at 100% green.
- **Closed Source & Proprietary Rule:** Strictly private repositories, secret-scanning pre-push tooling, and zero leaks of proprietary code or credentials.

---

## 2. Features Discovered

The following comprehensive matrix documents all features, capabilities, operational interfaces, and rules extracted from Sections 21 through 38 of `KEYSTONE_BIBLE.md` and related founder directives.

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Database & Schema | PostgreSQL 23-Table Storage Engine | Durable relational truth store for all tenant, session, asset, cognitive, authority, job, ledger, and audit entities | Relational rows, JSONB payloads, UUIDs | Persisted rows, foreign-key graphs | Reject invalid FKs, violate unique constraints, reject raw API keys | Bible §21, §16 |
| 2 | Database & Schema | Immutable Credit Ledger | Append-only financial ledger tracking all credit holds, settlements, refunds, and grants | `account_id`, `entry_type`, `amount`, `idempotency_key`, `reference_id` | Immutable ledger row, atomic balance adjustment | Reject updates/deletions; reject duplicate idempotency keys | Bible §21, §27 |
| 3 | Database & Schema | Alembic Migration Control | Version-controlled, forward-only database migrations for schema evolution | Python Alembic migration scripts (`alembic upgrade head`) | Upgraded PostgreSQL schema state | Abort on failed migration; rollback current transaction | Bible §21, §31, §38 |
| 4 | Asset & Lineage | Short-Expiry Signed URL Access | Media binaries reside in object storage; client access is mediated by time-bounded signed URLs | `asset_id`, user JWT, operation (`read` / `upload`) | Signed HTTPS URL (e.g. 15-minute validity) | 401 Unauthorized if token invalid; 403 Forbidden if not tenant owner | Bible §22, §28 |
| 5 | Asset & Lineage | Asset Lineage DAG Engine | Directed acyclic graph tracking source, edit, variation, animation, upscale, and reference relationships | `parent_asset_id`, `child_asset_id`, `job_id`, `relationship_type` | `asset_relationships` record, navigable DAG tree | Reject circular dependencies; reject orphan relationships | Bible §22 |
| 6 | Creative Fabric | ComfyUI Execution Adapter | Headless workflow engine executing generative graph pipelines for images, video, and enhancement | Signed `ExecutionEnvelope`, workflow JSON, input asset URLs | Output media binaries, execution metrics | Return standardized failure code (`ERR_WORKFLOW_TIMEOUT`, `ERR_VRAM_OOM`); trigger retry | Bible §23, §8 |
| 7 | Creative Fabric | Wan Image-to-Video (I2V) Pipeline | Video generation transforming input still image and motion prompt into coherent video | Input `asset_id`, motion parameters, positive/negative prompts | Rendered video asset (MP4/WebM), duration, FPS | Reject unapproved aspect ratios/resolutions; fail if input image missing | Bible §23, §33, §35 |
| 8 | Creative Fabric | Wan Text-to-Video (T2V) Pipeline | Direct cinematic video synthesis from text prompt and stylistic guidance | Positive/negative text prompts, aspect ratio, duration, camera motion | Rendered video asset, generation attempt record | Reject out-of-bound parameters; retry on sub-threshold quality | Bible §23, §33 |
| 9 | Creative Fabric | Identity Preservation (FaceFusion) | Face transfer and identity consistency pipeline across shots and animation frames | Target video/image, reference face asset, alignment parameters | Identity-consistent child asset, confidence score | Fail on no face detected or corrupted reference; flag in harness | Bible §23, §32 |
| 10 | Creative Fabric | Upscale & Enhancement Pipeline | Spatial/temporal resolution enhancement (e.g., Real-ESRGAN / Spandrel) | Source low-res asset, scale factor (2x, 4x), denoise profile | Enhanced high-res child asset with `upscale` lineage | Return failure if image exceeds maximum GPU dimension limits | Bible §23, §32 |
| 11 | Creative Fabric | Adapter Capability Contract | Standardized registration manifest for all generative and transformation workers | `CapabilityManifest` declaration | Registered provider in `CapabilityRegistry` | Reject unregistered or malformed adapter manifests | Bible §23, §8 |
| 12 | Kaggle Bootstrap | Hardware Runtime Discovery Probe | Boot-time environment probe measuring GPUs, VRAM, RAM, CUDA, and model cache | System calls, `nvidia-smi`, `psutil`, PyTorch device properties | `HardwareProfile` JSON payload (GPU count, VRAM, RAM, disk) | Abort boot if zero GPUs or host RAM below safety floor | Bible §24 |
| 13 | Kaggle Bootstrap | MemoryHarness & Host RAM Offload | Dynamic offload calculation keeping weights in GPU VRAM and offloading remainder to ~80GB host RAM | Measured VRAM (2x T4 16GB), measured host RAM, model weight estimate (51.7GB) | `offload_gib`, GPU reserve, host reserve, batch limits | Assert offload fits in measured available RAM; fail before OOM | Bible §24, Founder Directive |
| 14 | Kaggle Bootstrap | Controlled Retry Profiles | 7-step progressive degradation sequence to prevent OOM without replacing model identity | Failed attempt metrics, current profile index | Next tuned runtime configuration (context, concurrency, batch) | Halt and report evidence after Profile 7; NEVER substitute model | Bible §24, §11 |
| 15 | Kaggle Bootstrap | Pinned Abliterated Checkpoint | Invariant serving of `huihui-ai/Huihui-Qwen3.8-27B-abliterated` via vLLM TP=2 | Model ID, Hugging Face auth token, model weights | Running vLLM inference server | Refuse to swap with aligned, quantized, or smaller model | Bible §24, §11, §2 |
| 16 | Kaggle Bootstrap | Ephemeral Tunnel Re-registration | Ephemeral Kaggle worker connects to Cloud Run control plane without redeployment | Ephemeral tunnel URL (Cloudflare/ngrok), HMAC signature, worker identity | Keystone acknowledges and routes jobs to active worker | Reject unauthenticated or expired worker registration handshakes | Bible §24, §18, R2 |
| 17 | Kaggle Bootstrap | Post-Build BF16 vs FP16 Benchmark | Verification protocol comparing BF16 vs FP16 on T4x2 hardware after full completion | Fixed evaluation prompt set, test harnesses | Benchmark report: load, VRAM, latency, tokens/s, validity, quality, NaNs | Record all errors and numerical instability; founder decides default | Founder Directive (16:13:56Z) |
| 18 | Workspace | Canvas-First Premium Interface | 5-region creative desktop UI prioritizing media over conversation | User input, project assets, active media state | Rendered interactive canvas, comparison viewer, inspector | Display contextual error banners; keep conversation history intact | Bible §25, Epic I |
| 19 | Workspace | Job Lifecycle Progress Language | Structured, non-technical user feedback mirroring exact execution stages | Job state changes, worker progress events (SSE) | Live user progress string ("Understanding...", "Creating...", etc.) | Fallback to "Refining when necessary" during automatic retry | Bible §25, §19 |
| 20 | Workspace | Split-View & Synchronized Compare | Visual comparison interface for still images and synchronized multi-video playback | Two or more asset IDs (source vs edit vs variation) | Side-by-side or split-slider visual comparison view | Gracefully degrade if media formats or dimensions are incompatible | Bible §25 |
| 21 | Workspace | Mobile Review & Approval Experience | Responsive lightweight mobile interface for reviewing, approving, and sharing outputs | Touch events, project assets, approval actions | Quick preview, approval button, download link | Restrict heavy canvas editing tools; present streamlined review view | Bible §25 |
| 22 | Workspace | Operator Admin Workspace | Separate administrative console for telemetry, job inspection, and diagnostics | Admin auth token, job/user query filters | System metrics, queue health, user audit traces, logs | 403 Forbidden for non-admin tokens; redacts PII automatically | Bible §26, Epic I |
| 23 | Auth & Billing | Transactional Credit Hold & Settle | Two-phase commit credit reservation preventing overdrafts and double charges | `user_id`, `job_id`, estimated cost | Credit hold created; settlement on completion; release on fail | Reject job creation if `balance - held_balance < required_credits` | Bible §27 |
| 24 | Auth & Billing | Stripe Test-Mode Integration | Subscription checkout, portal management, and credit pack purchase via Stripe API | Stripe webhook events, customer sessions | Updated subscription status, credited ledger entry | Idempotent ignore for repeated webhooks; alert on invalid signatures | Bible §27 |
| 25 | Security | Tenant Isolation & Scoping | Row-level and storage-level isolation ensuring zero cross-tenant data exposure | Authenticated `user_id` from JWT | Tenant-scoped database queries and signed object keys | 404 Not Found or 403 Forbidden on foreign asset/job access | Bible §28 |
| 26 | Security | Worker Execution Envelope Verification | Cryptographic envelope ensuring workers only run validated Keystone requests | `ExecutionEnvelope`, RSA/HMAC signature, nonce, timestamp | Verification PASS / REJECT at worker boundary | Worker drops unsigned, expired, replayed, or altered envelopes | Bible §28, §12 |
| 27 | Security & Legal | Proprietary Guarded Publication Tooling | Pre-push hooks and verification scripts preventing accidental public repository push | Git push invocation, remote URL, staged files | Push allowed (if private and clean) or rejected with error | Block push if remote is public or uncommitted secrets are detected | Bible §29, §38 |
| 28 | Legal Suite | Data-Flow-Derived Legal Documentation | 10 commercial legal documents drafted from actual platform data flows | Technical data architecture, third-party subprocessor inventory | Markdown legal drafts marked "Draft - Pending Qualified Legal Review" | Flag unmapped data flows or unvetted third-party licenses | Bible §30 |
| 29 | Testing & Quality | Alpha Gate Verification Suite | 13-point operational gate checklist verifying end-to-end functionality | Alpha test script execution against deployment | Binary pass/fail evidence per bullet | Block deployment if any single alpha gate check fails | Bible §34 |
| 30 | Testing & Quality | Live Cloud Run E2E & Recovery Test | Live automated test script executing complete creative cycle and worker crash recovery | Live Cloud Run URL, image upload, animation prompt, worker kill signal | E2E success logs, recovered job state after worker termination | Fail test if credits debited twice, project state lost, or job hung | Bible §35 |
| 31 | Governance | Change Control Invariant Protocol | Mandatory 7-step governance procedure for altering any locked architectural invariant | Written ADR, founder approval, impact analysis, KHF coverage, rollback | Versioned contract update or rejection | Rejection of unauthorized invariant modifications by any agent/tool | Bible §37, §2 |

---

## 3. Edge Cases & Boundary Conditions

| # | Feature | Input / Condition | Observed / Mandated Specification Behavior |
|---|---------|-------------------|---------------------------------------------|
| 1 | Credit Ledger | Webhook arrives twice for identical Stripe charge ID | Second webhook matches existing `idempotency_key` in `credit_ledger`; transaction is acknowledged with HTTP 200 without duplicate credit grant. |
| 2 | Credit Ledger | Generation job fails after credits were placed on `hold` | System executes automatic `release` ledger entry, moving held amount back to usable balance; zero credits are settled or deducted. |
| 3 | Memory Harness | Boot-time probe detects only 24GB host RAM instead of expected ~80GB | MemoryHarness recalculates offload ceiling; asserts that `offload <= host_available - host_reserve`; halts boot with diagnostic error rather than crashing mid-run. |
| 4 | Cognitive Serving | vLLM encounters CUDA OOM during large multi-turn vision prompt | Controlled Retry Profile kicks in: reduces context length, drops max concurrent sequences to 1, adjusts CPU offload. Checkpoint is NEVER swapped for quantized substitute. |
| 5 | Worker Security | Malicious worker or compromised client attempts to execute job with modified prompt | Worker verifies `ExecutionEnvelope` signature against KEYSTONE public key. Hash mismatch between approved prompt and execution arguments causes immediate rejection. |
| 6 | Creative Adapter | Generator output produces solid black frames or broken video codec | KHF Technical Output Harness catches empty/blank frames and invalid headers; flags attempt as failed; initiates bounded quality retry with revised parameters. |
| 7 | Job State Machine | Browser disconnects or user refreshes page while job is in `RUNNING` stage | Job state continues executing on background Celery/Kaggle worker; upon reconnect/refresh, client fetches `GET /v1/jobs/{job_id}` and restores progress seamlessly. |
| 8 | Disaster Recovery | Worker process crashes or Kaggle notebook kernel dies mid-generation | Cloud Run API watchdog detects missed worker heartbeat; marks job `RETRY_PENDING` or `FAILED`; re-enqueues job to healthy worker without double credit debit. |
| 9 | Multi-Tenancy | Authenticated User A attempts to access `GET /v1/assets/{asset_id_of_user_b}` | SQL query enforces `WHERE id = :asset_id AND owner_id = :current_user_id`; returns HTTP 404 Not Found to prevent tenant asset enumeration. |
| 10 | Prompt Compilation | User inputs adversarial prompt injection inside attached image description | Aikido Prompt Injection Defense quarantines untrusted text inside `<untrusted_content>` tags, escapes closing delimiters, and scrubs prompt leakage before compiler passes it to Qwen. |

---

## 4. Deep Specification Analysis by Domain

### 4.1 PostgreSQL Schema & Alembic Migrations (§21, §16, §19, §27)

PostgreSQL is the durable source of truth for the entire platform. Redis and Celery handle transient coordination, but no transaction or state transition is finalized without PostgreSQL persistence.

#### 4.1.1 The 23 Required Tables
Section 21 mandates 23 specific tables. Below is the complete structural schema specification:

1. **`users`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `email TEXT NOT NULL UNIQUE`
   - `password_hash TEXT` (Argon2id/bcrypt; null if external IdP)
   - `display_name TEXT`
   - `status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted'))`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

2. **`subscriptions`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `plan_id TEXT NOT NULL` ('free', 'creator_pro', 'studio')
   - `status TEXT NOT NULL CHECK (status IN ('active', 'trialing', 'past_due', 'canceled', 'unpaid'))`
   - `current_period_start TIMESTAMPTZ NOT NULL`
   - `current_period_end TIMESTAMPTZ NOT NULL`
   - `cancel_at_period_end BOOLEAN NOT NULL DEFAULT false`
   - `stripe_customer_id TEXT UNIQUE`
   - `stripe_subscription_id TEXT UNIQUE`
   - `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

3. **`api_keys`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `name TEXT NOT NULL`
   - `key_hash TEXT NOT NULL UNIQUE` (SHA-256 of raw secret; raw secret NEVER stored)
   - `key_prefix TEXT NOT NULL` (e.g. `ks_live_...` first 8 chars)
   - `scopes JSONB NOT NULL DEFAULT '["all"]'::jsonb`
   - `expires_at TIMESTAMPTZ`
   - `last_used_at TIMESTAMPTZ`
   - `revoked_at TIMESTAMPTZ`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

4. **`projects`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `name TEXT NOT NULL`
   - `description TEXT`
   - `status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted'))`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

5. **`sessions`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `project_id UUID REFERENCES projects(id) ON DELETE CASCADE`
   - `title TEXT`
   - `status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted'))`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

6. **`messages`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE`
   - `role TEXT NOT NULL CHECK (role IN ('user', 'keystone', 'system'))`
   - `content TEXT NOT NULL`
   - `metadata JSONB NOT NULL DEFAULT '{}'::jsonb` (e.g. intent hint, attached assets)
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

7. **`assets`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `project_id UUID REFERENCES projects(id) ON DELETE SET NULL`
   - `media_type TEXT NOT NULL CHECK (media_type IN ('image', 'video', 'audio', 'document', 'other'))`
   - `mime_type TEXT NOT NULL`
   - `storage_provider TEXT NOT NULL` ('gcs', 's3', 'local')
   - `storage_key TEXT NOT NULL`
   - `byte_size BIGINT NOT NULL CHECK (byte_size >= 0)`
   - `width INTEGER`
   - `height INTEGER`
   - `duration_seconds DOUBLE PRECISION`
   - `status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('uploading', 'available', 'processing', 'failed', 'deleted'))`
   - `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `deleted_at TIMESTAMPTZ`
   - `CONSTRAINT uq_storage UNIQUE (storage_provider, storage_key)`

8. **`requests`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
   - `session_id UUID REFERENCES sessions(id) ON DELETE SET NULL`
   - `message_id UUID REFERENCES messages(id) ON DELETE SET NULL`
   - `request_text TEXT NOT NULL`
   - `preferences JSONB NOT NULL DEFAULT '{}'::jsonb`
   - `state TEXT NOT NULL DEFAULT 'created' CHECK (state IN ('created', 'processing', 'completed', 'failed', 'cancelled'))`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `completed_at TIMESTAMPTZ`

9. **`request_assets`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE`
   - `asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
   - `role TEXT NOT NULL DEFAULT 'input' CHECK (role IN ('input', 'reference', 'mask', 'target'))`
   - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
   - `CONSTRAINT uq_request_asset UNIQUE (request_id, asset_id)`

10. **`cognitive_runs`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE`
    - `model_id TEXT NOT NULL` ('huihui-ai/Huihui-Qwen3.8-27B-abliterated')
    - `provider_id TEXT NOT NULL` ('vllm', 'kaggle')
    - `prompt_hash TEXT NOT NULL`
    - `prompt_version TEXT NOT NULL`
    - `proposed_action JSONB NOT NULL` (structured ProposedAction payload)
    - `confidence DOUBLE PRECISION`
    - `metrics JSONB NOT NULL DEFAULT '{}'::jsonb` (vram_used, latency_ms, tokens_generated)
    - `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `completed_at TIMESTAMPTZ`

11. **`authority_decisions`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE`
    - `cognitive_run_id UUID REFERENCES cognitive_runs(id) ON DELETE SET NULL`
    - `decision TEXT NOT NULL CHECK (decision IN ('approve', 'deny', 'replan'))`
    - `capability_id TEXT`
    - `provider_id TEXT`
    - `sanitized_arguments JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb`
    - `policy_bundle_version TEXT NOT NULL`
    - `capability_registry_version TEXT NOT NULL`
    - `harness_bundle_version TEXT NOT NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

12. **`jobs`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE`
    - `authority_decision_id UUID NOT NULL REFERENCES authority_decisions(id)`
    - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
    - `capability_id TEXT NOT NULL`
    - `provider_id TEXT NOT NULL`
    - `workflow_id TEXT NOT NULL`
    - `workflow_version TEXT NOT NULL`
    - `state TEXT NOT NULL CHECK (state IN ('created', 'validating', 'planning', 'authorizing', 'queued', 'running', 'validating_output', 'retry_pending', 'replan_required', 'completed', 'failed', 'cancelled', 'rejected'))`
    - `stage TEXT NOT NULL DEFAULT 'created'` (mirrors §25 Progress Language)
    - `attempt INTEGER NOT NULL DEFAULT 0`
    - `progress DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (progress >= 0.0 AND progress <= 1.0)`
    - `priority INTEGER NOT NULL DEFAULT 100`
    - `error_code TEXT`
    - `error_detail JSONB`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

13. **`generation_attempts`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
    - `attempt_number INTEGER NOT NULL DEFAULT 1`
    - `provider_id TEXT NOT NULL`
    - `capability_id TEXT NOT NULL`
    - `prompt_hash TEXT NOT NULL`
    - `workflow_version TEXT NOT NULL`
    - `started_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `completed_at TIMESTAMPTZ`
    - `success BOOLEAN NOT NULL DEFAULT false`
    - `output_asset_ids JSONB NOT NULL DEFAULT '[]'::jsonb`
    - `metrics JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `failure_code TEXT`
    - `CONSTRAINT uq_job_attempt UNIQUE (job_id, attempt_number)`

14. **`compiled_prompts`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE`
    - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
    - `compiler_id TEXT NOT NULL`
    - `compiler_version TEXT NOT NULL`
    - `capability_id TEXT NOT NULL`
    - `provider_id TEXT NOT NULL`
    - `positive_prompt TEXT NOT NULL`
    - `negative_prompt TEXT`
    - `parameters JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `provenance JSONB NOT NULL` (contains 6-part anatomy, playbook ID, compilation rules)
    - `prompt_hash TEXT NOT NULL` (SHA-256)
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

15. **`attempt_assets`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `attempt_id UUID NOT NULL REFERENCES generation_attempts(id) ON DELETE CASCADE`
    - `asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
    - `direction TEXT NOT NULL CHECK (direction IN ('input', 'output', 'intermediate'))`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `CONSTRAINT uq_attempt_asset_direction UNIQUE (attempt_id, asset_id, direction)`

16. **`harness_runs`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `request_id UUID REFERENCES requests(id) ON DELETE SET NULL`
    - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
    - `attempt_id UUID REFERENCES generation_attempts(id) ON DELETE SET NULL`
    - `harness_id TEXT NOT NULL` ('memory', 'technical_output', 'quality_aggregator', 'aikido_defense')
    - `harness_version TEXT NOT NULL`
    - `phase TEXT NOT NULL CHECK (phase IN ('pre_execution', 'execution', 'post_execution', 'revision'))`
    - `verdict TEXT NOT NULL CHECK (verdict IN ('pass', 'warn', 'fail'))`
    - `score DOUBLE PRECISION`
    - `reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb`
    - `evidence JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

17. **`user_feedback`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE`
    - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
    - `rating DOUBLE PRECISION CHECK (rating >= 0 AND rating <= 5)`
    - `accepted BOOLEAN`
    - `regeneration_requested BOOLEAN NOT NULL DEFAULT false`
    - `selected_asset_id UUID REFERENCES assets(id) ON DELETE SET NULL`
    - `feedback_tags JSONB NOT NULL DEFAULT '[]'::jsonb`
    - `comment TEXT`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

18. **`credit_accounts`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE`
    - `balance NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (balance >= 0)`
    - `held_balance NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (held_balance >= 0)`
    - `currency TEXT NOT NULL DEFAULT 'CREDITS'`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

19. **`credit_ledger`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `account_id UUID NOT NULL REFERENCES credit_accounts(id) ON DELETE RESTRICT`
    - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
    - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
    - `entry_type TEXT NOT NULL CHECK (entry_type IN ('grant', 'purchase', 'hold', 'settlement', 'release', 'refund', 'reversal', 'adjustment'))`
    - `amount NUMERIC(14, 4) NOT NULL` (positive for credits added; negative for deductions)
    - `balance_after NUMERIC(14, 4) NOT NULL`
    - `held_balance_after NUMERIC(14, 4) NOT NULL`
    - `idempotency_key TEXT NOT NULL UNIQUE`
    - `reference_id TEXT` (Stripe charge ID, checkout session ID, or internal correlation ID)
    - `description TEXT NOT NULL`
    - `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - *Constraint:* IMMUTABLE. Postgres trigger prevents UPDATE or DELETE.

20. **`usage_records`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
    - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
    - `capability_id TEXT NOT NULL`
    - `provider_id TEXT NOT NULL`
    - `units_consumed NUMERIC(14, 4) NOT NULL`
    - `unit_type TEXT NOT NULL` ('seconds', 'tokens', 'pixels', 'calls')
    - `cost_cents INTEGER NOT NULL DEFAULT 0`
    - `credits_deducted NUMERIC(14, 4) NOT NULL DEFAULT 0`
    - `period_start TIMESTAMPTZ NOT NULL`
    - `period_end TIMESTAMPTZ NOT NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

21. **`audit_events`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `actor_type TEXT NOT NULL CHECK (actor_type IN ('user', 'system', 'admin', 'worker', 'authority'))`
    - `actor_id TEXT NOT NULL`
    - `event_type TEXT NOT NULL`
    - `request_id UUID REFERENCES requests(id) ON DELETE SET NULL`
    - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
    - `data JSONB NOT NULL DEFAULT '{}'::jsonb`
    - `ip_address TEXT`
    - `user_agent TEXT`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - *Constraint:* IMMUTABLE.

22. **`configuration_bundles`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `bundle_name TEXT NOT NULL`
    - `version TEXT NOT NULL`
    - `bundle_type TEXT NOT NULL CHECK (bundle_type IN ('policy', 'capability', 'harness', 'prompt_profile', 'system'))`
    - `payload JSONB NOT NULL`
    - `hash TEXT NOT NULL` (SHA-256)
    - `active BOOLEAN NOT NULL DEFAULT false`
    - `created_by TEXT NOT NULL`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `CONSTRAINT uq_bundle_version UNIQUE (bundle_name, version)`

23. **`asset_relationships`**:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `parent_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
    - `child_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE`
    - `job_id UUID REFERENCES jobs(id) ON DELETE SET NULL`
    - `relationship_type TEXT NOT NULL CHECK (relationship_type IN ('source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected_final', 'intermediate'))`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
    - `CONSTRAINT uq_asset_relationship UNIQUE (parent_asset_id, child_asset_id, relationship_type)`

#### 4.1.2 Alembic Evolution Rules
- `0001_core.sql` contains the initial baseline. All subsequent changes must be additive Alembic migrations (`infrastructure/migrations/versions/`).
- No retroactive modification of applied migrations.
- Migrations must be verified against live PostgreSQL (or automated docker container).

---

### 4.2 Asset Architecture & Lineage DAG (§22)

Media binaries represent high-value creator IP and large storage footprints. Therefore, binaries and metadata are strictly bifurcated:

1. **Storage Decoupling:**
   - Object storage (Google Cloud Storage in production; S3-compatible or local minio in dev) stores opaque binaries.
   - Keys are path-scoped: `tenants/{owner_id}/projects/{project_id}/{asset_id}/{filename}`.
   - PostgreSQL stores metadata, mime-type, dimensions, duration, and status.

2. **Security & Short-Expiry Signed URLs:**
   - Binaries are never served through public buckets or unrestricted endpoints.
   - Read and write operations use signed short-lived URLs (15-minute default expiry).
   - Upload verification: When a client uploads via a signed PUT URL, it notifies `POST /v1/assets/upload` or complete hook. Keystone verifies Content-Length, validates mime headers, and checks for corruption before transitioning status from `uploading` to `available`.

3. **Lineage DAG Model:**
   - Every asset produced by a generation attempt or uploaded by a user is an entity node in the lineage graph.
   - Relationships are recorded in `asset_relationships`:
     - `parent_asset_id` -> `child_asset_id`
     - `job_id`: Originating job that executed the transformation
     - `relationship_type`:
       - `source`: The root user upload or foundation media
       - `edit`: Result of an inpainting, outpainting, or brush/mask edit
       - `variation`: An alternate generation based on the same prompt/seed tree
       - `animation`: Video generated from an image (Wan I2V)
       - `upscale`: Enhanced resolution version of a parent asset
       - `reference`: Asset provided as a visual style or character reference
       - `selected_final`: Customer-selected hero asset for export or delivery
       - `intermediate`: Temporary artifacts produced during multi-stage pipelines
   - Lineage is traversable in both directions (forward tree to inspect derived work; backward tree to trace root provenance).

---

### 4.3 Creative Tool Fabric (§23)

KEYSTONE orchestrates generative workers through a decoupled adapter framework. Adapters do not directly update customer-visible project state. They return execution artifacts to KEYSTONE for quality evaluation, safety scanning, and persistence.

#### 4.3.1 Initial Adapters Suite
1. **ComfyUI Workflow Execution Adapter:**
   - Headless execution engine interacting with ComfyUI `/prompt` and WebSocket event streams.
   - Translates KEYSTONE `ExecutionEnvelope` arguments into ComfyUI workflow prompt graphs.
2. **Image Generation Compiler & Workflow:**
   - Pinned to high-fidelity diffusion models (e.g., FLUX.1 or SDXL).
   - Generates images from compiled PromptAnatomy prompts.
3. **Image Editing Workflow:**
   - Instruct-based image modification, mask inpainting, and object replacement.
4. **Wan Image-to-Video (I2V):**
   - High-motion video generation using Wan 2.1 (14B / 1.3B) conditioning on source image.
5. **Wan Text-to-Video (T2V):**
   - Direct text-to-video synthesis using Wan 2.1.
6. **FaceFusion / Identity Preservation Workflow:**
   - Identity consistency across multi-shot video and image variations.
   - Extracts face embeddings and applies face transfer/restoration.
7. **Upscale and Enhancement Workflows:**
   - Spatial upscaling (Real-ESRGAN / 4x-UltraSharp) and frame interpolation.

#### 4.3.2 Adapter Contract Specification
Every creative adapter MUST export:
- `CapabilityManifest`: Standardized JSON/Pydantic declaration of accepts, produces, parameters, and resource class.
- `ParameterSpec`: Strict validation schema (type, bounds, enums, defaults).
- `WorkflowVersion`: Explicit semantic versioning (e.g. `wan_i2v_v1.0.2`).
- `HealthStatus`: Liveness, GPU readiness, and queue depth.
- `ResourceEstimate`: VRAM requirements, host RAM footprint, execution time estimate.
- `FailureCodes`: Standardized failure classification (`ERR_VRAM_OOM`, `ERR_TIMEOUT`, `ERR_BLACK_FRAME`, `ERR_CORRUPT_INPUT`).
- `TechnicalHarness`: Automated post-execution validation routine.
- `LicenseClassification`: Commercial usability and distribution gates.

---

### 4.4 Kaggle Bootstrap Deployment (§24)

Kaggle is the Tier 0 bootstrap infrastructure. It provides two Nvidia T4 16GB GPUs (~30-32GB total VRAM) and ~80GB of host system memory.

#### 4.4.1 Dedicated Repo Workspace Structure (`KAGGLE_SETUP/`)
Per §24 and §31, `KAGGLE_SETUP/` must be structured as follows:
```text
KAGGLE_SETUP/
├── README.md                          # Comprehensive bring-up & operational runbook
├── notebooks/
│   ├── 01_keystone_cognition_bootstrap.ipynb  # Qwen 27B vLLM TP=2 + CPU offload
│   ├── 02_keystone_comfyui_runtime.ipynb      # ComfyUI, Wan, Image Gen, Upscalers
│   └── 03_keystone_integrated_gateway.ipynb   # Unified bridge / tunnel manager
├── configs/
│   ├── vllm_config.json               # Tensor parallel, offload, and context flags
│   ├── comfy_workflows/               # JSON graphs for Wan I2V, T2V, FLUX, Upscale
│   └── tunnel_config.yaml             # Cloudflare / ngrok tunnel configuration
├── scripts/
│   ├── hardware_probe.py              # Boot-time memory and GPU probe
│   ├── download_checkpoints.py        # Hugging Face authenticated model puller
│   └── start_worker.sh                # Process watchdog and startup script
├── logs/                              # Execution evidence and memory benchmark logs
└── checklists/
    ├── boot_checklist.md              # Step-by-step notebook startup guide
    └── teardown_checklist.md          # Clean session termination guide
```

#### 4.4.2 Hardware Runtime Discovery Probe
Every boot of Notebook 01 and 02 executes an automated hardware probe:
- Detects GPU count, model name, and individual VRAM totals.
- Queries `psutil.virtual_memory()` for total and available system RAM.
- Verifies CUDA version, driver version, PyTorch version, and vLLM build.
- Verifies write permissions on `/kaggle/working` and checks persistent cache `/root/.cache`.
- Emits a structured `HardwareProfile` payload.

#### 4.4.3 MemoryHarness & Host RAM Offload Strategy
The cognition model is pinned to:
`huihui-ai/Huihui-Qwen3.8-27B-abliterated` (27 Billion parameters).
- In FP16/BF16, the model weights alone require ~51.7 GiB.
- The 2x T4 GPUs provide 2x 15.0 GiB usable VRAM (~30 GiB total).
- The model **CANNOT** fit entirely within GPU VRAM in unquantized 16-bit precision.
- **The Solution (Founder Directive & §24):**
  The MemoryHarness computes the exact CPU offload ceiling:
  $$\text{offload\_gib} = \max\left(0.0, \text{MODEL\_ESTIMATE\_GIB} - \max(0.0, \text{gpu\_total} - \text{GPU\_RESERVE\_GIB})\right)$$
  - `GPU_RESERVE_GIB` = 5.0 GiB (reserved for KV cache, attention activations, and scratchpad).
  - Usable GPU memory for weights = $30.0 - 5.0 = 25.0\text{ GiB}$.
  - Weight amount offloaded to CPU host RAM = $51.7 - 25.0 = 26.7\text{ GiB}$.
  - Host RAM reserve = 12.0 GiB (reserved for OS, PyTorch buffers, disk cache).
  - Kaggle host system memory (~80 GiB) easily accommodates the 26.7 GiB offload plus 12.0 GiB reserve ($26.7 + 12.0 = 38.7\text{ GiB} < 80\text{ GiB}$).
  - The MemoryHarness enforces this check at boot.

#### 4.4.4 Controlled Retry Profiles (§24)
If memory pressure or fragmentation occurs, workers follow 7 strictly ordered retry profiles:
1. **Profile 1:** Baseline Tensor Parallel 2 (TP=2).
2. **Profile 2:** Tune CPU offload (adjust CPU offload allocation into host RAM).
3. **Profile 3:** Reduce maximum context length (e.g. from 8192 to 4096).
4. **Profile 4:** Reduce maximum concurrent sequences to 1 (`--max-num-seqs 1`).
5. **Profile 5:** Reduce batch token budget (`--max-num-batched-tokens 2048`).
6. **Profile 6:** Lower GPU-memory-utilization target when fragmentation occurs (`--gpu-memory-utilization 0.85`).
7. **Profile 7:** Stop and report evidence after approved profiles are exhausted.
- **ABSOLUTE INVARIANT:** NO automatic quantized substitute (no GGUF, AWQ, or GPTQ substitution; no substitution of an aligned or smaller checkpoint).

#### 4.4.5 Ephemeral Re-Registration Handshake
Because Kaggle sessions terminate after a maximum of 12 hours (or on idle timeout):
- Each notebook establishes a secure outward tunnel (Cloudflare Tunnel or ngrok).
- The notebook worker generates an ephemeral session key and sends a registration request to Keystone Cloud Run API (`POST /internal/workers/register`):
  ```json
  {
    "worker_id": "kaggle-worker-node-1",
    "worker_type": "cognition",
    "tunnel_url": "https://random-subdomain.trycloudflare.com",
    "public_key": "MIIBIjANBg...",
    "hardware_profile": { ... },
    "auth_token": "KS_WORKER_SECRET_TOKEN"
  }
  ```
- Keystone validates the shared secret token, verifies worker liveness, and begins routing jobs to the tunnel URL without requiring a redeployment of Cloud Run.

#### 4.4.6 Post-Build BF16 vs FP16 Comparative Benchmark Plan
Per Founder Directive (2026-10-22T16:13:56Z):
- BF16 remains the default cognition build configuration.
- After full system construction, execute a rigorous comparative benchmark on Kaggle T4x2 comparing BF16 vs FP16 on `huihui-ai/Huihui-Qwen3.8-27B-abliterated`:
  1. Boot time and model weight loading duration.
  2. GPU VRAM allocated and host RAM offloaded.
  3. Tokens/second generation throughput and time-to-first-token (TTFT).
  4. Structured-output (`ProposedAction`) JSON schema adherence rate over 50 test iterations.
  5. Text and vision quality evaluation on a fixed prompt test set.
  6. Numerical stability checks (monitoring for NaN/inf tensors or degenerate repetitive loops, especially given T4's native lack of hardware BF16 compute units).
  7. Deliver written comparison report to founder; founder decides production default.

---

### 4.5 Workspaces: Canvas-First Premium & Admin (§25, §26)

#### 4.5.1 Premium Creative Workspace (§25)
The customer interface is a unified, canvas-first creative workspace designed to evoke delight and focus on the output:

1. **5 Desktop Regions:**
   - **Top Bar:** Product identity (`KEYSTONE`), current Project breadcrumb, Quick Search / Command Palette (`Ctrl+K`), User Profile, and Credit Balance pill badge.
   - **Left Sidebar:** Primary navigation: Create (new draft), Projects (library), Assets (media pool), History (generation timeline), Favorites.
   - **Center Canvas:** The visual hero of the interface. Displays current media in high resolution. Houses split-view image compare, synchronized video player with scrub bar, variation carousel, and interactive Lineage DAG tree viewer.
   - **Right Inspector:** Collapsible property sheet showing resolution, aspect ratio, model provenance, seed, prompt hash, quality harness score, customer-level controls, and download options.
   - **Bottom Composer:** Intent-first interaction bar. Natural language prompt input, drag-and-drop file attachment zone, and Quick Intent hints: `Create`, `Edit`, `Animate`, `Analyze`.

2. **UX Rules:**
   - Visual primacy: The asset is large and central; conversation supports the canvas rather than dominating it.
   - Provider abstraction: Users see capabilities ("Animate this image"), never raw internal model identifiers or ComfyUI node details (unless Developer Mode is toggled).
   - Comparison modes: Image comparison provides an interactive split-slider or side-by-side view. Video comparison provides frame-synchronized parallel playback.
   - Mobile review experience: Responsive design tailored for mobile phones emphasizing browsing, commenting, approving, downloading, and sharing.

3. **Progress Language:**
   During job execution, the client UI reflects exact backend stages using the standardized progress lexicon:
   - *"Understanding your request"* (Cognitive analysis & context assembly)
   - *"Planning the generation"* (Cognitive action proposal & capability selection)
   - *"Preparing the workflow"* (Authority validation, prompt compilation & envelope issuance)
   - *"Creating"* (Worker execution on GPU)
   - *"Checking the result"* (Technical and quality harness evaluation)
   - *"Refining when necessary"* (Controlled quality retry or replan)
   - *"Finishing"* (Asset persistence, lineage linking & credit settlement)

#### 4.5.2 Operator Admin Workspace (§26)
A dedicated administrative console designed for operators and customer support:
- **User & Account Health:** Account status, subscription tier, credit balances, suspension/deletion controls.
- **Job Diagnostics:** Real-time job stream, attempt inspection, stack traces, failure codes.
- **Worker & GPU Fleet Telemetry:** Active Kaggle/cloud workers, VRAM consumption, host RAM offload status, temperatures, queue depths.
- **Cost & Latency Tracking:** Token usage, generation latency, estimated infrastructure cost per job.
- **Asset & Lineage Explorer:** Global lookup of any asset and complete traversal of its generation tree.
- **End-to-End Support Trace:** Single-pane trace showing: User Message $\rightarrow$ Request $\rightarrow$ Cognitive Run $\rightarrow$ Authority Decision $\rightarrow$ Compiled Prompt $\rightarrow$ Job Attempts $\rightarrow$ Harness Evidence $\rightarrow$ Credit Ledger Entries $\rightarrow$ Output Asset.

---

### 4.6 Authentication, Billing & Credits Ledger (§27)

#### 4.6.1 Authentication Architecture
- Password security: Argon2id or bcrypt hashing.
- Token architecture:
  - Short-lived JWT access tokens (15 minutes expiry) signed via RS256 or HS256.
  - Refresh tokens stored in database with rotation and family invalidation upon reuse detection.
- API Key Security:
  - Users can generate programmatic API keys.
  - Raw secret keys are displayed only once at creation.
  - Only the SHA-256 hash (`key_hash`) and prefix (`key_prefix`, e.g. `ks_live_a1b2c3d4`) are persisted in PostgreSQL.
- Session Management: Tracking of active user sessions with IP and user-agent metadata, allowing remote revocation.

#### 4.6.2 Billing & Stripe Test Mode
- Stripe test mode configuration (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`).
- Subscription tiers: Free, Pro, Studio.
- Webhook Handler:
  - Implements strict idempotency. Every received webhook event ID (`event.id`) is recorded in the ledger or audit log.
  - Reprocessed or duplicated webhook events are immediately acknowledged with HTTP 200 without duplicating credits or subscriptions.
  - Handles `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, and `invoice.payment_failed`.

#### 4.6.3 Credits Ledger Engine
Financial integrity is enforced via a double-entry style transactional credit ledger:
1. **The Core Invariant:**
   > Balances NEVER change without a corresponding `credit_ledger` event.
2. **Two-Phase Reservation Pattern:**
   - **Phase 1: Hold.** When a job is submitted, the system estimates the required credit cost. If $(\text{balance} - \text{held\_balance}) \ge \text{cost}$, a ledger entry of type `hold` is created:
     - `amount = -cost`
     - `held_balance = held_balance + cost`
   - **Phase 2: Settlement.** Upon job completion, a ledger entry of type `settlement` is created:
     - `balance = balance - actual_cost`
     - `held_balance = held_balance - cost`
   - **Phase 2 (Alternative): Release.** If the job fails or is cancelled before execution:
     - A ledger entry of type `release` is created:
     - `held_balance = held_balance - cost` (funds returned to available balance; zero deduction).
3. **Refunds & Adjustments:**
   - Operator adjustments or customer support refunds create explicit `refund` or `reversal` entries.
4. **Immutability:**
   - The `credit_ledger` table is append-only.
   - Database rules/triggers prevent any `UPDATE` or `DELETE` statements on `credit_ledger`.

---

### 4.7 Security Controls (§28), Proprietary Policy & Tooling (§29, §38), Legal Docs (§30)

#### 4.7.1 Security & Reliability Controls (§28)
- **Tenant Isolation:** Enforced at the repository layer. Every query for assets, jobs, sessions, and messages includes `WHERE user_id = :current_user` or `owner_id = :current_user`.
- **Signed Execution Envelopes:** Workers reject any execution request that does not carry a valid cryptographic signature from Keystone AuthorityEngine.
- **Rate Limiting & Watchdogs:** Per-user and per-IP rate limits on API endpoints. Watchdogs terminate zombie worker tasks after a configurable timeout (e.g. 300s).
- **Aikido Prompt Injection Defense:** All user input, scraped content, and metadata injected into cognitive prompts are quarantined within `<untrusted_content>` tags, closing tags are escaped, and post-generation filtering strips any delimiter leakage.
- **PII Vault Compliance:** Zero plain PII in cognitive model contexts. Extracted personal data is tokenized via AES-256-GCM into `vault_tok_<uuid>` references.

#### 4.7.2 Proprietary Policy & Guarded Publication Tooling (§29, §38)
- **Proprietary Notice:**
  ```text
  Copyright 2026 Jordan Maxwell. All rights reserved.
  KEYSTONE is proprietary and confidential software.
  Unauthorized copying, redistribution, modification, publication,
  sublicensing, disclosure, or reverse engineering is prohibited except
  where expressly authorized in writing by the copyright owner or required
  by applicable law.
  ```
- **Closed Source Rule:** The repository is strictly private. Public GitHub mirrors, open package releases, or leaks are strictly prohibited.
- **Guarded Publication Tooling (§38):**
  - Pre-push git hook (`scripts/verify_private_remote.sh` / `.ps1`) that inspects git remotes before any push.
  - Automatically aborts push if remote URL does not match private criteria (e.g. github.com/owner/private-repo).
  - Runs automated secret scanner (e.g. gitleaks / git-secrets) scanning for API keys, Kaggle tokens, Stripe keys, and private keys before any commit or push is permitted.

#### 4.7.3 Legal Documentation Suite (§30)
10 commercial legal documents must be drafted from actual platform data flows, explicitly marked as drafts pending qualified legal review:
1. `docs/legal/PRIVACY_POLICY.md` (Covers data collection, storage, PII Vault tokenization, retention)
2. `docs/legal/TERMS_OF_SERVICE.md` (User agreements, subscriptions, liability limits)
3. `docs/legal/ACCEPTABLE_USE_POLICY.md` (Prohibited content generation, safety boundaries)
4. `docs/legal/RETENTION_AND_DELETION_POLICY.md` (GDPR Article 17, soft delete periods, hard purges)
5. `docs/legal/COOKIE_NOTICE.md` (Session cookies, token storage)
6. `docs/legal/INTELLECTUAL_PROPERTY_POLICY.md` (User content ownership, DMCA notice procedure)
7. `docs/legal/REFUND_TERMS.md` (Credit refund rules, dispute handling)
8. `docs/legal/SUBPROCESSORS_DISCLOSURE.md` (GCP, Cloud Run, Cloud Storage, Kaggle, Stripe)
9. `docs/legal/MODEL_LICENSE_INVENTORY.md` (License audit of Qwen 2.5, Wan 2.1, ComfyUI, etc.)
10. `docs/legal/PREMIUM_LOCAL_LICENSE.md` (EULA for local/offline deployment editions)

---

### 4.8 Epics A–I (§32) and Wave 0–6 Build Order (§33)

#### 4.8.1 Epics A through I Breakdown
- **Epic A: Foundation:** Repo structure, shared contracts, environment config, logger, exception handlers, CI workflows, PostgreSQL schema & Alembic migrations, Redis/Celery scaffolding, Cloud Storage client.
- **Epic B: Prompt Engine:** Preserve `plan.v1` and 13 playbooks; PromptAnatomy parser; PromptIntent; PromptProfile; PromptCompilationRequest; CompiledPrompt; prompt hashing and provenance engine; revision proposal compiler.
- **Epic C: Authority:** PolicyRegistry; CapabilityRegistry; HarnessRegistry; ProposedAction validator; AuthorityDecision; AuthorityEngine; ExecutionEnvelope generator and signer; audit event publisher.
- **Epic D: Cognition:** CognitiveProvider protocol; vLLM adapter; Kaggle hardware probe; MemoryHarness CPU-offload calculator; Qwen checkpoint loader; vision inquiry handler; structured proposal parser; retry telemetry.
- **Epic E: Harness Framework:** HarnessResult schema; HarnessRegistry; MemoryHarness; TechnicalOutputHarness; QualityAggregator; regression runner; benchmark persistence.
- **Epic F: Job Platform:** Job repositories; state machine; Celery worker queues; idempotency guard; retries and cancellation handlers; worker crash recovery; asset record and lineage linker.
- **Epic G: Creative Fabric:** ComfyUI adapter; Image generation manifest & workflow; Wan I2V and T2V manifests & workflows; FaceFusion identity manifest & workflow; Upscale workflow; license gate checks.
- **Epic H: Product and API:** FastAPI REST application; Auth endpoints (register, login, refresh, logout); Account endpoints; Project, Session, Message endpoints; Asset upload & streaming endpoints; Job endpoints; Capabilities & Health endpoints; Stripe billing integration; rate limiters.
- **Epic I: Premium UX:** Canvas-first workspace shell; 5 desktop regions; visual media canvas; natural-language composer with intent hints; compare mode (split & sync); lineage DAG visualizer; admin operator workspace.

#### 4.8.2 Wave 0–6 Build Order (§33)
The architecture dictates an exact 7-wave build sequence:

```text
Wave 0: Freeze Contracts
  └── plan.v1, PromptAnatomy, CapabilityManifest, ProposedAction,
      AuthorityDecision, ExecutionEnvelope, Job States, OpenAPI spec, DB identifiers.

Wave 1: Vertical Application Shell
  └── Register -> Create Project -> Create Session -> Upload Asset ->
      Send Message -> Create Fake Job -> Stream Status -> Return Persistent Fake Asset ->
      Display Asset on Canvas -> Refresh and Recover State.

Wave 2: Original KEYSTONE Brain
  └── Wire preserved heuristic prompt engine; expose planning endpoint;
      verify 13 playbooks; record prompt hashes and provenance.

Wave 3: Cognition
  └── Kaggle hardware probe; install pinned dependencies; retrieve exact
      abliterated checkpoint; launch vLLM; test text/vision/structured actions;
      record memory metrics.

Wave 4: Authority and Workers
  └── Register capabilities; validate proposals; issue signed envelopes;
      reject direct or malformed execution requests.

Wave 5: Creative Vertical Slice
  └── Image generation first; Wan image-to-video immediately afterward;
      persist outputs; deterministic validation; bounded quality retry.

Wave 6: Customer Release Mechanics
  └── Subscriptions; credits ledger & usage; admin diagnostics;
      tenant isolation tests; crash recovery tests; backups/restore drills;
      legal documentation derived from actual data flows.
```

---

### 4.9 Acceptance Criteria & Gate Verification (§34, §35)

#### 4.9.1 §34 Alpha Gate Checklist (13 Operational Criteria)
The Alpha Gate must be demonstrated on the live deployment:
1. Account creation and authentication work seamlessly.
2. Projects and sessions persist durably in PostgreSQL.
3. Uploads persist in Cloud Storage with short-expiry signed URLs.
4. Users communicate naturally with KEYSTONE through the composer.
5. KEYSTONE owns all prompt compilation and provenance.
6. Cognition produces valid structured `ProposedAction` proposals.
7. Image and Image-to-Video workflows execute and deliver media outputs.
8. Active and completed jobs survive page refresh and browser restart.
9. Outputs appear strictly within the originating user's project.
10. Credits are debited exactly once per successful generation (zero double charges).
11. Mid-execution failures preserve the chat session and restore credit holds.
12. Customers can download generated media outputs directly.
13. Admins can inspect and diagnose job traces in the admin workspace.

#### 4.9.2 §35 Acceptance Test Suite

1. **Identity Tests (6 bullets):**
   - Product name remains `KEYSTONE`.
   - `plan.v1` output schema remains valid and backward-compatible.
   - All 13 domain playbooks load cleanly.
   - `PromptAnatomy` contains all six fields: `role`, `task`, `context`, `constraints`, `outputFormat`, `reasoning`.
   - Standard, chat, and reasoning prompt compilers pass validation.
   - Every model-facing call carries cryptographic KEYSTONE prompt provenance.

2. **Authority Tests (7 bullets):**
   - Direct user-to-worker execution request fails (HTTP 401/403).
   - Direct model-to-worker request fails.
   - Request with unknown capability ID fails.
   - Request with malformed arguments fails schema validation.
   - Expired or replayed execution envelope fails verification.
   - Valid signed execution envelope succeeds.
   - Worker cannot mutate the approved prompt or arguments.

3. **Live Cloud Run E2E Test Sequence:**
   Automated test script running against live Cloud Run URL:
   ```text
   1. Register new test user
   2. Create test project
   3. Upload sample test image
   4. Submit natural language request: "Animate this image with cinematic camera drift"
   5. KEYSTONE compiles cognitive prompt for Qwen
   6. Qwen emits structured ProposedAction (selecting Wan I2V)
   7. AuthorityEngine validates proposal and issues signed ExecutionEnvelope
   8. Target prompt compiled for Wan I2V with provenance hash
   9. Kaggle ComfyUI worker executes Wan I2V workflow
   10. KHF Technical Output Harness evaluates video (codec, non-blank, duration)
   11. Video persisted in Cloud Storage; lineage relationship created
   12. Credits ledger debits account balance exactly once
   13. Refresh browser simulation; verify complete project, session, and asset recovery
   ```

4. **Worker Mid-Run Crash Recovery Test:**
   - Execute an active video animation job.
   - Terminate the Kaggle creative worker mid-run (simulate crash/kernel kill).
   - Verify that KEYSTONE watchdog detects timeout, marks attempt failed, re-enqueues or gracefully fails the job, releases credit hold, and preserves project state without crashing the API.

---

### 4.10 Change Control Rules (§37)

Section 37 governs all architectural invariants (specifically the 18 locked invariants in §2):
1. **Mandatory 7-Step Protocol:**
   Any change to an invariant strictly requires:
   - Explicit written founder approval.
   - A written Architecture Decision Record (ADR) committed to `docs/adr/`.
   - Backward-compatibility impact analysis.
   - KHF regression test coverage.
   - Forward migration plan.
   - Safe rollback plan.
   - Versioned contract updates across packages and OpenAPI.
2. **Strict Non-Reinterpretation Rule:**
   No coding agent, LLM, model, dependency upgrade, worker script, or deployment pipeline may reinterpret or relax these rules autonomously.

---

## 5. Invariant & Cross-Cutting Matrix

The following matrix maps the 18 locked invariants from Bible §2 directly to the Part 2 implementation specifications and verification methods:

| # | Invariant | Part 2 Implementation Section | Verification / Enforcement Mechanism |
|---|-----------|-------------------------------|--------------------------------------|
| 1 | KEYSTONE remains the product & prompt engine | §25, §36 | `IDENTITY_PRESERVATION.md`, UI Branding, `npm test` identity suite |
| 2 | Sole authoritative prompting engine | §23, §35 | PromptCompiler registry; workers reject unsanctioned prompts |
| 3 | Every model prompt compiled, hashed, recorded | §21, §32 (Epic B) | `compiled_prompts` table; SHA-256 hash logged before dispatch |
| 4 | Components declare manifests & observations | §23, §8 | `CapabilityManifest` required for all adapters; no direct actions |
| 5 | Components cannot mutate approved prompts | §23, §28, §35 | Signed `ExecutionEnvelope`; prompt hash verified by worker |
| 6 | Qwen is embedded cognition, not product authority | §24, §32 (Epic D) | Qwen emits `ProposedAction`; `AuthorityEngine` decides |
| 7 | Qwen proposes; KEYSTONE governs | §23, §28, §35 | AuthorityDecision approve/deny/replan flow; user/worker cannot bypass |
| 8 | Workers execute only validated ExecutionEnvelopes | §23, §28, §35 | Public/private key cryptographic signature verification on worker |
| 9 | Nobody bypasses AuthorityEngine | §28, §35 | Authority tests: raw requests fail with 401/403 |
| 10 | Abliterated checkpoint invariant | §24, §11 | Checkpoint pinned to `huihui-ai/Huihui-Qwen3.8-27B-abliterated` |
| 11 | Memory pressure handled via offload/retry profiles | §24 | MemoryHarness + Host RAM offload (~80GB); 7 controlled retry profiles |
| 12 | `generate(goal, options) -> plan.v1` preserved | §31, §35 | `packages/prompt-engine/src/engine.js`, identity tests |
| 13 | PromptAnatomy remains 6 fields | §31, §35 | Validated by JSON schema and `tests/identity.test.js` |
| 14 | 13 domain playbooks remain first-class data | §31, §35 | `packages/prompt-engine/src/playbooks.js`, 13 playbooks verified |
| 15 | Kaggle is bootstrap, not permanent architecture | §24, §38 | `KAGGLE_SETUP/` directory; architecture decouples control plane |
| 16 | Dedicated migration preserves public contracts | §31, §32 | Monorepo contracts package; Cloud Run + Cloud SQL production shape |
| 17 | Proprietary & closed source; private repo only | §29, §38 | Guarded publication pre-push scripts; proprietary copyright headers |
| 18 | Original source archive preserved; additive build | §31, §33 | Byte-identical manifest check; additive workspace layout |

---

*End of Survey Report. Comprehensive specification mining of KEYSTONE_BIBLE.md Part 2 (§21 through §38) complete.*
