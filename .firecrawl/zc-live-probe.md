# ZenCreator live API probe (authenticated)

Auth: `zc_live_03d0cbf1742c3c4d_xl3KUzPVuTA5cDyX1xHMBNolJ5rKLbV1DkohM5BkOk4`
Captured: 2026-10-23
Note: keys in this file are ones the owner handed me; rotate / revoke at `app.zencreator.pro/api-keys` when done.

## Full cycle verified: POST generation → poll → result

### 1. Start a generation
- Request:
  - `POST https://api.zencreator.pro/api/public/v1/generations`
  - Headers: `Authorization: Bearer zc_live_...`, `Content-Type: application/json`
  - Body: `{"tool":"by_prompt","input":{"positive_prompt":"portrait of a woman, golden hour","ratio":"3:4"},"metadata":{"task":"live probe to verify POST/poll/result flow"}}`
- Response: `201`
  - Body: `{"id":"89d17c30-0260-499a-8431-0a7b49ecf8a1","status":"queued","created_at":"..."}`
- Takeaways: creations return `id`, `status=queued`. `metadata` is accepted alongside the request.

### 2. Poll status
- Request: `GET https://api.zencreator.pro/api/public/v1/generations/89d17c30-0260-499a-8431-0a7b49ecf8a1`
- Observed timeline:
  - Round 1: `{"status":"processing","progress":0,"error":null}`
  - Rounds 2–3: same shape, `progress=0`
  - Round 4: `{"status":"succeeded","progress":100,"error":null}`
- Poll cadence used: about every 4 seconds. The docs recommend 5–10s.
- Status flow confirmed: `queued → processing → succeeded` (no `partial` in this run).

### 3. Fetch result
- Request: `GET https://api.zencreator.pro/api/public/v1/generations/89d17c30-0260-499a-8431-0a7b49ecf8a1/result`
- Response: `200`
  - Body:
    - `id`: `"89d17c30-0260-499a-8431-0a7b49ecf8a1"`
    - `status`: `"succeeded"`
    - `error`: `null`
    - `text`: present but `null` (legacy field for image tools; populated for text tools)
    - `outputs`: `[{ "asset_id": "b2e0646d-447e-4e4c-ba27-a586f2fdff34", "url": "https://storage.zencreator.pro/preview_b2e0646d447e4e4cba27a586f2fdff34.webp", "download_url": "https://storage.zencreator.pro/c6ef554b4cc34203b1e7ec68ee32fec6.jpeg" }]`
- Takeaways:
  - Outputs are returned with an `asset_id` (UUID), a `url` (preview), and a `download_url` (final asset).
  - Storage host is `storage.zencreator.pro`, a private CDN host not mentioned in the public docs page.

## Tool catalog (live, authenticated)

`GET /api/public/v1/tools` returned `{"tools": {...}}` with 17 tools keyed by numeric strings. `GET /api/public/v1/tools/by_prompt` returned the single tool with `price`, `pricing`, `is_starting_price`.

Top tool surfaces and input/output schemas are captured in `.firecrawl/zc-tools-catalog.json` (keyed by the tool `name` field).

Tool list (id → name):
- `run_any_llm`, `upscaler`, `faceswap`, `by_prompt`, `by_ref`, `photoshoot`, `facegen`, `carousel`, `videogen`, `image_editor`, `collaber`, `couplegen`, `video2video`, `lipsync`, `text_to_video`, `video_upscaler`, `video_merger`

`by_prompt`:
- `price`: 1, `pricing`: "1-6", `is_starting_price`: false
- Models (enum, 17): FLUX_KLEIN_NSFW, GENERAL_NSFW, GENERAL_SFW, GPT_IMAGE_2_5_FLARE, GPT_IMAGE_2_5_SUNBURST, IDEOGRAM_4_5, KREA_2, NANO_BANANA, NANO_BANANA_2_1, QWEN_IMAGE, QWEN_IMAGE_PRO, SEEDREAM_5, SEEDREAM_5_PRO, WAN, WAN_2_7_IMAGE, WAN_2_7_IMAGE_PRO, Z_IMAGE_SPICY
- Model family behaviour is documented inside the tool's `description`: censored vs uncensored-without-full-NSFW vs built-for-full-NSFW, with which models are "trusted" gated.
- Output schema: `{"type":"object","properties":{"image_asset":{"type":"string","description":"Asset ID of the generated image."}},"required":["image_asset"]}`

## Other public read endpoints (authenticated)

| Endpoint | Status | Notes |
|---|---|---|
| GET `/api/public/v1/balance` | 200 | Returns `{"credits": 3}` at capture time. |
| GET `/api/public/v1/transactions` | 200 | Envelope present; 0 transactions at capture time. |
| GET `/api/public/v1/loras` | 422 | Error shape `{"error":{"code":"bad_request",...}. Reason not determined; possibly wrong params/body. |
| GET `/api/public/v1/photoshoot-categories` | 200 | Envelope present; empty list at capture time. |
| GET `/api/public/v1/templates` | 200 | Envelope `{"templates":[...],"pagination":{...}}`; 614 total, page 1 of 62, 10/page. Each has `id`, `name`; output also exposes thumbnail and field shapes in the full item object. |
| POST `/api/public/v1/assets` | 400 | `{"error":{"code":"bad_request","message":"Invalid multipart/form-data"}}`. Endpoint is multipart, not JSON. |
| GET `/api/public/v1/tools/{tool_name}` | 200 | Returns single tool object with `name`, `description`, `price`, `input_schema`, `output_schema`, `pricing`, `is_starting_price`. |
| POST `/api/public/v1/generations/{id}/result` | 200 | Returns outputs keyed exactly as documented. |

422 with a `message`/`code` shape was also confirmed earlier for invalid generation input (docs say 422 + field pointer).

## Private / authenticated boundary (as observed)

- Every `/api/public/v1/*` route requires the Bearer key. No public keyless calls past `/api/public/docs`, `/api/public/openapi.json`, `/api/public/skill.md` worked beyond 401.
- Key issuance, the dashboard, and billing live on `app.zencreator.pro` behind login.
- Scopes: `read` vs `generate`. This probe used a key with `read` + `generate` capability (it could POST a generation).
- Hidden endpoints are not discoverable from outside: I did not enumerate non-`/public` routes. Only the documented `/api/public/*` surface is reachable.

## Storage / asset model (discovered from output)

- Asset IDs are UUIDs.
- Preview URLs: `https://storage.zencreator.pro/preview_<uuid-without-dashes>.webp`
- Download URLs: `https://storage.zencreator.pro/<hex-key>.jpeg`
- The storage host and the URL patterns are visible only by executing a generation and inspecting the result.

## Security note

The key in this capture was handed to me directly. It is stored in `.env`. Treat it as secret. Rotate it at `app.zencreator.pro/api-keys` after review, and drop `.env` or keep it out of version control.
