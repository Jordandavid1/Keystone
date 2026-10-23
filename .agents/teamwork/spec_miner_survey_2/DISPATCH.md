## 2026-10-22T16:17:11Z
[Message] timestamp=2026-10-22T16:17:11Z sender=6f59f58e-8034-400a-bd25-c869a10728f4 priority=MESSAGE_PRIORITY_HIGH content=You are spec_miner_survey_2, a teamwork_preview_spec_miner subagent.
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_2

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (STRICTLY READ-ONLY! SHA-256 must remain 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788).

OBJECTIVE:
Perform a deep specification mining survey of KEYSTONE_BIBLE.md Part 2 (§21 through §38) and related requirements in ORIGINAL_REQUEST.md.
Extract, organize, and document:
1. PostgreSQL schema and Alembic migrations (§21): all required tables, relations, indexes, enum types, constraints.
2. Assets & lineage (§22): storage, short-expiry signed URLs, lineage DAG model.
3. Creative tool fabric (§23): image generation, image editing, Wan I2V and T2V, identity workflow, upscale pipelines.
4. KAGGLE_SETUP (§24): all 3 notebooks, vLLM / ComfyUI / Wan setups, memory harness, CPU offload into host RAM (~80GB), retry profiles.
5. Workspaces: §25 canvas-first premium workspace, §26 admin workspace.
6. Auth, billing & credits ledger (§27): Stripe test mode, holds/settlement/refunds/reversals, idempotent webhooks.
7. Security controls (§28), proprietary policy & guarded publication tooling (§29, §38), legal documents (§30).
8. Epics A–I (§32) and Wave 0–6 build order (§33): list all deliverables per wave.
9. Acceptance criteria: §34 alpha gate and §35 automated acceptance tests (identity, authority, E2E script against live Cloud Run, recovery test).
10. Change control (§37) rules.

SCOPE BOUNDARIES:
- Read-only analysis. Do NOT modify any file outside your dedicated folder.
- Do NOT touch KEYSTONE_BIBLE.md.
- Write your comprehensive findings to: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_2\survey_specs_part2.md
- Write your handoff to: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_survey_2\handoff.md
- When complete, send a message to parent (6f59f58e-8034-400a-bd25-c869a10728f4) reporting completion and pointing to the artifacts.
