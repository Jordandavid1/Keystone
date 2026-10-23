## 2026-10-22T20:21:11Z

Your identity: worker_m2_impl
Your working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m2_impl
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative requests: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Scope document: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_3\PROJECT.md
Canonical specification: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md
Spec miner handoff: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_m2_wave2\handoff.md
Explorer handoff: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_wave2\handoff.md

MANDATORY FIRST STEP:
Read c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md before starting any work.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

EXCLUSIVE WRITE BOUNDARIES:
You own exclusively:
- packages/prompt_engine/* (or additive Python modules in packages/prompt-engine/keystone_prompt_engine/*; do NOT touch prebuilt JS files)
- packages/security/*
- services/cognition/src/*
- apps/api/src/routers/planning.py
- apps/api/src/server.py (additive modifications only)
- KAGGLE_SETUP/*
- tests/e2e_v2/test_m2_prompt_cognition.py

STRICT PROHIBITION:
DO NOT modify or overwrite any of the 69 pre-built baseline files (such as packages/prompt-engine/src/*.js, infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb, KEYSTONE_BIBLE.md, etc.). All 69 baseline files must remain 100% byte-identical.

TASKS TO IMPLEMENT:
1. F10: Python Prompt Compiler & 13 Playbooks:
   - Implement Python `PromptCompiler`, `PlaybookRegistry` (all 13 playbooks), 6-part `PromptAnatomy`, 3 profiles (standard, chat, reasoning), deterministic SHA-256 prompt hashing, and legacy `/v1/plan` endpoint.
2. F11: Aikido Prompt-Injection Defense:
   - Implement `packages/security/aikido.py`: `<untrusted_content>` quarantine, closing tag escaping `&lt;/untrusted_content&gt;`, script/comment scrubbing, threat scoring (`SAFE`, `SUSPICIOUS`, `MALICIOUS`), and post-generation tag sanitization.
3. F12: PII Vault & Boundary Scrubbing:
   - Implement `packages/security/vault.py`: Edge scrubbing (`[REDACTED_EMAIL]`, `[REDACTED_PHONE]`, `Bearer [REDACTED_KEY]`), AES-256-GCM tokenization with random 12-byte IV and 16-byte auth tag (`vault_tok_<uuid>`), authenticated detokenization with 1-bit tamper detection, and GDPR Art. 17 cryptographic shredding.
4. F13: Cognition Connector & Client:
   - Implement `services/cognition/src/client.py`: OpenAI-compatible vLLM client for pinned checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated`, prohibiting model substitution (`PROHIBITED_CHECKPOINT_MUTATION`), empty prompt rejection (`EMPTY_PROMPT`), system instructions, structured `ProposedAction` validation, and telemetry.
5. KAGGLE_SETUP Production Workspace:
   - Create `KAGGLE_SETUP/` directory structure with:
     - `01_keystone_cognition_bootstrap.ipynb`: Hardware probe (T4x2, host RAM ~80GB, CPU offload calculation), vLLM launch script, text/vision/ProposedAction health check.
     - `02_keystone_comfyui_runtime.ipynb`: ComfyUI runtime with Wan 2.1 (T2V, I2V), FaceFusion, Upscale models, and signed envelope harness.
     - `03_keystone_integrated_gateway.ipynb`: Cloudflare tunnel / ngrok worker gateway registering ephemeral endpoints with Keystone Cloud Run via `POST /internal/workers/register`.
     - `KAGGLE_SETUP/notebooks/`: Provide copies / symlinks for KaggleSetupOracle compliance.
     - `KAGGLE_SETUP/README.md`: Step-by-step founder execution guide and post-build BF16 vs FP16 comparative benchmark procedure.
6. Comprehensive Test Suite:
   - Create `tests/e2e_v2/test_m2_prompt_cognition.py` exercising all F10–F13 and Kaggle setup contracts.

VERIFICATION REQUIRED:
Execute:
1. `npm test` (3/3 passing)
2. `node tests/e2e/runner.js` (132/132 passing)
3. `python scripts/verify_invariants.py --require-docs-bible` (100% invariants satisfied, 69/69 files byte-identical)
4. `pytest tests/e2e_v2/test_m2_prompt_cognition.py` (All passing)
5. `pytest tests/e2e_v2/test_m1_core_shell.py` (23/23 passing)
6. `node tests/e2e_v2/runner.js` (373/373 passing)

OUTPUT:
Write your complete handoff report to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m2_impl\handoff.md`.
Send a completion message back to your parent orchestrator with the file path when done.
