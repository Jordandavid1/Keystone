## 2026-10-22T16:30:06Z
From: 6f59f58e-8034-400a-bd25-c869a10728f4 (Project Orchestrator)
Priority: MESSAGE_PRIORITY_HIGH

You are explorer_m0_3, a teamwork_preview_explorer subagent for Milestone M0 (Wave 0: Contract Freeze & Additive Foundation).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_3

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (§2 Invariants, §37 Change control, §38 Deliverables)
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md

OBJECTIVE:
Investigate and design the Invariant Guards, Bible Deliverables, and Verification Automation (F01):
1. Design the automated invariant verification script `scripts/verify_invariants.py` that:
   - Computes and verifies SHA-256 of `KEYSTONE_BIBLE.md` against `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788`.
   - Verifies all 69 pre-built files remain byte-identical against the pre-built manifest.
   - Runs `npm test` and confirms 3/3 identity tests pass.
   - Runs `node tests/e2e/runner.js` and confirms Run 1 tests pass.
   - Verifies cognition checkpoint in Kaggle configuration is pinned to `huihui-ai/Huihui-Qwen3.8-27B-abliterated`.
2. Specify the exact delivery of `docs/KEYSTONE_BIBLE.md` as a byte-identical copy of root `KEYSTONE_BIBLE.md` per §38.
3. Design change-control logging and test harness scripts for Wave 0.
4. Write your report to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_3\m0_invariants_and_verification_blueprint.md`.
5. Write your handoff to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_3\handoff.md`.
6. Send a message to parent when done. Do NOT modify source files.
