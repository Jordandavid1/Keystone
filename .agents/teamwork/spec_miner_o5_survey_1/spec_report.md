# Technical Specification Report: OpenAI Videos API, ComfyUI MiniMax-H3, & Atomic Chat Integration

**Date**: 2026-10-28T05:15:00Z  
**Author**: Spec Miner Survey 1 (`spec_miner_o5_survey_1`)  
**Mission**: Extract and verify technical specifications for OpenAI Videos API, ComfyUI MiniMax-H3 prompt JSON schema, and Atomic Chat provider registration.

---

## 1. Authoritative Specification Sources

All specifications and schemas documented herein were discovered and verified from primary, authoritative sources:
1. **Firecrawl Developer Index & Upstream OpenAPI Documented Specs**:
   - Primary upstream source: `https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml` (indexed via Firecrawl Developer Search `https://api.firecrawl.dev/v2/search/developer`).
2. **Atomic Chat Public OpenAPI Specification**:
   - `http://127.0.0.1:1337/openapi.json` (37,152 bytes) — Canonical schema for Atomic Chat Local API Server v2.2.26.
3. **Atomic Chat Core Architecture & Dialect Source**:
   - Reverse-engineered binary inspection of `atomic-chat-app-core 0.19.0` (`\\?\C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe`):
     - `src/media/adapters/openai-videos.ts` (`OPENAI_VIDEOS` adapter implementation)
     - `src/server/public/videos.ts` (`serveCreate`, `serveList`, `serveContent`, `serveDelete`)
     - `src/cloud/registry.ts` (`CloudRegistry.upsert`, `checkedMedia`, `readStoredMedia`)
     - `src/control/server.ts` (`PUT /atomic/v1/server/selection`, `GET/PUT /atomic/v1/cloud/providers`)
4. **Active Kaggle ComfyUI PinkCherry-MiniMax-H3 Environment**:
   - Live Kaggle Notebook (`Tab 1746398736` / `https://www.kaggle.com/code/rigormortice/pinkcherry-nsfw-minimax-h3-download/edit`):
     - `Cell 4`: ComfyUI runtime configuration & startup (`127.0.0.1:8188`)
     - `Cell 6`: Model checkpoints (`SexGod1979/PinkCherry-NSFW_MiniMax-H3` pruned int8 21.1GB + `Comfy-Org/MiniMax-H3` nvfp4 AWQ text encoder, VAEs, turbo LoRA)
     - `Cell 7`: `comfy_openai_bridge.py` & Cloudflare tunnel bridge (`/v1/videos`)
     - `Cell 8`: `RUN_ATOMIC_VIDEO` client execution switch
     - `Cell 9`: `h3_api_prompt.json` prompt compilation, API submission, polling loop, and `ffprobe` verification of generated `.mp4` video.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | OpenAI Videos API | `POST /v1/videos` | Creates a video generation job (text-to-video or image-to-video) | JSON object or multipart form (`model`, `prompt`, `seconds`, `size`, `seed`, `negative_prompt`, optional `input_reference`) | `VideoDto` with `status: "queued"`, `id`, `progress: 0`, timestamps | HTTP 400 for empty prompt/invalid params; 503 if model not loaded/enabled | `openapi.json`, `videos.ts`, Stainless OpenAPI |
| 2 | OpenAI Videos API | `GET /v1/videos/{video_id}` | Retrieves execution status and metadata of a video job | Path parameter `video_id` (string) | `VideoDto` with `status: "queued"\|"in_progress"\|"completed"\|"failed"`, `progress: 0..100`, `error`, `atomic` | HTTP 404 if `video_id` does not exist | `openapi.json`, `videos.ts`, `OPENAI_VIDEOS` adapter |
| 3 | OpenAI Videos API | `GET /v1/videos/{video_id}/content` | Streams binary media clip of a completed video | Path parameter `video_id`, optional query `?variant=video\|thumbnail` | Binary stream: `video/mp4` or `video/webm` (or `image/png` for thumbnail poster) with `Content-Length` | HTTP 404 if video is still in progress or not found | `openapi.json`, `serveContent`, `OPENAI_VIDEOS.download` |
| 4 | OpenAI Videos API | `GET /v1/videos` | Lists local gallery videos and running jobs | Query params: `limit` (int 1-100, default 20), `after` (cursor id) | `VideoListResponseDto` (`object: "list"`, `data: [...]`, `has_more: bool`) | HTTP 400 if `limit` is out of bounds | `openapi.json`, `serveList` |
| 5 | OpenAI Videos API | `DELETE /v1/videos/{video_id}` | Cancels running generation or removes finished video from gallery | Path parameter `video_id` | `DeleteVideoResponseDto` (`{ id, object: "video", deleted: true }`) | HTTP 404 if video not found | `openapi.json`, `OPENAI_VIDEOS.cancel` |
| 6 | OpenAI Videos API | `GET /v1/videos/models` / `GET /v1/models` | Lists available video generation models | None (optional Bearer auth) | `{ "data": [ { "id": "...", "name": "..." } ] }` | HTTP 401 if unauthenticated | `OPENAI_VIDEOS.listModels`, `models.ts` |
| 7 | ComfyUI Execution | `POST 127.0.0.1:8188/prompt` | Submits prompt workflow DAG to ComfyUI execution queue | JSON `{ "prompt": api_prompt, "client_id": "..." }` where `api_prompt` maps node IDs to `{ class_type, inputs }` | `{ "prompt_id": "...", "number": int, "node_errors": {} }` | HTTP 400 if node schema or required inputs fail validation | Kaggle Notebook Cell 9, ComfyUI API spec |
| 8 | ComfyUI Execution | `GET 127.0.0.1:8188/history/{id}` | Polls status and outputs of queued prompt | Path parameter `prompt_id` | `{ "<id>": { "status": { "status_str": "success"\|"error", "completed": true }, "outputs": { "<node>": { "gifs": [...] } } } }` | Empty dict `{}` if job not yet completed | Kaggle Notebook Cell 9, `find_mp4_in_outputs` |
| 9 | ComfyUI Execution | `ws://127.0.0.1:8188/ws` | Real-time WebSocket execution progress stream | Query parameter `?clientId=<uuid>` | JSON events: `execution_start`, `executing`, `progress`, `executed`, `execution_success`, `execution_error` | WebSocket disconnect / close event | ComfyUI frontend protocol, `probe_hardware.py` |
| 10 | ComfyUI Execution | `GET 127.0.0.1:8188/view` | Fetches generated output binary file | Query parameters: `filename`, `subfolder`, `type="output"` | Binary data stream (`video/mp4`) | HTTP 404 if file does not exist in output dir | ComfyUI standard server API |
| 11 | Atomic Chat Control | `GET /atomic/v1/cloud/providers` | Lists all configured cloud and self-hosted providers | Control Bearer token | `{ "providers": [ ProviderConfig... ] }` | HTTP 401 if control token invalid | `dump_control_routes.py`, `atomic-core` |
| 12 | Atomic Chat Control | `PUT /atomic/v1/cloud/providers/:provider` | Registers or updates a cloud/self-hosted provider config | JSON body with `base_url`, `api_key`, `models`, `custom_headers`, `media` (with `models` and `video_api`) | Updated provider object with `has_api_key: true` | HTTP 400 if `media` or dialect is malformed | `CloudRegistry.upsert`, `checkedMedia` |
| 13 | Atomic Chat Control | `DELETE /atomic/v1/cloud/providers/:provider` | Removes a registered cloud provider | Path param `:provider` | `{ "removed": true }` | HTTP 401 if unauthenticated | `registerCloudRoutes` |
| 14 | Atomic Chat Control | `GET /atomic/v1/server/selection` | Lists currently active model-to-provider mappings | Control Bearer token | `{ "models": [ { "model": "<id>", "provider": "<slug>" } ] }` | HTTP 401 if unauthenticated | `deps.publicServer.selection()` |
| 15 | Atomic Chat Control | `PUT /atomic/v1/server/selection` | Sets active server model selection for Public API | JSON `{ "models": [ { "model": "<id>", "provider": "<slug>" } ] }` | Updated `{ "models": [ ... ] }` | HTTP 400 `INVALID_ARGUMENT` if strings empty | `parseSelection`, `setSelection` |
| 16 | Atomic Chat Control | `GET /atomic/v1/diffusion/video/gallery` | Queries generated video items in local storage | Query params: `offset`, `limit`, `includeArchived` | `{ "items": [ VideoItem... ], "total": int }` | HTTP 401 if unauthenticated | `registerDiffusionVideoRoutes` |

---

## 3. Edge Cases & Observed Behaviors

| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| 1 | `POST /v1/videos` (Public API) | `prompt` is empty string `""` and no `input_reference` | Returns HTTP 400 `invalid_request_error` with message `"prompt is required"`, param `"prompt"`. |
| 2 | `POST /v1/videos` (Public API) | `seconds` > 60 on remote provider | Rejects with HTTP 400: `"seconds must be a number between 0 and 60"`. |
| 3 | `POST /v1/videos` (Public API) | `model` is specified but not loaded locally and not registered on Cloud page | Returns HTTP 503 `server_error`, code `"model_not_loaded"`, message `"No video model loaded. Load a video model in Atomic Chat first."` |
| 4 | `GET /v1/videos/{id}/content` | Clip is currently in state `"queued"` or `"in_progress"` | Returns HTTP 404 Not Found (`"The clip is not ready or does not exist."`). |
| 5 | `PUT /atomic/v1/server/selection` | Body contains `{ "models": [{"model": "", "provider": "pinkcherry"}] }` | Returns HTTP 400 with `AtomicCoreError("INVALID_ARGUMENT", 'selection needs {"models": [{"model": "<id>", "provider": "<provider>"}]} with non-empty strings')`. |
| 6 | `PUT /atomic/v1/cloud/providers/:provider` | `media.video_api` set to an unknown dialect string (e.g. `"custom-api"`) | Returns HTTP 400 `INVALID_ARGUMENT`: `"media.video_api must be one of the video adapters"`. Supported video dialects: `"openai-videos"`, `"openrouter-videos"`, `"xai-videos"`, `"gemini-veo"`, `"minimax-video"`, `"minimax-video-v2"`, `"dashscope-video"`, `"aimlapi-videos"`, `"hf-videos"`. |
| 7 | ComfyUI `comfy_openai_bridge` | Bridge receives `POST /v1/videos` while ComfyUI process on `127.0.0.1:8188` is offline | Fails with `urllib.error.URLError: <urlopen error [Errno 111] Connection refused>` during `load_prompt_template()`. ComfyUI MUST be online on `127.0.0.1:8188` prior to bridge invocation. |
| 8 | ComfyUI Workflow Parsing | Node `PathchSageAttentionKJ` present in workflow on T4 GPU without SageAttention support | Custom nodes throw CUDA execution errors; bridge automatically patches the graph by splicing source model slot `[source_id, source_slot]` directly to downstream nodes and popping `PathchSageAttentionKJ`. |
| 9 | Public Server Host Header | Request to `127.0.0.1:1337/v1` with Host header not in `trusted_hosts` | Returns HTTP 403 Forbidden: `"The request Host is not allowed by Trusted Hosts"`. |
| 10 | Video Format | Video generated by ComfyUI `VHS_VideoCombine` | Generates standard H.264 video with AAC audio in MP4 container (`video/h264-mp4`), valid `ftyp` box header (`isom/iso2/avc1/mp41`), playable across all browser engines. |

---

## 4. Technical Specification: OpenAI Videos API

### 4.1 Endpoint Overview
The OpenAI Videos API specification exposed by Atomic Chat (`http://127.0.0.1:1337/v1`) and implemented by the Kaggle ComfyUI bridge (`comfy_openai_bridge.py`) defines an asynchronous generation protocol:

```
Client                             API Server / Bridge                         ComfyUI Backend
  |                                        |                                          |
  |--- POST /v1/videos ------------------->|                                          |
  |    {model, prompt, seconds, size}      |--- Compile prompt & POST /prompt ------->|
  |                                        |<-- 200 OK {prompt_id: "..."} ------------|
  |<-- 200 OK {id, status: "queued"} ------|                                          |
  |                                        |                                          |
  |--- GET /v1/videos/{id} --------------->|                                          |
  |<-- 200 OK {status: "in_progress"} -----|                                          |
  |                                        |                                          |
  |                                        |<-- History complete (video written) -----|
  |--- GET /v1/videos/{id} --------------->|                                          |
  |<-- 200 OK {status: "completed"} -------|                                          |
  |                                        |                                          |
  |--- GET /v1/videos/{id}/content ------->|                                          |
  |<-- 200 OK [binary video/mp4 stream] ---|                                          |
```

### 4.2 Detailed Endpoints & Schemas

#### 1. Create Video (`POST /v1/videos`)
- **Headers**:
  - `Authorization: Bearer <API_KEY>`
  - `Content-Type: application/json` (or `multipart/form-data`)
- **JSON Request Body (`CreateVideoDto`)**:
  ```json
  {
    "prompt": "A cinematic aerial view of a quiet mountain lake at sunrise",
    "model": "PinkCherry-MiniMax-H3",
    "seconds": "2",
    "size": "768x512",
    "seed": 42,
    "negative_prompt": "blurry, distorted, low quality",
    "generate_audio": false,
    "input_reference": null
  }
  ```
- **Multipart Form alternative**:
  - `model`: `"PinkCherry-MiniMax-H3"`
  - `prompt`: string
  - `seconds`: `"2"`
  - `size`: `"768x512"`
  - `input_reference`: binary image file (`image/png` or `image/jpeg`)
- **Response (`VideoDto`)**:
  ```json
  {
    "id": "video_41b631aa-5925-4fa3-921c-4b80c5b386a0",
    "object": "video",
    "model": "PinkCherry-MiniMax-H3",
    "status": "queued",
    "progress": 0,
    "created_at": 1793164800,
    "completed_at": null,
    "expires_at": null,
    "seconds": "2",
    "size": "768x512",
    "prompt": "A cinematic aerial view of a quiet mountain lake at sunrise",
    "remixed_from_video_id": null,
    "error": null,
    "atomic": {
      "job_id": "video_41b631aa-5925-4fa3-921c-4b80c5b386a0",
      "seed": 42,
      "path": null,
      "poster_path": null
    }
  }
  ```

#### 2. Retrieve Video Status (`GET /v1/videos/{video_id}`)
- **Response**:
  ```json
  {
    "id": "video_41b631aa-5925-4fa3-921c-4b80c5b386a0",
    "object": "video",
    "model": "PinkCherry-MiniMax-H3",
    "status": "completed",
    "progress": 100,
    "created_at": 1793164800,
    "completed_at": 1793164835,
    "expires_at": null,
    "seconds": "1.625",
    "size": "352x608",
    "prompt": "A cinematic aerial view of a quiet mountain lake at sunrise",
    "remixed_from_video_id": null,
    "error": null,
    "atomic": {
      "job_id": "video_41b631aa-5925-4fa3-921c-4b80c5b386a0",
      "seed": 42,
      "path": "C:\\Users\\Lesia Eden\\AppData\\Roaming\\Atomic Chat\\data\\videos\\video_41b631aa-5925-4fa3-921c-4b80c5b386a0.mp4",
      "poster_path": "C:\\Users\\Lesia Eden\\AppData\\Roaming\\Atomic Chat\\data\\videos\\video_41b631aa-5925-4fa3-921c-4b80c5b386a0.png"
    }
  }
  ```

#### 3. Download Video Content (`GET /v1/videos/{video_id}/content`)
- **Query Parameters**: `variant` (`"video"` default, or `"thumbnail"`)
- **Response Headers**:
  - `Content-Type: video/mp4` (or `image/png`)
  - `Content-Length: 430379`
  - `Content-Disposition: attachment; filename="video_41b631aa.mp4"`
- **Response Body**: Binary video stream (H.264 + AAC in MP4 container).

---

## 5. Technical Specification: ComfyUI MiniMax-H3 API Execution Contract

### 5.1 Architecture & Model Weights
- **Model Repo**: `SexGod1979/PinkCherry-NSFW_MiniMax-H3`
  - Diffusion weights: `1.8-hybrid/PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors` (stored in `/tmp/ComfyUI/models/diffusion_models/`, ~21.06 GB)
- **Official Components**: `Comfy-Org/MiniMax-H3`
  - Text encoder: `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
  - Video VAE: `vae/minimax_h3_video_vae_fp16.safetensors`
  - Audio VAE: `vae/minimax_h3_audio_vae_fp32.safetensors`
  - LoRA: `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`

### 5.2 API Prompt Format (`/kaggle/working/h3_api_prompt.json`)
The ComfyUI API does NOT accept the graphical UI workflow (`workflow.json` with `nodes`, `links`, and canvas coordinates). Instead, it requires an **API prompt dictionary**:
```json
{
  "132": {
    "class_type": "MiniMaxH3ModelLoader",
    "inputs": {
      "model_name": "PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors",
      "torch_dtype": "int8"
    }
  },
  "134": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "clip": ["132", 1],
      "text": "A cinematic aerial view of a quiet mountain lake at sunrise, gentle camera push-in, warm afternoon light"
    }
  },
  "140": {
    "class_type": "KSampler",
    "inputs": {
      "model": ["132", 0],
      "positive": ["134", 0],
      "negative": ["135", 0],
      "latent_image": ["138", 0],
      "seed": 42,
      "steps": 8,
      "cfg": 4.0,
      "sampler_name": "euler",
      "scheduler": "simple",
      "denoise": 1.0
    }
  },
  "145": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["140", 0],
      "vae": ["133", 0]
    }
  },
  "150": {
    "class_type": "VHS_VideoCombine",
    "inputs": {
      "images": ["145", 0],
      "frame_rate": 16,
      "loop_count": 0,
      "filename_prefix": "PinkCherry_H3_Test",
      "format": "video/h264-mp4",
      "pix_fmt": "yuv420p",
      "crf": 19,
      "save_output": true
    }
  }
}
```

### 5.3 Execution & Output Parsing
1. **Submission**:
   ```python
   response = requests.post(
       "http://127.0.0.1:8188/prompt",
       json={"prompt": api_prompt, "client_id": client_id},
       timeout=60,
   )
   prompt_id = response.json()["prompt_id"]
```
2. **Polling Loop**:
   ```python
   deadline = time.monotonic() + 900
   while time.monotonic() < deadline:
     res = requests.get(
         f"http://127.0.0.1:8188/history/{prompt_id}", timeout=30
     ).json()
     if prompt_id in res:
       hist = res[prompt_id]
       if hist["status"]["status_str"] == "success":
         # Parse outputs
         output_node = hist["outputs"]["150"]  # VHS_VideoCombine node ID
         video_info = (output_node.get("gifs") or output_node.get("videos"))[0]
         # video_info["fullpath"] -> '/tmp/ComfyUI/output/PinkCherry_H3_Test_00001.mp4'
         break
     time.sleep(5)
```

---

## 6. Technical Specification: Atomic Chat Provider Registration & Control API

### 6.1 Authentication & Base URL
- **Base URL**: `http://127.0.0.1:56603/atomic/v1`
- **Authentication**: Header `Authorization: Bearer <control-token>`
- **Token Location**: `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token`

### 6.2 Provider Registration (`PUT /atomic/v1/cloud/providers/:provider`)
To register the Kaggle GPU ComfyUI instance as an active cloud provider in Atomic Chat:
- **Method**: `PUT`
- **URL**: `http://127.0.0.1:56603/atomic/v1/cloud/providers/pinkcherry-kaggle` (or `llamacpp-server`)
- **Headers**:
  - `Authorization: Bearer <control-token>`
  - `Content-Type: application/json`
- **Payload**:
  ```json
  {
    "base_url": "https://likewise-transmission-violations-investigations.trycloudflare.com/v1",
    "api_key": "sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay",
    "custom_headers": [],
    "models": [
      "PinkCherry-MiniMax-H3"
    ],
    "media": {
      "models": [
        {
          "id": "PinkCherry-MiniMax-H3",
          "kind": "video"
        }
      ],
      "video_api": "openai-videos"
    }
  }
  ```
- **Validation Rules (from `CloudRegistry.upsert`)**:
  1. `provider`: Must match path param `:provider`, non-empty string.
  2. `base_url`: Trimmed string or null.
  3. `media.models`: Must be an array of objects `{ id: string, kind: "image" | "video" }`.
  4. `media.video_api`: Must be a recognized dialect: `"openai-videos"`.
- **Response**:
  ```json
  {
    "provider": "pinkcherry-kaggle",
    "base_url": "https://likewise-transmission-violations-investigations.trycloudflare.com/v1",
    "custom_headers": [],
    "models": ["PinkCherry-MiniMax-H3"],
    "media": {
      "models": [
        { "id": "PinkCherry-MiniMax-H3", "kind": "video" }
      ],
      "video_api": "openai-videos"
    },
    "has_api_key": true
  }
  ```

### 6.3 Server Model Selection (`PUT /atomic/v1/server/selection`)
To activate the model on Atomic Chat's Public Local API Server (`127.0.0.1:1337/v1`):
- **Method**: `PUT`
- **URL**: `http://127.0.0.1:56603/atomic/v1/server/selection`
- **Headers**:
  - `Authorization: Bearer <control-token>`
  - `Content-Type: application/json`
- **Payload**:
  ```json
  {
    "models": [
      {
        "model": "PinkCherry-MiniMax-H3",
        "provider": "pinkcherry-kaggle"
      }
    ]
  }
  ```
- **Response**:
  ```json
  {
    "models": [
      {
        "model": "PinkCherry-MiniMax-H3",
        "provider": "pinkcherry-kaggle"
      }
    ]
  }
  ```

Once selected, requests to `POST http://127.0.0.1:1337/v1/videos` with `{"model": "PinkCherry-MiniMax-H3"}` are automatically proxied via the `openai-videos` adapter to `https://likewise-transmission-violations-investigations.trycloudflare.com/v1/videos`. Completed clips are saved directly into `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos` and populated into `GET /atomic/v1/diffusion/video/gallery`.

---

## 7. Verification Method

1. **Verify OpenAI Videos API Contract**:
   Query `http://127.0.0.1:1337/openapi.json` and verify operation IDs `createVideo`, `retrieveVideo`, `downloadVideoContent`, and schemas `CreateVideoDto`, `VideoDto`.
2. **Verify Provider & Model Registration**:
   Execute `GET http://127.0.0.1:56603/atomic/v1/cloud/providers` with control token header and verify `"PinkCherry-MiniMax-H3"` appears with `video_api: "openai-videos"`.
3. **Verify Server Selection**:
   Execute `GET http://127.0.0.1:56603/atomic/v1/server/selection` and confirm `models` contains `{ "model": "PinkCherry-MiniMax-H3", "provider": "pinkcherry-kaggle" }`.
4. **Verify ComfyUI Video Output Compatibility**:
   Run `ffprobe` on any generated `.mp4` video in `/kaggle/working` or Atomic Chat video directory:
   - Video stream: `codec_name=h264`, pixel format `yuv420p`
   - Audio stream: `codec_name=aac`
   - Header: valid `ftyp` box header (`isom`, `iso2`, `mp41`)
   - File size > 100 KB
