# ADR-005: Execution Architecture — The Gate, Envelope v2, Evaluator Tank, Memory Fabric, UX Parity

- **Status:** FOUNDER_APPROVED (Accepted — execution ratification; code changes land under its criteria)
- **Date:** 2026-11-22
- **Depends on:** ADR-004
- **Target Invariant:** KEYSTONE_BIBLE.md §2 Invariants 1, 3, 4, 8, 9, 10, 11, 12, 13, 14; §12; §13; §18; §21; §25.9; §26–§28; §35; §40–§43

---

## 1. Explicit Founder Approval

- **Approval Timestamp:** 2026-11-22 (Founder Ratification Session — Execution Architecture)
- **Sign-off Identification:** Jordan Maxwell (Founder, sole owner)
- **Basis:** Explicit Founder ratification of ADR-005 execution architecture, Gate & Envelope v2 contracts, Evaluator Tank, Memory Fabric, UX Parity Ledger, Dependency Manifest, and PR1–PR10 ratification sequence.

---

## 2. Architecture Decision Record

### Context

The audits of 2026-11-22 found the authority architecture excellent on paper and bypassed in practice: every live generation route skipped `AuthorityEngine`/`ExecutionEnvelope`; workers and admin routes had no auth; cross-tenant IDORs and SSRF existed; video generations were never inspected; `khf_quality.py` averaged supplied floats; state lived in RAM and 13 of 24 tables had zero rows.

### Decision (Architecture)

1. **The Gate.** One dispatch point (`apps/api/src/services/gate.py`) executes:
   `resolve mode → verify age gate → compile (mode-scoped playbooks) → floor check (lawful-content watchdog) → AuthorityEngine decision → sign Envelope v2 → dispatch → validate on worker`.
   Route wiring follows `specs/SPEC_GATE.md`; `/v1/creative/execute` MUST return `400` on `envelope=null`; `/internal/workers/*` require service token + envelope verification; `/v1/admin/*` and `*/configure` require admin auth; envelope issue route becomes internal/admin-only. The in-RAM `audit_log` dies here — gate decisions write `authority_decisions` + `audit_events` rows.
2. **Envelope v2.** HMAC payload: `{envelope_version, job_id, intent, content_mode, age_verified, floor_verdict, playbook, expires_at}` (bound alongside job/user/capability/prompt provenance per Bible v2 §12). Secret in env (`KEYSTONE_ENVELOPE_SECRET`); hardcoded defaults deleted; mode cannot be altered after signing.
3. **Evaluator tank (`services/harness/src/evaluators/`).** Five families (deterministic, OCR, VLM prompt-adherence, temporal, identity), tiered budgets per Bible §13; mode-aware critique rubrics compiled by the same compiler discipline as generation; every run writes `harness_runs`; bounded retries; never silent accept, never silent drop.
4. **Memory fabric.** Postgres + `pgvector`; `recipes`, `recipe_embeddings`, `style_rules`; retrieval always `tenant_id + project_id` scoped and mode-filtered; embeddings from a local Qwen-embedding-class model only (no external vendor — Invariant 2 closure); replay re-executes stored envelope + prompt + seed through the normal Gate.
5. **UX parity.** The Legacy Feature Ledger (`specs/UX_PARITY.md`) is the shipping gate: every row reaches `PORTED-WIRED` or `OWNER-DROPPED` with recorded reason before the legacy SPA is retired. `AnalysisPane` becomes genuinely multimodal; agent chat renders assets and persists.
6. **Dependencies.** The Dependency Manifest (`specs/DEPENDENCY_MANIFEST.md`: Postgres + `pgvector`, Redis, `ffmpeg`, ComfyUI workflow zoo incl. extend-chain and stitch, H3/PinkCherry v1.8, SDXL + FLUX slot, Qwen OBLITERATED cognition+VLM, Qwen-embedding, OCR engine, ElevenLabs + local fallback, C2PA libs, Stripe + adult rails, age verify, Modal/Colab workers) is the staged registry; build order phases 1–10 as delivered.

### Consequences

Agents can no longer satisfy gates with mocks; the Bible's architecture and the code's behavior converge; NSFW-capable revenue can be processed without platform risk. Rollback: tag `bible-v1-final` plus per-operation revert granularity (commit messages cite op/PR numbers from the Application Protocol).

---

## 3. Compatibility Impact Analysis

- **API Impact:** Breaking hardening on insecure routes: `/v1/creative/execute` rejects missing `envelope` (`400`); `/v1/admin/*`, `*/configure`, `/internal/workers/*`, and `/v1/authority/envelope/issue` reject unauthenticated calls (`401`/`403`); additive routes for modes, age verification, recipes, and replay per Bible v2 §17.
- **Client Impact:** Next.js Studio migrates off unwired `/v1/zencreator/*` stubs onto the Gate-backed intent fabric; every Legacy Feature Ledger control is wired to real backend behavior.
- **State & Storage Impact:** Alembic migrations add `personas`, `projects.deleted_at`, user/project/session `content_mode`, `users.age_verified`, `assets.mature`, `credit_ledger` processor provenance, `recipes`, `recipe_embeddings` (`pgvector`), and `style_rules`. In-RAM stores (`audit_log`, `credits_ledger`, `_JOB_EVENTS`, `nonce_cache`, `worker_bridge`, `generation_progress`) migrate to PostgreSQL + Redis.

---

## 4. KHF Regression Coverage (Acceptance Criteria — Real Tests Only)

- **Gate:** age-unset UNRESTRICTED → `403`; floor-violation fixture → `422` + audit row + no dispatch; `envelope=null` → `400`; SFW envelope replayed on UNRESTRICTED path → rejected; unsigned job → worker refuses; mature asset excluded from SFW gallery.
- **Evaluators:** corrupted file fails deterministic; OCR fixture fails; persona-drift fixture scores below threshold; UNRESTRICTED rubric passes a fixture the SFW rubric flags; retry exhaustion yields review-flagged, not accepted.
- **Memory:** cross-tenant retrieval returns zero rows; SFW compile never retrieves mature recipes; replay reproduces deterministic staging; promotion requires two passing runs.
- **Security wall:** admin/config/worker routes authed; IDORs and SSRF closed; secrets out of repo/exe/container; leaked `sk-atomic-*` rotated.
- **Theater retired:** `verify_alpha_gate.py` PASS-dicts deleted (`O0.5`); `e2e_v2` oracle archived (`O0.5`) and replaced in PR10 with a real HTTP/DB suite; `verify_invariants.py` repurposed to v2 structural lint (advisory checks flipping to blocking as each PR lands).

---

## 5. Migration Plan (Phase C — PR1–PR10)

- **PR1:** Alembic migrations (users/sessions/projects/assets/credit_ledger columns + `recipes`/`recipe_embeddings`/`style_rules` + `personas` & `projects.deleted_at` gap fix).
- **PR2:** Envelope v2 + env-held `KEYSTONE_ENVELOPE_SECRET` (delete hardcoded defaults).
- **PR3:** `apps/api/src/services/gate.py` + Tier-A deterministic/floor checks + durable DB `authority_decisions` & `audit_events` + security wall (auth on admin/config/workers, IDORs, SSRF).
- **PR4:** Image-gen crash fix (`assets.py:478`) + ComfyUI workflow zoo image paths + single consolidated client & compiler.
- **PR5:** Video variants (`t2v`/`i2v`/`ref2v`/`v2v`) + `extend` chain & stitch + deterministic grade lane + neural ESRGAN upscale.
- **PR6:** Cross-modal Personas (`as: persona_id`, `PersonasModal` unwrap fix, avatar IDOR fix, `depicts` lineage) + UX Parity pass (`specs/UX_PARITY.md` → `PORTED-WIRED`, retire legacy SPA).
- **PR7:** Tier-B evaluators (`services/harness/src/evaluators/`: OCR, mode-aware VLM critique, temporal, identity) + bounded retry wiring.
- **PR8:** Memory & Recipe Library (`pgvector`, local Qwen embeddings, `POST /v1/recipes/{id}/replay`, two-run promotion).
- **PR9:** Immutable DB credit ledger with processor provenance + age gate + C2PA Content Credentials (§43).
- **PR10:** Real HTTP/DB acceptance suite replacing retired v1 theater; flip remaining structural lint checks to blocking; final Phase D verification.

---

## 6. Rollback Plan

- **Trigger Conditions:** Gate lockout on valid SFW requests, evaluator false-fail rate blocking delivery, or database migration failure.
- **Immediate Reversion Steps:** Every PR lands as an isolated, op/PR-cited commit series revertible cleanly via `git revert`; database migrations ship with explicit Alembic `downgrade()` paths; pre-v2 baseline remains tagged at `bible-v1-final`.
- **State Recovery:** Append-only ledger and soft-delete policies preserve user/asset data across rollbacks.

---

## 7. Versioned Contract Updates

- **ExecutionEnvelope:** Bumped to `envelope_version = "2.0"` with `content_mode`, `age_verified`, and `floor_verdict` signed inside HMAC payload.
- **HarnessResult / QualityScore:** Backed by durable `harness_runs` rows written by `services/harness/src/evaluators/`.
- **Canonical Specs Added:** `specs/SPEC_GATE.md`, `specs/SPEC_EVALUATORS.md`, `specs/SPEC_MEMORY.md`, `specs/UX_PARITY.md`, `specs/DEPENDENCY_MANIFEST.md`, `docs/bible-v2/APPLICATION_PROTOCOL.md`.
