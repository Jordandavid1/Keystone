## 2026-10-28T04:55:50Z
You are the Project Orchestrator for the task specified in `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md` under timestamp `## 2026-10-28T04:53:37Z`.

Your working directory is `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_5`.
All your coordination metadata, plan, progress, and briefing must reside inside your working directory. Maintain `progress.md` and `BRIEFING.md` continuously.

## Mission
Connect the Kaggle GPU ComfyUI `PinkCherry-MiniMax-H3` workflow (`SexGod1979/PinkCherry-NSFW_MiniMax-H3` + `Comfy-Org/MiniMax-H3`) to Atomic Chat's desktop UI and `/v1/videos` API using the rotated remote-access API key (`sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay`), trusted Cloudflare HTTPS tunnels, and the `firecrawl-developer-index` skill (`C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-developer-index\SKILL.md`) for primary-source API/library verification.

## Context & References
- Working directory: `c:\Users\Lesia Eden\Downloads\keystone-cowork`
- Firecrawl Developer Index Skill: `C:\Users\Lesia Eden\.gemini\config\skills\firecrawl-developer-index\SKILL.md`
- Active Kaggle Notebook Editor Tab in `browsermcp` (Microsoft Edge): Tab `1746398736` (`https://www.kaggle.com/code/rigormortice/pinkcherry-nsfw-minimax-h3-download/edit#PinkCherry-MiniMax-H3-+-Atomic-Chat-client`)
- Atomic Chat Control API: `http://127.0.0.1:56603/atomic/v1` (token at `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token`)
- Atomic Chat Public API: `http://127.0.0.1:1337/v1`

## Critical Constraints & User Rules
1. **Browser Preference**: Always use **Microsoft Edge** as default and primary browser for all web automation, navigation, DevTools sessions, debugging, and web testing (`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`). Strictly DO NOT use or suggest Google Chrome.
2. **Security & Secrets**: Never hardcode or print raw API keys or secrets in notebook code cells, chat output, or git commits. Use Kaggle's `UserSecretsClient()` (`from kaggle_secrets import UserSecretsClient`) over HTTPS.
3. **Firecrawl Skill**: Use `firecrawl-developer-index` (`https://api.firecrawl.dev/v2/search/developer` or `firecrawl developer`) to resolve any library, ComfyUI node, or OpenAI Videos API contract questions from primary sources.

## Requirements
### R1. Secure Atomic Chat Remote Access & Kaggle Secrets Synchronization
Ensure Atomic Chat's Local API Server (`127.0.0.1:1337/v1`) and remote-access Cloudflare HTTPS tunnel (`*.trycloudflare.com/v1`) are active and authenticated with the rotated key (`sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay`). Synchronize `ATOMIC_API_BASE_URL` and `ATOMIC_API_KEY` in Kaggle Secrets on `browsermcp` Tab `1746398736` (using Microsoft Edge, never Chrome) without hardcoding or printing raw secrets in notebook cells.

### R2. Kaggle ComfyUI to Atomic Chat Video Bridge & UI Registration
Ensure the OpenAI-Videos compatible bridge (`/v1/models`, `/v1/videos/models`, `POST /v1/videos`, `GET /v1/videos/{id}`, `GET /v1/videos/{id}/content`) and its Cloudflare HTTPS tunnel are running on the Kaggle GPU session wrapping ComfyUI (`127.0.0.1:8188` and `/kaggle/working/h3_api_prompt.json`). Register `PinkCherry-MiniMax-H3` in Atomic Chat (`llamacpp-server` and/or custom cloud provider plus `PUT /atomic/v1/server/selection`) so `PinkCherry-MiniMax-H3` is selectable and usable directly inside Atomic Chat's UI and via `POST /v1/videos`.

### R3. End-to-End Video Generation & Verification with Firecrawl Developer Index
Use `firecrawl-developer-index` to resolve any library, ComfyUI node, or OpenAI Videos API contract questions from primary sources. Execute the Kaggle notebook's Atomic Chat client cells (`Cell 8` and `Cell 9` with `RUN_ATOMIC_VIDEO = True` and `ATOMIC_MODEL = 'PinkCherry-MiniMax-H3'`) and verify that a generated H.264+AAC `.mp4` video completes end-to-end and appears in Atomic Chat's Video Gallery (`C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos`).

## Acceptance Criteria
- [ ] `GET {ATOMIC_API_BASE_URL}/videos` in the Kaggle notebook authenticates via `UserSecretsClient()` over HTTPS (`*.trycloudflare.com/v1`) and returns HTTP 200.
- [ ] No raw API keys appear in notebook code cells or chat output.
- [ ] `PinkCherry-MiniMax-H3` appears in `GET http://127.0.0.1:56603/atomic/v1/cloud/providers` and `GET {ATOMIC_API_BASE_URL}/models`.
- [ ] Running the Kaggle Atomic Chat client cell (`POST {ATOMIC_API_BASE_URL}/videos` with `model: "PinkCherry-MiniMax-H3"`) triggers ComfyUI inference on the Kaggle GPU, reaches `status: "completed"`, and writes a valid `.mp4` video (`> 100 KB`, valid `ftyp` header) into `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos` and `GET http://127.0.0.1:56603/atomic/v1/diffusion/video/gallery`.
