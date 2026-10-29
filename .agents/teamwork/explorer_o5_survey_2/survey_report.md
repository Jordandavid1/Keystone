# Comprehensive Survey Report: Atomic Chat APIs, Tunnels & Local State

**Author**: Explorer Survey 2 (`teamwork_preview_explorer`)  
**Date**: 2026-10-28  
**Scope**: Local Atomic Chat Control API, Public API, Cloudflare Tunnels, Filesystem State  

---

## Executive Summary

1. **Atomic Chat Control API (`http://127.0.0.1:56603/atomic/v1`)** is **online** and functional:
   - Authenticates via header `Authorization: Bearer <control-token>` where `<control-token>` is read from `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token`.
   - `GET /atomic/v1/cloud/providers` returns HTTP 200 with 7 providers, including `pinkcherry-kaggle` and `llamacpp-server`.
   - `GET /atomic/v1/server/selection` returns HTTP 200 with active model `PinkCherry-MiniMax-H3` assigned to provider `pinkcherry-kaggle`.
   - `GET /atomic/v1/diffusion/video/gallery?offset=0&limit=10` returns HTTP 200 (`total: 0`, `items: []`).
   - `GET /atomic/v1/remote-access` returns HTTP 200 reporting active tunnel status and URL.

2. **Atomic Chat Public API Server (`http://127.0.0.1:1337/v1`)** is **online** and functional:
   - Protected by rotated bearer token `sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay`.
   - `GET /v1/models` returns HTTP 200 with 131 models; `PinkCherry-MiniMax-H3` is included.
   - `GET /v1/videos` returns HTTP 200 (`{"object": "list", "data": [], ...}`).
   - `POST /v1/videos` validates input against OpenAI Videos API specs (returned HTTP 400 `prompt is required` on `{}`).

3. **Cloudflare Tunnels**:
   - **Local Atomic Chat Remote-Access Tunnel**:
     - Process: `cloudflared.exe` PID 2308.
     - Binary: `C:\Users\Lesia Eden\AppData\Local\Atomic Chat\cloudflared.exe`.
     - Target: `http://127.0.0.1:1337`.
     - Active Public URL: `https://models-stopped-follows-problems.trycloudflare.com`
     - Live verification: Tested over HTTPS with bearer token; returned HTTP 200 on both `/v1/models` and `/v1/videos`.
     - Configuration for Kaggle Secrets:
       - `ATOMIC_API_BASE_URL`: `https://models-stopped-follows-problems.trycloudflare.com/v1`
       - `ATOMIC_API_KEY`: `sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay`
   - **Kaggle GPU ComfyUI Bridge Tunnel**:
     - Active Public URL: `https://likewise-transmission-violations-investigations.trycloudflare.com`
     - Status: Live; `GET /v1/models` returns `PinkCherry-MiniMax-H3` (owned by `kaggle-comfyui`), `GET /v1/videos` returns HTTP 200.
     - Already wired into Atomic Chat's `pinkcherry-kaggle` and `llamacpp-server` providers.

4. **Filesystem State**:
   - Video Gallery Directory: `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos` exists and currently contains 0 files.
   - Control Token File: `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token` exists (43 bytes).
   - Configuration & Metadata: `local-api-server.json`, `remote-access-tunnel.json`, `settings.json`, and `credentials.json` all exist in valid JSON state.

---

## 1. Atomic Chat Control API (`http://127.0.0.1:56603/atomic/v1`)

### Authentication Mechanism
- The Control API requires an `Authorization: Bearer <control-token>` header.
- Token location: `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token`
- Token format: 43-character alphanumeric string (`IITDjy...wpBE`).

### Tested Endpoints & Exact Evidence

#### `GET /atomic/v1/cloud/providers`
- **HTTP Status**: 200 OK
- **Payload Summary**:
  ```json
  {
    "providers": [
      {
        "provider": "ollama",
        "base_url": "http://localhost:11434/v1",
        "custom_headers": [],
        "models": [],
        "has_api_key": false
      },
      {
        "provider": "chatgpt",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "custom_headers": [],
        "models": [],
        "has_api_key": false
      },
      {
        "provider": "llamacpp-server",
        "base_url": "https://likewise-transmission-violations-investigations.trycloudflare.com/v1",
        "custom_headers": [],
        "models": ["PinkCherry-MiniMax-H3"],
        "has_api_key": true
      },
      {
        "provider": "automatic1111",
        "base_url": "http://127.0.0.1:7860",
        "custom_headers": [],
        "models": [],
        "has_api_key": false
      },
      {
        "provider": "sdcpp-server",
        "base_url": "http://127.0.0.1:1234",
        "custom_headers": [],
        "models": [],
        "has_api_key": false
      },
      {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "custom_headers": [],
        "models": ["gpt-5.5", "gpt-5.4", ...],
        "has_api_key": true
      },
      {
        "provider": "pinkcherry-kaggle",
        "base_url": "https://likewise-transmission-violations-investigations.trycloudflare.com/v1",
        "custom_headers": [],
        "models": ["PinkCherry-MiniMax-H3"],
        "has_api_key": true
      }
    ]
  }
  ```

#### `GET /atomic/v1/server/selection`
- **HTTP Status**: 200 OK
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

#### `GET /atomic/v1/diffusion/video/gallery`
- **Calling without parameters**: Returned HTTP 400: `{"error":{"code":"INVALID_REQUEST","message":"The request is not valid.","details":"offset: expected a whole number, zero or more"}}`.
- **Calling with `?offset=0` only**: Returned HTTP 400: `{"error":{"code":"INVALID_REQUEST","message":"The request is not valid.","details":"limit: expected a whole number, zero or more"}}`.
- **Calling with `?offset=0&limit=10`**:
  - **HTTP Status**: 200 OK
  - **Payload**:
    ```json
    {
      "items": [],
      "hasMore": false,
      "total": 0
    }
    ```

#### Discovered Endpoint: `GET /atomic/v1/remote-access`
- **HTTP Status**: 200 OK
- **Payload**:
  ```json
  {
    "state": "online",
    "url": "https://models-stopped-follows-problems.trycloudflare.com",
    "error": null,
    "blockReason": null,
    "canStart": false,
    "canStop": true,
    "serverHasApiKey": true
  }
  ```

#### Discovered Endpoint: `GET /atomic/v1/server`
- **HTTP Status**: 200 OK
- **Payload**:
  ```json
  {
    "running": true,
    "host": "127.0.0.1",
    "port": 1337,
    "prefix": "/v1",
    "requires_api_key": true,
    "pid": 32524
  }
  ```

---

## 2. Atomic Chat Public API Server (`http://127.0.0.1:1337/v1`)

### Authentication Mechanism
- Header: `Authorization: Bearer sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay`
- Process: PID 32524 (`atomic-chat-app-core.exe`).

### Tested Endpoints & Exact Evidence

#### `GET /v1/models`
- **HTTP Status**: 200 OK
- **Total Models**: 131 models returned.
- **Verification**: `PinkCherry-MiniMax-H3` is present in the model list.

#### `GET /v1/videos`
- **HTTP Status**: 200 OK
- **Payload**:
  ```json
  {
    "object": "list",
    "data": [],
    "first_id": null,
    "last_id": null,
    "has_more": false
  }
  ```

#### `POST /v1/videos` (Validation Contract Test)
- **Request**: `POST /v1/videos` with empty JSON body `{}`
- **HTTP Status**: 400 Bad Request
- **Payload**:
  ```json
  {
    "error": {
      "message": "prompt is required",
      "type": "invalid_request_error",
      "param": "prompt",
      "code": null
    }
  }
  ```
  *Confirms standard OpenAI-compatible Video API endpoint implementation.*

---

## 3. Local Processes and Cloudflare Tunnels

### Active Processes
- **`atomic-chat-app-core.exe`**:
  - PID: `32524`
  - Path: `C:\Users\Lesia Eden\AppData\Local\Atomic Chat\resources\bin\atomic-chat-app-core.exe`
  - Listening ports: `127.0.0.1:56603` (Control API) and `127.0.0.1:1337` (Public API).
- **`cloudflared.exe`**:
  - PID: `2308`
  - Path: `C:\Users\Lesia Eden\AppData\Local\Atomic Chat\cloudflared.exe`
  - Start time: `2026-10-28 12:52:07 AM`
  - Command line:
    `"C:\Users\Lesia Eden\AppData\Local\Atomic Chat\cloudflared.exe" tunnel --config "C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\cloudflared-empty.yml" --url http://127.0.0.1:1337 --no-autoupdate`

### Cloudflare Tunnel Architecture
There are **two** distinct Cloudflare tunnels involved in this ecosystem:

| Tunnel Identifier | Origin / Target | Public URL | Status | Role |
|-------------------|-----------------|------------|--------|------|
| **Local Remote Access Tunnel** | `127.0.0.1:1337` on user desktop (PID 2308) | `https://models-stopped-follows-problems.trycloudflare.com` | **ONLINE** (HTTP 200) | Exposes local Atomic Chat Public API to Kaggle notebook (`ATOMIC_API_BASE_URL`) |
| **Kaggle ComfyUI Bridge Tunnel** | Kaggle GPU ComfyUI bridge (wrapping `8188`) | `https://likewise-transmission-violations-investigations.trycloudflare.com` | **ONLINE** (HTTP 200) | Serves `PinkCherry-MiniMax-H3` inference back to Atomic Chat |

### Live Tunnel Endpoint Verification
1. `GET https://models-stopped-follows-problems.trycloudflare.com/v1/models` -> **HTTP 200 OK**
2. `GET https://models-stopped-follows-problems.trycloudflare.com/v1/videos` -> **HTTP 200 OK**
3. `GET https://likewise-transmission-violations-investigations.trycloudflare.com/v1/models` -> **HTTP 200 OK**
   - Returns: `{"object": "list", "data": [{"id": "PinkCherry-MiniMax-H3", "object": "model", "name": "PinkCherry 1.8 MiniMax H3 (Kaggle GPU)", "owned_by": "kaggle-comfyui"}]}`
4. `GET https://likewise-transmission-violations-investigations.trycloudflare.com/v1/videos` -> **HTTP 200 OK**
   - Returns: `{"object": "list", "data": []}`

---

## 4. Filesystem State

### Video Directory
- Path: `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos`
- Exists: `True`
- File count: `0` (Ready to receive `.mp4` video outputs from inference).

### Configuration & State Files
- `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token`:
  - Size: 43 bytes
  - Masked prefix/suffix: `IITDjy...wpBE`
- `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\local-api-server.json`:
  - Contains: `{"running": true, "host": "127.0.0.1", "port": 1337, "prefix": "/v1", "requires_api_key": true, "pid": 32524}`
- `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\remote-access-tunnel.json`:
  - Contains: `{"pid": 2308, "process_start_id": "win32-utc:639287599271702824", "started_at_secs": 1793163127, "instance_id": "8140e166-180c-4669-a5f1-9e53fa3061a3", "exe": "C:\\Users\\Lesia Eden\\AppData\\Local\\Atomic Chat\\cloudflared.exe"}`
- `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\credentials.json`:
  - Contains bound provider credentials for `openai`, `pinkcherry-kaggle`, and `llamacpp-server`.

---

## 5. Parameter Mapping for Downstream Workers (Milestones 1 & 2)

| Setting Name | Verified Value | Destination / Usage |
|--------------|----------------|---------------------|
| `ATOMIC_API_BASE_URL` | `https://models-stopped-follows-problems.trycloudflare.com/v1` | Kaggle Secrets via Edge Tab `1746398736` |
| `ATOMIC_API_KEY` | `sk-atomic-bsOlH4cKir-ThsyEJFy-xDpAntQWgjay` | Kaggle Secrets via Edge Tab `1746398736` |
| `KAGGLE_BRIDGE_URL` | `https://likewise-transmission-violations-investigations.trycloudflare.com/v1` | Configured in Atomic Chat `pinkcherry-kaggle` & `llamacpp-server` |
| `CONTROL_API_URL` | `http://127.0.0.1:56603/atomic/v1` | Local Control API calls |
| `CONTROL_TOKEN` | Read from `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\atomic-core\control-token` | Header `Authorization: Bearer <token>` |
| `VIDEO_GALLERY_DIR` | `C:\Users\Lesia Eden\AppData\Roaming\Atomic Chat\data\videos` | Target destination for completed video files |
| `MODEL_NAME` | `PinkCherry-MiniMax-H3` | Request payload for video generation |
