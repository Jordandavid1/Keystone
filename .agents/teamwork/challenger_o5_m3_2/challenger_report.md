# Challenger Adversarial Verification Report: Milestone 3_2

**Target**: OpenAI-Videos API Contracts, Model Registration, and Video Stream Verification for `PinkCherry-MiniMax-H3`  
**Challenger**: Challenger M3_2 (`challenger_o5_m3_2`)  
**Verdict**: **CONFIRM** (All 5 primary contract assertions verified empirically; 6 adversarial stress dimensions evaluated)  
**Date**: 2026-10-28T07:10:00Z  

---

## Challenge Summary

**Overall Risk Assessment**: **LOW**

All primary interface contracts specified by the orchestrator passed empirical verification with 100% fidelity:
1. Remote Cloudflare Tunnel `GET /v1/models` reliably serves `PinkCherry-MiniMax-H3` with bearer authentication.
2. Local Control API `GET /atomic/v1/cloud/providers` binds `PinkCherry-MiniMax-H3` under provider `llamacpp-server` (and `pinkcherry-kaggle`) with `video_api: "openai-videos"`.
3. Target job `GET /v1/videos/d3321dfa79d545228d13f16d61e0c619` confirms `status == "completed"` and `progress == 100`.
4. Adversarial probing of non-existent jobs (`GET /v1/videos/non-existent-video-999`) reliably triggers proper HTTP 404 responses with standard OpenAI `invalid_request_error / not_found` payloads.
5. Video stream download `GET /v1/videos/d3321dfa79d545228d13f16d61e0c619/content` returns HTTP 200, `Content-Type: video/mp4`, exactly 2,818,134 bytes (> 100 KB), and an identical SHA-256 checksum matching the disk artifact (`3e447aac96bf68cb342c0cab3f55a9e51c462c63a7ed13e27326b5b137747917`).

---

## Challenges

### [Medium] Challenge 1: Upstream Kaggle Bridge Permissive Video ID Lookup
- **Assumption Challenged**: That the upstream ComfyUI bridge script (`comfy_openai_bridge.py` on Kaggle port 8189) independently manages per-job state and rejects invalid video IDs with HTTP 404.
- **Attack Scenario**: Direct probing of `https://likewise-transmission-violations-investigations.trycloudflare.com/v1/videos/non-existent-video-999` and `/content` bypasses Atomic Chat's local API server and queries the Kaggle bridge directly.
- **Observed Behavior**: The Kaggle bridge directly returns HTTP 200 and serves the latest generated `.mp4` artifact regardless of the requested job ID.
- **Blast Radius**: Low. Atomic Chat's desktop server (`http://127.0.0.1:1337` and its public Cloudflare tunnel `https://models-stopped-follows-problems.trycloudflare.com`) acts as an authoritative proxy and state store. Atomic Chat rejects non-existent job IDs with HTTP 404 prior to forwarding downstream. Direct access to the Kaggle bridge is only possible if an attacker discovers the ephemeral tunnel URL.
- **Mitigation**: In future revisions of `comfy_openai_bridge.py`, store ComfyUI prompt IDs in an in-memory dictionary mapping `prompt_id -> output_files`, returning HTTP 404 if the prompt ID is not present.

### [Low] Challenge 2: Parameter Validation on Duration Dialect
- **Assumption Challenged**: That the OpenAI Videos API standard allows arbitrary duration seconds (e.g. 2, 5, 10).
- **Attack Scenario**: Submitting `POST /v1/videos` with `seconds: "2"`, `seconds: "10"`, or `seconds: "99"`.
- **Observed Behavior**: Atomic Chat's video dispatcher rejects these requests with HTTP 400: `"PinkCherry-MiniMax-H3 cannot make a clip of 2 s."` or `"seconds must be a number between 0 and 60"`. Supported clips are 4, 8, 12 seconds.
- **Blast Radius**: None. Client applications (such as the Kaggle notebook client) specify `seconds: "4"` or omit the parameter (defaulting to 4), adhering to model constraints.
- **Mitigation**: Document supported durations in the model schema.

---

## Stress Test Results

| Test Scenario | Target URL | Expected Behavior | Actual Empirical Result | Status |
|---|---|---|---|---|
| **1. Model Registration** | `https://models-stopped-follows-problems.trycloudflare.com/v1/models` | HTTP 200, contains `PinkCherry-MiniMax-H3` | HTTP 200, `id: "PinkCherry-MiniMax-H3"`, `owned_by: "remote"` found among 131 models | **PASS** |
| **2. Provider Mapping** | `http://127.0.0.1:56603/atomic/v1/cloud/providers` | `llamacpp-server` / `pinkcherry-kaggle` with `video_api: "openai-videos"` | HTTP 200, both `llamacpp-server` and `pinkcherry-kaggle` contain `PinkCherry-MiniMax-H3` and `video_api: "openai-videos"` | **PASS** |
| **3. Video Status** | `http://127.0.0.1:1337/v1/videos/d3321dfa79d545228d13f16d61e0c619` | HTTP 200, `status == "completed"`, `progress == 100` | HTTP 200, `status: "completed"`, `progress: 100`, size 672x1216 | **PASS** |
| **4. Adversarial 404 (Local)** | `http://127.0.0.1:1337/v1/videos/non-existent-video-999` | HTTP 404 `not_found` | HTTP 404, `{"error":{"message":"Video not found.","code":"not_found"}}` | **PASS** |
| **5. Adversarial 404 (Cloudflare)** | `https://models-stopped-follows-problems.trycloudflare.com/v1/videos/non-existent-video-999` | HTTP 404 `not_found` | HTTP 404, identical error body | **PASS** |
| **6. Video Download (Local)** | `http://127.0.0.1:1337/v1/videos/d3321dfa79d545228d13f16d61e0c619/content` | HTTP 200, `video/mp4`, size > 100 KB, valid container | HTTP 200, `Content-Type: video/mp4`, size 2,818,134 bytes, `ftyp` box present | **PASS** |
| **7. Video Download (Cloudflare)** | `https://models-stopped-follows-problems.trycloudflare.com/v1/videos/d3321dfa79d545228d13f16d61e0c619/content` | HTTP 200, `video/mp4`, size > 100 KB | HTTP 200, `Content-Type: video/mp4`, size 2,818,134 bytes | **PASS** |
| **8. SHA-256 Parity** | Local File vs HTTP Stream | Exact byte match | Both hashes: `3e447aac96bf68cb342c0cab3f55a9e51c462c63a7ed13e27326b5b137747917` | **PASS** |
| **9. Unauthorized Access** | `GET /v1/videos/d3321dfa79d545228d13f16d61e0c619` without token | HTTP 401 Unauthorized | HTTP 401 | **PASS** |
| **10. Invalid Token** | `GET /v1/videos/...` with dummy bearer token | HTTP 401 Unauthorized | HTTP 401 | **PASS** |
| **11. Malformed JSON Body** | `POST /v1/videos` with invalid JSON | HTTP 400 Bad Request | HTTP 400 `Invalid JSON body` | **PASS** |
| **12. Missing Prompt** | `POST /v1/videos` with `{}` | HTTP 400 Bad Request | HTTP 400 `prompt is required` | **PASS** |
| **13. Unsupported Model** | `POST /v1/videos` with unknown model | Proper error | HTTP 503 `No video model loaded` | **PASS** |
| **14. Non-Existent Content 404** | `GET /v1/videos/non-existent-video-999/content` | HTTP 404 | HTTP 404 `Video not found` | **PASS** |
| **15. Gallery Indexing** | `GET http://127.0.0.1:56603/atomic/v1/diffusion/video/gallery` | Indexed in gallery | `total: 3`, contains target video ID and valid local path | **PASS** |

---

## Unchallenged Areas

- **Full Kaggle ComfyUI Generation Re-run (23-minute GPU execution)**: Re-running a new 23-minute full GPU sampling job was not re-triggered during this check to avoid redundant T4 quota consumption, since the generated artifacts, ComfyUI execution logs, and API state are active, verifiable, and validated.

---

## Verdict

**CONFIRM**. The integration satisfies all contract specifications, security bounds, and empirical criteria.
