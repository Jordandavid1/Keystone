# ADR-004: Bible v2 — Content Modes, Personas, Memory, Credentials, Canonical Recast

- **Status:** FOUNDER_APPROVED (Accepted)
- **Date:** 2026-11-22
- **Deciders:** Jordan Maxwell (Founder, sole owner); ratified against the forensic audits of 2026-11-22
- **Target Invariant:** KEYSTONE_BIBLE.md §2, §6, §10–11, §13, §16–21, §22, §23, §24, §25, §26–28, §29–31, §33, §37, §38–39, new §40–§43
- **Supersedes:** the byte-exact SHA-256 freeze on `KEYSTONE_BIBLE.md` and the 69-file freeze in `scripts/verify_invariants.py` (the mechanism of §37 *as written*); model-name pinning as a property of Bible canon as introduced by ADR-002/ADR-003.
- **Does NOT supersede:** ADR-002 (agent chat as product concept) or ADR-003 (as an operator configuration record). Both remain valid history; their checkpoint pinning moves to operator config under the `CapabilityManifest`.

---

## 1. Explicit Founder Approval

- **Approval Timestamp:** 2026-11-22 (Founder Ratification Session — Bible v2)
- **Sign-off Identification:** Jordan Maxwell (Founder, sole owner)
- **Basis:** Explicit Founder ratification of Bible v2 Amendment Register (D1–D14), Content Modes (`SFW | UNRESTRICTED`), Personas as v1 canon, Memory & Recipe Library, Content Credentials, retirement of checksum freezes, and archival of Bible v1 at git tag `bible-v1-final`.

---

## 2. Architecture Decision Record

### Context

Forensic audits of 2026-11-22 established three facts:
1. The Bible barely changed since creation — instead, six build tracks mutated the codebase *around* a checksum-frozen Bible, producing ten documented inter-document contradictions and parallel duplicate systems (3 prompt engines, 3 UIs, 3 ComfyUI clients).
2. Verification was theater: green suites tested mocks, oracles testing themselves, and hardcoded PASS dictionaries, including an acceptance test that passed a malformed envelope while `envelope=None` bypassed verification entirely.
3. Founder intent — an uncensored multimodal creative platform under sole KEYSTONE authority — survives intact in §1/§3/§36/§4–9/§12 but was contradicted by bolt-on tracks (closed vendor model in BigQuery, Stripe-dependency vs. NSFW playbooks, Kaggle hardware law as canon).

### Founder Decisions Ratified

- **D1** — Primary product: multimodal creative studio; prompt-intelligence playbooks retained as compiler library.
- **D2** — Commercial arc: single-user local alpha → hosted multi-tenant SaaS (phasing lives in the roadmap, never in the Bible).
- **D3** — Positioning: adult-capable, unrestricted platform with SFW default; content modes are a platform function enforced at one Gate; lawful-content floor is non-configurable.
- **D4** — Cognition: architecture locked, checkpoint names unlocked (operator config, disclosed in the manifest).
- **D5** — Quantization sanctioned (GGUF/int8/fp8-class) where hardware demands; quality judged by evaluators, not doctrine.
- **D6** — UX: intents-only canvas; Next.js is the single UI; **Port Parity Rule** — every capability of prior UX builds carries forward wired, or is retired by recorded owner decision; no silent feature loss may recur.
- **D7** — **Full modality package is v2 canon:** chat, image gen/edit/vary/upscale, t2v/i2v/ref2v/v2v/extend/video-upscale, speech, analyze, personas (cross-modal). All intents default-enabled in the `CapabilityManifest`.
- **D8** — New §40 (Content Modes & Hard Floors), including age gating and dual-processor revenue routing.
- **D9** — New §41 (Personas & Cross-Modal Identity): reference-set conditioning at v1, identity adapters (LoRA-class) at v1.5, identity continuity as a KHF check.
- **D10** — New §42 (Memory & Recipe Library): project-scoped, mode-filtered, vector search in Postgres/pgvector, local embeddings only; recipes are replayable; evaluation closes the loop into a self-improving flywheel.
- **D11** — New §43 (Content Credentials): C2PA manifests on every generated asset.
- **D12** — Pricing as measurement now (VRAM-minutes + scores per job in the immutable ledger), priced at M2.
- **D13** — Intelligence/BigQuery track archived; BigQuery's semantic role is superseded by §42.
- **D14** — Checksum freezes permanently retired; change control = owner-approved ADR amendments + behavioral tests.

### Decision

Bible v2 is a **living amendment of v1, not a re-authorship.** The Amendment Register as delivered in the founder ratification session is adopted: §2 recast (14 invariants), §6 mode-scoped, §13 replaced (real evaluator tank), §23 replaced (as-built fabric), §24 reduced to a runbook pointer, §25 gains clause 25.9 (Port Parity Rule), §40–§43 appended, redlines R1–R6 applied to the living text; **all sections not listed are preserved byte-exact.** The canonical copies at `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` must remain identical to each other after every edit (a sync check, not a content freeze). v1 is archived at git tag `bible-v1-final`.

### Consequences

- **Positive:** one truth of product and law; censorship and liberation become a signed, audited platform function; generation quality compounds per project via §42; commercial survival for adult content is structurally provided (§40.9 processor split, §43 provenance); drift caused by freeze-workaround is impossible by mechanism.
- **Honest costs:** M1 scope grows (evaluators, modes, personas, parity pass); the intelligence/BigQuery track is archived and its demo value is surrendered; Stripe may settle only SFW revenue; UNRESTRICTED purchases require an age gate that strengthens at M2.

---

## 3. Compatibility Impact Analysis

- **API Impact:** Backwards-compatible `generate(goal, options) -> plan.v1` and 6-part `PromptAnatomy` preserved (§6); public API (§17) synced to live route families plus additive mode, age-verification, persona, cognition chat, speech, and recipe routes; `envelope=null` on execution routes transitions to strict `400`.
- **Client Impact:** Next.js Studio becomes the single UI under the §25.9 Port Parity Rule (Legacy Feature Ledger prevents silent feature loss before retiring the legacy SPA). Customer UI remains intents-only with no exposed model names.
- **State & Storage Impact:** Additive PostgreSQL (+`pgvector`) tables (`recipes`, `recipe_embeddings`, `style_rules`, plus `personas` migration and mode/age/mature columns); `services/intelligence/` and `infrastructure/bigquery/` retired from core monorepo.

---

## 4. KHF Regression Coverage

- **Regression Suite:** `scripts/verify_invariants.py` (v2 structural lint: `bible_sync`, `banned_strings`, `change_control`, `npm_test_identity`, plus advisory `no_duplicate_engines`, `manifest_accounting`, `license_policy` flipping to blocking per milestone), `scripts/verify_change_control.py`, `npm test`, and full `pytest` suite.
- **Test Scenarios:** Root/`docs` Bible byte-sync; zero-placeholder live-output invariants; ADR §37 compliance; real HTTP/DB acceptance criteria defined in ADR-005 (replacing retired v1 mock-oracle and PASS-dict suites).
- **Pre-Change vs Post-Change Verification:** Verified at `O0.5` (v2 structural lint + 35 targeted tests green) prior to landing Bible v2 in `O2`, eliminating any red window.

---

## 5. Migration Plan

- **Step 1 (`O0`):** Tag current `HEAD` (`f3c04b3`) as `bible-v1-final`.
- **Step 2 (`O0.5`):** Retire v1 verification freeze, PASS-dict alpha gate, and mock-oracle `e2e_v2` JS suite; install v2 structural lint in advisory mode.
- **Step 3 (`O1`):** Commit ADR-004, ADR-005, `docs/bible-v2/APPLICATION_PROTOCOL.md`, and companion `specs/` documents.
- **Step 4 (`O2`):** Land Bible v2 identically in `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` (embodying `O3–O16`) and flip `bible_sync` to blocking.
- **Step 5 (`O17`):** Housekeeping — proprietary `LICENSE`/`package.json`, `docs/runbooks/kaggle.md`, refreshed `FILE_MANIFEST.txt` / `IDENTITY_PRESERVATION.md` / `TEST_READY.md`, regenerated `openapi.yaml`, and flip `license_policy` to blocking.
- **Step 6 (Phase C):** Execute ADR-005 code ratification PRs (`PR1–PR10`).

---

## 6. Rollback Plan

- **Trigger Conditions:** Any unresolvable regression in `plan.v1` compatibility, change-control compliance, or Founder decision to revert Bible v2 canon.
- **Immediate Reversion Steps:** `git checkout bible-v1-final -- KEYSTONE_BIBLE.md docs/KEYSTONE_BIBLE.md scripts/verify_invariants.py scripts/verify_alpha_gate.py` or per-op `git revert <commit>` citing op numbers (`O17`, `O2`, `O1`, `O0.5`).
- **State Recovery:** `O0.5–O17` introduce no destructive database migrations; tag `bible-v1-final` preserves the complete pre-v2 repository byte-for-byte.

---

## 7. Versioned Contract Updates

- **Canonical Spec:** `KEYSTONE_BIBLE.md` & `docs/KEYSTONE_BIBLE.md` promoted from Version 1.0 (archived at `bible-v1-final`) to Version 2.0 (Bible v2).
- **PromptCompilationRequest / ExecutionEnvelope:** Extended with `content_mode`, `age_verified`, `floor_verdict`, and advisory `memory_context` (implemented in ADR-005 PR2/PR3).
- **OpenAPI Specification:** Regenerated from the live FastAPI application in `O17` (replacing stale v0.1.0 scaffold).
