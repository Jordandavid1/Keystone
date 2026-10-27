## 2026-10-23T11:06:01Z
You are worker_m3_impl, a teamwork_preview_worker subagent implementing Milestone M3 (Wave 3: Cognition & Authority).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m3_impl

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (STRICTLY READ-ONLY! Checksum 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788)
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md
- Read Blueprint at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_2\m3_cognition_authority_blueprint.md
- Read Handoff at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m3_2\handoff.md

EXCLUSIVE WRITE OWNERSHIP (You may only write/create these files):
1. packages/contracts/src/models.py (update/verify ProposedAction, AuthorityDecision, ExecutionEnvelope schemas)
2. services/authority/src/__init__.py
3. services/authority/src/rules.py (safety policies, boundary ceilings, credit formulas)
4. services/authority/src/evaluator.py (SafetyPolicyEvaluator, CreditBalanceEvaluator, ParameterBoundaryEvaluator)
5. services/authority/src/engine.py (AuthorityEngine with evaluate, evaluate_request, and audit logging to audit_events)
6. services/harness/src/__init__.py
7. services/harness/src/envelope.py (EnvelopeEngine: HMAC-SHA256 signing, verify_envelope, TTL nonce replay prevention, clock skew tolerance)
8. services/harness/src/worker_bridge.py (WorkerBridge: register_worker, heartbeat, offline detection timeout, capability registry)
9. apps/api/src/routers/authority.py (REST endpoints: POST /v1/authority/evaluate, GET /v1/authority/policies)
10. apps/api/src/routers/workers.py (REST endpoints: POST /internal/workers/register, POST /internal/workers/heartbeat, GET /internal/workers)
11. apps/api/src/server.py (mount authority_router and workers_router additively without modifying main.py)
12. KAGGLE_SETUP/scripts/probe_hardware.py (verify exact 26.7GB offload math & 7 retry profiles)
13. tests/e2e_v2/test_m3_cognition_authority.py (comprehensive verification suite for M3)

FORBIDDEN FILES (DO NOT MODIFY, OVERWRITE, OR TOUCH):
- Root KEYSTONE_BIBLE.md
- Any of the 69 pre-built files (apps/api/src/main.py, apps/api/src/intelligence_router.py, infrastructure/migrations/versions/0001_core.sql, tests/identity.test.js, tests/e2e/*, etc.)
- M0–M2 files: packages/prompt_engine/*, packages/security/*, apps/api/src/db/*, apps/api/src/repositories/*, apps/api/src/auth/*, apps/api/src/storage/*, apps/api/src/lineage/*, apps/api/src/jobs/*

TASK EXECUTION STEPS:
1. Implement services/authority/src/ (rules.py, evaluator.py, engine.py, __init__.py) per Blueprint §2.
2. Implement services/harness/src/ (envelope.py, worker_bridge.py, __init__.py) per Blueprint §4 and §5.
3. Implement apps/api/src/routers/authority.py and apps/api/src/routers/workers.py per Blueprint §6.
4. Mount routers in apps/api/src/server.py additively.
5. Verify KAGGLE_SETUP/scripts/probe_hardware.py per Blueprint §3.
6. Implement tests/e2e_v2/test_m3_cognition_authority.py per Blueprint §7 covering all 5 features (F14–F18), boundary cases, and adversarial replay/tamper attacks.
7. Execute all verification commands:
   - pytest tests/e2e_v2/test_m3_cognition_authority.py -v
   - pytest tests/e2e_v2/test_m2_prompt_cognition.py -v
   - pytest tests/e2e_v2/test_m1_core_shell.py -v
   - node tests/e2e_v2/runner.js
   - npm test
   - node tests/e2e/runner.js
   - python scripts/verify_invariants.py --require-docs-bible
   - git status --porcelain (confirm 0 baseline files modified)
8. Write comprehensive handoff.md in your dedicated folder.
9. Send completion message to parent when done.
