# Handoff Report: Technical Specification Survey 1

**Agent**: Spec Miner Survey 1 (`spec_miner_o5_survey_1`)  
**Recipient**: Orchestrator (`ed5a80a8-29be-484b-b744-03a33d6a167b`)  
**Date**: 2026-10-28T05:20:00Z  
**Type**: Hard Handoff (Task Complete)

---

## 1. Observation

1. **Firecrawl Developer Index & OpenAI Documented OpenAPI**:
   - Querying `https://api.firecrawl.dev/v2/search/developer` for `OpenAI Videos API` returned status 200 with hits pointing to `https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml`. Passages verify primary-source cURL and SDK syntax: `curl https://api.openai.com/v1/videos -H "Authorization: Bearer $OPENAI_API_KEY" -F "model=..." -F "prompt=..."`.
2. **Atomic Chat Public OpenAPI Specification**:
   - Fetched `http://127.0.0.1:1337/openapi.json` (37,152 bytes, saved at `.agents/teamwork/spec_miner_o5_survey_1/openapi_1337.json`).
   - Documented endpoints:
     - `POST /videos`: operationId `createVideo`, request body `CreateVideoDto` (`prompt`, `seconds`, `size`, `model`, `seed`, `negative_prompt`, `aspect_ratio`, `generate_audio`, `input_reference`), response `VideoDto` with `status: "queued"|"in_progress"|"completed"|"failed"`.
     - `GET /videos/{video_id}`: operationId `retrieveVideo`, returns `VideoDto`.
     - `GET /videos/{video_id}/content`: operationId `downloadVideoContent`, query parameter `?variant=video|thumbnail`, returns binary `video/mp4`, `video/webm`, or `image/png`.
     - `GET /videos`: operationId `listVideos`, query `limit` (int 1-100), `after` (cursor), returns `VideoListResponseDto`.
     - `DELETE /videos/{video_id}`: operationId `deleteVideo`, returns `DeleteVideoResponseDto` (`{ id, object: "video", deleted: true }`).
3. **Atomic Chat Core Reverse-Engineered Bundle**:
   - Inspected `atomic-chat-app-core.exe` (`\\?\C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe`):
     - `OPENAI_VIDEOS` adapter (`src/media/adapters/openai-videos.ts` at index 116333435): submits `POST {baseUrl}/videos`, polls `GET {baseUrl}/videos/{id}`, downloads `GET {baseUrl}/videos/{id}/content`, cancels `DELETE {baseUrl}/videos/{id}`.
     - `MEDIA_DIALECTS` array contains `"openai-videos"`, `"minimax-video"`, `"minimax-video-v2"`, etc.
     - `CloudRegistry.upsert`: accepts `media: { models: [{ id, kind: "video" }], video_api: "openai-videos" }`.
     - Control endpoints registered with prefix `/atomic/v1`:
       - `GET /atomic/v1/cloud/providers`: `sendJson(res, 200, { providers: deps.cloud.list() })`.
       - `PUT /atomic/v1/cloud/providers/:provider`: `deps.cloud.upsert({ ...body, provider: params.provider })`.
       - `GET /atomic/v1/server/selection`: `sendJson(res, 200, { models: deps.publicServer.selection() })`.
       - `PUT /atomic/v1/server/selection`: requires `{"models": [{"model": "<id>", "provider": "<provider>"}]}` with non-empty strings.
4. **Live Kaggle Notebook Editor Tab (`1746398736`)**:
   - `Cell 4`: ComfyUI runtime started on `127.0.0.1:8188` using `main.py --listen 127.0.0.1 --port 8188 --cuda-device 0`.
   - `Cell 6`: Downloads fine-tune weights `SexGod1979/PinkCherry-NSFW_MiniMax-H3` (`PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors`, 21.1 GB) and official components `Comfy-Org/MiniMax-H3` (AWQ text encoder, VAEs, turbo LoRA).
   - `Cell 7`: Deploys `comfy_openai_bridge.py` wrapping ComfyUI on port 8189 and exposing through Cloudflare tunnel `https://likewise-transmission-violations-investigations.trycloudflare.com/v1`. Observed error when bridge called with ComfyUI down: `urllib.error.URLError: <urlopen error [Errno 111] Connection refused>`.
   - `Cell 8`: Verified `RUN_ATOMIC_VIDEO = False` flag and `atomic.post(f'{ATOMIC_BASE_URL}/videos')` client logic using Kaggle Secrets `ATOMIC_API_BASE_URL` and `ATOMIC_API_KEY`.
   - `Cell 9`: Converts UI workflow to API prompt `api_prompt`, submits to `POST http://127.0.0.1:8188/prompt`, polls `GET http://127.0.0.1:8188/history/{prompt_id}`, parses `outputs[output_id]['gifs'][0]['fullpath']`, copies to `/kaggle/working/PinkCherry_H3_T2V_Test.mp4`.
   - Executed output observed: `GENERATION_SUCCESS /kaggle/working/PinkCherry_H3_T2V_Test.mp4 430379 bytes codec_name=h264 width=352 height=608 codec_name=aac duration=1.625000`.

---

## 2. Logic Chain

1. Starting from the user request and scope, the integration requires bridging Kaggle GPU ComfyUI `PinkCherry-MiniMax-H3` to Atomic Chat's UI and API via an OpenAI-compatible Videos format.
2. Direct inspection of Atomic Chat's public server OpenAPI spec (`/openapi.json`) and core runtime (`atomic-chat-app-core.exe`) established the exact request/response schemas for `/v1/videos`, `/v1/videos/{id}`, and `/v1/videos/{id}/content`.
3. In the core's `OPENAI_VIDEOS` adapter implementation, Atomic Chat communicates with upstream cloud providers by making `POST {baseUrl}/videos` with `{ model, prompt, seconds, size, seed, negative_prompt }`, polling `GET {baseUrl}/videos/{id}`, and downloading `GET {baseUrl}/videos/{id}/content`.
4. To register a provider so that Atomic Chat's Desktop UI and Public API recognise it, the Control API requires:
   - Calling `PUT /atomic/v1/cloud/providers/{provider}` with `media: { models: [{ id: "PinkCherry-MiniMax-H3", kind: "video" }], video_api: "openai-videos" }`.
   - Calling `PUT /atomic/v1/server/selection` with `models: [{ model: "PinkCherry-MiniMax-H3", provider: "{provider}" }]`.
5. In the Kaggle ComfyUI session, the graph must be represented in API Prompt format (`/kaggle/working/h3_api_prompt.json`), not UI workflow format. The terminal output node `VHS_VideoCombine` produces an H.264+AAC `.mp4` video.
6. The bridge on Kaggle (`comfy_openai_bridge.py`) must be active while ComfyUI (`127.0.0.1:8188`) is running, exposing `/v1/videos` over the Cloudflare HTTPS tunnel so that Atomic Chat's adapter can submit and poll jobs seamlessly.

---

## 3. Caveats

- ComfyUI must be started and ready on `127.0.0.1:8188` before any request hits `comfy_openai_bridge.py` (otherwise it fails with `ConnectionRefusedError` during prompt template loading).
- `PathchSageAttentionKJ` custom node in ComfyUI must be bypassed on Nvidia T4 hardware (which lacks SageAttention kernel support), as already automated in Cell 9.
- Cloudflare tunnels on trycloudflare.com are ephemeral; when a tunnel process restarts, `base_url` in Atomic Chat's provider configuration and `ATOMIC_API_BASE_URL` in Kaggle Secrets must be updated with the new hostname.

---

## 4. Conclusion

All technical specifications for:
1. OpenAI Videos API (`POST /v1/videos`, `GET /v1/videos/{id}`, `GET /v1/videos/{id}/content`, `VideoDto` schema),
2. ComfyUI MiniMax-H3 API Execution Contract (`/kaggle/working/h3_api_prompt.json`, `VHS_VideoCombine` output node, polling loop, H.264+AAC mp4 output), and
3. Atomic Chat Control API (`PUT /atomic/v1/cloud/providers/:provider`, `PUT /atomic/v1/server/selection`)
have been comprehensively extracted, reverse-engineered, and documented in `spec_report.md` with primary-source verification. The technical path for Milestone 1, 2, and 3 implementation is 100% clear.

---

## 5. Verification Method

To independently verify all findings:
1. **OpenAPI Spec**: Fetch `http://127.0.0.1:1337/openapi.json` and inspect paths `/videos`, `/videos/{video_id}`, `/videos/{video_id}/content`.
2. **Atomic Chat Control API**:
   ```bash
   TOKEN=$(cat "C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token")
   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:56603/atomic/v1/cloud/providers
   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:56603/atomic/v1/server/selection
   ```
3. **ComfyUI Output**:
   Check Kaggle Notebook Cell 9 execution output or run `ffprobe` on `/kaggle/working/PinkCherry_H3_T2V_Test.mp4`:
   `ffprobe -v error -show_entries format=duration:stream=codec_name,width,height -of default=noprint_wrappers=1 /kaggle/working/PinkCherry_H3_T2V_Test.mp4`.
