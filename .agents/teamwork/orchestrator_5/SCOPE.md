# Scope: Kaggle GPU ComfyUI PinkCherry-MiniMax-H3 to Atomic Chat Integration

## Architecture
- **Kaggle GPU Session**: Runs ComfyUI on `127.0.0.1:8188` hosting the `SexGod1979/PinkCherry-NSFW_MiniMax-H3` + `Comfy-Org/MiniMax-H3` workflow via `/kaggle/working/h3_api_prompt.json`.
- **OpenAI-Videos Bridge on Kaggle**: Fast/Flask/aiohttp bridge exposing `/v1/models`, `/v1/videos/models`, `POST /v1/videos`, `GET /v1/videos/{id}`, `GET /v1/videos/{id}/content` wrapping ComfyUI queue and output. Exposed via trusted Cloudflare HTTPS tunnel.
- **Local Atomic Chat Desktop & Core**:
  - Control API on `http://127.0.0.1:56603/atomic/v1` (control token at `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token`).
  - Local API server on `http://127.0.0.1:1337/v1` protected by bearer token `sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay`.
  - Cloudflare tunnel exposing `127.0.0.1:1337/v1` to the internet (`*.trycloudflare.com/v1`).
- **Kaggle Secrets Client**: Notebook accesses `ATOMIC_API_BASE_URL` and `ATOMIC_API_KEY` securely via `UserSecretsClient()` over HTTPS without exposing secrets in code cells.
- **Atomic Chat UI & Video Gallery**: Models registered in Atomic Chat provider/server selection; generated `.mp4` videos saved into `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos` and queryable via `/atomic/v1/diffusion/video/gallery`.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Atomic Chat Remote Access & Tunnel | Ensure Atomic Chat API (127.0.0.1:1337) and Cloudflare tunnel are active with rotated key | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Kaggle Secrets Sync in Edge | Synchronize ATOMIC_API_BASE_URL & ATOMIC_API_KEY in Kaggle Notebook Secrets via Edge tab 1746398736 | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Kaggle ComfyUI OpenAI Videos Bridge | Run OpenAI-Videos compatible API bridge wrapping ComfyUI (8188) and expose via Cloudflare tunnel | M2 | ORIGINAL_REQUEST §R2 |
| 4 | Atomic Chat Model & UI Registration | Register PinkCherry-MiniMax-H3 in Atomic Chat via Control API so it appears in UI & models list | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Notebook Client Execution & Video Gen | Execute Kaggle notebook Cells 8 & 9 (RUN_ATOMIC_VIDEO=True) targeting PinkCherry-MiniMax-H3 | M3 | ORIGINAL_REQUEST §R3 |
| 6 | End-to-End Verification & Video Gallery | Verify generation completes, valid .mp4 (>100KB, ftyp) reaches Atomic Chat gallery, and 200 OK | M3 | ORIGINAL_REQUEST §R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Remote Access & Secrets Sync | Atomic Chat API server verification, Cloudflare tunnel check, Edge Kaggle Secrets sync | none | DONE |
| M2 | ComfyUI Bridge & Registration | Kaggle ComfyUI video bridge tunnel, Atomic Chat model registration via Control API | M1 | DONE |
| M3 | E2E Generation & Verification | Run Kaggle cells, verify inference, validate video in gallery, multi-tier checks & audit | M2 | DONE |

## Interface Contracts
### Kaggle Notebook ↔ Atomic Chat Cloudflare Tunnel
- Endpoint: `POST {ATOMIC_API_BASE_URL}/videos`
- Auth: `Authorization: Bearer {ATOMIC_API_KEY}` (loaded via `UserSecretsClient().get_secret(...)`)
- Payload: `{"model": "PinkCherry-MiniMax-H3", "prompt": "...", ...}`
- Response: `{"id": "...", "status": "queued"|"processing"|"completed", ...}`

### Atomic Chat Desktop ↔ Kaggle ComfyUI Bridge
- Endpoint: `GET /v1/models`, `POST /v1/videos`
- Format: OpenAI Videos API format
- Video Output: H.264 + AAC `.mp4`, valid `ftyp` header, size > 100 KB
- Gallery Path: `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos`
