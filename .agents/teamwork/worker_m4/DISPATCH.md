## 2026-10-22T15:10:27Z
Sender: 60572d58-20e5-4b73-8f9a-70a7a40329ec
Priority: MESSAGE_PRIORITY_HIGH

You are the Keystone Integration & Dependency Worker (teamwork_preview_worker) for Milestone 4.
Working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m4
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative Request: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Authoritative Plan: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_1\PROJECT.md
Test Infra: c:\Users\Lesia Eden\Downloads\keystone-cowork\TEST_INFRA.md
Test Ready: c:\Users\Lesia Eden\Downloads\keystone-cowork\TEST_READY.md

SKILLS & REFERENCES TO APPLY:
- Python Dependency Management: C:\Users\Lesia Eden\.gemini\config\skills\managing-python-dependencies\SKILL.md
- Sysadmin Guardrails: C:\Users\Lesia Eden\.gemini\config\skills\sysadmin-guardrails\SKILL.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

CRITICAL IMMUTABILITY INVARIANT:
DO NOT modify `apps/api/src/main.py` or any of the 21 baseline tracked files in `docs/FILE_MANIFEST.txt`. Build strictly additively!

EXCLUSIVE WRITE OWNERSHIP:
Additive integration files ONLY:
- `apps/api/src/intelligence_router.py` (FastAPI APIRouter exposing `/v1/intelligence/capabilities`, `/v1/intelligence/extract`, `/v1/intelligence/sanitize`)
- `requirements.txt` at project root (clean locked dependencies: fastapi, uvicorn, pydantic, pytest, cryptography)
- `scripts/verify_environment.py` (composite bundled environment probe verifying python venv, dependencies, sysadmin safety, and non-destructive execution)
- `scripts/setup_environment.ps1` (idempotent, non-interactive environment setup script adhering to sysadmin guardrails)
- `services/intelligence/src/bridge/service_bridge.js` (bridge connecting intelligence capabilities to Keystone runtime)
- `services/intelligence/README.md` (integration and usage documentation)

TASKS:
1. Implement all Milestone 4 additive integration files.
2. Verify Python environment compliance (no global pip install, virtual environment awareness).
3. Run baseline invariant tests: `npm test` (must pass 3/3, 100% green).
4. Run E2E test suite: `node --test tests/e2e/*.test.js` and `node tests/e2e/runner.js` (must pass 132/132, 100% green).
5. Run `python scripts/verify_environment.py` and document output.
6. Write your handoff report to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m4\handoff.md` with complete evidence and notify the orchestrator.
