## 2026-10-22T16:30:05Z
You are explorer_m0_1, a teamwork_preview_explorer subagent for Milestone M0 (Wave 0: Contract Freeze & Additive Foundation).
Your parent is the Project Orchestrator (Conversation ID: 6f59f58e-8034-400a-bd25-c869a10728f4).
Your dedicated working directory is: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_1

MANDATORY INPUTS:
- Read ORIGINAL_REQUEST.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
- Read KEYSTONE_BIBLE.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md (§6–§19, §33 Wave 0)
- Read PROJECT.md at: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_2\PROJECT.md

OBJECTIVE:
Investigate and design the implementation blueprint for M0 Canonical Contracts & Schemas (F02) and Additive API Server Extension (F03):
1. Specify the exact schemas for `packages/contracts/` in Python (Pydantic v2 models) and TypeScript/JSON (`packages/contracts/src/contracts.json`) covering:
   - PromptIntent, CapabilityManifest, ParameterSpec, PromptCompilationRequest, CompiledPrompt, CognitiveResult, ProposedAction, AuthorityDecision, ExecutionEnvelope, HarnessResult, QualityScore, RetryPolicy.
2. Specify the design of `apps/api/src/server.py` that:
   - Imports `app` from `apps.api.src.main` (preserving `main.py` byte-identical).
   - Mounts `apps.api.src.intelligence_router.router` (`/v1/intelligence`).
   - Adds OpenAPI documentation metadata and `/v1/contracts` endpoint.
   - Preserves `/v1/health` and `/v1/plan`.
3. Provide concrete code structure, type annotations, and import paths for the upcoming Worker.
4. Write your design report to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_1\m0_contracts_api_blueprint.md`.
5. Write your handoff to: `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m0_1\handoff.md`.
6. Send a message to parent when done. Do NOT modify source files.
