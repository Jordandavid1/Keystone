# ZenCreator Public API

Programmatic access to ZenCreator's AI generation tools: image generation, face swap, upscaling,
video generation, lipsync and more. Authenticate with an API key from https://app.zencreator.pro/api-keys
sent as a Bearer token. Generations are asynchronous: start, poll, fetch outputs.

## Quickstart for AI Integration

Machine-readable resources for AI agents, MCP clients and code generators:

- [OpenAPI JSON specification](https://api.zencreator.pro/api/public/openapi.json)
- [SKILL.md for AI agents](https://api.zencreator.pro/api/public/skill.md)
- [Get an API key](https://app.zencreator.pro/api-keys)

Open SearchSearchKeyboard Shortcut: `Control⌃ k`

- [Introduction](https://api.zencreator.pro/api/public/docs#description/introduction)
Open Group - Introduction

- [Tools](https://api.zencreator.pro/api/public/docs#tag/tools)
Close Group - Tools


  - [Get a tool\\
    HTTP Method:  GET](https://api.zencreator.pro/api/public/docs#tag/tools/GET/api/public/v1/tools/{tool_name})
  - [List tools\\
    HTTP Method:  GET](https://api.zencreator.pro/api/public/docs#tag/tools/GET/api/public/v1/tools)
- [Generations](https://api.zencreator.pro/api/public/docs#tag/generations)
Open Group - Generations

- [Assets](https://api.zencreator.pro/api/public/docs#tag/assets)
Open Group - Assets

- [Templates](https://api.zencreator.pro/api/public/docs#tag/templates)
Open Group - Templates

- [LoRAs](https://api.zencreator.pro/api/public/docs#tag/loras)
Open Group - LoRAs

- [Photoshoot Categories](https://api.zencreator.pro/api/public/docs#tag/photoshoot-categories)
Open Group - Photoshoot Categories

- [Balance](https://api.zencreator.pro/api/public/docs#tag/balance)
Open Group - Balance

- [Transactions](https://api.zencreator.pro/api/public/docs#tag/transactions)
Open Group - Transactions

- [Models](https://api.zencreator.pro/api/public/docs#models)
Open Group - Models


[Open API Client](https://client.scalar.com/?url=https%3A%2F%2Fapi.zencreator.pro%2Fapi%2Fpublic%2Fopenapi.json&integration=html&utm_source=api-reference&utm_medium=button&utm_campaign=sidebar)

[Powered by Scalar](https://scalar.com/?utm_source=powered-by&utm_medium=api-reference&utm_campaign=html)

Open Menu

v1.0.0

OpenAPI 3.1.0

# ZenCreator Public API

[ZenCreator Support](mailto:support@zencreator.pro)

Download OpenAPI Document
json
Download OpenAPI Document
yaml

ZenCreator Public API gives programmatic access to ZenCreator's AI generation tools: image generation, face swap, upscaling, video generation, lipsync and more. Every generation is asynchronous: you start it, poll its status and download the outputs.

## Quickstart for AI Integration

Machine-readable resources for AI agents, MCP clients and code generators:

| Resource | URL |
| --- | --- |
| OpenAPI JSON | [`https://api.zencreator.pro/api/public/openapi.json`](https://api.zencreator.pro/api/public/openapi.json) |
| SKILL.md for AI agents | [`https://api.zencreator.pro/api/public/skill.md`](https://api.zencreator.pro/api/public/skill.md) |
| Get an API key | [https://app.zencreator.pro/api-keys](https://app.zencreator.pro/api-keys) |

**3-step quickstart:**

1. Create an API key at [https://app.zencreator.pro/api-keys](https://app.zencreator.pro/api-keys) and send it as `Authorization: Bearer zc_live_...`.
2. Call `GET /api/public/v1/tools` — every tool comes with `input_schema` (JSON Schema) describing exactly which fields it accepts, their allowed values and defaults.
3. `POST /api/public/v1/generations` with `{"tool": "<name>", "input": {...}}`, poll `GET /api/public/v1/generations/{id}` until the status is terminal, then fetch `GET /api/public/v1/generations/{id}/result`.

## Access Points

| Environment | Base URL |
| --- | --- |
| Current | `https://api.zencreator.pro` |

All endpoints are prefixed with `/api/public/v1`.

## Authentication

Authenticate every request with an **API key** sent as a Bearer token:

```bash
curl "https://api.zencreator.pro/api/public/v1/tools" \
  -H "Authorization: Bearer zc_live_<key_id>_<secret>"
```

### How to get an API key

1. Sign in to [app.zencreator.pro](https://app.zencreator.pro/).
2. Open [API Keys](https://app.zencreator.pro/api-keys).
3. Create a key and copy it — the full key is shown **only once**.

Keys carry scopes: `read` (list tools, poll generations, read transactions) and `generate` (start generations, upload assets). Pick the scopes when creating the key.

## Generation Workflow

**1\. Pick a tool and read its input schema:**

```bash
curl "https://api.zencreator.pro/api/public/v1/tools/by_prompt" \
  -H "Authorization: Bearer $ZC_API_KEY"
```

**2\. Start a generation:**

```bash
curl -X POST "https://api.zencreator.pro/api/public/v1/generations" \
  -H "Authorization: Bearer $ZC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool": "by_prompt", "input": {"positive_prompt": "portrait of a woman, golden hour", "ratio": "3:4"}}'
# -> {"id": "0196...", "status": "queued", "created_at": "..."}
```

The `input` payload is validated against the tool's `input_schema` before any credits are charged — invalid payloads are rejected with `422` and a message pointing at the offending field.

**3\. Poll the status** (every 5-10 seconds):

```bash
curl "https://api.zencreator.pro/api/public/v1/generations/<id>" \
  -H "Authorization: Bearer $ZC_API_KEY"
# -> {"id": "...", "status": "processing", "progress": 50, "error": null}
```

Statuses: `queued` → `processing` → `succeeded` \| `partial` \| `failed`. When the status is `failed` or `partial`, the `error` field explains why.

**4\. Fetch the outputs:**

```bash
curl "https://api.zencreator.pro/api/public/v1/generations/<id>/result" \
  -H "Authorization: Bearer $ZC_API_KEY"
# -> {"status": "succeeded", "outputs": [{"asset_id": "...", "url": "...", "download_url": "..."}], "error": null}
```

Text-producing tools return their result in the top-level `text` field with an empty `outputs` list.

Tools that take images, video or audio as input reference **asset IDs** — upload the file first (see below) and pass the returned `asset_id` in the tool input.

## Tools & Pricing

Every generation tool with the exact credit prices charged by the billing engine and the JSON `input` parameters it accepts. Prices on this page are computed by the same calculator that charges your generations, so they always match the actual charge. The machine-readable version of this catalog (with `input_schema` as JSON Schema) is `GET /api/public/v1/tools`. Tools marked 🔒 require a **Trusted account** (see the Trusted Accounts section): they are accepted by `POST /generations` and returned by `GET /api/public/v1/tools` only once your account is trusted.

| Tool | Description | Credits |
| --- | --- | --- |
| `run_any_llm` | Run an uncensored large language model over a text prompt and return the generated text. Useful as a text-generation or prompt-rewriting node — e.g. inside a workflow to compose or expand a prompt before an image/video tool. | 1 |
| `upscaler` | Increase the resolution of an existing image while restoring or adding detail. Best for low-resolution sources that need to be cleaned up and improved; gains are limited on an already-sharp 4K image. Input: one image asset. Output: one higher-resolution image. | 1-3 |
| `faceswap` | Swap a face on a photo: the face from `face_asset` is placed onto the person in `ref_asset`, keeping the reference image's body, pose and scene. Image only — there is no video face swap. Output: one image with the face replaced. | 1-3 |
| `by_prompt` | Generate an image from a text prompt, with no input image (text-to-image). The entry point for creation: use it when there is no source image and the picture is described in words — building a character or content from scratch, concepts, backgrounds, NSFW from a description, quick drafts and final hero shots. Supports fast/quality modes and aspect ratios; for several images pass several input objects, one per image. | 1-6 |
| `by_ref` | Recreate a reference photo's scene for your character (image-to-image). `SEEDREAM_5_PRO` recreates the reference's scene (pose, outfit, composition, light) for the character(s) from `character_assets` (required for this model, 1-4). With `keep_pose` the reference is instead edited in place: its pose, body, composition, outfit, lighting and background stay exactly as they are and only the person's identity (face, hair, skin tone) is taken from `character_assets`. Output size follows the reference by default, or a fixed `ratio` (ignored with `keep_pose`); `tier` picks 1K/2K. The pre-August `face_asset` and `body_asset` fields are still accepted and fold into `character_assets`. | 2-3 |
| `photoshoot` | Run a consistent photoshoot of one character from a photo of the face and a photo of the body (without a face): each shot is generated from scratch, so poses come out organically different between frames — unlike `image_editor`, which keeps the source composition. The tool feeds the references through prepared prompt presets and returns a batch of images. Presets are grouped by category, so you can produce a set in a given style or action. Strength: reproducible, satisfying results with no manual prompting — at the cost of fine-grained control. | 3 / image |
| `facegen` | Generate a brand-new face from structured attributes: gender, age, ethnicity, body type, eye/hair/beard colour, hairstyle, beard and makeup. No reference image; returns a single square image per request. Strength: full parametric control over the appearance — use it to create a fresh persona to reuse in other tools. For each attribute the accepted values are listed in that field's enum. Niche — used occasionally. | 2-3 |
| `carousel` | Bring an image and get the same subject from different camera angles (up to 10). Use it for social-media carousels and a "3D"/product overview of an object or character. Niche — used occasionally. | 2-3 / image |
| `videogen` | Animate a photo into a video (image-to-video). Cost depends on the model, duration (5-15 s, up to 30 s on the `wan@3.0` line) and resolution (480p-1080p). Supports prompt enhancement, fixed camera, LoRAs and optional audio. Quick guide: general content (best price/quality) — Seedance; NSFW content — `wan@2.7-nsfw` or `wan@2.2-lora`; tasteful content with complex actions — Kling (censored). | 2-595 |
| `image_editor` | Edit and composite existing images by prompt — the main, most flexible image tool. Bring references, edit and combine them; bring your character and dress them from a reference photo; keep a product or object **exactly** (fabric, pattern, shape) while changing the scene. It offers both SFW and NSFW models, plus LoRA presets that extend NSFW capability. You are limited mainly by your imagination. Edits inherit the source composition (pose, framing), so for a photoshoot-style series of varied organic poses of one character use `photoshoot` instead. | 1-6 / image |
| `collaber` | Put two characters together in one frame: bring two reference subjects and an optional background/location photo; the tool combines them into a single scene (1-4 images). Strength: keeps both characters' likeness — a convenient preset for collabs and duets. | 1-3 / image |
| `couplegen` | Paired photo to video: combine two character photos (Seedream) then animate (wan-2.2 i2v + LoRA) | 10 |
| `video2video` | Transfer motion or replace a character in a video using a reference video or an Instagram/TikTok URL; the original soundtrack can be kept. SFW and NSFW modes. Provide the source as exactly one of `video_asset`, `instagram_url` or `tiktok_url`; the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes read it only from `video_asset` or `ref_videos`, never from a link. Output: one video. | 1-20 / second |
| `lipsync` | Make a character speak your audio (talking head): bring an audio file and a portrait first frame, and get a video in which the character talks or sings in sync. Up to 35 seconds of audio; image JPG/PNG under 5 MB. Use it to voice a character or avatar. Niche — used occasionally. Priced at 3 credits per second of audio. | 3 / second of audio |
| `text_to_video` 🔒 | **Trusted only.** Generate a video from a text prompt alone (text-to-video): the tool generates a first frame and then animates it. NSFW-capable. | 4-595 |
| `video_upscaler` | Bring a medium-quality video and get a sharper, higher-resolution result via BytePlus vCube. Pick a quality tier (`standard` — fast and affordable, or `pro` — premium model) and a target output resolution (`1080p`, `2k` or `4k`). Output is locked to 30fps. Priced per output second by tier x resolution x duration. | 1 / second and up |
| `video_merger` | Concatenate 2-5 video clips with transitions | 1 |

### run\_any\_llm

Run an uncensored large language model over a text prompt and return the generated text. Useful as a text-generation or prompt-rewriting node — e.g. inside a workflow to compose or expand a prompt before an image/video tool.

**Models:**`grok` (text + up to 4 reference images — computer vision), `hermes-3-405b`, `euryale-70b` (text-only).

Input: a `model`, a `prompt`, an optional `system_prompt`, an optional `max_tokens`, and optional `image_assets` (grok only). `prompt` and `system_prompt` together must not exceed 32000 characters. Output: the generated `text`.

**Price:** 1 credit.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `model` | enum | yes | — | One of: `euryale-70b`, `grok`, `hermes-3-405b`. Which model to use: grok \| hermes-3-405b \| euryale-70b. Only grok accepts image\_assets. All three are uncensored. |
| `prompt` | string | yes | — | The user prompt to send to the model. |
| `system_prompt` | string |  | `""` | Optional system prompt that steers the model. |
| `max_tokens` | integer |  | `2048` | Maximum number of tokens to generate (default 2048, max 4096). |
| `image_assets` | array\[string\] or null |  | `null` | Optional reference image(s) to analyze alongside the prompt (vision-capable models only, e.g. grok). |

**Outputs:**`text` (string)

### upscaler

Increase the resolution of an existing image while restoring or adding detail. Best for low-resolution sources that need to be cleaned up and improved; gains are limited on an already-sharp 4K image. Input: one image asset. Output: one higher-resolution image.

**Versions:**

- `seedvr2_7b` _(default)_ — Premium diffusion-restoration upscaler for 4K/6K output; `detail` and `target_resolution` control it, plus `noise_scale`.
- `seedvr2_3b` — Fast diffusion-restoration upscaler; `detail` and `target_resolution` control it.

**Price** (credits):

| `version` | `target_resolution` | Credits |
| --- | --- | --- |
| `seedvr2_3b` | _any_ | 1 |
| `seedvr2_7b` | `2k`, `8k` | 1 |
| `seedvr2_7b` | `4k` | 2 |
| `seedvr2_7b` | `6k` | 3 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `image_asset` | string | yes | — | Asset ID of the image to upscale (upload via POST /assets). |
| `version` | enum |  | `seedvr2_7b` | One of: `seedvr2_3b`, `seedvr2_7b`. Upscale engine. `seedvr2_7b` — premium diffusion-restoration upscale for 4K/6K output, controlled by `detail`/`target_resolution` plus `noise_scale`; `seedvr2_3b` — fast diffusion-restoration upscale controlled by `detail`/`target_resolution`. Default `seedvr2_7b`. |
| `target_resolution` | enum |  | `4k` | One of: `2k`, `4k`, `6k`, `8k`. Output size tier. `seedvr2_3b` accepts `2k`, `4k`, `8k`; `seedvr2_7b` accepts `4k`, `6k`. Default `4k`. |
| `detail` | enum |  | `medium` | One of: `high`, `low`, `medium`. How much of the source is preserved before upscaling — `high` keeps the most source detail (smallest pre-processing budget), `low` allows the most restoration. One of `high`, `medium`, `low`. Default `medium`. |
| `noise_scale` | number |  | `0` | `seedvr2_7b` only: amount of synthetic detail added during upscaling, 0-1. Default 0. |

**Outputs:**`image_asset` (string)

### faceswap

Swap a face on a photo: the face from `face_asset` is placed onto the person in `ref_asset`, keeping the reference image's body, pose and scene. Image only — there is no video face swap. Output: one image with the face replaced.

**Models:**

- `SEEDREAM_5_PRO` _(default)_ — Highest-quality swap. `swap_type` picks what is replaced: `face` (face only, reference's hairstyle kept), `head` (whole head including hair) or `person` (the person in `face_asset` replaces the person in `ref_asset`: face, hair and skin tone come from `face_asset`, while pose, body, outfit, background and light stay from the reference). `tier` picks 1K/2K; the output's aspect ratio always follows `ref_asset`.
- `FULL_HEAD` — Replaces the entire head, not just the face — use it when the target's hairstyle or head shape differs strongly from the source.

**Price** (credits):

| `model` | `tier` | Credits |
| --- | --- | --- |
| `FULL_HEAD`, `MULEROUTER_FACE`, `MULEROUTER_HEAD` | _any_ | 1 |
| `SEEDREAM_5_PRO` | `1K` | 2 |
| `SEEDREAM_5_PRO` | `2K` | 3 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `ref_asset` | string | yes | — | Asset ID of the target image whose face will be replaced. |
| `face_asset` | string | yes | — | Asset ID of the image providing the new face. |
| `model` | enum |  | `SEEDREAM_5_PRO` | One of: `FULL_HEAD`, `MULEROUTER_FACE`, `MULEROUTER_HEAD`, `SEEDREAM_5_PRO`. Face-swap model: `SEEDREAM_5_PRO` (default), a full-head variant or a MuleRouter swap. |
| `seed` | integer or null |  | `null` | Seed for reproducibility. Default random. |
| `swap_type` | enum |  | `face` | One of: `face`, `head`, `person`. What `SEEDREAM_5_PRO` replaces: `face` (default), `head` or `person`. |
| `tier` | enum |  | `2K` | One of: `1K`, `2K`. Output resolution tier for `SEEDREAM_5_PRO`: `1K` or `2K` (default). The aspect ratio always follows `ref_asset`. |

**Outputs:**`image_asset` (string)

### by\_prompt

Generate an image from a text prompt, with no input image (text-to-image). The entry point for creation: use it when there is no source image and the picture is described in words — building a character or content from scratch, concepts, backgrounds, NSFW from a description, quick drafts and final hero shots. Supports fast/quality modes and aspect ratios; for several images pass several input objects, one per image.

**Three content groups (pick by what you need):**

- **Top cloud models, censored** (`GENERAL_NSFW`, `NANO_BANANA`, `NANO_BANANA_2_1`, `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST`, `IDEOGRAM_4_5`) — highest quality and realism, but they block full NSFW content.
- **Uncensored, not built for full NSFW** (`WAN_2_7_IMAGE`, `QWEN_IMAGE`, `SEEDREAM_5`, `SEEDREAM_5_PRO`) — high quality and won't block, but won't create full NSFW content from scratch; they accurately **transform NSFW references** you provide.
- **Built for full NSFW** (`FLUX_KLEIN_NSFW`, `Z_IMAGE_SPICY`) — slightly lower quality and more artifacts, but real full-NSFW capability.

**Models:**

- `GENERAL_NSFW` _(default, trusted)_ — General-purpose workhorse with a good quality/speed/price balance and strong facial likeness; the NSFW version is uncensored but does not produce full NSFW anatomy from text alone (it covers it up). Older model — occasional hand/limb artifacts.
- `GENERAL_SFW` — The same pipeline, SFW only.
- `WAN_2_7_IMAGE` / `WAN_2_7_IMAGE_PRO` — Modern model with higher quality and detail (Pro = top consistency). Renders bodies, scenes and composition more aesthetically and has fewer hand/limb artifacts. Weaker at in-image text. Uncensored, but transforms your NSFW references rather than inventing full NSFW content.
- `WAN` — Legacy WAN image model; prefer `WAN_2_7_IMAGE`.
- `Z_IMAGE_SPICY` _(trusted only)_ — Z-Image Spicy (MuleRouter): uncensored photoreal images from text. `mode` picks `fast` (Standard, 1 credit) or `quality` (Pro, 2 credits); `ratio` is the only size control — `width`/`height`, `negative_prompt` and `tier` are ignored.
- `QWEN_IMAGE` / `QWEN_IMAGE_PRO` — Aesthetic results with good facial likeness and few artifacts; great for stylized / illustrative / anime subjects. Pro adds realism. Uncensored; transforms NSFW references.
- `SEEDREAM_5` — Newer generation: better prompt understanding, stronger stylization, better likeness, fewer artifacts. Uncensored; transforms NSFW references.
- `SEEDREAM_5_PRO` — The newest Seedream flagship: top prompt understanding and realism; supports all 15 aspect ratios and a `tier` resolution switch (`1K` = 2 credits, `2K` = 3 credits). Uncensored; transforms NSFW references.
- `NANO_BANANA` — Among the best for realism, and reliably renders legible in-image text (posters, signage, captions); strong real-world knowledge. Heavily censored — won't produce even mildly suggestive content. Weaker facial likeness.
- `NANO_BANANA_2_1` — Google Nano Banana 2.1: precise prompt following, consistent characters and legible in-image text (posters, infographics), up to 4K. Censored. The only model with the extra aspect ratios 4:1, 1:4, 8:1 and 1:8, `thinking_level` and `web_search`. Credits for `tier` 1K / 2K / 4K: 1 / 2 / 4, with `thinking_level``high` 2 / 3 / 5.
- `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` — OpenAI GPT Image 2.5: strict prompt following, exact in-image copy and controlled layouts, up to 4K (`4K` is beta). Flare is faster, Sunburst is slower and more precise; same price. Censored. The 8 standard aspect ratios, `quality` and `transparent_background`. Credits for `tier` 1K / 2K / 4K: `quality``low` 1 / 1 / 1, `medium` 1 / 1 / 2, `high` 2 / 3 / 5.
- `IDEOGRAM_4_5` — Ideogram 4.5: the best lettering of our models — readable quoted text, typography and logos on posters and signs. Censored. The 8 standard aspect ratios, `tier` 1K or 2K, `quality` and `rewrite_prompt`; no `negative_prompt`. Credits for `quality``low` / `medium` / `high`: 1 / 2 / 6 at any `tier`.
- `FLUX_KLEIN_NSFW` _(trusted)_ — The most advanced local full-NSFW model: creates uncensored NSFW content and also works with references — bring a character's face and create an action. Slightly lower quality, occasional artifacts.
- `KREA_2` _(trusted only)_ — Krea v2 (WaveSpeed) with its built-in style LoRA; `negative_prompt`, `mode` and `width`/`height` are ignored. `tier` picks 1K (1 credit) / 2K (2 credits); `ratio` is the only size control.

Models marked _(trusted)_ unlock NSFW behaviour only for trusted accounts (or accounts with an NSFW content policy).

**Price** (credits):

| `model` | `mode` | `tier` | `thinking_level` | `quality` | Credits |
| --- | --- | --- | --- | --- | --- |
| `FLUX_KLEIN_NSFW`, `IDEOGRAM_4_5`, `NANO_BANANA`, `QWEN_IMAGE_PRO`, `WAN_2_7_IMAGE_PRO` | _any_ | `1K`, `2K` | `minimal` | `medium` | 2 |
| `GENERAL_NSFW`, `GENERAL_SFW`, `QWEN_IMAGE`, `SEEDREAM_5`, `WAN`, `WAN_2_7_IMAGE` | _any_ | `1K`, `2K` | `minimal` | `medium` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | _any_ | `1K`, `2K` | `minimal` | `low`, `medium` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | _any_ | `1K` | `minimal` | `high` | 2 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | _any_ | `2K` | `minimal` | `high` | 3 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | _any_ | `4K` | `minimal` | `low` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | _any_ | `4K` | `minimal` | `medium` | 2 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | _any_ | `4K` | `minimal` | `high` | 5 |
| `IDEOGRAM_4_5` | _any_ | `1K`, `2K` | `minimal` | `low` | 1 |
| `IDEOGRAM_4_5` | _any_ | `1K`, `2K` | `minimal` | `high` | 6 |
| `KREA_2`, `NANO_BANANA_2_1` | _any_ | `1K` | `minimal` | `medium` | 1 |
| `KREA_2`, `NANO_BANANA_2_1` | _any_ | `2K` | `minimal` | `medium` | 2 |
| `NANO_BANANA_2_1` | _any_ | `1K` | `high` | `medium` | 2 |
| `NANO_BANANA_2_1` | _any_ | `2K` | `high` | `medium` | 3 |
| `NANO_BANANA_2_1` | _any_ | `4K` | `high` | `medium` | 5 |
| `NANO_BANANA_2_1` | _any_ | `4K` | `minimal` | `medium` | 4 |
| `SEEDREAM_5_PRO` | _any_ | `1K` | `minimal` | `medium` | 2 |
| `SEEDREAM_5_PRO` | _any_ | `2K` | `minimal` | `medium` | 3 |
| `Z_IMAGE_SPICY` | `fast` | `1K`, `2K` | `minimal` | `medium` | 1 |
| `Z_IMAGE_SPICY` | `quality` | `1K`, `2K` | `minimal` | `medium` | 2 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `positive_prompt` | string | yes | — | Text describing what to generate. |
| `negative_prompt` | string |  | `""` | Text describing what to avoid in the image. |
| `batch_size` | integer |  | `1` | Must be 1: this tool generates one image per input. For N images pass N input objects. |
| `model` | enum |  | `GENERAL_NSFW` | One of: `FLUX_KLEIN_NSFW`, `GENERAL_NSFW`, `GENERAL_SFW`, `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST`, `IDEOGRAM_4_5`, `KREA_2`, `NANO_BANANA`, `NANO_BANANA_2_1`, `QWEN_IMAGE`, `QWEN_IMAGE_PRO`, `SEEDREAM_5`, `SEEDREAM_5_PRO`, `WAN`, `WAN_2_7_IMAGE`, `WAN_2_7_IMAGE_PRO`, `Z_IMAGE_SPICY`. Generation model, covering the WAN (incl. WAN 2.7 image), Nano Banana, Seedream, Qwen and Flux Klein families; `*_PRO` variants trade speed for higher quality. The general NSFW family is offered where the brand allows adult content. |
| `ratio` | enum |  | `1:1` | One of: `16:9`, `1:1`, `1:2`, `1:3`, `1:4`, `1:8`, `21:9`, `2:1`, `2:3`, `3:1`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `9:21`. Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2 or 21:9 (default 1:1, square). `SEEDREAM_5_PRO` additionally supports 1:2, 2:1, 1:3, 3:1, 4:5, 5:4 and 9:21. `NANO_BANANA_2_1` also takes the four extreme banner ratios, up to eight to one. `IDEOGRAM_4_5` takes the 8 standard ratios only. |
| `tier` | enum |  | `2K` | One of: `1K`, `2K`, `4K`. Output resolution tier: `1K`, `2K` (default) or `4K`. `SEEDREAM_5_PRO` / `KREA_2` take `1K` or `2K`; models without a tier ignore it. `NANO_BANANA_2_1` also takes the top tier. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take the top tier, in beta. `IDEOGRAM_4_5` takes `1K` or `2K`, at the same price. Other models reject `4K`. |
| `thinking_level` | enum |  | `minimal` | One of: `high`, `minimal`. Default `minimal` (fast); ignored by other models. `NANO_BANANA_2_1` also takes the longer-reasoning level for a more accurate result, +1 credit. |
| `web_search` | boolean |  | `false` | One of: `true`, `false`. Default `false`; ignored by other models. `NANO_BANANA_2_1` can check Google Search for current facts, places and logos at the same price. |
| `quality` | enum or null |  | `null` | One of: `high`, `low`, `medium`. Default `medium`, the level every model takes. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take a cheaper draft level and a top level that adds detail, latency and credits. `IDEOGRAM_4_5` takes `low` / `medium` / `high` too. |
| `transparent_background` | boolean |  | `false` | One of: `true`, `false`. Default `false`. `true` works on `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` only: they return a PNG with a transparent background (stickers, logos, product cut-outs) at the same price. |
| `mode` | enum |  | `fast` | One of: `fast`, `quality`. Generation mode: `fast` (quicker and cheaper) or `quality` (slower, higher fidelity). |
| `width` | integer or null |  | `null` | Optional output width in pixels; if omitted a size is derived from `ratio`. |
| `height` | integer or null |  | `null` | Optional output height in pixels; if omitted a size is derived from `ratio`. |
| `rewrite_prompt` | boolean |  | `false` | One of: `true`, `false`. For `SEEDREAM_5_PRO` / `IDEOGRAM_4_5` only: let the provider rewrite/expand the prompt before generation (default `false`). Leave off for NSFW prompts — the rewriter can corrupt them and produce an image unrelated to what was asked. `IDEOGRAM_4_5` may uppercase quoted text when it rewrites. |

**Outputs:**`image_asset` (string)

### by\_ref

Recreate a reference photo's scene for your character (image-to-image). `SEEDREAM_5_PRO` recreates the reference's scene (pose, outfit, composition, light) for the character(s) from `character_assets` (required for this model, 1-4). With `keep_pose` the reference is instead edited in place: its pose, body, composition, outfit, lighting and background stay exactly as they are and only the person's identity (face, hair, skin tone) is taken from `character_assets`. Output size follows the reference by default, or a fixed `ratio` (ignored with `keep_pose`); `tier` picks 1K/2K. The pre-August `face_asset` and `body_asset` fields are still accepted and fold into `character_assets`.

**Price** (credits):

| `tier` | Credits |
| --- | --- |
| `1K` | 2 |
| `2K` | 3 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `ref_asset` | string | yes | — | Asset ID of the reference image to guide the generation. |
| `face_asset` | string or null |  | `null` | Asset ID of a face. `SEEDREAM_5_PRO` accepts it as a legacy alias and appends it to `character_assets`. |
| `model` | enum |  | `SEEDREAM_5_PRO` | One of: `SEEDREAM_5_PRO`. Generation model. |
| `positive_prompt` | string |  | `""` | Text describing what to generate. |
| `batch_size` | integer |  | `4` | Number of images to generate, 1-10. Default 4. |
| `strength` | number |  | `1.0` | How strongly the reference image constrains the result, 0.0-1.0 (higher sticks closer to the reference). |
| `keep_pose` | boolean |  | `false` | One of: `true`, `false`. `SEEDREAM_5_PRO`: edit the reference in place, keeping its pose, body, outfit, lighting and background and swapping in the character's identity (face, hair, skin tone); the output keeps the reference's aspect. Default false. |
| `body_asset` | string or null |  | `null` | Legacy alias accepted only by `SEEDREAM_5_PRO`, appended to `character_assets` after `face_asset`. Rejected by the other models rather than ignored. |
| `character_assets` | array\[string\] or null | yes | `null` | Asset ID(s) of the character photo(s), 1-4. Required by `SEEDREAM_5_PRO`; the legacy `face_asset` and `body_asset` fields are folded into this list when sent. |
| `ratio` | enum or null |  | `null` | One of: `16:9`, `1:1`, `1:2`, `1:3`, `21:9`, `2:1`, `2:3`, `3:1`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `9:21`. Output aspect ratio for `SEEDREAM_5_PRO`: 1:1, 1:2, 2:1, 1:3, 3:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 9:21 or 21:9. Defaults to the reference's own aspect; ignored with `keep_pose` and `CHARACTER_SWAP`. |
| `tier` | enum |  | `1K` | One of: `1K`, `2K`. Output resolution tier for `SEEDREAM_5_PRO` / `CHARACTER_SWAP` / `KREA_2`: `1K` (default) or `2K`. |

**Outputs:**`image_assets` (array\[string\])

### photoshoot

Run a consistent photoshoot of one character from a photo of the face and a photo of the body (without a face): each shot is generated from scratch, so poses come out organically different between frames — unlike `image_editor`, which keeps the source composition. The tool feeds the references through prepared prompt presets and returns a batch of images. Presets are grouped by category, so you can produce a set in a given style or action. Strength: reproducible, satisfying results with no manual prompting — at the cost of fine-grained control.

**Price:** 3 credits per image (multiplied by `image_count`).

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `face_ref` | string | yes | — | Asset ID of the face reference (upload via POST /assets). |
| `body_ref` | string | yes | — | Asset ID of the body/pose reference (upload via POST /assets). |
| `prompt` | string |  | `""` | Free-text description of the shot (scene, outfit, lighting). Provide `prompt` for a custom shot, or `category_id` to use a curated category instead. If both are given, `category_id` takes precedence. |
| `category_id` | string or null |  | `null` | ID of a curated photoshoot category (see GET /photoshoot-categories). When set, the shot's prompts are taken from the category and `image_count` images are produced; it takes precedence over `prompt`. |
| `image_count` | integer |  | `1` | Total number of images to generate (min 1). Drives how many shots are produced from the chosen `category_id` (or how many times `prompt` is repeated). |
| `ratio` | enum |  | `1:1` | One of: `16:9`, `1:1`, `1:2`, `1:3`, `21:9`, `2:1`, `2:3`, `3:1`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `9:21`. Aspect ratio of the output image: 1:1, 1:2, 2:1, 1:3, 3:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 9:21 or 21:9 (default 1:1, square). Takes precedence over `width`/`height` when they describe a different shape. |
| `width` | integer |  | `1024` | Output width in pixels (default 1024; clamped to 512-4096). |
| `height` | integer |  | `1024` | Output height in pixels (default 1024; clamped to 512-4096). |
| `number_of_images` | integer |  | `1` | Parallel images per shot (default 1); leave at 1 — use `image_count` to control the total. |
| `rewrite_prompt` | boolean |  | `false` | One of: `true`, `false`. Let the provider rewrite/expand `prompt` before generation (default `false`). Leave off for NSFW prompts — the rewriter can corrupt them and produce an image unrelated to what was asked. |

**Outputs:**`image_assets` (array\[string\])

### facegen

Generate a brand-new face from structured attributes: gender, age, ethnicity, body type, eye/hair/beard colour, hairstyle, beard and makeup. No reference image; returns a single square image per request. Strength: full parametric control over the appearance — use it to create a fresh persona to reuse in other tools. For each attribute the accepted values are listed in that field's enum. Niche — used occasionally.

**Price** (credits):

| `tier` | Credits |
| --- | --- |
| `1K` | 2 |
| `2K` | 3 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `gender` | enum | yes | — | One of: `Female`, `Male`. Gender of the face. |
| `age` | enum | yes | — | One of: `18-25`, `26-35`, `36-45`, `46-55`, `56-65`, `66-75`, `75-85`, `85+`. Apparent age band. |
| `origin` | enum | yes | — | One of: `Central American`, `Central Asian`, `East Asian`, `European`, `Middle Eastern`, `North African`, `North American`, `Oceanian / Pacific Islander`, `South American`, `South Asian`, `Southeast Asian`. Ethnic origin / look. |
| `body_type` | enum or null |  | `null` | One of: `Chubby`, `Curvy`, `Fit`, `Muscular`, `Normal`, `Slim`. Body type. |
| `eye_color` | enum or null |  | `null` | One of: `Albino`, `Amber`, `Blue`, `Brown`, `Gray`, `Green`, `Hazel`, `Heterochromia`, `Red`, `Violet`. Eye colour. |
| `hair_color` | enum or null |  | `null` | One of: `Black`, `Blonde`, `Blue`, `Brunette`, `Gray`, `Green`, `Honey`, `Ombre`, `Pink`, `Platinum`, `Red`, `Salt and Pepper`, `Violet`. Hair colour. |
| `hair_type` | enum or null |  | `null` | One of: `Bald`, `Coily`, `Curly`, `Frizzy`, `Silky`, `Straight`, `Thick`, `Thin`, `Wavy`. Hair type, e.g. straight/wavy/curly. |
| `hair_style` | enum or null |  | `null` | One of: `Afro`, `Bob`, `Bowl`, `Braids`, `Bun`, `Buzzcut`, `Caesar`, `Mohawk`, `Pigtails`, `Pixie`, `Ponytail`, `Shag`, `Undercut`, `Updo`. Hair style. |
| `beard` | enum or null |  | `null` | One of: `Anchor Beard`, `Balbo Beard`, `Chevron Mustache`, `Chinstrap Beard`, `Circle Beard`, `Corporate Beard`, `Ducktail Beard`, `Friendly Mutton Chops`, `Full Beard`, `Garibaldi Beard`, `Goatee`, `Handlebar Mustache`, `Horseshoe Mustache`, `Imperial Mustache`, `Mutton Chops`, `Pencil Mustache`, `Soul Patch`, `Stubble Beard`, `Van Dyke Beard`, `Zappa Mustache`. Beard style. |
| `beard_color` | enum or null |  | `null` | One of: `Black`, `Blonde`, `Blue`, `Brunette`, `Gray`, `Green`, `Honey`, `Ombre`, `Pink`, `Platinum`, `Red`, `Salt and Pepper`, `Violet`. Beard colour. |
| `makeup` | enum or null |  | `null` | One of: `Anime Makeup`, `Artistic Makeup`, `Avant-garde Makeup`, `Bohemian Makeup`, `Boho Makeup`, `Classic Makeup`, `Cut Crease Makeup`, `Dewy Makeup`, `Edgy Makeup`, `Festival Makeup`, `Glam Makeup`, `Glowy Makeup`, `Golden Makeup`, `Monochromatic Makeup`, `Natural Makeup`, `Party Makeup`, `Retro Makeup`, `Sunset Eye Makeup`, `Vintage Makeup`, `Watercolor Makeup`. Makeup style. |
| `tier` | enum |  | `2K` | One of: `1K`, `2K`. Output resolution tier: `1K` (~1 MP) or `2K` (~4 MP). Default `2K`. |

**Outputs:**`image_assets` (array\[string\])

### carousel

Bring an image and get the same subject from different camera angles (up to 10). Use it for social-media carousels and a "3D"/product overview of an object or character. Niche — used occasionally.

**Price** (credits per image, multiplied by `number_of_images`):

| `tier` | Credits |
| --- | --- |
| `1K` | 2 |
| `2K` | 3 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `asset_ref` | string | yes | — | Asset ID of the subject/reference image. |
| `ratio` | enum |  | `1:1` | One of: `16:9`, `1:1`, `21:9`, `2:3`, `3:2`, `3:4`, `4:3`, `9:16`. Aspect ratio of the outputs (e.g. 1:1, 16:9, 9:16). |
| `tier` | enum |  | `2K` | One of: `1K`, `2K`. Output resolution tier: `1K` (~1 MP) or `2K` (~4 MP). Default `2K`. |
| `width` | integer |  | `1024` | Ignored: the output size is derived from `ratio` and `tier`. |
| `height` | integer |  | `1024` | Ignored: the output size is derived from `ratio` and `tier`. |
| `number_of_images` | integer |  | `4` | Number of angle variations to generate, 1-10. Default 4. |

**Outputs:**`image_assets` (array\[string\])

### videogen

Animate a photo into a video (image-to-video). Cost depends on the model, duration (5-15 s, up to 30 s on the `wan@3.0` line) and resolution (480p-1080p). Supports prompt enhancement, fixed camera, LoRAs and optional audio. Quick guide: general content (best price/quality) — Seedance; NSFW content — `wan@2.7-nsfw` or `wan@2.2-lora`; tasteful content with complex actions — Kling (censored).

**Wan** — the `wan@2.7` and `wan@3.0` lines understand prompts best and animate a first frame well (1080p, good physics, up to 5 references):

- `wan@3.0` — Newest Wan; native audio, first frame (+ optional last frame) or references, 480p/720p/1080p and clips up to 30 s. No `21:9`. A run takes 15-55 minutes (hours at 1080p x 30 s), so poll instead of waiting on it.
- `wan@3.0-nsfw` _(trusted)_ — The same model with content inspection lifted; identical fields, price and timings.
- `wan@3.0-prime` — The same model on a faster queue: identical fields and results, about 40% quicker, roughly 10% dearer. Pick it when the wait matters more than the price.
- `wan@3.0-prime-nsfw` _(trusted)_ — The prime queue with content inspection lifted.
- `wan@2.7` — Previous line; top prompt understanding and first-frame animation, and much faster than the `wan@3.0` line.
- `wan@2.7-nsfw` _(trusted)_ — Wan 2.7 for NSFW; the best choice when you have a first frame (or a frame with an action) to animate.
- `wan@2.6` / `wan@2.6-flash` — Cheaper and older; **flash** is even cheaper and faster.
- `wan@2.5` — Older generation; prefer `wan@2.6` or `wan@2.7`.
- `wan@2.2` — Animates a first frame; uncensored NSFW base.
- `wan@2.2-lora` — Presets with action-trained LoRAs that turn a first frame into a complex action. Includes "Blink" LoRAs: bring any photo of your character and the frame morphs into the desired NSFW action. The **easiest option for beginners** — no prompt needed, just a photo similar to the example's first frame.

**Kling** — censored, but animates a first frame well; newer versions cost more and understand prompts and complex actions better:

- `kling@2.6` — Top motion and physics, plus native audio (dialogue, effects).
- `kling@2.5` — High quality, cheaper, consistent at volume.
- `kling@2.1` — Stable motion.
- `kling@1.6` — Oldest and cheapest Kling.

**Seedance** — uncensored; best price/quality balance for content:

- `seedance_pro_fast` — Faster and cheaper, less "smart".
- `seedance_pro` — Pricier and smarter.
- `seedance_v1_5_pro` — Best quality and result; joint audio+video, micro-expressions, first+last frame.
- `seedance_2_0` — Latest line; first/first+last frame, native audio, fixed camera, and a multimodal mode (pass `ref_images`/`ref_videos`/`ref_audios` to drive generation by references addressed in the prompt as `[Image N]`/`[Video N]`/`[Audio N]`). 480p/720p only.
- `seedance_2_0_fast` — Faster and cheaper Seedance 2.0; no fixed camera.
- `seedance_2_0_mini` — Cheapest Seedance 2.0 variant.
- `seedance_2_5` _(trusted)_ — Same shape as Seedance 2.0 with wider limits: up to 30 s, 1080p, 30 images + 10 videos + 10 audios of references (≤30 s of video in total), and a `task_type` that says whether the references drive a new clip, an edit of one of them, or its continuation.

**Grok:**

- `grok@4.1` — Censored; animates a first frame, top image-to-video, always with native audio.

**MiniMax** — censored, native audio, 480p/720p/1080p and 5-15 s. Trusted accounts have the provider-side filter lifted; the model still refuses explicit briefs itself, and a refused run is failed and refunded rather than billed:

- `minimax@3.0` — Animates a first frame, a last frame or both, or drives the whole clip from references (`ref_images`/`ref_videos`/`ref_audios`, up to 12 files, addressed in the prompt as `[Image N]`/`[Video N]`/`[Audio N]`).
- `minimax@3.0-turbo` — Faster and half the price; frames only, no reference mode.

Model capabilities differ — read the `model`, `last_frame` and `resolution` fields for which model supports what.

Models marked _(trusted)_ unlock NSFW behaviour only for trusted accounts (or accounts with an NSFW content policy).

**Price** (credits):

| `model` | `duration` | `generate_audio` | Credits (480p) | Credits (720p) | Credits (1080p) |
| --- | --- | --- | --- | --- | --- |
| `grok@4.1` | `6` | _any_ | 12 | 18 | 18 |
| `grok@4.1` | `10` | _any_ | 20 | 30 | 30 |
| `kling@1.6`, `kling@2.1`, `kling@2.5` | `5`, `6`, `8`, `12`, `15` | _any_ | 7 | 7 | 7 |
| `kling@1.6`, `kling@2.1`, `kling@2.5` | `10` | _any_ | 13 | 13 | 13 |
| `kling@2.6` | `5` | `true` | 10 | 10 | 10 |
| `kling@2.6` | `5` | `false` | 5 | 5 | 5 |
| `kling@2.6` | `10` | `true` | 20 | 20 | 20 |
| `kling@2.6` | `10` | `false` | 10 | 10 | 10 |
| `minimax@3.0` | `5` | _any_ | 7 | 10 | 20 |
| `minimax@3.0` | `6` | _any_ | 8 | 12 | 24 |
| `minimax@3.0` | `8` | _any_ | 10 | 16 | 32 |
| `minimax@3.0` | `10` | _any_ | 13 | 20 | 40 |
| `minimax@3.0` | `12` | _any_ | 15 | 24 | 48 |
| `minimax@3.0` | `15` | _any_ | 19 | 30 | 60 |
| `minimax@3.0-turbo` | `5` | _any_ | 4 | 5 | 10 |
| `minimax@3.0-turbo` | `6` | _any_ | 4 | 6 | 12 |
| `minimax@3.0-turbo` | `8` | _any_ | 5 | 8 | 16 |
| `minimax@3.0-turbo` | `10` | _any_ | 7 | 10 | 20 |
| `minimax@3.0-turbo` | `12` | _any_ | 8 | 12 | 24 |
| `minimax@3.0-turbo` | `15` | _any_ | 10 | 15 | 30 |
| `seedance_2_0` | `5` | _any_ | 7 | 16 | 35 |
| `seedance_2_0` | `6` | _any_ | 9 | 19 | 41 |
| `seedance_2_0` | `8` | _any_ | 11 | 25 | 55 |
| `seedance_2_0` | `10` | _any_ | 14 | 31 | 69 |
| `seedance_2_0` | `12` | _any_ | 17 | 37 | 82 |
| `seedance_2_0` | `15` | _any_ | 21 | 46 | 103 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `5` | _any_ | 6 | 13 | 28 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `6` | _any_ | 7 | 15 | 33 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `8` | _any_ | 9 | 20 | 44 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `10` | _any_ | 11 | 25 | 55 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `12` | _any_ | 13 | 30 | 66 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `15` | _any_ | 17 | 37 | 82 |
| `seedance_2_5` | `5` | _any_ | 13 | 29 | 100 |
| `seedance_2_5` | `10` | _any_ | 26 | 58 | 199 |
| `seedance_2_5` | `15` | _any_ | 39 | 87 | 298 |
| `seedance_2_5` | `20` | _any_ | 52 | 116 | 397 |
| `seedance_2_5` | `25` | _any_ | 65 | 145 | 496 |
| `seedance_2_5` | `30` | _any_ | 78 | 174 | 595 |
| `seedance_pro` | `5` | _any_ | 4 | 8 | 15 |
| `seedance_pro`, `seedance_pro_fast` | `6`, `8`, `12`, `15` | _any_ | 7 | 7 | 7 |
| `seedance_pro` | `10` | _any_ | 8 | 15 | 30 |
| `seedance_pro_fast` | `5` | _any_ | 2 | 4 | 7 |
| `seedance_pro_fast` | `10` | _any_ | 4 | 8 | 13 |
| `seedance_v1_5_pro` | `5` | `true` | 8 | 8 | 16 |
| `seedance_v1_5_pro` | `5` | `false` | 4 | 4 | 8 |
| `seedance_v1_5_pro` | `6`, `8`, `15` | `true` | 8 | 8 | 8 |
| `seedance_v1_5_pro` | `6`, `8`, `15` | `false` | 4 | 4 | 4 |
| `seedance_v1_5_pro` | `10` | `true` | 8 | 16 | 32 |
| `seedance_v1_5_pro` | `10` | `false` | 4 | 8 | 16 |
| `seedance_v1_5_pro` | `12` | `true` | 8 | 20 | 40 |
| `seedance_v1_5_pro` | `12` | `false` | 4 | 10 | 20 |
| `wan@2.2`, `wan@2.2-lora` | `5` | _any_ | 10 | 10 | 10 |
| `wan@2.2` | `8` | _any_ | 13 | 13 | 13 |
| `wan@2.2-lora` | `8` | _any_ | 15 | 15 | 15 |
| `wan@2.5`, `wan@2.7`, `wan@2.7-lora` | `5` | _any_ | 5 | 10 | 15 |
| `wan@2.5` | `6` | _any_ | 6 | 12 | 18 |
| `wan@2.5` | `8` | _any_ | 8 | 16 | 24 |
| `wan@2.5`, `wan@2.7`, `wan@2.7-lora` | `10` | _any_ | 10 | 20 | 30 |
| `wan@2.5` | `12` | _any_ | 12 | 24 | 36 |
| `wan@2.5`, `wan@2.7`, `wan@2.7-lora` | `15` | _any_ | 15 | 30 | 45 |
| `wan@2.6` | `5` | _any_ | 10 | 10 | 15 |
| `wan@2.6` | `10` | _any_ | 20 | 20 | 30 |
| `wan@2.6` | `15` | _any_ | 30 | 30 | 45 |
| `wan@2.6-flash` | `5` | `true` | 5 | 5 | 7 |
| `wan@2.6-flash` | `5`, `6` | `false` | 3 | 3 | 4 |
| `wan@2.6-flash` | `6` | `true` | 6 | 6 | 9 |
| `wan@2.6-flash` | `8` | `true` | 8 | 8 | 12 |
| `wan@2.6-flash` | `8` | `false` | 4 | 4 | 6 |
| `wan@2.6-flash` | `10` | `true` | 10 | 10 | 14 |
| `wan@2.6-flash` | `10` | `false` | 5 | 5 | 7 |
| `wan@2.6-flash` | `12` | `true` | 12 | 12 | 17 |
| `wan@2.6-flash` | `12` | `false` | 6 | 6 | 8 |
| `wan@2.6-flash` | `15` | `true` | 15 | 15 | 21 |
| `wan@2.6-flash` | `15` | `false` | 8 | 8 | 10 |
| `wan@2.7-nsfw` | `5` | _any_ | 10 | 13 | 17 |
| `wan@2.7-nsfw` | `10` | _any_ | 20 | 26 | 34 |
| `wan@2.7-nsfw` | `15` | _any_ | 30 | 39 | 51 |
| `wan@3.0`, `wan@3.0-nsfw` | `5` | _any_ | 12 | 24 | 40 |
| `wan@3.0`, `wan@3.0-nsfw` | `6` | _any_ | 15 | 29 | 48 |
| `wan@3.0`, `wan@3.0-nsfw` | `8` | _any_ | 20 | 39 | 64 |
| `wan@3.0`, `wan@3.0-nsfw` | `10` | _any_ | 24 | 48 | 80 |
| `wan@3.0`, `wan@3.0-nsfw` | `12` | _any_ | 29 | 58 | 96 |
| `wan@3.0`, `wan@3.0-nsfw` | `15` | _any_ | 36 | 72 | 120 |
| `wan@3.0`, `wan@3.0-nsfw` | `20` | _any_ | 48 | 96 | 160 |
| `wan@3.0`, `wan@3.0-nsfw` | `25` | _any_ | 60 | 120 | 200 |
| `wan@3.0`, `wan@3.0-nsfw` | `30` | _any_ | 72 | 144 | 240 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `5` | _any_ | 14 | 27 | 45 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `6` | _any_ | 16 | 32 | 54 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `8` | _any_ | 21 | 43 | 72 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `10` | _any_ | 27 | 53 | 90 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `12` | _any_ | 32 | 64 | 108 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `15` | _any_ | 40 | 80 | 135 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `20` | _any_ | 53 | 106 | 180 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `25` | _any_ | 66 | 133 | 225 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `30` | _any_ | 79 | 159 | 270 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `ref_asset` | string or null |  | `null` | Asset ID of the starting image to animate (image-to-video). Required for all models except Seedance 2.0 and `seedance_2_5` in multimodal mode, where the images come from `ref_images` and `ref_asset` is optional (on `seedance_2_5` reference audio alone is enough), and `minimax@3.0*`, which also runs from a `last_frame` alone. |
| `model` | enum |  | `wan@2.2` | One of: `grok@4.1`, `kling@1.6`, `kling@2.1`, `kling@2.5`, `kling@2.6`, `minimax@3.0`, `minimax@3.0-turbo`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5`, `seedance_pro`, `seedance_pro_fast`, `seedance_v1_5_pro`, `wan@2.2`, `wan@2.2-lora`, `wan@2.5`, `wan@2.6`, `wan@2.6-flash`, `wan@2.7`, `wan@2.7-lora`, `wan@2.7-nsfw`, `wan@3.0`, `wan@3.0-nsfw`, `wan@3.0-prime`, `wan@3.0-prime-nsfw`. Video model. Kling: `kling@1.6`, `kling@2.1` (supports last\_frame), `kling@2.5`, `kling@2.6`. WAN: `wan@2.2` (image-to-video, no last\_frame), `wan@2.2-lora` (same as wan@2.2 but accepts `loras`), `wan@2.5`, `wan@2.6`, `wan@2.6-flash` (faster), `wan@2.7`, `wan@2.7-nsfw`, `wan@3.0`, `wan@3.0-nsfw`, `wan@3.0-prime` and `wan@3.0-prime-nsfw` (these support last\_frame and a reference mode; the `-prime` pair runs the same model on a faster, slightly dearer queue). Seedance: `seedance_pro_fast`, `seedance_pro` (supports last\_frame), `seedance_v1_5_pro` (supports last\_frame), `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini` (support last\_frame and a multimodal reference mode), `seedance_2_5` _(trusted)_ (the same, with wider limits, 1080p, up to 30 s and a `task_type`). Grok: `grok@4.1`. MiniMax: `minimax@3.0` (supports last\_frame and a reference mode), `minimax@3.0-turbo` (supports last\_frame). Default `wan@2.2`. |
| `last_frame` | string or null |  | `null` | Asset ID of the target final frame: the video interpolates from `ref_asset` to this frame. Only honoured by models that support it (`kling@2.1`, `seedance_pro`, `seedance_v1_5_pro`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5`, `wan@3.0*`, `minimax@3.0*`); the older WAN models (incl. wan@2.2 and wan@2.7) do not support a last frame. `minimax@3.0*` also takes it without `ref_asset`, for an end-frame-only run. |
| `audio_asset` | string or null |  | `null` | Asset ID of an audio track to drive the video, for models that support audio input. |
| `prompt` | string |  | `""` | Text describing the desired motion and scene. Seedance 2.0, `seedance_2_5`, `wan@3.0*` and `minimax@3.0*` address the media as `[Image N]`, `[Video N]`, `[Audio N]`; the short `[img1]`, `[vid1]`, `[audio1]` the app inserts are accepted too and mean `[Image 1]`, `[Video 1]`, `[Audio 1]`. |
| `duration` | enum |  | `5` | One of: `-1`, `5`, `6`, `8`, `10`, `12`, `15`, `16`, `18`, `20`, `22`, `24`, `25`, `26`, `28`, `30`. Clip length in seconds; valid values are model-dependent: `kling@2.6` → 5 or 10; `wan@2.2`, `wan@2.2-lora` → 5 or 8; `wan@2.6`, `wan@2.7`, `wan@2.7-lora`, `wan@2.7-nsfw` → 5, 10 or 15; `grok@4.1` → 6 or 10; `seedance_2_5` → 5, 10, 15, 20, 25 or 30; `wan@3.0`, `wan@3.0-nsfw`, `wan@3.0-prime`, `wan@3.0-prime-nsfw` → 5, 6, 8, 10, 12, 15, 20, 25 or 30; everything else → 5, 6, 8, 10, 12 or 15. `-1` is not a length: it is `seedance_2_5` with a `task_type` of `edit`, where the result is exactly as long as the source, and no other model or task type accepts it. Any listed value is also accepted under `edit` and ignored. Default 5. |
| `negative_prompt` | string |  | `""` | Text describing what to avoid in the video. |
| `resolution` | enum |  | `720p` | One of: `1080p`, `480p`, `720p`. Output resolution. Most models accept `720p` and `1080p`. `480p` is NOT supported by `wan@2.6`, `wan@2.6-flash`, `wan@2.7`, `wan@2.7-nsfw` or `seedance_v1_5_pro` (use 720p or 1080p for those). `wan@2.2`, `grok@4.1`, `seedance_2_0`, `seedance_2_0_fast` and `seedance_2_0_mini` accept only `480p` or `720p`. `wan@3.0*`, `minimax@3.0*` and `seedance_2_5` accept all three. Default `720p`, except `wan@3.0*`, which defaults to `480p`. |
| `ratio` | enum |  | `adaptive` | One of: `16:9`, `1:1`, `21:9`, `3:4`, `4:3`, `9:16`, `adaptive`. Aspect ratio: `adaptive`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`. Only the Seedance 2.0 models, `seedance_2_5`, `wan@3.0*` and `minimax@3.0` in its reference mode honour this, and `wan@3.0*` rejects `21:9`. On `seedance_2_5` it is ignored and forced to `adaptive` whenever the run has a first frame, or a `task_type` of `edit` or `extend`. Default `adaptive`. |
| `seed` | integer or null |  | `null` | Seed for reproducibility (Seedance 2.0 models, `seedance_2_5`, `wan@3.0*` and `minimax@3.0*`). Default random. |
| `generate_audio` | boolean |  | `true` | One of: `true`, `false`. Generate an audio track too, for models that support it. `minimax@3.0*` always returns one and cannot be silenced — the switch does not reach it. Default true. |
| `camera_fixed` | boolean |  | `false` | One of: `true`, `false`. Keep the camera fixed instead of letting it move. Default false. |
| `prompt_extend` | boolean |  | `false` | One of: `true`, `false`. Let the model auto-expand and enhance your prompt. On `minimax@3.0*` it picks the slower, richer rewrite (~30 s) over the one-second default. Default false. |
| `loras` | object or null |  | `null` | LoRA styles to apply, as a map of LoRA id to a scale-settings object (`{high_scale?, low_scale?}`, both optional — not a bare number). Only `wan@2.2-lora` uses this; browse compatible ids via GET /loras?model=wan@2.2. |
| `ref_images` | array\[string\] or null |  | `null` | Seedance 2.0, `seedance_2_5`, `wan@3.0*` and `minimax@3.0` reference mode: extra reference image asset IDs (up to 8 in addition to `ref_asset`; `seedance_2_5` takes 30 images counting `ref_asset`). Reference them in the prompt as `[Image N]`. |
| `ref_videos` | array\[string\] or null |  | `null` | Seedance 2.0 and `minimax@3.0` multimodal mode: reference video asset IDs (up to 3, ≤15 s total; `seedance_2_5` takes up to 10, ≤30 s total and 2-30 s each). Reference them in the prompt as `[Video N]`. This is the video-to-video path. `wan@3.0*` takes video references only in the video2video tool. |
| `ref_audios` | array\[string\] or null |  | `null` | Seedance 2.0, `seedance_2_5`, `wan@3.0*` and `minimax@3.0` reference mode: reference audio asset IDs (up to 3, ≤15 s each; `seedance_2_5` takes up to 10, ≤30 s each, and accepts audio with no image or video beside it). Reference them in the prompt as `[Audio N]` (`minimax@3.0` also needs a reference image or video alongside). |
| `task_type` | enum or null |  | `null` | One of: `auto`, `edit`, `extend`, `reference`. `seedance_2_5` with references only: what the model does with the reference videos. `auto` (default) lets the model decide from the wording of the prompt — which can silently turn the run into an edit and refuse the requested length. `reference` drives a NEW clip from the references. `edit` changes one reference video in place (exactly one video; the result is as long as the source and is billed for twice its length). `extend` continues one reference video by `duration` more seconds. `edit` and `extend` force `ratio` to `adaptive`, and `edit` takes `duration` as `-1` and ignores any other value. Omit it for frame runs and for every other model. |

**Outputs:**`video_asset` (string), `audio_stripped` (boolean)

### image\_editor

Edit and composite existing images by prompt — the main, most flexible image tool. Bring references, edit and combine them; bring your character and dress them from a reference photo; keep a product or object **exactly** (fabric, pattern, shape) while changing the scene. It offers both SFW and NSFW models, plus LoRA presets that extend NSFW capability. You are limited mainly by your imagination. Edits inherit the source composition (pose, framing), so for a photoshoot-style series of varied organic poses of one character use `photoshoot` instead.

**Models:**

- `GENERAL_NSFW` _(default, trusted)_ — Universal default, uncensored, good facial likeness; general NSFW edits such as outfit or pose changes. Older model — occasional limb artifacts.
- `NANO_BANANA` — High realism and the most precise prompt-driven edits; good at edits involving in-image text. Heavily censored (no NSFW); weaker likeness.
- `NANO_BANANA_2_1` — Google Nano Banana 2.1: precise edits and composites from up to 14 references (the first is the base image), consistent characters and legible in-image text, up to 4K. Censored. The only editor with the extra aspect ratios 4:1, 1:4, 8:1 and 1:8, `thinking_level` and `web_search`; the result keeps the provider's size. Credits per image for `tier` 1K / 2K / 4K: 2 / 2 / 4, with `thinking_level``high` 2 / 3 / 5, independent of the number of references.
- `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` — OpenAI GPT Image 2.5: controlled edits that keep the person, product and layout, exact in-image copy, up to 16 references (the first is the base image), up to 4K (`4K` is beta). Flare is faster, Sunburst is slower and more precise in edits; same price. Censored. `quality`, `transparent_background` and `mask_asset`; without `ratio` the result takes the standard ratio closest to the first image, uncropped. Credits per image for `tier` 1K / 2K / 4K with up to 4 references: `quality``low` 2 / 2 / 2, `medium` 2 / 3 / 3, `high` 3 / 5 / 6; each started 3 references above 4 add 1 credit (5-7: +1, 8-10: +2, 11-13: +3, 14-16: +4).
- `IDEOGRAM_4_5` — Ideogram 4.5: precise edits that leave untouched areas as they were, the best at fixing text and logos, up to 5 images (the first is edited, the rest only guide). Censored. `quality`, `edit_precision` and `mask_asset`; the result keeps the first image's size, so `ratio` and `tier` are ignored. Credits per image for `quality``low` / `medium` / `high`: 1 / 2 / 6.
- `QWEN_IMAGE` / `QWEN_IMAGE_PRO` — Aesthetic, good likeness, few artifacts; Pro adds realism. Uncensored; transforms your NSFW references rather than creating full NSFW content from scratch.
- `SEEDREAM_5` — Newer than the default: better prompt understanding, stronger stylization, better likeness, fewer artifacts. Uncensored; transforms NSFW references.
- `SEEDREAM_5_PRO` — The newest Seedream flagship editor: up to 10 reference images (their order is preserved), all 15 aspect ratios and a `tier` resolution switch (`1K` = 2 credits, `2K` = 3 credits, independent of the number of references). Uncensored; transforms NSFW references.
- `WAN_2_7_IMAGE` / `WAN_2_7_IMAGE_PRO` — Aesthetic bodies and composition, few artifacts, precise editing; Pro = higher quality. Uncensored; transforms NSFW references. Weaker at in-image text.
- `FLUX_KLEIN_NSFW` _(trusted)_ — Local flagship for full NSFW with references: it knows anatomy and accepts a face reference. Slightly lower quality, occasional artifacts.
- `FLUX_KLEIN_LORA` _(trusted)_ — LoRA presets that extend NSFW capability (including clothing-removal presets) and style templates; pass `loras` or `lora_id` (browse via GET /templates).

Models marked _(trusted)_ unlock NSFW behaviour only for trusted accounts (or accounts with an NSFW content policy).

**Price** (credits per image, multiplied by `number_of_images`):

| `model` | `tier` | `thinking_level` | `quality` | Credits |
| --- | --- | --- | --- | --- |
| `FLUX_KLEIN_LORA` | `1K`, `2K` | `minimal` | `medium` | 3 |
| `FLUX_KLEIN_NSFW`, `GENERAL_NSFW`, `QWEN_IMAGE`, `SEEDREAM_4_5`, `SEEDREAM_5`, `WAN_2_7_IMAGE` | `1K`, `2K` | `minimal` | `medium` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | `1K` | `minimal` | `low`, `medium` | 2 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | `1K` | `minimal` | `high` | 3 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | `2K`, `4K` | `minimal` | `low` | 2 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | `2K`, `4K` | `minimal` | `medium` | 3 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | `2K` | `minimal` | `high` | 5 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | `4K` | `minimal` | `high` | 6 |
| `IDEOGRAM_4_5` | `1K`, `2K` | `minimal` | `low` | 1 |
| `IDEOGRAM_4_5`, `QWEN_IMAGE_PRO`, `WAN_2_7_IMAGE_PRO` | `1K`, `2K` | `minimal` | `medium` | 2 |
| `IDEOGRAM_4_5` | `1K`, `2K` | `minimal` | `high` | 6 |
| `NANO_BANANA` | `1K`, `2K` | `minimal` | `medium` | 4 |
| `NANO_BANANA_2_1` | `1K` | _any_ | `medium` | 2 |
| `NANO_BANANA_2_1` | `2K` | `high` | `medium` | 3 |
| `NANO_BANANA_2_1` | `2K` | `minimal` | `medium` | 2 |
| `NANO_BANANA_2_1` | `4K` | `high` | `medium` | 5 |
| `NANO_BANANA_2_1` | `4K` | `minimal` | `medium` | 4 |
| `SEEDREAM_5_PRO` | `1K` | `minimal` | `medium` | 2 |
| `SEEDREAM_5_PRO` | `2K` | `minimal` | `medium` | 3 |

`GPT_IMAGE_2_5_FLARE` and `GPT_IMAGE_2_5_SUNBURST` add 1 credit per image for each started 3 `image_assets` above 4 (5-7: +1, 8-10: +2, 11-13: +3, 14-16: +4; at most 16 images); a `mask_asset` is free, and in `batch_mode` each image is billed alone.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `image_assets` | array\[string\] | yes | — | Asset ID(s) of the source image(s). Pass a single id to edit one image, or several (as an array) to combine them into one result (unless `batch_mode` is set). When `ratio` is not set, the combined result inherits the first image's geometry — put the scene or base image first and face/detail references after it (in `batch_mode` each image keeps its own geometry). |
| `prompt` | string | yes | — | Instruction describing the edit to apply. |
| `model` | enum |  | `GENERAL_NSFW` | One of: `FLUX_KLEIN_LORA`, `FLUX_KLEIN_NSFW`, `GENERAL_NSFW`, `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST`, `IDEOGRAM_4_5`, `NANO_BANANA`, `NANO_BANANA_2_1`, `QWEN_IMAGE`, `QWEN_IMAGE_PRO`, `SEEDREAM_4_5`, `SEEDREAM_5`, `SEEDREAM_5_PRO`, `WAN_2_7_IMAGE`, `WAN_2_7_IMAGE_PRO`. Editing model. `GENERAL_NSFW` — general-purpose editor (default, allows NSFW); `SEEDREAM_4_5` — the same general-purpose editor under another name; `NANO_BANANA` — Google Nano Banana; `QWEN_IMAGE` / `QWEN_IMAGE_PRO` — Qwen editors (Pro = higher quality); `SEEDREAM_5` — Seedream; `SEEDREAM_5_PRO` — the newest Seedream flagship (up to 10 references); `FLUX_KLEIN_NSFW` — Flux Klein editor; `FLUX_KLEIN_LORA` — Flux Klein with a style template (requires `loras` or `lora_id`); `WAN_2_7_IMAGE` / `WAN_2_7_IMAGE_PRO` — WAN 2.7 editors (Pro = higher quality); `NANO_BANANA_2_1` — Google Nano Banana 2.1 (up to 14 references and the top tier); `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` — OpenAI GPT Image 2.5 (up to 16 references and the top tier, Sunburst is more precise in edits); `IDEOGRAM_4_5` — Ideogram 4.5 (best lettering, up to 5 images). |
| `ratio` | enum or null |  | `null` | One of: `16:9`, `1:1`, `1:2`, `1:3`, `1:4`, `1:8`, `21:9`, `2:1`, `2:3`, `3:1`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `9:21`. Aspect ratio (e.g. 1:1, 16:9, 9:16). Overrides width/height when set. When omitted the ratio of the first source image is used and the result is centre-cropped to it, so set `ratio` explicitly whenever the output needs a specific framing. `SEEDREAM_5_PRO` supports 15 ratios (adds 1:2, 2:1, 1:3, 3:1, 4:5, 5:4 and 9:21). `NANO_BANANA_2_1` also takes the four extreme banner ratios and, when the ratio is omitted, follows the first image uncropped. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` take the 8 standard ratios and, when it is omitted, use the standard ratio closest to the first image, uncropped. `IDEOGRAM_4_5` ignores it: the result keeps the first image's size. |
| `tier` | enum |  | `2K` | One of: `1K`, `2K`, `4K`. Output resolution tier: `1K`, `2K` (default) or `4K`. `SEEDREAM_5_PRO` takes `1K` or `2K`; models without a tier ignore it. `NANO_BANANA_2_1` also takes the top tier. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take the top tier, in beta. `IDEOGRAM_4_5` takes `1K` or `2K`, at the same price. Other models reject `4K`. |
| `thinking_level` | enum |  | `minimal` | One of: `high`, `minimal`. Default `minimal` (fast); ignored by other models. `NANO_BANANA_2_1` also takes the longer-reasoning level for a more accurate result, +1 credit. |
| `web_search` | boolean |  | `false` | One of: `true`, `false`. Default `false`; ignored by other models. `NANO_BANANA_2_1` can check Google Search for current facts, places and logos at the same price. |
| `quality` | enum or null |  | `null` | One of: `high`, `low`, `medium`. Default `medium`, the level every model takes. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take a cheaper draft level and a top level that adds detail, latency and credits. `IDEOGRAM_4_5` takes `low` / `medium` / `high` too. |
| `transparent_background` | boolean |  | `false` | One of: `true`, `false`. Default `false`. `true` works on `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` only: they return a PNG with a transparent background (stickers, logos, product cut-outs) at the same price. |
| `width` | integer |  | `1024` | Output width in pixels (default 1024). Used when `ratio` is not set. |
| `height` | integer |  | `1024` | Output height in pixels (default 1024). Used when `ratio` is not set. |
| `batch_mode` | boolean |  | `false` | One of: `true`, `false`. When several `image_assets` are given, edit each one separately (one result per image) instead of combining them into a single image. Default false. |
| `number_of_images` | integer |  | `1` | How many images to generate (default 1). |
| `sequential_generation` | boolean |  | `false` | One of: `true`, `false`. Generate the requested images one after another, each conditioned on the previous result (for consistent, story-like sequences) instead of independently. Default false. |
| `lora_id` | string or null |  | `null` | Deprecated: use `loras` instead. ID of a LoRA style template to apply (when `model=FLUX_KLEIN_LORA`). Browse available templates and their ids via GET /templates. |
| `loras` | object or null |  | `null` | LoRA style templates to apply when `model=FLUX_KLEIN_LORA`, as a map of LoRA id to a scale-settings object (`{high_scale?, low_scale?}`, both optional — not a bare number). Browse ids via GET /templates. All LoRAs must share the same model. |
| `rewrite_prompt` | boolean |  | `false` | One of: `true`, `false`. For `SEEDREAM_5_PRO` only: let the provider rewrite/expand the prompt before generation (default `false`). Leave off for NSFW prompts — the rewriter can corrupt them and produce an image unrelated to what was asked. |
| `mask_asset` | string or null |  | `null` | For `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` / `IDEOGRAM_4_5` only: asset ID of a PNG mask the size of the first image. On a mask with transparency every painted pixel, any colour, marks the area to edit and transparent pixels are kept; on an opaque mask white marks the area and black keeps it. The mask does not change the price, takes one image slot and is not allowed with `batch_mode`. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` read it as guidance: the change lands in the area, the border is approximate and pixels outside may shift slightly; at most 15 `image_assets`. `IDEOGRAM_4_5` edits only the area and needs part of the image left unpainted; at most 4 `image_assets`. |
| `edit_precision` | enum or null |  | `null` | One of: `high`, `regular`. Default `regular`. `IDEOGRAM_4_5` takes `high` for a precise edit: it changes only what the prompt asks and restores every other pixel, at the same price. |

**Outputs:**`image_assets` (array\[string\])

### collaber

Put two characters together in one frame: bring two reference subjects and an optional background/location photo; the tool combines them into a single scene (1-4 images). Strength: keeps both characters' likeness — a convenient preset for collabs and duets.

**Price** (credits per image, multiplied by `number_of_images`):

| `model` | `tier` | Credits |
| --- | --- | --- |
| `GENERAL` | _any_ | 1 |
| `SEEDREAM_5_PRO` | `1K` | 2 |
| `SEEDREAM_5_PRO` | `2K` | 3 |

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `asset_image_1` | string | yes | — | Asset ID of the first persona/subject. |
| `asset_image_2` | string | yes | — | Asset ID of the second persona/subject. |
| `location_asset` | string or null |  | `null` | Optional asset ID of a location/background reference for the scene. |
| `prompt` | string or null |  | `null` | What the two subjects are doing together and the scene to place them in. |
| `model` | enum |  | `GENERAL` | One of: `GENERAL`, `SEEDREAM_5_PRO`. Generation model. `GENERAL` _(default)_ — legacy Bytedance combiner, 8 aspect ratios. `SEEDREAM_5_PRO` — newest Seedream flagship: all 15 aspect ratios and a `tier` resolution switch (`1K` = 2 credits, `2K` = 3 credits). |
| `ratio` | enum |  | `1:1` | One of: `16:9`, `1:1`, `1:2`, `1:3`, `21:9`, `2:1`, `2:3`, `3:1`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `9:21`. Aspect ratio of the output (e.g. 1:1, 16:9, 9:16). `SEEDREAM_5_PRO` supports 15 ratios; `GENERAL` supports the original 8. |
| `tier` | enum |  | `2K` | One of: `1K`, `2K`. Output resolution tier for `SEEDREAM_5_PRO`: `1K` or `2K` (default `2K`). Ignored by `GENERAL`. |
| `width` | integer |  | `1024` | Output width in pixels (used by `GENERAL` when `ratio` is not set; ignored by `SEEDREAM_5_PRO`). |
| `height` | integer |  | `1024` | Output height in pixels (used by `GENERAL` when `ratio` is not set; ignored by `SEEDREAM_5_PRO`). |
| `number_of_images` | integer |  | `1` | Number of images to generate, 1-4. Default 1. |

**Outputs:**`image_assets` (array\[string\])

### couplegen

Paired photo to video: combine two character photos (Seedream) then animate (wan-2.2 i2v + LoRA)

**Price:** 10 credits.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `left_asset` | string | yes | — | Left character photo asset ID |
| `right_asset` | string | yes | — | Right character photo asset ID |
| `lora_id` | string or null |  | `null` | Deprecated: use `loras` instead. Paired preset (LoRA) ID. |
| `loras` | object or null |  | `null` | Paired presets (LoRA) to apply, as a map of LoRA id to a scale-settings object (`{high_scale?, low_scale?}`, both optional — not a bare number). The first entry's is\_paired/combined\_photo\_prompt/duration settings are used. All LoRAs must share the same model. |
| `duration` | enum or null |  | `null` | One of: `5`, `8`. Clip length in seconds: 5 or 8. Defaults to the chosen preset's own duration. |

**Outputs:**`video_asset` (string), `combined_image_asset` (string)

### video2video

Transfer motion or replace a character in a video using a reference video or an Instagram/TikTok URL; the original soundtrack can be kept. SFW and NSFW modes. Provide the source as exactly one of `video_asset`, `instagram_url` or `tiktok_url`; the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes read it only from `video_asset` or `ref_videos`, never from a link. Output: one video.

**Modes:**

- `kling_2_6_sfw` — Handles character replacement best (censored); billed per second.
- `replace_sfw` / `replace_nsfw` — Replace the person in the source video with your image's subject; `replace_nsfw` is uncensored.
- `animate_sfw` / `animate_nsfw` — Motion transfer / animation of your image; `animate_nsfw` is uncensored.
- `dreamactor_m2` _(trusted)_ — Same character-replacement logic, uncensored.
- `seedance_2_0_sfw` / `seedance_2_0_nsfw` / `seedance_2_0_fast_sfw` / `seedance_2_0_fast_nsfw` / `seedance_2_0_mini_sfw` / `seedance_2_0_mini_nsfw` — Seedance 2.0 generation driven by the source video as a reference: a `prompt` is REQUIRED and refers to the source as `[Video 1]`; `image_asset` is OPTIONAL (added as `[Image 1]`). `duration` 5/6/8/10/12/15; native audio via `generate_audio`. The `_fast` and `_mini` variants are cheaper/faster; all variants support only 480p/720p.
- `seedance_2_5_sfw` / `seedance_2_5_nsfw` _(trusted; the nsfw entry is not in every region)_ — The same shape with wider limits: 480p/720p/1080p, `duration` 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 24, 25, 26, 28 or 30 capped so that it plus the source video's length stays within 30 s, up to 30 images and 10 videos of references. `task_type` chooses what the source video is for: a reference for a new clip, a video to edit in place, or one to continue.
- `wan3_0_sfw` / `wan3_0_nsfw` _(the nsfw entry: trusted, not in every region)_ — Wan 3.0 generation driven by the source video, same shape as the `seedance_2_0*` modes: `prompt` is REQUIRED and refers to the source as `[Video 1]`, `image_asset` is OPTIONAL (`[Image 1]`). `duration` 5/6/8/10/12/15/20/25/30 — capped so that it plus the source video's length stays within 30 s — resolution `480p`/`720p`/`1080p`, every ratio except `21:9`. Runs for 15-55 minutes (hours at 1080p) — poll, do not wait.
- `wan3_0_prime_sfw` / `wan3_0_prime_nsfw` _(the nsfw entry: trusted, not in every region)_ — The same Wan 3.0 modes on a faster queue: same fields and results, about 40% quicker, roughly 10% dearer.
- `minimax_3_0` — MiniMax H3 Max driven by the source video, same shape as the `seedance_2_0*` modes: `prompt` is REQUIRED and refers to the source as `[Video 1]`, `image_asset` is OPTIONAL (`[Image 1]`). `duration` 5/6/8/10/12/15, resolution `480p`/`720p`/`1080p`, native audio always. Censored, and the source video is a reference here, so it must fit in 15 s — longer sources are refused rather than trimmed. A run takes seconds.

_Note:_ the uncensored modes trade some quality and prompt understanding — you may need to change the input (the source video or the character) to get a good result on the first try. Modes marked _(trusted)_ are available only to trusted accounts (or accounts with an NSFW content policy).

**Price:** depends on `mode` and the duration of the source video (`video_asset` / `instagram_url` / `tiktok_url`): `dreamactor_m2` _(trusted)_ — 1 credit per second; `kling_2_6_sfw` — 2 credits per second (both capped at 30 seconds of source video); `wan3_0_sfw` / `wan3_0_nsfw` — 2.4 credits per second at 480p, 4.8 at 720p, 8 at 1080p, billed on `duration` plus the summed length of `ref_videos`; `wan3_0_prime_sfw` / `wan3_0_prime_nsfw` — the same modes on a faster queue at 2.625 credits per second at 480p, 5.3 at 720p, 9 at 1080p, billed the same way; the `seedance_2_0*` modes — billed the same way, about 1.4 credits per second at 480p and 3.1 at 720p, the `_fast` and `_mini` variants about a fifth less; `seedance_2_5_sfw` / `seedance_2_5_nsfw` — 1.54 credits per second at 480p, 3.46 at 720p and 11.79 at 1080p over `duration` plus the summed length of `ref_videos`, with at least 9 seconds billed and never less than the same output would cost without a source (so a 5-second source and a 5-second result cost 16 / 35 / 118 credits, and a 25-second result 65 / 145 / 496); a `task_type` of `edit` returns a clip as long as the source and is billed for twice its length; `minimax_3_0` — 1.25 credits per second at 480p, 2 at 720p, 4 at 1080p, billed the same way; other modes — at 480p flat 7 credits for videos up to 5 seconds, then 1.4 credits per second; at 720p flat 13 credits up to 5 seconds, then 2.8 credits per second; at 1080p always 2.8 credits per second.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `image_asset` | string or null |  | `null` | Asset ID of the image whose subject is animated or swapped in. Required for all modes except the `seedance_2_0*`, `wan3_0_*` and `minimax_3_0` modes, where it is an optional reference (`[Image 1]`). |
| `video_asset` | string or null |  | `null` | Asset ID of the source/driving video; with `instagram_url` and `tiktok_url`, one source only. On the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes `[Video 1]` is `video_asset` when it is set, otherwise `ref_videos[0]`; the remaining reference videos follow in order as `[Video 2]`, `[Video 3]` and so on. |
| `instagram_url` | string or null |  | `null` | Instagram post/reel URL used as the source video (one source only). |
| `tiktok_url` | string or null |  | `null` | TikTok post/reel URL used as the source video (one source only). |
| `mode` | enum |  | `replace_sfw` | One of: `animate_nsfw`, `animate_sfw`, `dreamactor_m2`, `kling_2_6_sfw`, `replace_nsfw`, `replace_sfw`, `seedance_2_0_fast_nsfw`, `seedance_2_0_fast_sfw`, `seedance_2_0_mini_nsfw`, `seedance_2_0_mini_sfw`, `seedance_2_0_nsfw`, `seedance_2_0_sfw`, `seedance_2_5_nsfw`, `seedance_2_5_sfw`, `wan3_0_nsfw`, `wan3_0_prime_nsfw`, `wan3_0_prime_sfw`, `wan3_0_sfw`, `minimax_3_0`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5`, `wan3_0`, `wan3_0_prime`. How the image and source video are combined. `replace_sfw` / `replace_nsfw` — replace the person in the source video with your image's subject; `animate_sfw` / `animate_nsfw` — animate your image using the source video's motion; `kling_2_6_sfw` — Kling 2.6 driven animation; `dreamactor_m2` — DreamActor M2 driven animation; `seedance_2_0_sfw`/`seedance_2_0_nsfw`/`seedance_2_0_fast_sfw`/`seedance_2_0_fast_nsfw`/`seedance_2_0_mini_sfw`/`seedance_2_0_mini_nsfw` — Seedance 2.0 generation from the source video as a reference (requires `prompt` and a video in `video_asset` or `ref_videos`); `seedance_2_5_sfw`/`seedance_2_5_nsfw` — the same on Seedance 2.5, which also edits or extends the source video, see `task_type`; `wan3_0_sfw`/`wan3_0_nsfw` — Wan 3.0 generation from the source video as a reference (requires `prompt` and a video in `video_asset` or `ref_videos`); `wan3_0_prime_sfw`/`wan3_0_prime_nsfw` — the same on Wan 3.0's faster, slightly dearer queue; `minimax_3_0` — MiniMax H3 Max generation from the source video as a reference (requires `prompt` and a video in `video_asset` or `ref_videos`). Every `_sfw`/`_nsfw` pair above may also be named without the suffix — `wan3_0`, `wan3_0_prime`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5` — and the half is then chosen from your account: the nsfw entry for a trusted account where the brand allows it, the sfw one otherwise. |
| `resolution` | enum |  | `720p` | One of: `1080p`, `480p`, `720p`. Output resolution: `480p` or `720p`. All Seedance 2.0 modes (`seedance_2_0_sfw`/`seedance_2_0_nsfw`/`seedance_2_0_fast_sfw`/`seedance_2_0_fast_nsfw`/`seedance_2_0_mini_sfw`/`seedance_2_0_mini_nsfw`) accept only `480p` or `720p`; the `seedance_2_5*` modes also accept `1080p`; all `wan3_0*` modes also accept `1080p` and default to `480p`; `minimax_3_0` accepts `480p`, `720p` or `1080p`. |
| `keep_original_sound` | boolean |  | `true` | One of: `true`, `false`. Keep the source video's audio (only for `kling_2_6_sfw`). Default true. |
| `prompt` | string |  | `""` | Text prompt. REQUIRED for the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes; reference the source video as `[Video 1]` and the optional `image_asset` as `[Image 1]`; the short `[img1]`, `[vid1]`, `[audio1]` the app inserts are accepted too and mean `[Image 1]`, `[Video 1]`, `[Audio 1]`. On the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes `[Video 1]` is `video_asset` when it is set, otherwise `ref_videos[0]`; the remaining reference videos follow in order as `[Video 2]`, `[Video 3]` and so on. Ignored by other modes. |
| `ratio` | enum |  | `adaptive` | One of: `16:9`, `1:1`, `21:9`, `3:4`, `4:3`, `9:16`, `adaptive`. Aspect ratio (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` only): `adaptive`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`. The `wan3_0_*` modes reject `21:9`. On `seedance_2_5*` it is forced to `adaptive` when `task_type` is `edit` or `extend`. Default `adaptive`. |
| `duration` | enum |  | `5` | One of: `-1`, `5`, `6`, `8`, `10`, `12`, `15`, `16`, `18`, `20`, `22`, `24`, `25`, `26`, `28`, `30`. Output length in seconds (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` only). Seedance 2.0 and `minimax_3_0`: 5, 6, 8, 10, 12 or 15. `seedance_2_5*`: 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 24, 25, 26, 28 or 30, and `wan3_0_*`: also 20, 25 or 30 - both provided the value plus the source video's length, rounded up to whole seconds, stays within 30. Send `-1` when `task_type` is `edit`, where the result is exactly as long as the source; any listed value is also accepted there and ignored. No other mode or task type accepts `-1`. Default 5. |
| `seed` | integer or null |  | `null` | Seed for reproducibility (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` only). Default random. |
| `generate_audio` | boolean |  | `false` | One of: `true`, `false`. Generate a native audio track (`seedance_2_0*`, `seedance_2_5*` and `wan3_0_*` only). Default false. |
| `camera_fixed` | boolean |  | `false` | One of: `true`, `false`. Keep the camera fixed (`seedance_2_0_sfw`/`seedance_2_0_nsfw` only, ignored by `_fast`). Default false. |
| `ref_images` | array\[string\] or null |  | `null` | Reference image asset IDs (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0`), up to 9 counting `image_asset` (30 on the `seedance_2_5*` modes). Order matters: the prompt addresses them as `[Image N]`. `minimax_3_0` additionally caps images, videos and audios at 12 reference files in total. |
| `ref_videos` | array\[string\] or null |  | `null` | Source/reference video asset IDs (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0`), counted together with `video_asset`: at least 1, up to 3, 15 seconds in total - the `seedance_2_5*` modes take up to 10, 30 seconds in total, and exactly one when `task_type` is `edit` or `extend`. On the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes `[Video 1]` is `video_asset` when it is set, otherwise `ref_videos[0]`; the remaining reference videos follow in order as `[Video 2]`, `[Video 3]` and so on. |
| `ref_audios` | array\[string\] or null |  | `null` | Reference audio asset IDs (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0`), up to 3, 15 seconds in total - the `seedance_2_5*` modes take up to 10, 30 seconds in total. `minimax_3_0` takes them only alongside at least one reference image or video. |
| `task_type` | enum or null |  | `null` | One of: `auto`, `edit`, `extend`, `reference`. `seedance_2_5*` modes only: what the model does with the source video. `auto` (default) lets the model decide from the wording of the prompt - which can silently turn the run into an edit and refuse the requested length. `reference` drives a NEW clip from it. `edit` changes it in place (exactly one video; the result is as long as the source and is billed for twice its length). `extend` continues it by `duration` more seconds. `edit` and `extend` force `ratio` to `adaptive`, and `edit` ignores `duration`, which is sent as `-1`. |

**Outputs:**`video_asset` (string), `audio_stripped` (boolean)

### lipsync

Make a character speak your audio (talking head): bring an audio file and a portrait first frame, and get a video in which the character talks or sings in sync. Up to 35 seconds of audio; image JPG/PNG under 5 MB. Use it to voice a character or avatar. Niche — used occasionally. Priced at 3 credits per second of audio.

**Price:** 3 credits per second of audio, measured from the uploaded `audio_asset` (audio longer than 35 seconds is rejected).

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `image_asset` | string | yes | — | Asset ID of the portrait image (JPG/PNG, under 5MB, up to 4096x4096). |
| `audio_asset` | string | yes | — | Asset ID of the audio track to lip-sync to (under 35 seconds). |
| `prompt` | string |  | `""` | Optional text to guide expression/performance. |
| `model` | enum |  | `GENERAL_NSFW` | One of: `GENERAL_NSFW`, `OMNIHUMAN`. Lip-sync model; every value runs the same OmniHuman pipeline. |

**Outputs:**`video_asset` (string)

### text\_to\_video 🔒

**🔒 Trusted account required** — available only to trusted accounts (granted automatically after your first credit purchase).

Generate a video from a text prompt alone (text-to-video): the tool generates a first frame and then animates it. NSFW-capable.

**Models:**

- `wan@2.7` _(default)_ — Top quality, 720p/1080p, up to 15 s.
- `wan@2.2` — Budget option.
- `wan@3.0` / `wan@3.0-nsfw` _(the nsfw entry: trusted, not in every region)_ — Direct text-to-video with native audio; 480p/720p/1080p, durations 5/6/8/10/12/15/20/25/30 s, prompts up to 20000 characters. No `21:9`. Generation takes 15-55 minutes (hours at 1080p/30 s).
- `wan@3.0-prime` / `wan@3.0-prime-nsfw` — The same pair on a faster queue: identical fields and results, about 40% quicker, roughly 10% dearer.
- `seedance_2_0` / `seedance_2_0_fast` / `seedance_2_0_mini` — Direct text-to-video (no first-frame step); native audio, fixed camera (non-fast), durations 5/6/8/10/12/15 s. All three are 480p/720p only; `seedance_2_0_mini` is the cheapest of the three.
- `seedance_2_5` _(trusted)_ — The same, reaching further: 480p/720p/1080p and durations 5, 10, 15, 20, 25 or 30 s.
- `minimax@3.0` / `minimax@3.0-turbo` — Censored; direct text-to-video with native audio, 480p/720p/1080p, durations 5/6/8/10/12/15 s. Turbo is faster and half the price.

**Price:** depends on `model`, `duration` and `resolution`. `wan@2.2` (budget, resolution-independent): 10 credits at 5 s, 13 credits at 8 s. `wan@2.7` at 720p: 13 credits at 5 s, 26 at 10 s, 39 at 15 s; at 1080p: 17 credits at 5 s, 34 at 10 s, 51 at 15 s. `wan@3.0` and `wan@3.0-nsfw` bill per second at the same rate: 2.4 credits per second at 480p, 4.8 at 720p, 8 at 1080p (so 12-72, 24-144 and 40-240 credits for 5-30 s), the credit total rounded up. `wan@3.0-prime` and `wan@3.0-prime-nsfw` run the same model on a faster queue and bill 2.625 credits per second at 480p, 5.3 at 720p, 9 at 1080p (so 14-79, 27-159 and 45-270 credits for 5-30 s). `seedance_2_0` bills about 1.4 credits per second at 480p and 3.1 at 720p (7-21 and 16-46 credits for 5-15 s); `seedance_2_0_fast` and `seedance_2_0_mini` about 1.1 and 2.5 (6-17 and 13-37). `seedance_2_5` bills about 2.6 credits per second at 480p, 5.8 at 720p and 19.8 at 1080p (13-78, 29-174 and 100-595 credits for 5-30 s). `minimax@3.0` bills 1.25 credits per second at 480p, 2 at 720p and 4 at 1080p; `minimax@3.0-turbo` half of that (0.625 / 1 / 2), the credit total rounded up.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `prompt` | string | yes | — | Text prompt |
| `model` | enum |  | `wan@2.7` | One of: `minimax@3.0`, `minimax@3.0-turbo`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5`, `wan@2.2`, `wan@2.7`, `wan@3.0`, `wan@3.0-nsfw`, `wan@3.0-prime`, `wan@3.0-prime-nsfw`. Video model. `wan@2.7` (default) — top quality, durations 5/10/15 s, 720p or 1080p. `wan@2.2` — budget, durations 5/8 s. `wan@3.0` / `wan@3.0-nsfw` — direct text-to-video with native audio, durations 5/6/8/10/12/15/20/25/30 s, 480p/720p/1080p, no `21:9` ratio; the `-nsfw` entry skips content inspection and is limited to trusted accounts outside the openmov region. `wan@3.0-prime` / `wan@3.0-prime-nsfw` — the same pair on a faster, slightly dearer queue, same fields and limits. `seedance_2_0` / `seedance_2_0_fast` / `seedance_2_0_mini` — direct text-to-video, durations 5/6/8/10/12/15 s; all three are 480p or 720p only. `seedance_2_5` _(trusted)_ — the same, 480p/720p/1080p and durations 5, 10, 15, 20, 25 or 30 s. `minimax@3.0` / `minimax@3.0-turbo` — censored direct text-to-video with native audio, durations 5/6/8/10/12/15 s, 480p/720p/1080p; turbo is half the price. |
| `ratio` | enum |  | `1:1` | One of: `16:9`, `1:1`, `21:9`, `3:4`, `4:3`, `9:16`, `adaptive`. Aspect ratio. wan@2.2/wan@2.7: 1:1, 16:9, 9:16, 4:3, 3:4. `wan@3.0*` also accept `adaptive` but reject `21:9`. Seedance 2.0 and `seedance_2_5` accept every value. `minimax@3.0*` accepts every value except `adaptive`, which it resolves to 16:9. Default 1:1. |
| `duration` | enum |  | `5` | One of: `5`, `6`, `8`, `10`, `12`, `15`, `16`, `18`, `20`, `22`, `24`, `25`, `26`, `28`, `30`. Clip length in seconds; valid values are model-dependent: `wan@2.7` → 5, 10 or 15; `wan@2.2` → 5 or 8; `wan@3.0*` → 5, 6, 8, 10, 12, 15, 20, 25 or 30; Seedance 2.0 and `minimax@3.0*` → 5, 6, 8, 10, 12 or 15; `seedance_2_5` → 5, 10, 15, 20, 25 or 30. Default 5. Other model/duration combinations are rejected. |
| `resolution` | enum |  | `720p` | One of: `1080p`, `480p`, `720p`. Output resolution. `wan@2.7` → `720p` (default) or `1080p`; `wan@2.2` → `480p` or `720p` (default); `wan@3.0*` → `480p` (default), `720p` or `1080p`; Seedance 2.0 (`seedance_2_0` / `seedance_2_0_fast` / `seedance_2_0_mini`) → `480p` or `720p`; `seedance_2_5` → `480p`, `720p` (default) or `1080p`; `minimax@3.0` / `minimax@3.0-turbo` → `480p`, `720p` (default) or `1080p`. |
| `seed` | integer or null |  | `null` | Seed for reproducibility (Seedance 2.0, `seedance_2_5` and `minimax@3.0*` models). Default random. |
| `generate_audio` | boolean |  | `false` | One of: `true`, `false`. Generate an audio track too (Seedance 2.0 models, `seedance_2_5` and `wan@3.0*`; `minimax@3.0*` always returns one, with or without this switch). Default false. |
| `camera_fixed` | boolean |  | `false` | One of: `true`, `false`. Keep the camera fixed (Seedance 2.0, not the fast variant). Default false. |

**Outputs:**`video_asset` (string), `audio_stripped` (boolean)

### video\_upscaler

Bring a medium-quality video and get a sharper, higher-resolution result via BytePlus vCube. Pick a quality tier (`standard` — fast and affordable, or `pro` — premium model) and a target output resolution (`1080p`, `2k` or `4k`). Output is locked to 30fps. Priced per output second by tier x resolution x duration.

**Price:** depends on `mode` and `resolution` (BytePlus vCube engine): `standard` — $0.00689/s at 1080p, $0.01377/s at 2k, $0.02755/s at 4k; `pro` — roughly 10x standard ($0.06887/s at 1080p, $0.13774/s at 2k, $0.27548/s at 4k), converted to credits and floored at 1 credit. Output is locked to 30 fps.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `video_asset` | string | yes | — | Asset ID of the video to upscale. |
| `mode` | enum or null |  | `null` | One of: `pro`, `standard`. Quality tier: `standard` (fast, affordable) or `pro` (premium model, ~10x price). Default `standard`. |
| `resolution` | enum or null |  | `null` | One of: `1080p`, `2k`, `4k`. Target output resolution: `1080p`, `2k` or `4k`. Higher costs more. Default `1080p`. |

**Outputs:**`video_asset` (string)

### video\_merger

Concatenate 2-5 video clips with transitions

**Price:** 1 credit.

**Input parameters:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `clips` | array\[object\] | yes | — | Clips to concatenate: {asset\_id, source\_duration\_sec, trim\_start\_sec, trim\_end\_sec}, or a bare asset id, which is what a workflow edge into this port carries; source\_duration\_sec is optional and probed automatically when omitted |
| `transition` | enum |  | `cut` | One of: `cut`, `dissolve`, `fade`, `slide`. cut \| fade \| slide \| dissolve |
| `keep_audio` | boolean |  | `true` | One of: `true`, `false`. Preserve audio tracks |
| `fps` | integer |  | `30` | Output FPS (24 or 30) |
| `width` | integer |  | `1280` | Output width |
| `height` | integer |  | `720` | Output height |

**Outputs:**`video_asset` (string)

## Trusted Accounts

Some tools and models are limited to **trusted accounts**. Trusted status unlocks extended capabilities — trusted-only tools and uncensored, full-NSFW generation models. An account becomes trusted **automatically after its first successful payment** (purchasing any credit pack at [https://app.zencreator.pro/billing](https://app.zencreator.pro/billing)); the status is permanent.

- **Trusted-only tools** are marked 🔒 in the Tools & Pricing table above. `POST /generations` rejects them for non-trusted accounts (`403 forbidden`), and `GET /api/public/v1/tools` returns them only once your account is trusted.
- **Full-NSFW models** — several otherwise-public tools (e.g. `by_prompt`, `image_editor`, `videogen`, `video2video`) expose models or modes annotated _(trusted)_ in their description. These produce uncensored NSFW output and are available only to trusted accounts (or accounts with an NSFW content policy); other accounts receive an error when selecting them.
- **LoRA styles** — `GET /api/public/v1/loras` returns 18+ / trusted styles only for trusted accounts.
- **Templates & photoshoot categories** — `GET /api/public/v1/templates` and `GET /api/public/v1/photoshoot-categories` return only SFW, public presets through the public API, regardless of account status.

Listings are therefore account-dependent: a trusted key sees a superset of the tools, models and LoRA styles an untrusted key sees.

## Uploading Files

`POST /api/public/v1/assets` accepts `multipart/form-data` with two parts: `media_type` and `file` (max **50 MB**):

```bash
curl -X POST "https://api.zencreator.pro/api/public/v1/assets" \
  -H "Authorization: Bearer $ZC_API_KEY" \
  -F "media_type=image/png" \
  -F "file=@face.png"
# -> {"asset_id": "0196...", "media_type": "image/png"}
```

Supported media types: images `image/png`, `image/jpeg`, `image/jpg`, `image/webp`, `image/heic`, `image/heif`; video `video/mp4`, `video/mov`, `video/quicktime`; audio `audio/mpeg`, `audio/mp3`, `audio/wav`, `audio/x-wav`, `audio/x-m4a`.

## Templates, LoRA styles & Photoshoot categories

Several tools accept _presets_ — ready-made styles you reference by id instead of crafting from scratch:

- **Templates** — `GET /api/public/v1/templates` lists ready-to-use generation presets (`id`, `name`, `tags`, `description`, and the baked-in `input`). Send a template's `input` straight to `POST /generations`, or pass its `id` as the `lora_id` of tools that accept one (e.g. `image_editor` with `model=FLUX_KLEIN_LORA`).
- **LoRA styles** — `GET /api/public/v1/loras?model=<model>` lists LoRA styles for a model; pass a LoRA's `id` (or name) in the `loras` / `lora_id` field of tools that support it and include its `trigger_word` in the prompt. `model=wan@2.7` lists video LoRAs for the `videogen` tool: pass the LoRA's `id` as a key of its `loras` object with `model=wan@2.7-lora`; when `prompt` is empty the LoRA's `trigger_word` (its default prompt) is used. The `is_nsfw` flag marks adult styles; 18+ and trusted styles are returned only for trusted accounts (see Trusted Accounts).
- **Photoshoot categories** — `GET /api/public/v1/photoshoot-categories` lists curated categories; pass a category's `id` as `category_id` to the `photoshoot` tool to generate `image_count` images from that category.

Templates and photoshoot categories returned by the public API are SFW and public only, regardless of account.

## Credits & Billing

Generations are paid in **credits**. Exact prices per tool are listed in the Tools & Pricing section above; the `price` field of `GET /tools` is the tool's base price — the actual charge can vary with the input (model, duration, resolution, number of images). The exact amount charged for every generation is recorded in your transaction history (`GET /api/public/v1/transactions`). Credits are charged when a generation is accepted and **automatically refunded** if it fails.

- Check your balance: `GET /api/public/v1/balance`.
- Top up credits: [https://app.zencreator.pro/billing](https://app.zencreator.pro/billing).
- When the balance is too low, the API responds `402` with code `insufficient_credits`.

## Rate Limits

Limits are applied per API key over a 60-second sliding window:

| Operation | Limit |
| --- | --- |
| Read (GET endpoints) | 180/min |
| Start generation | 30/min |
| Upload asset | 30/min |

Every response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. On `429` and `503` also check `Retry-After` (seconds).

## Idempotency

`POST /generations` supports the `Idempotency-Key` header. Requests repeated with the same key within **24 hours** return the original generation instead of creating (and charging for) a new one. Use it to make network retries safe.

## Errors

All errors share one envelope:

```json
{"error": {"code": "validation_error", "message": "Invalid enum value 'NOT_A_MODEL' - at `$.model`"}}
```

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `bad_request` | Malformed request or JSON body |
| 401 | `missing_api_key` | No `Authorization: Bearer` header |
| 401 | `invalid_api_key` | Key not found, revoked or expired |
| 402 | `insufficient_credits` | Not enough credits — top up at [https://app.zencreator.pro/billing](https://app.zencreator.pro/billing) |
| 403 | `insufficient_scope` | The key lacks the required scope (`read` / `generate`) |
| 403 | `forbidden` | The resource belongs to another account |
| 403 | `user_blocked` | The account is blocked |
| 404 | `not_found` | Unknown tool, generation or route |
| 409 | `conflict` | Conflicting state |
| 413 | `payload_too_large` | Upload exceeds 50 MB |
| 415 | `unsupported_media_type` | Media type not supported |
| 422 | `validation_error` | Input failed validation — the message names the offending field |
| 429 | `rate_limit_exceeded` | Rate limit hit — retry after `Retry-After` seconds |
| 500 | `internal_error` | Unexpected server error |
| 503 | `service_unavailable` | Service temporarily unavailable — retry after `Retry-After` seconds |

A _failed generation_ is not an HTTP error: the generation responds `200` with `"status": "failed"` and a human-readable `error` field.

## Polling

There are no webhooks yet — poll `GET /generations/{id}` every 5-10 seconds. Generations typically finish within 10-120 seconds depending on the tool.

Server

Server:https://api.zencreator.pro

AuthenticationRequired

|     |
| --- |
| Public API key: `Authorization: Bearer zc_live_<key_id>_<secret>`. |
| Bearer Token: |

Client Libraries

Shell

Ruby

Node.js

PHP

Python

MoreSelect from all clients

Shell Curl

## Tools

​Copy link

Catalog of generation tools with prices and machine-readable input schemas.

Tools Operations

- [get/api/public/v1/tools/{tool\_name}](https://api.zencreator.pro/api/public/docs#tag/tools/GET/api/public/v1/tools/{tool_name})
- [get/api/public/v1/tools](https://api.zencreator.pro/api/public/docs#tag/tools/GET/api/public/v1/tools)