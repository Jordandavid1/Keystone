## 2026-10-22T20:10:53Z
Your identity: explorer_m2_wave2
Your working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_wave2
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative requests: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Scope document: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_3\PROJECT.md
Canonical specification: c:\Users\Lesia Eden\Downloads\keystone-cowork\KEYSTONE_BIBLE.md

MANDATORY FIRST STEP:
Read c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md before starting any work.

YOUR TASK:
Technical investigation and architectural blueprint for Milestone M2 (Wave 2: Kaggle Tier 0 Notebooks & Prompt Reasoning, F10–F13):
1. F10: Prompt Compiler & Playbook Engine:
   - Inspect existing packages/prompt-engine/src/* (pre-built JS playbooks and engine).
   - Design Python PromptCompiler port supporting all 13 domain playbooks, 6-part PromptAnatomy, standard/chat/reasoning compiler profiles, SHA-256 prompt hashing and provenance metadata.
2. F11: Aikido Prompt-Injection Defense:
   - Structural delimiter containment (`<untrusted_content>`), nested tag escaping (`&lt;/untrusted_content&gt;`), script/comment scrubbing, threat scoring (`SAFE`, `SUSPICIOUS`, `MALICIOUS`), and post-generation tag sanitization.
3. F12: PII Scrubbing & Tokenization:
   - Boundary edge-level PII scrubbing for emails, phone numbers, bearer tokens; AES-256-GCM tokenization with 12-byte IV per token; authenticated detokenization and tamper rejection.
4. F13: Cognition Connector & Client:
   - OpenAI-compatible vLLM client for pinned checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated` on Kaggle T4x2 with CPU offload into host RAM (~80 GB).
5. KAGGLE_SETUP Production Workspace:
   - Design the 3 production notebooks to be placed in `KAGGLE_SETUP/`:
     - `01_cognition_bootstrap.ipynb`: Real hardware probe (T4x2 VRAM, host RAM ~80GB, CPU offload calculation), vLLM launch script, text/vision/structured ProposedAction health check.
     - `02_comfyui_runtime.ipynb`: ComfyUI runtime with Wan 2.1 (T2V, I2V), FaceFusion, Upscale models, and harness endpoints.
     - `03_integrated_gateway.ipynb`: Cloudflare tunnel / ngrok worker gateway registering ephemeral endpoints with Keystone Cloud Run via `POST /internal/workers/register`.
     - `README.md`: Step-by-step founder execution guide and checklists.

OUTPUT:
Write your complete technical findings and implementation strategy to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_m2_wave2\handoff.md`.
Send a completion message back to your parent orchestrator with the file path when done.
