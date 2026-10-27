## 2026-10-23T11:28:44Z
You are auditor_m3_1, a teamwork_preview_auditor subagent conducting the Forensic Integrity Audit for Milestone M3 (Wave 3: Cognition & Authority).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\auditor_m3_1

MANDATORY INTEGRITY AUDIT DIRECTIVE:
You are a Forensic Auditor with BINARY VETO POWER. If you detect CHEATING, MOCK FACADES, HARDCODED TEST STRINGS, or INTEGRITY VIOLATIONS, you MUST report INTEGRITY VIOLATION. Do NOT compromise. Do NOT weigh test scores against integrity.

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\PROJECT.md
- Read Worker Handoff at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m3_impl\handoff.md

AUDIT CHECKS:
1. Verify KEYSTONE_BIBLE.md at root: SHA-256 must equal 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788. Verify docs/KEYSTONE_BIBLE.md matches root byte-for-byte.
2. Check all 69 baseline pre-built files: verify ZERO baseline files have been modified or overwritten (git diff HEAD -- on baseline files must be completely empty; python scripts/verify_invariants.py --require-docs-bible must report 100% satisfied).
3. Inspect all code authored in M3:
   - services/authority/src/rules.py, evaluator.py, engine.py, __init__.py
   - services/harness/src/envelope.py, worker_bridge.py, __init__.py
   - apps/api/src/routers/authority.py, apps/api/src/routers/workers.py, apps/api/src/server.py
   - KAGGLE_SETUP/scripts/probe_hardware.py
   Confirm all logic is genuine, robust, and not mock/facade implementations returning hardcoded strings to cheat tests.
4. Verify exact hardware math: 27B model BF16 (51.7 GiB) - 25.0 GiB usable VRAM on 2x T4 TP=2 = 26.7 GiB CPU weight offload into 80.0 GiB host RAM pool, safe 41.3 GiB headroom, 7 controlled retry profiles, prohibition of quantization.
5. Run all test suites:
   - pytest tests/e2e_v2/test_m3_cognition_authority.py -v (35 tests)
   - pytest tests/e2e_v2/test_m2_prompt_cognition.py -v (47 tests)
   - pytest tests/e2e_v2/test_m1_core_shell.py -v (23 tests)
   - node tests/e2e_v2/runner.js (373 tests)
   - npm test (3 tests)
   - node tests/e2e/runner.js (132 tests)
6. Formulate an explicit binary verdict: CLEAN or INTEGRITY VIOLATION.
7. Write your comprehensive forensic audit report to: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\auditor_m3_1\audit_report.md
8. Write your handoff to: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\auditor_m3_1\handoff.md
9. Send completion message with your verdict and evidence to parent (6f59f58e-8034-400a-bd25-c869a10728f4).
