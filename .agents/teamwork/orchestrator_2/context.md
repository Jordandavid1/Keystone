# Context Tracking — Orchestrator 2 (Phase 1)

## Workspace Details
- Project root: `c:\Users\Lesia Eden\Downloads\keystone-cowork`
- Dedicated orchestrator directory: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2`
- Authoritative request: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md`
- Canonical specification: `c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md` (SHA-256: 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788)

## Invariants & Critical Instructions
1. **`KEYSTONE_BIBLE.md` is read-only.** Nothing changes without founder approval.
2. **Do not modify or overwrite any pre-built code.** The founder's original scaffold and all Run 1 deliverables (`services/intelligence/`, `infrastructure/bigquery/`, `apps/api/src/intelligence_router.py`, `tests/e2e/`, `scripts/`, etc.) stay byte-identical. Build additively.
3. Baseline tests (`npm test` and `node --test tests/e2e/`) must remain 100% green at all times.
4. Orchestrator never writes application code directly, never runs test commands directly — delegate all technical tasks to subagents.
5. Pinned cognition checkpoint: `huihui-ai/Huihui-Qwen3.8-27B-abliterated` on Kaggle T4x2 via tensor parallel 2 with CPU offload to host RAM (~80 GB). BF16 default; after full build, run documented BF16 vs FP16 comparison benchmark on Kaggle.
6. Epics A–I following Wave 0–6 build order.
7. Go live on Google Cloud Run + Kaggle GPUs.
8. Stripe test mode billing + full credits ledger.
9. Benchmark UX research on the 6 apps using Firecrawl skills; build premium canvas-first workspace.
10. PII Vault compliance & Aikido prompt injection defense.
