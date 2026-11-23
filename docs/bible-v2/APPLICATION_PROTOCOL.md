# Bible v2 — Application Protocol

**Executor rules (binding for humans and AI agents alike):**
1. One file per concept. Creating a parallel copy of an engine, UI, client, or contract set is a defect, not a contribution.
2. Every commit message cites its operation number (`O#` / `PR#`) below. Ops outside this protocol require a new ADR — no freelancing.
3. Tests added during any op must hit real FastAPI + DB boundaries. No mock-oracle suites.
4. Both canonical Bible copies (`KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md`) must remain byte-identical on every commit (enforced as a blocking sync check from `O2` onward; content checksum freezes are permanently retired per ADR-004 D14).

---

## Effective Ratified Op Order (Zero-Red-Window Sequence)

Because the fully stitched Bible v2 was delivered as one ratified document and v1 verification retirement was hoisted ahead of landing Bible v2 to prevent any red window, the active op order is:

```text
O0    git tag bible-v1-final                                        (rollback point)
O0.5  Retire v1 verification (single atomic commit, cites ADR-004):
        - verify_invariants.py 69-file freeze deleted -> v2 structural lint (advisory mode)
        - verify_alpha_gate.py fabricated PASS-dicts deleted (fail-closed pending PR10)
        - tests/e2e_v2 JS mock-oracle suite archived under archive/v1_verification/
O1    Commit ADR-004 + ADR-005 + APPLICATION_PROTOCOL.md + specs/*
O2    Land Bible v2 — BOTH copies identically in one commit ("O2 (embodies O3–O16)")
      and flip bible_sync check in scripts/verify_invariants.py to BLOCKING
O17   Housekeeping (proprietary LICENSE/package.json, docs/runbooks/kaggle.md,
      refreshed FILE_MANIFEST / IDENTITY_PRESERVATION / TEST_READY, server.py ref,
      regenerated openapi.yaml from live API; flip license_policy to BLOCKING)
->    Phase C: PR1–PR10 (code ratification per ADR-005)
->    Phase D: Final verification
```

---

## Companion Specification Artifacts

| Spec Path | Role |
|---|---|
| `specs/SPEC_GATE.md` | Gate spec: data model, Envelope v2, gate flow, route table, mode-aware cognition prompt, config, acceptance tests |
| `specs/SPEC_EVALUATORS.md` | Spec A: Evaluator Tank (5 families, tiered budgets, mode-aware rubrics, retry/promotion) |
| `specs/SPEC_MEMORY.md` | Spec B: Memory & Recipe Library (`pgvector`, local Qwen embeddings, replay, 2-run promotion) |
| `specs/UX_PARITY.md` | UX Parity Matrix (lead sheet for Bible v2 §25.9 Legacy Feature Ledger) |
| `specs/DEPENDENCY_MANIFEST.md` | Dependency manifest + 10-phase build order |

---

## Phase B — Bible Amendment Register (`O3–O16` Embodied in `O2`, Plus `O17`)

| Op | Action | Status / Verify |
|---|---|---|
| O0 | `git tag bible-v1-final` on pre-v2 HEAD (`f3c04b3`) | Tag exists |
| O0.5 | Retire v1 freeze, PASS-dict alpha gate, and mock-oracle `e2e_v2` JS suite; install v2 structural lint (advisory) | Single atomic commit before `O1`/`O2` |
| O1 | Commit ADR-004 + ADR-005 to `docs/change_control/` + protocol & `specs/*` | `verify_change_control.py` passes |
| O2 (O3–O16) | Land stitched Bible v2 in BOTH `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` + flip `bible_sync` to BLOCKING | Embodied ops: O3 (§2 14 invariants), O4 (§6 mode-scoped playbooks), O5 (§10–11 Cognition Core merge), O6 (§13 real evaluator tank), O7 (§16–21 API/table sync), O8 (§22 `depicts` + mature), O9 (§23 as-built fabric), O10 (§24 tier statement → runbook), O11 (§25.9 Port Parity Rule), O12 (§26–28 admin/ledger/security), O13 (§29–31, §33 policy/monorepo/waves), O14 (§37 living change control), O15 (§39 absorbed tombstone), O16 (§40–§43 new sections) |
| O17 | Housekeeping: move v1 §24 detail into `docs/runbooks/kaggle.md`, fix `LICENSE`/`package.json` to proprietary, refresh `FILE_MANIFEST.txt` / `IDENTITY_PRESERVATION.md` / `TEST_READY.md` / `server.py`, regenerate `openapi.yaml` from live API, flip `license_policy` to BLOCKING | Zero stale hashes/counts or Apache/MIT license twins |

---

## Phase C — Code Ratification (PR Sequence, per ADR-005)

1. **PR1** — Alembic migrations (`users`/`sessions`/`projects`/`assets`/`credit_ledger` columns + `recipes`/`recipe_embeddings`/`style_rules` + `personas` & `projects.deleted_at` gap fix)
2. **PR2** — Envelope v2 + env-held `KEYSTONE_ENVELOPE_SECRET` (hardcoded secrets removed)
3. **PR3** — `apps/api/src/services/gate.py` + Tier-A floor/deterministic checks + durable DB `authority_decisions`/`audit_events` + P0/P1 security wall (admin/config/worker auth, IDORs, SSRF)
4. **PR4** — Image-gen crash fix (`assets.py:478`) + ComfyUI workflow zoo image paths + single consolidated client & compiler (flip `no_duplicate_engines` compiler/client checks)
5. **PR5** — Video variants (`t2v`/`i2v`/`ref2v`/`v2v`) + `extend` chain & stitch + deterministic grade lane + neural ESRGAN upscale (flip `manifest_accounting` to blocking)
6. **PR6** — Cross-modal Personas (`as: persona_id`, `PersonasModal` unwrap fix, avatar IDOR fix, `depicts` lineage) + UX Parity pass (`specs/UX_PARITY.md` rows → `PORTED-WIRED`, retire legacy SPA, flip `no_duplicate_engines` UI check to blocking)
7. **PR7** — Tier-B evaluators (`services/harness/src/evaluators/`: OCR, mode-aware VLM critique, temporal, identity) + bounded retry wiring
8. **PR8** — Memory & Recipe Library (`pgvector`, local Qwen embeddings, `POST /v1/recipes/{id}/replay`, two-run promotion)
9. **PR9** — Billing provenance (immutable DB credit ledger, hold→settle→release, VRAM-minute metering, dual-rail SFW/UNRESTRICTED processor routing) + age gate + C2PA Content Credentials (§43)
10. **PR10** — Real HTTP/DB acceptance suite replacing retired v1 theater; wire live `verify_alpha_gate.py`; flip all structural lint checks to blocking

---

## Phase D — Final Verification

All ADR-005 acceptance criteria green against real FastAPI + PostgreSQL + Redis + worker boundaries; both Bible copies identical; Legacy Feature Ledger 100% dispositioned (`PORTED-WIRED` or `OWNER-DROPPED` with recorded reason); `scripts/verify_invariants.py --strict` passes with zero blocking or advisory failures.
