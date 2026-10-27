# ZenCreator Public API — Skill for AI Agents

Programmatic access to ZenCreator's AI generation tools: image generation, face swap, upscaling,
video generation, lipsync and more. All generations are asynchronous: start, poll, fetch outputs.

## Authentication

Send `Authorization: Bearer <API_KEY>` with every request. Keys look like
`zc_live_<key_id>_<secret>` and are created at https://app.zencreator.pro/api-keys (scopes: `read`, `generate`).

- Base URL: https://api.zencreator.pro
- OpenAPI JSON: https://api.zencreator.pro/api/public/openapi.json
- Human documentation: https://api.zencreator.pro/api/public/docs

## Quickstart

1. `GET /api/public/v1/tools` — pick a tool; its `input_schema` (JSON Schema) defines the `input` payload.
2. `POST /api/public/v1/generations` with body `{"tool": "<name>", "input": {...}}`.
   Invalid input returns `422` with the offending field; nothing is charged.
3. Poll `GET /api/public/v1/generations/{id}` every 5-10s until status is `succeeded`, `partial` or `failed`.
   On `failed`/`partial` the `error` field explains why.
4. `GET /api/public/v1/generations/{id}/result` — asset outputs with URLs or top-level `text`.

Tools referencing images/video/audio take **asset IDs**: upload via
`POST /api/public/v1/assets` (multipart: `media_type`, `file`; max 50 MB) and pass the returned `asset_id`.

## Endpoints

Every `GET` endpoint requires the `read` scope; `POST /generations` and `POST /assets` require `generate`.

- `GET /api/public/v1/tools` — list tools with prices and input schemas
- `GET /api/public/v1/tools/{tool_name}` — one tool
- `POST /api/public/v1/generations` — start a generation (header `Idempotency-Key` makes retries safe, 24h)
- `GET /api/public/v1/generations/{id}` — status: `queued` | `processing` | `succeeded` | `partial` | `failed`
- `GET /api/public/v1/generations/{id}/result` — asset outputs or text of a finished generation
- `POST /api/public/v1/assets` — upload an input file, returns `asset_id`
- `GET /api/public/v1/loras?model=<model>` — LoRA styles (pass `id` as `lora_id` in tool inputs; `model=wan@2.7` lists video LoRAs — pass `id` as a key of `videogen`'s `loras` with `model=wan@2.7-lora`)
- `GET /api/public/v1/templates` — ready-to-use presets (send its `input`, or pass `id` as `lora_id`)
- `GET /api/public/v1/photoshoot-categories` — categories for the `photoshoot` tool (pass `id` as `category_id`)
- `GET /api/public/v1/balance` — current credit balance
- `GET /api/public/v1/transactions` — credit history (top-ups, spends, refunds)

## Credits

Prices are listed per tool in the catalog below; for many tools the charge depends on the input
(model, duration, resolution, number of images). Credits are charged on acceptance and
refunded automatically when a generation fails. Balance too low → `402 insufficient_credits`. Top up at https://app.zencreator.pro/billing.

## Rate Limits

Per API key, 60-second sliding window: read 180/min, generate 30/min,
upload 30/min. Watch `X-RateLimit-Remaining` and `Retry-After` headers.

## Errors

Envelope: `{"error": {"code": "...", "message": "..."}}`. Codes: `missing_api_key`/`invalid_api_key` (401),
`insufficient_credits` (402), `insufficient_scope`/`forbidden`/`user_blocked` (403), `not_found` (404),
`payload_too_large` (413), `unsupported_media_type` (415), `validation_error` (422),
`rate_limit_exceeded` (429), `internal_error` (500), `service_unavailable` (503, retry after `Retry-After`).
A failed generation is NOT an HTTP error — it is `200` with `"status": "failed"` and an `error` message.

## Trusted Accounts

Some capabilities are limited to **trusted accounts**. An account becomes trusted automatically
after its first successful payment (purchasing any credit pack); the status is permanent.

- **Trusted-only tools** — marked 🔒 in the catalog below. `POST /generations` rejects them for
  non-trusted accounts, and `GET /api/public/v1/tools` returns them only once your account is trusted.
- **Full-NSFW models** — some otherwise-public tools (e.g. `by_prompt`, `image_editor`, `videogen`,
  `video2video`) expose models/modes marked *(trusted)* that produce uncensored NSFW output. They are
  available only to trusted accounts; other accounts get an error.
- **LoRA styles** — `GET /api/public/v1/loras` returns 18+ / trusted styles only for trusted accounts.
- **Templates & photoshoot categories** — the public API returns only SFW, public presets, regardless
  of account status.

Account-dependent listings mean the tool, model and LoRA sets a trusted key sees are a superset of an
untrusted key's. This document lists every tool (🔒 included) so agents know the full surface.

## Tool Catalog

### run_any_llm

Run an uncensored large language model over a text prompt and return the generated text. Useful as a text-generation or prompt-rewriting node — e.g. inside a workflow to compose or expand a prompt before an image/video tool.

**Models:** `grok` (text + up to 4 reference images — computer vision), `hermes-3-405b`, `euryale-70b` (text-only).

Input: a `model`, a `prompt`, an optional `system_prompt`, an optional `max_tokens`, and optional `image_assets` (grok only). `prompt` and `system_prompt` together must not exceed 32000 characters. Output: the generated `text`.

**Price:** 1 credit.

Input fields:
- `model` (one of: "euryale-70b" | "grok" | "hermes-3-405b"; required) — Which model to use: grok | hermes-3-405b | euryale-70b. Only grok accepts image_assets. All three are uncensored.
- `prompt` (string; required) — The user prompt to send to the model.
- `system_prompt` (string; default: "") — Optional system prompt that steers the model.
- `max_tokens` (integer; default: 2048) — Maximum number of tokens to generate (default 2048, max 4096).
- `image_assets` (array[string] or null; default: null) — Optional reference image(s) to analyze alongside the prompt (vision-capable models only, e.g. grok).

**Outputs:** `text` (string)

### upscaler

Increase the resolution of an existing image while restoring or adding detail. Best for low-resolution sources that need to be cleaned up and improved; gains are limited on an already-sharp 4K image. Input: one image asset. Output: one higher-resolution image.

**Versions:**
- `seedvr2_7b` *(default)* — Premium diffusion-restoration upscaler for 4K/6K output; `detail` and `target_resolution` control it, plus `noise_scale`.
- `seedvr2_3b` — Fast diffusion-restoration upscaler; `detail` and `target_resolution` control it.

**Price** (credits):

| `version` | `target_resolution` | Credits |
|---|---|---|
| `seedvr2_3b` | *any* | 1 |
| `seedvr2_7b` | `2k`, `8k` | 1 |
| `seedvr2_7b` | `4k` | 2 |
| `seedvr2_7b` | `6k` | 3 |

Input fields:
- `image_asset` (string; required) — Asset ID of the image to upscale (upload via POST /assets).
- `version` (one of: "seedvr2_3b" | "seedvr2_7b"; default: "seedvr2_7b") — Upscale engine. `seedvr2_7b` — premium diffusion-restoration upscale for 4K/6K output, controlled by `detail`/`target_resolution` plus `noise_scale`; `seedvr2_3b` — fast diffusion-restoration upscale controlled by `detail`/`target_resolution`. Default `seedvr2_7b`.
- `target_resolution` (one of: "2k" | "4k" | "6k" | "8k"; default: "4k") — Output size tier. `seedvr2_3b` accepts `2k`, `4k`, `8k`; `seedvr2_7b` accepts `4k`, `6k`. Default `4k`.
- `detail` (one of: "high" | "low" | "medium"; default: "medium") — How much of the source is preserved before upscaling — `high` keeps the most source detail (smallest pre-processing budget), `low` allows the most restoration. One of `high`, `medium`, `low`. Default `medium`.
- `noise_scale` (number; default: 0) — `seedvr2_7b` only: amount of synthetic detail added during upscaling, 0-1. Default 0.

**Outputs:** `image_asset` (string)

### faceswap

Swap a face on a photo: the face from `face_asset` is placed onto the person in `ref_asset`, keeping the reference image's body, pose and scene. Image only — there is no video face swap. Output: one image with the face replaced.

**Models:**
- `SEEDREAM_5_PRO` *(default)* — Highest-quality swap. `swap_type` picks what is replaced: `face` (face only, reference's hairstyle kept), `head` (whole head including hair) or `person` (the person in `face_asset` replaces the person in `ref_asset`: face, hair and skin tone come from `face_asset`, while pose, body, outfit, background and light stay from the reference). `tier` picks 1K/2K; the output's aspect ratio always follows `ref_asset`.
- `FULL_HEAD` — Replaces the entire head, not just the face — use it when the target's hairstyle or head shape differs strongly from the source.

**Price** (credits):

| `model` | `tier` | Credits |
|---|---|---|
| `FULL_HEAD`, `MULEROUTER_FACE`, `MULEROUTER_HEAD` | *any* | 1 |
| `SEEDREAM_5_PRO` | `1K` | 2 |
| `SEEDREAM_5_PRO` | `2K` | 3 |

Input fields:
- `ref_asset` (string; required) — Asset ID of the target image whose face will be replaced.
- `face_asset` (string; required) — Asset ID of the image providing the new face.
- `model` (one of: "FULL_HEAD" | "MULEROUTER_FACE" | "MULEROUTER_HEAD" | "SEEDREAM_5_PRO"; default: "SEEDREAM_5_PRO") — Face-swap model: `SEEDREAM_5_PRO` (default), a full-head variant or a MuleRouter swap.
- `seed` (integer or null; default: null) — Seed for reproducibility. Default random.
- `swap_type` (one of: "face" | "head" | "person"; default: "face") — What `SEEDREAM_5_PRO` replaces: `face` (default), `head` or `person`.
- `tier` (one of: "1K" | "2K"; default: "2K") — Output resolution tier for `SEEDREAM_5_PRO`: `1K` or `2K` (default). The aspect ratio always follows `ref_asset`.

**Outputs:** `image_asset` (string)

### by_prompt

Generate an image from a text prompt, with no input image (text-to-image). The entry point for creation: use it when there is no source image and the picture is described in words — building a character or content from scratch, concepts, backgrounds, NSFW from a description, quick drafts and final hero shots. Supports fast/quality modes and aspect ratios; for several images pass several input objects, one per image.

**Three content groups (pick by what you need):**
- **Top cloud models, censored** (`GENERAL_NSFW`, `NANO_BANANA`, `NANO_BANANA_2_1`, `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST`, `IDEOGRAM_4_5`) — highest quality and realism, but they block full NSFW content.
- **Uncensored, not built for full NSFW** (`WAN_2_7_IMAGE`, `QWEN_IMAGE`, `SEEDREAM_5`, `SEEDREAM_5_PRO`) — high quality and won't block, but won't create full NSFW content from scratch; they accurately **transform NSFW references** you provide.
- **Built for full NSFW** (`FLUX_KLEIN_NSFW`, `Z_IMAGE_SPICY`) — slightly lower quality and more artifacts, but real full-NSFW capability.

**Models:**
- `GENERAL_NSFW` *(default, trusted)* — General-purpose workhorse with a good quality/speed/price balance and strong facial likeness; the NSFW version is uncensored but does not produce full NSFW anatomy from text alone (it covers it up). Older model — occasional hand/limb artifacts.
- `GENERAL_SFW` — The same pipeline, SFW only.
- `WAN_2_7_IMAGE` / `WAN_2_7_IMAGE_PRO` — Modern model with higher quality and detail (Pro = top consistency). Renders bodies, scenes and composition more aesthetically and has fewer hand/limb artifacts. Weaker at in-image text. Uncensored, but transforms your NSFW references rather than inventing full NSFW content.
- `WAN` — Legacy WAN image model; prefer `WAN_2_7_IMAGE`.
- `Z_IMAGE_SPICY` *(trusted only)* — Z-Image Spicy (MuleRouter): uncensored photoreal images from text. `mode` picks `fast` (Standard, 1 credit) or `quality` (Pro, 2 credits); `ratio` is the only size control — `width`/`height`, `negative_prompt` and `tier` are ignored.
- `QWEN_IMAGE` / `QWEN_IMAGE_PRO` — Aesthetic results with good facial likeness and few artifacts; great for stylized / illustrative / anime subjects. Pro adds realism. Uncensored; transforms NSFW references.
- `SEEDREAM_5` — Newer generation: better prompt understanding, stronger stylization, better likeness, fewer artifacts. Uncensored; transforms NSFW references.
- `SEEDREAM_5_PRO` — The newest Seedream flagship: top prompt understanding and realism; supports all 15 aspect ratios and a `tier` resolution switch (`1K` = 2 credits, `2K` = 3 credits). Uncensored; transforms NSFW references.
- `NANO_BANANA` — Among the best for realism, and reliably renders legible in-image text (posters, signage, captions); strong real-world knowledge. Heavily censored — won't produce even mildly suggestive content. Weaker facial likeness.
- `NANO_BANANA_2_1` — Google Nano Banana 2.1: precise prompt following, consistent characters and legible in-image text (posters, infographics), up to 4K. Censored. The only model with the extra aspect ratios 4:1, 1:4, 8:1 and 1:8, `thinking_level` and `web_search`. Credits for `tier` 1K / 2K / 4K: 1 / 2 / 4, with `thinking_level` `high` 2 / 3 / 5.
- `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` — OpenAI GPT Image 2.5: strict prompt following, exact in-image copy and controlled layouts, up to 4K (`4K` is beta). Flare is faster, Sunburst is slower and more precise; same price. Censored. The 8 standard aspect ratios, `quality` and `transparent_background`. Credits for `tier` 1K / 2K / 4K: `quality` `low` 1 / 1 / 1, `medium` 1 / 1 / 2, `high` 2 / 3 / 5.
- `IDEOGRAM_4_5` — Ideogram 4.5: the best lettering of our models — readable quoted text, typography and logos on posters and signs. Censored. The 8 standard aspect ratios, `tier` 1K or 2K, `quality` and `rewrite_prompt`; no `negative_prompt`. Credits for `quality` `low` / `medium` / `high`: 1 / 2 / 6 at any `tier`.
- `FLUX_KLEIN_NSFW` *(trusted)* — The most advanced local full-NSFW model: creates uncensored NSFW content and also works with references — bring a character's face and create an action. Slightly lower quality, occasional artifacts.
- `KREA_2` *(trusted only)* — Krea v2 (WaveSpeed) with its built-in style LoRA; `negative_prompt`, `mode` and `width`/`height` are ignored. `tier` picks 1K (1 credit) / 2K (2 credits); `ratio` is the only size control.

Models marked *(trusted)* unlock NSFW behaviour only for trusted accounts (or accounts with an NSFW content policy).

**Price** (credits):

| `model` | `mode` | `tier` | `thinking_level` | `quality` | Credits |
|---|---|---|---|---|---|
| `FLUX_KLEIN_NSFW`, `IDEOGRAM_4_5`, `NANO_BANANA`, `QWEN_IMAGE_PRO`, `WAN_2_7_IMAGE_PRO` | *any* | `1K`, `2K` | `minimal` | `medium` | 2 |
| `GENERAL_NSFW`, `GENERAL_SFW`, `QWEN_IMAGE`, `SEEDREAM_5`, `WAN`, `WAN_2_7_IMAGE` | *any* | `1K`, `2K` | `minimal` | `medium` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | *any* | `1K`, `2K` | `minimal` | `low`, `medium` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | *any* | `1K` | `minimal` | `high` | 2 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | *any* | `2K` | `minimal` | `high` | 3 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | *any* | `4K` | `minimal` | `low` | 1 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | *any* | `4K` | `minimal` | `medium` | 2 |
| `GPT_IMAGE_2_5_FLARE`, `GPT_IMAGE_2_5_SUNBURST` | *any* | `4K` | `minimal` | `high` | 5 |
| `IDEOGRAM_4_5` | *any* | `1K`, `2K` | `minimal` | `low` | 1 |
| `IDEOGRAM_4_5` | *any* | `1K`, `2K` | `minimal` | `high` | 6 |
| `KREA_2`, `NANO_BANANA_2_1` | *any* | `1K` | `minimal` | `medium` | 1 |
| `KREA_2`, `NANO_BANANA_2_1` | *any* | `2K` | `minimal` | `medium` | 2 |
| `NANO_BANANA_2_1` | *any* | `1K` | `high` | `medium` | 2 |
| `NANO_BANANA_2_1` | *any* | `2K` | `high` | `medium` | 3 |
| `NANO_BANANA_2_1` | *any* | `4K` | `high` | `medium` | 5 |
| `NANO_BANANA_2_1` | *any* | `4K` | `minimal` | `medium` | 4 |
| `SEEDREAM_5_PRO` | *any* | `1K` | `minimal` | `medium` | 2 |
| `SEEDREAM_5_PRO` | *any* | `2K` | `minimal` | `medium` | 3 |
| `Z_IMAGE_SPICY` | `fast` | `1K`, `2K` | `minimal` | `medium` | 1 |
| `Z_IMAGE_SPICY` | `quality` | `1K`, `2K` | `minimal` | `medium` | 2 |

Input fields:
- `positive_prompt` (string; required) — Text describing what to generate.
- `negative_prompt` (string; default: "") — Text describing what to avoid in the image.
- `batch_size` (integer; default: 1) — Must be 1: this tool generates one image per input. For N images pass N input objects.
- `model` (one of: "FLUX_KLEIN_NSFW" | "GENERAL_NSFW" | "GENERAL_SFW" | "GPT_IMAGE_2_5_FLARE" | "GPT_IMAGE_2_5_SUNBURST" | "IDEOGRAM_4_5" | "KREA_2" | "NANO_BANANA" | "NANO_BANANA_2_1" | "QWEN_IMAGE" | "QWEN_IMAGE_PRO" | "SEEDREAM_5" | "SEEDREAM_5_PRO" | "WAN" | "WAN_2_7_IMAGE" | "WAN_2_7_IMAGE_PRO" | "Z_IMAGE_SPICY"; default: "GENERAL_NSFW") — Generation model, covering the WAN (incl. WAN 2.7 image), Nano Banana, Seedream, Qwen and Flux Klein families; `*_PRO` variants trade speed for higher quality. The general NSFW family is offered where the brand allows adult content.
- `ratio` (one of: "16:9" | "1:1" | "1:2" | "1:3" | "1:4" | "1:8" | "21:9" | "2:1" | "2:3" | "3:1" | "3:2" | "3:4" | "4:1" | "4:3" | "4:5" | "5:4" | "8:1" | "9:16" | "9:21"; default: "1:1") — Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2 or 21:9 (default 1:1, square). `SEEDREAM_5_PRO` additionally supports 1:2, 2:1, 1:3, 3:1, 4:5, 5:4 and 9:21. `NANO_BANANA_2_1` also takes the four extreme banner ratios, up to eight to one. `IDEOGRAM_4_5` takes the 8 standard ratios only.
- `tier` (one of: "1K" | "2K" | "4K"; default: "2K") — Output resolution tier: `1K`, `2K` (default) or `4K`. `SEEDREAM_5_PRO` / `KREA_2` take `1K` or `2K`; models without a tier ignore it. `NANO_BANANA_2_1` also takes the top tier. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take the top tier, in beta. `IDEOGRAM_4_5` takes `1K` or `2K`, at the same price. Other models reject `4K`.
- `thinking_level` (one of: "high" | "minimal"; default: "minimal") — Default `minimal` (fast); ignored by other models. `NANO_BANANA_2_1` also takes the longer-reasoning level for a more accurate result, +1 credit.
- `web_search` (boolean; default: false) — Default `false`; ignored by other models. `NANO_BANANA_2_1` can check Google Search for current facts, places and logos at the same price.
- `quality` (one of: "high" | "low" | "medium"; default: null) — Default `medium`, the level every model takes. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take a cheaper draft level and a top level that adds detail, latency and credits. `IDEOGRAM_4_5` takes `low` / `medium` / `high` too.
- `transparent_background` (boolean; default: false) — Default `false`. `true` works on `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` only: they return a PNG with a transparent background (stickers, logos, product cut-outs) at the same price.
- `mode` (one of: "fast" | "quality"; default: "fast") — Generation mode: `fast` (quicker and cheaper) or `quality` (slower, higher fidelity).
- `width` (integer or null; default: null) — Optional output width in pixels; if omitted a size is derived from `ratio`.
- `height` (integer or null; default: null) — Optional output height in pixels; if omitted a size is derived from `ratio`.
- `rewrite_prompt` (boolean; default: false) — For `SEEDREAM_5_PRO` / `IDEOGRAM_4_5` only: let the provider rewrite/expand the prompt before generation (default `false`). Leave off for NSFW prompts — the rewriter can corrupt them and produce an image unrelated to what was asked. `IDEOGRAM_4_5` may uppercase quoted text when it rewrites.

**Outputs:** `image_asset` (string)

### by_ref

Recreate a reference photo's scene for your character (image-to-image). `SEEDREAM_5_PRO` recreates the reference's scene (pose, outfit, composition, light) for the character(s) from `character_assets` (required for this model, 1-4). With `keep_pose` the reference is instead edited in place: its pose, body, composition, outfit, lighting and background stay exactly as they are and only the person's identity (face, hair, skin tone) is taken from `character_assets`. Output size follows the reference by default, or a fixed `ratio` (ignored with `keep_pose`); `tier` picks 1K/2K. The pre-August `face_asset` and `body_asset` fields are still accepted and fold into `character_assets`.

**Price** (credits):

| `tier` | Credits |
|---|---|
| `1K` | 2 |
| `2K` | 3 |

Input fields:
- `ref_asset` (string; required) — Asset ID of the reference image to guide the generation.
- `face_asset` (string or null; default: null) — Asset ID of a face. `SEEDREAM_5_PRO` accepts it as a legacy alias and appends it to `character_assets`.
- `model` (one of: "SEEDREAM_5_PRO"; default: "SEEDREAM_5_PRO") — Generation model.
- `positive_prompt` (string; default: "") — Text describing what to generate.
- `batch_size` (integer; default: 4) — Number of images to generate, 1-10. Default 4.
- `strength` (number; default: 1.0) — How strongly the reference image constrains the result, 0.0-1.0 (higher sticks closer to the reference).
- `keep_pose` (boolean; default: false) — `SEEDREAM_5_PRO`: edit the reference in place, keeping its pose, body, outfit, lighting and background and swapping in the character's identity (face, hair, skin tone); the output keeps the reference's aspect. Default false.
- `body_asset` (string or null; default: null) — Legacy alias accepted only by `SEEDREAM_5_PRO`, appended to `character_assets` after `face_asset`. Rejected by the other models rather than ignored.
- `character_assets` (array[string] or null; required) — Asset ID(s) of the character photo(s), 1-4. Required by `SEEDREAM_5_PRO`; the legacy `face_asset` and `body_asset` fields are folded into this list when sent.
- `ratio` (one of: "16:9" | "1:1" | "1:2" | "1:3" | "21:9" | "2:1" | "2:3" | "3:1" | "3:2" | "3:4" | "4:3" | "4:5" | "5:4" | "9:16" | "9:21"; default: null) — Output aspect ratio for `SEEDREAM_5_PRO`: 1:1, 1:2, 2:1, 1:3, 3:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 9:21 or 21:9. Defaults to the reference's own aspect; ignored with `keep_pose` and `CHARACTER_SWAP`.
- `tier` (one of: "1K" | "2K"; default: "1K") — Output resolution tier for `SEEDREAM_5_PRO` / `CHARACTER_SWAP` / `KREA_2`: `1K` (default) or `2K`.

**Outputs:** `image_assets` (array[string])

### photoshoot

Run a consistent photoshoot of one character from a photo of the face and a photo of the body (without a face): each shot is generated from scratch, so poses come out organically different between frames — unlike `image_editor`, which keeps the source composition. The tool feeds the references through prepared prompt presets and returns a batch of images. Presets are grouped by category, so you can produce a set in a given style or action. Strength: reproducible, satisfying results with no manual prompting — at the cost of fine-grained control.

**Price:** 3 credits per image (multiplied by `image_count`).

Input fields:
- `face_ref` (string; required) — Asset ID of the face reference (upload via POST /assets).
- `body_ref` (string; required) — Asset ID of the body/pose reference (upload via POST /assets).
- `prompt` (string; default: "") — Free-text description of the shot (scene, outfit, lighting). Provide `prompt` for a custom shot, or `category_id` to use a curated category instead. If both are given, `category_id` takes precedence.
- `category_id` (string or null; default: null) — ID of a curated photoshoot category (see GET /photoshoot-categories). When set, the shot's prompts are taken from the category and `image_count` images are produced; it takes precedence over `prompt`.
- `image_count` (integer; default: 1) — Total number of images to generate (min 1). Drives how many shots are produced from the chosen `category_id` (or how many times `prompt` is repeated).
- `ratio` (one of: "16:9" | "1:1" | "1:2" | "1:3" | "21:9" | "2:1" | "2:3" | "3:1" | "3:2" | "3:4" | "4:3" | "4:5" | "5:4" | "9:16" | "9:21"; default: "1:1") — Aspect ratio of the output image: 1:1, 1:2, 2:1, 1:3, 3:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 9:21 or 21:9 (default 1:1, square). Takes precedence over `width`/`height` when they describe a different shape.
- `width` (integer; default: 1024) — Output width in pixels (default 1024; clamped to 512-4096).
- `height` (integer; default: 1024) — Output height in pixels (default 1024; clamped to 512-4096).
- `number_of_images` (integer; default: 1) — Parallel images per shot (default 1); leave at 1 — use `image_count` to control the total.
- `rewrite_prompt` (boolean; default: false) — Let the provider rewrite/expand `prompt` before generation (default `false`). Leave off for NSFW prompts — the rewriter can corrupt them and produce an image unrelated to what was asked.

**Outputs:** `image_assets` (array[string])

### facegen

Generate a brand-new face from structured attributes: gender, age, ethnicity, body type, eye/hair/beard colour, hairstyle, beard and makeup. No reference image; returns a single square image per request. Strength: full parametric control over the appearance — use it to create a fresh persona to reuse in other tools. For each attribute the accepted values are listed in that field's enum. Niche — used occasionally.

**Price** (credits):

| `tier` | Credits |
|---|---|
| `1K` | 2 |
| `2K` | 3 |

Input fields:
- `gender` (one of: "Female" | "Male"; required) — Gender of the face.
- `age` (one of: "18-25" | "26-35" | "36-45" | "46-55" | "56-65" | "66-75" | "75-85" | "85+"; required) — Apparent age band.
- `origin` (one of: "Central American" | "Central Asian" | "East Asian" | "European" | "Middle Eastern" | "North African" | "North American" | "Oceanian / Pacific Islander" | "South American" | "South Asian" | "Southeast Asian"; required) — Ethnic origin / look.
- `body_type` (one of: "Chubby" | "Curvy" | "Fit" | "Muscular" | "Normal" | "Slim"; default: null) — Body type.
- `eye_color` (one of: "Albino" | "Amber" | "Blue" | "Brown" | "Gray" | "Green" | "Hazel" | "Heterochromia" | "Red" | "Violet"; default: null) — Eye colour.
- `hair_color` (one of: "Black" | "Blonde" | "Blue" | "Brunette" | "Gray" | "Green" | "Honey" | "Ombre" | "Pink" | "Platinum" | "Red" | "Salt and Pepper" | "Violet"; default: null) — Hair colour.
- `hair_type` (one of: "Bald" | "Coily" | "Curly" | "Frizzy" | "Silky" | "Straight" | "Thick" | "Thin" | "Wavy"; default: null) — Hair type, e.g. straight/wavy/curly.
- `hair_style` (one of: "Afro" | "Bob" | "Bowl" | "Braids" | "Bun" | "Buzzcut" | "Caesar" | "Mohawk" | "Pigtails" | "Pixie" | "Ponytail" | "Shag" | "Undercut" | "Updo"; default: null) — Hair style.
- `beard` (one of: "Anchor Beard" | "Balbo Beard" | "Chevron Mustache" | "Chinstrap Beard" | "Circle Beard" | "Corporate Beard" | "Ducktail Beard" | "Friendly Mutton Chops" | "Full Beard" | "Garibaldi Beard" | "Goatee" | "Handlebar Mustache" | "Horseshoe Mustache" | "Imperial Mustache" | "Mutton Chops" | "Pencil Mustache" | "Soul Patch" | "Stubble Beard" | "Van Dyke Beard" | "Zappa Mustache"; default: null) — Beard style.
- `beard_color` (one of: "Black" | "Blonde" | "Blue" | "Brunette" | "Gray" | "Green" | "Honey" | "Ombre" | "Pink" | "Platinum" | "Red" | "Salt and Pepper" | "Violet"; default: null) — Beard colour.
- `makeup` (one of: "Anime Makeup" | "Artistic Makeup" | "Avant-garde Makeup" | "Bohemian Makeup" | "Boho Makeup" | "Classic Makeup" | "Cut Crease Makeup" | "Dewy Makeup" | "Edgy Makeup" | "Festival Makeup" | "Glam Makeup" | "Glowy Makeup" | "Golden Makeup" | "Monochromatic Makeup" | "Natural Makeup" | "Party Makeup" | "Retro Makeup" | "Sunset Eye Makeup" | "Vintage Makeup" | "Watercolor Makeup"; default: null) — Makeup style.
- `tier` (one of: "1K" | "2K"; default: "2K") — Output resolution tier: `1K` (~1 MP) or `2K` (~4 MP). Default `2K`.

**Outputs:** `image_assets` (array[string])

### carousel

Bring an image and get the same subject from different camera angles (up to 10). Use it for social-media carousels and a "3D"/product overview of an object or character. Niche — used occasionally.

**Price** (credits per image, multiplied by `number_of_images`):

| `tier` | Credits |
|---|---|
| `1K` | 2 |
| `2K` | 3 |

Input fields:
- `asset_ref` (string; required) — Asset ID of the subject/reference image.
- `ratio` (one of: "16:9" | "1:1" | "21:9" | "2:3" | "3:2" | "3:4" | "4:3" | "9:16"; default: "1:1") — Aspect ratio of the outputs (e.g. 1:1, 16:9, 9:16).
- `tier` (one of: "1K" | "2K"; default: "2K") — Output resolution tier: `1K` (~1 MP) or `2K` (~4 MP). Default `2K`.
- `width` (integer; default: 1024) — Ignored: the output size is derived from `ratio` and `tier`.
- `height` (integer; default: 1024) — Ignored: the output size is derived from `ratio` and `tier`.
- `number_of_images` (integer; default: 4) — Number of angle variations to generate, 1-10. Default 4.

**Outputs:** `image_assets` (array[string])

### videogen

Animate a photo into a video (image-to-video). Cost depends on the model, duration (5-15 s, up to 30 s on the `wan@3.0` line) and resolution (480p-1080p). Supports prompt enhancement, fixed camera, LoRAs and optional audio. Quick guide: general content (best price/quality) — Seedance; NSFW content — `wan@2.7-nsfw` or `wan@2.2-lora`; tasteful content with complex actions — Kling (censored).

**Wan** — the `wan@2.7` and `wan@3.0` lines understand prompts best and animate a first frame well (1080p, good physics, up to 5 references):
- `wan@3.0` — Newest Wan; native audio, first frame (+ optional last frame) or references, 480p/720p/1080p and clips up to 30 s. No `21:9`. A run takes 15-55 minutes (hours at 1080p x 30 s), so poll instead of waiting on it.
- `wan@3.0-nsfw` *(trusted)* — The same model with content inspection lifted; identical fields, price and timings.
- `wan@3.0-prime` — The same model on a faster queue: identical fields and results, about 40% quicker, roughly 10% dearer. Pick it when the wait matters more than the price.
- `wan@3.0-prime-nsfw` *(trusted)* — The prime queue with content inspection lifted.
- `wan@2.7` — Previous line; top prompt understanding and first-frame animation, and much faster than the `wan@3.0` line.
- `wan@2.7-nsfw` *(trusted)* — Wan 2.7 for NSFW; the best choice when you have a first frame (or a frame with an action) to animate.
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
- `seedance_2_5` *(trusted)* — Same shape as Seedance 2.0 with wider limits: up to 30 s, 1080p, 30 images + 10 videos + 10 audios of references (≤30 s of video in total), and a `task_type` that says whether the references drive a new clip, an edit of one of them, or its continuation.

**Grok:**
- `grok@4.1` — Censored; animates a first frame, top image-to-video, always with native audio.

**MiniMax** — censored, native audio, 480p/720p/1080p and 5-15 s. Trusted accounts have the provider-side filter lifted; the model still refuses explicit briefs itself, and a refused run is failed and refunded rather than billed:
- `minimax@3.0` — Animates a first frame, a last frame or both, or drives the whole clip from references (`ref_images`/`ref_videos`/`ref_audios`, up to 12 files, addressed in the prompt as `[Image N]`/`[Video N]`/`[Audio N]`).
- `minimax@3.0-turbo` — Faster and half the price; frames only, no reference mode.

Model capabilities differ — read the `model`, `last_frame` and `resolution` fields for which model supports what.

Models marked *(trusted)* unlock NSFW behaviour only for trusted accounts (or accounts with an NSFW content policy).

**Price** (credits):

| `model` | `duration` | `generate_audio` | Credits (480p) | Credits (720p) | Credits (1080p) |
|---|---|---|---|---|---|
| `grok@4.1` | `6` | *any* | 12 | 18 | 18 |
| `grok@4.1` | `10` | *any* | 20 | 30 | 30 |
| `kling@1.6`, `kling@2.1`, `kling@2.5` | `5`, `6`, `8`, `12`, `15` | *any* | 7 | 7 | 7 |
| `kling@1.6`, `kling@2.1`, `kling@2.5` | `10` | *any* | 13 | 13 | 13 |
| `kling@2.6` | `5` | `true` | 10 | 10 | 10 |
| `kling@2.6` | `5` | `false` | 5 | 5 | 5 |
| `kling@2.6` | `10` | `true` | 20 | 20 | 20 |
| `kling@2.6` | `10` | `false` | 10 | 10 | 10 |
| `minimax@3.0` | `5` | *any* | 7 | 10 | 20 |
| `minimax@3.0` | `6` | *any* | 8 | 12 | 24 |
| `minimax@3.0` | `8` | *any* | 10 | 16 | 32 |
| `minimax@3.0` | `10` | *any* | 13 | 20 | 40 |
| `minimax@3.0` | `12` | *any* | 15 | 24 | 48 |
| `minimax@3.0` | `15` | *any* | 19 | 30 | 60 |
| `minimax@3.0-turbo` | `5` | *any* | 4 | 5 | 10 |
| `minimax@3.0-turbo` | `6` | *any* | 4 | 6 | 12 |
| `minimax@3.0-turbo` | `8` | *any* | 5 | 8 | 16 |
| `minimax@3.0-turbo` | `10` | *any* | 7 | 10 | 20 |
| `minimax@3.0-turbo` | `12` | *any* | 8 | 12 | 24 |
| `minimax@3.0-turbo` | `15` | *any* | 10 | 15 | 30 |
| `seedance_2_0` | `5` | *any* | 7 | 16 | 35 |
| `seedance_2_0` | `6` | *any* | 9 | 19 | 41 |
| `seedance_2_0` | `8` | *any* | 11 | 25 | 55 |
| `seedance_2_0` | `10` | *any* | 14 | 31 | 69 |
| `seedance_2_0` | `12` | *any* | 17 | 37 | 82 |
| `seedance_2_0` | `15` | *any* | 21 | 46 | 103 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `5` | *any* | 6 | 13 | 28 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `6` | *any* | 7 | 15 | 33 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `8` | *any* | 9 | 20 | 44 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `10` | *any* | 11 | 25 | 55 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `12` | *any* | 13 | 30 | 66 |
| `seedance_2_0_fast`, `seedance_2_0_mini` | `15` | *any* | 17 | 37 | 82 |
| `seedance_2_5` | `5` | *any* | 13 | 29 | 100 |
| `seedance_2_5` | `10` | *any* | 26 | 58 | 199 |
| `seedance_2_5` | `15` | *any* | 39 | 87 | 298 |
| `seedance_2_5` | `20` | *any* | 52 | 116 | 397 |
| `seedance_2_5` | `25` | *any* | 65 | 145 | 496 |
| `seedance_2_5` | `30` | *any* | 78 | 174 | 595 |
| `seedance_pro` | `5` | *any* | 4 | 8 | 15 |
| `seedance_pro`, `seedance_pro_fast` | `6`, `8`, `12`, `15` | *any* | 7 | 7 | 7 |
| `seedance_pro` | `10` | *any* | 8 | 15 | 30 |
| `seedance_pro_fast` | `5` | *any* | 2 | 4 | 7 |
| `seedance_pro_fast` | `10` | *any* | 4 | 8 | 13 |
| `seedance_v1_5_pro` | `5` | `true` | 8 | 8 | 16 |
| `seedance_v1_5_pro` | `5` | `false` | 4 | 4 | 8 |
| `seedance_v1_5_pro` | `6`, `8`, `15` | `true` | 8 | 8 | 8 |
| `seedance_v1_5_pro` | `6`, `8`, `15` | `false` | 4 | 4 | 4 |
| `seedance_v1_5_pro` | `10` | `true` | 8 | 16 | 32 |
| `seedance_v1_5_pro` | `10` | `false` | 4 | 8 | 16 |
| `seedance_v1_5_pro` | `12` | `true` | 8 | 20 | 40 |
| `seedance_v1_5_pro` | `12` | `false` | 4 | 10 | 20 |
| `wan@2.2`, `wan@2.2-lora` | `5` | *any* | 10 | 10 | 10 |
| `wan@2.2` | `8` | *any* | 13 | 13 | 13 |
| `wan@2.2-lora` | `8` | *any* | 15 | 15 | 15 |
| `wan@2.5`, `wan@2.7`, `wan@2.7-lora` | `5` | *any* | 5 | 10 | 15 |
| `wan@2.5` | `6` | *any* | 6 | 12 | 18 |
| `wan@2.5` | `8` | *any* | 8 | 16 | 24 |
| `wan@2.5`, `wan@2.7`, `wan@2.7-lora` | `10` | *any* | 10 | 20 | 30 |
| `wan@2.5` | `12` | *any* | 12 | 24 | 36 |
| `wan@2.5`, `wan@2.7`, `wan@2.7-lora` | `15` | *any* | 15 | 30 | 45 |
| `wan@2.6` | `5` | *any* | 10 | 10 | 15 |
| `wan@2.6` | `10` | *any* | 20 | 20 | 30 |
| `wan@2.6` | `15` | *any* | 30 | 30 | 45 |
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
| `wan@2.7-nsfw` | `5` | *any* | 10 | 13 | 17 |
| `wan@2.7-nsfw` | `10` | *any* | 20 | 26 | 34 |
| `wan@2.7-nsfw` | `15` | *any* | 30 | 39 | 51 |
| `wan@3.0`, `wan@3.0-nsfw` | `5` | *any* | 12 | 24 | 40 |
| `wan@3.0`, `wan@3.0-nsfw` | `6` | *any* | 15 | 29 | 48 |
| `wan@3.0`, `wan@3.0-nsfw` | `8` | *any* | 20 | 39 | 64 |
| `wan@3.0`, `wan@3.0-nsfw` | `10` | *any* | 24 | 48 | 80 |
| `wan@3.0`, `wan@3.0-nsfw` | `12` | *any* | 29 | 58 | 96 |
| `wan@3.0`, `wan@3.0-nsfw` | `15` | *any* | 36 | 72 | 120 |
| `wan@3.0`, `wan@3.0-nsfw` | `20` | *any* | 48 | 96 | 160 |
| `wan@3.0`, `wan@3.0-nsfw` | `25` | *any* | 60 | 120 | 200 |
| `wan@3.0`, `wan@3.0-nsfw` | `30` | *any* | 72 | 144 | 240 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `5` | *any* | 14 | 27 | 45 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `6` | *any* | 16 | 32 | 54 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `8` | *any* | 21 | 43 | 72 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `10` | *any* | 27 | 53 | 90 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `12` | *any* | 32 | 64 | 108 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `15` | *any* | 40 | 80 | 135 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `20` | *any* | 53 | 106 | 180 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `25` | *any* | 66 | 133 | 225 |
| `wan@3.0-prime`, `wan@3.0-prime-nsfw` | `30` | *any* | 79 | 159 | 270 |

Input fields:
- `ref_asset` (string or null; default: null) — Asset ID of the starting image to animate (image-to-video). Required for all models except Seedance 2.0 and `seedance_2_5` in multimodal mode, where the images come from `ref_images` and `ref_asset` is optional (on `seedance_2_5` reference audio alone is enough), and `minimax@3.0*`, which also runs from a `last_frame` alone.
- `model` (one of: "grok@4.1" | "kling@1.6" | "kling@2.1" | "kling@2.5" | "kling@2.6" | "minimax@3.0" | "minimax@3.0-turbo" | "seedance_2_0" | "seedance_2_0_fast" | "seedance_2_0_mini" | "seedance_2_5" | "seedance_pro" | "seedance_pro_fast" | "seedance_v1_5_pro" | "wan@2.2" | "wan@2.2-lora" | "wan@2.5" | "wan@2.6" | "wan@2.6-flash" | "wan@2.7" | "wan@2.7-lora" | "wan@2.7-nsfw" | "wan@3.0" | "wan@3.0-nsfw" | "wan@3.0-prime" | "wan@3.0-prime-nsfw"; default: "wan@2.2") — Video model. Kling: `kling@1.6`, `kling@2.1` (supports last_frame), `kling@2.5`, `kling@2.6`. WAN: `wan@2.2` (image-to-video, no last_frame), `wan@2.2-lora` (same as wan@2.2 but accepts `loras`), `wan@2.5`, `wan@2.6`, `wan@2.6-flash` (faster), `wan@2.7`, `wan@2.7-nsfw`, `wan@3.0`, `wan@3.0-nsfw`, `wan@3.0-prime` and `wan@3.0-prime-nsfw` (these support last_frame and a reference mode; the `-prime` pair runs the same model on a faster, slightly dearer queue). Seedance: `seedance_pro_fast`, `seedance_pro` (supports last_frame), `seedance_v1_5_pro` (supports last_frame), `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini` (support last_frame and a multimodal reference mode), `seedance_2_5` *(trusted)* (the same, with wider limits, 1080p, up to 30 s and a `task_type`). Grok: `grok@4.1`. MiniMax: `minimax@3.0` (supports last_frame and a reference mode), `minimax@3.0-turbo` (supports last_frame). Default `wan@2.2`.
- `last_frame` (string or null; default: null) — Asset ID of the target final frame: the video interpolates from `ref_asset` to this frame. Only honoured by models that support it (`kling@2.1`, `seedance_pro`, `seedance_v1_5_pro`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5`, `wan@3.0*`, `minimax@3.0*`); the older WAN models (incl. wan@2.2 and wan@2.7) do not support a last frame. `minimax@3.0*` also takes it without `ref_asset`, for an end-frame-only run.
- `audio_asset` (string or null; default: null) — Asset ID of an audio track to drive the video, for models that support audio input.
- `prompt` (string; default: "") — Text describing the desired motion and scene. Seedance 2.0, `seedance_2_5`, `wan@3.0*` and `minimax@3.0*` address the media as `[Image N]`, `[Video N]`, `[Audio N]`; the short `[img1]`, `[vid1]`, `[audio1]` the app inserts are accepted too and mean `[Image 1]`, `[Video 1]`, `[Audio 1]`.
- `duration` (one of: -1 | 5 | 6 | 8 | 10 | 12 | 15 | 16 | 18 | 20 | 22 | 24 | 25 | 26 | 28 | 30; default: 5) — Clip length in seconds; valid values are model-dependent: `kling@2.6` → 5 or 10; `wan@2.2`, `wan@2.2-lora` → 5 or 8; `wan@2.6`, `wan@2.7`, `wan@2.7-lora`, `wan@2.7-nsfw` → 5, 10 or 15; `grok@4.1` → 6 or 10; `seedance_2_5` → 5, 10, 15, 20, 25 or 30; `wan@3.0`, `wan@3.0-nsfw`, `wan@3.0-prime`, `wan@3.0-prime-nsfw` → 5, 6, 8, 10, 12, 15, 20, 25 or 30; everything else → 5, 6, 8, 10, 12 or 15. `-1` is not a length: it is `seedance_2_5` with a `task_type` of `edit`, where the result is exactly as long as the source, and no other model or task type accepts it. Any listed value is also accepted under `edit` and ignored. Default 5.
- `negative_prompt` (string; default: "") — Text describing what to avoid in the video.
- `resolution` (one of: "1080p" | "480p" | "720p"; default: "720p") — Output resolution. Most models accept `720p` and `1080p`. `480p` is NOT supported by `wan@2.6`, `wan@2.6-flash`, `wan@2.7`, `wan@2.7-nsfw` or `seedance_v1_5_pro` (use 720p or 1080p for those). `wan@2.2`, `grok@4.1`, `seedance_2_0`, `seedance_2_0_fast` and `seedance_2_0_mini` accept only `480p` or `720p`. `wan@3.0*`, `minimax@3.0*` and `seedance_2_5` accept all three. Default `720p`, except `wan@3.0*`, which defaults to `480p`.
- `ratio` (one of: "16:9" | "1:1" | "21:9" | "3:4" | "4:3" | "9:16" | "adaptive"; default: "adaptive") — Aspect ratio: `adaptive`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`. Only the Seedance 2.0 models, `seedance_2_5`, `wan@3.0*` and `minimax@3.0` in its reference mode honour this, and `wan@3.0*` rejects `21:9`. On `seedance_2_5` it is ignored and forced to `adaptive` whenever the run has a first frame, or a `task_type` of `edit` or `extend`. Default `adaptive`.
- `seed` (integer or null; default: null) — Seed for reproducibility (Seedance 2.0 models, `seedance_2_5`, `wan@3.0*` and `minimax@3.0*`). Default random.
- `generate_audio` (boolean; default: true) — Generate an audio track too, for models that support it. `minimax@3.0*` always returns one and cannot be silenced — the switch does not reach it. Default true.
- `camera_fixed` (boolean; default: false) — Keep the camera fixed instead of letting it move. Default false.
- `prompt_extend` (boolean; default: false) — Let the model auto-expand and enhance your prompt. On `minimax@3.0*` it picks the slower, richer rewrite (~30 s) over the one-second default. Default false.
- `loras` (object or null; default: null) — LoRA styles to apply, as a map of LoRA id to a scale-settings object (`{high_scale?, low_scale?}`, both optional — not a bare number). Only `wan@2.2-lora` uses this; browse compatible ids via GET /loras?model=wan@2.2.
- `ref_images` (array[string] or null; default: null) — Seedance 2.0, `seedance_2_5`, `wan@3.0*` and `minimax@3.0` reference mode: extra reference image asset IDs (up to 8 in addition to `ref_asset`; `seedance_2_5` takes 30 images counting `ref_asset`). Reference them in the prompt as `[Image N]`.
- `ref_videos` (array[string] or null; default: null) — Seedance 2.0 and `minimax@3.0` multimodal mode: reference video asset IDs (up to 3, ≤15 s total; `seedance_2_5` takes up to 10, ≤30 s total and 2-30 s each). Reference them in the prompt as `[Video N]`. This is the video-to-video path. `wan@3.0*` takes video references only in the video2video tool.
- `ref_audios` (array[string] or null; default: null) — Seedance 2.0, `seedance_2_5`, `wan@3.0*` and `minimax@3.0` reference mode: reference audio asset IDs (up to 3, ≤15 s each; `seedance_2_5` takes up to 10, ≤30 s each, and accepts audio with no image or video beside it). Reference them in the prompt as `[Audio N]` (`minimax@3.0` also needs a reference image or video alongside).
- `task_type` (one of: "auto" | "edit" | "extend" | "reference"; default: null) — `seedance_2_5` with references only: what the model does with the reference videos. `auto` (default) lets the model decide from the wording of the prompt — which can silently turn the run into an edit and refuse the requested length. `reference` drives a NEW clip from the references. `edit` changes one reference video in place (exactly one video; the result is as long as the source and is billed for twice its length). `extend` continues one reference video by `duration` more seconds. `edit` and `extend` force `ratio` to `adaptive`, and `edit` takes `duration` as `-1` and ignores any other value. Omit it for frame runs and for every other model.

**Outputs:** `video_asset` (string), `audio_stripped` (boolean)

### image_editor

Edit and composite existing images by prompt — the main, most flexible image tool. Bring references, edit and combine them; bring your character and dress them from a reference photo; keep a product or object **exactly** (fabric, pattern, shape) while changing the scene. It offers both SFW and NSFW models, plus LoRA presets that extend NSFW capability. You are limited mainly by your imagination. Edits inherit the source composition (pose, framing), so for a photoshoot-style series of varied organic poses of one character use `photoshoot` instead.

**Models:**
- `GENERAL_NSFW` *(default, trusted)* — Universal default, uncensored, good facial likeness; general NSFW edits such as outfit or pose changes. Older model — occasional limb artifacts.
- `NANO_BANANA` — High realism and the most precise prompt-driven edits; good at edits involving in-image text. Heavily censored (no NSFW); weaker likeness.
- `NANO_BANANA_2_1` — Google Nano Banana 2.1: precise edits and composites from up to 14 references (the first is the base image), consistent characters and legible in-image text, up to 4K. Censored. The only editor with the extra aspect ratios 4:1, 1:4, 8:1 and 1:8, `thinking_level` and `web_search`; the result keeps the provider's size. Credits per image for `tier` 1K / 2K / 4K: 2 / 2 / 4, with `thinking_level` `high` 2 / 3 / 5, independent of the number of references.
- `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` — OpenAI GPT Image 2.5: controlled edits that keep the person, product and layout, exact in-image copy, up to 16 references (the first is the base image), up to 4K (`4K` is beta). Flare is faster, Sunburst is slower and more precise in edits; same price. Censored. `quality`, `transparent_background` and `mask_asset`; without `ratio` the result takes the standard ratio closest to the first image, uncropped. Credits per image for `tier` 1K / 2K / 4K with up to 4 references: `quality` `low` 2 / 2 / 2, `medium` 2 / 3 / 3, `high` 3 / 5 / 6; each started 3 references above 4 add 1 credit (5-7: +1, 8-10: +2, 11-13: +3, 14-16: +4).
- `IDEOGRAM_4_5` — Ideogram 4.5: precise edits that leave untouched areas as they were, the best at fixing text and logos, up to 5 images (the first is edited, the rest only guide). Censored. `quality`, `edit_precision` and `mask_asset`; the result keeps the first image's size, so `ratio` and `tier` are ignored. Credits per image for `quality` `low` / `medium` / `high`: 1 / 2 / 6.
- `QWEN_IMAGE` / `QWEN_IMAGE_PRO` — Aesthetic, good likeness, few artifacts; Pro adds realism. Uncensored; transforms your NSFW references rather than creating full NSFW content from scratch.
- `SEEDREAM_5` — Newer than the default: better prompt understanding, stronger stylization, better likeness, fewer artifacts. Uncensored; transforms NSFW references.
- `SEEDREAM_5_PRO` — The newest Seedream flagship editor: up to 10 reference images (their order is preserved), all 15 aspect ratios and a `tier` resolution switch (`1K` = 2 credits, `2K` = 3 credits, independent of the number of references). Uncensored; transforms NSFW references.
- `WAN_2_7_IMAGE` / `WAN_2_7_IMAGE_PRO` — Aesthetic bodies and composition, few artifacts, precise editing; Pro = higher quality. Uncensored; transforms NSFW references. Weaker at in-image text.
- `FLUX_KLEIN_NSFW` *(trusted)* — Local flagship for full NSFW with references: it knows anatomy and accepts a face reference. Slightly lower quality, occasional artifacts.
- `FLUX_KLEIN_LORA` *(trusted)* — LoRA presets that extend NSFW capability (including clothing-removal presets) and style templates; pass `loras` or `lora_id` (browse via GET /templates).

Models marked *(trusted)* unlock NSFW behaviour only for trusted accounts (or accounts with an NSFW content policy).

**Price** (credits per image, multiplied by `number_of_images`):

| `model` | `tier` | `thinking_level` | `quality` | Credits |
|---|---|---|---|---|
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
| `NANO_BANANA_2_1` | `1K` | *any* | `medium` | 2 |
| `NANO_BANANA_2_1` | `2K` | `high` | `medium` | 3 |
| `NANO_BANANA_2_1` | `2K` | `minimal` | `medium` | 2 |
| `NANO_BANANA_2_1` | `4K` | `high` | `medium` | 5 |
| `NANO_BANANA_2_1` | `4K` | `minimal` | `medium` | 4 |
| `SEEDREAM_5_PRO` | `1K` | `minimal` | `medium` | 2 |
| `SEEDREAM_5_PRO` | `2K` | `minimal` | `medium` | 3 |

`GPT_IMAGE_2_5_FLARE` and `GPT_IMAGE_2_5_SUNBURST` add 1 credit per image for each started 3 `image_assets` above 4 (5-7: +1, 8-10: +2, 11-13: +3, 14-16: +4; at most 16 images); a `mask_asset` is free, and in `batch_mode` each image is billed alone.

Input fields:
- `image_assets` (array[string]; required) — Asset ID(s) of the source image(s). Pass a single id to edit one image, or several (as an array) to combine them into one result (unless `batch_mode` is set). When `ratio` is not set, the combined result inherits the first image's geometry — put the scene or base image first and face/detail references after it (in `batch_mode` each image keeps its own geometry).
- `prompt` (string; required) — Instruction describing the edit to apply.
- `model` (one of: "FLUX_KLEIN_LORA" | "FLUX_KLEIN_NSFW" | "GENERAL_NSFW" | "GPT_IMAGE_2_5_FLARE" | "GPT_IMAGE_2_5_SUNBURST" | "IDEOGRAM_4_5" | "NANO_BANANA" | "NANO_BANANA_2_1" | "QWEN_IMAGE" | "QWEN_IMAGE_PRO" | "SEEDREAM_4_5" | "SEEDREAM_5" | "SEEDREAM_5_PRO" | "WAN_2_7_IMAGE" | "WAN_2_7_IMAGE_PRO"; default: "GENERAL_NSFW") — Editing model. `GENERAL_NSFW` — general-purpose editor (default, allows NSFW); `SEEDREAM_4_5` — the same general-purpose editor under another name; `NANO_BANANA` — Google Nano Banana; `QWEN_IMAGE` / `QWEN_IMAGE_PRO` — Qwen editors (Pro = higher quality); `SEEDREAM_5` — Seedream; `SEEDREAM_5_PRO` — the newest Seedream flagship (up to 10 references); `FLUX_KLEIN_NSFW` — Flux Klein editor; `FLUX_KLEIN_LORA` — Flux Klein with a style template (requires `loras` or `lora_id`); `WAN_2_7_IMAGE` / `WAN_2_7_IMAGE_PRO` — WAN 2.7 editors (Pro = higher quality); `NANO_BANANA_2_1` — Google Nano Banana 2.1 (up to 14 references and the top tier); `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` — OpenAI GPT Image 2.5 (up to 16 references and the top tier, Sunburst is more precise in edits); `IDEOGRAM_4_5` — Ideogram 4.5 (best lettering, up to 5 images).
- `ratio` (one of: "16:9" | "1:1" | "1:2" | "1:3" | "1:4" | "1:8" | "21:9" | "2:1" | "2:3" | "3:1" | "3:2" | "3:4" | "4:1" | "4:3" | "4:5" | "5:4" | "8:1" | "9:16" | "9:21"; default: null) — Aspect ratio (e.g. 1:1, 16:9, 9:16). Overrides width/height when set. When omitted the ratio of the first source image is used and the result is centre-cropped to it, so set `ratio` explicitly whenever the output needs a specific framing. `SEEDREAM_5_PRO` supports 15 ratios (adds 1:2, 2:1, 1:3, 3:1, 4:5, 5:4 and 9:21). `NANO_BANANA_2_1` also takes the four extreme banner ratios and, when the ratio is omitted, follows the first image uncropped. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` take the 8 standard ratios and, when it is omitted, use the standard ratio closest to the first image, uncropped. `IDEOGRAM_4_5` ignores it: the result keeps the first image's size.
- `tier` (one of: "1K" | "2K" | "4K"; default: "2K") — Output resolution tier: `1K`, `2K` (default) or `4K`. `SEEDREAM_5_PRO` takes `1K` or `2K`; models without a tier ignore it. `NANO_BANANA_2_1` also takes the top tier. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take the top tier, in beta. `IDEOGRAM_4_5` takes `1K` or `2K`, at the same price. Other models reject `4K`.
- `thinking_level` (one of: "high" | "minimal"; default: "minimal") — Default `minimal` (fast); ignored by other models. `NANO_BANANA_2_1` also takes the longer-reasoning level for a more accurate result, +1 credit.
- `web_search` (boolean; default: false) — Default `false`; ignored by other models. `NANO_BANANA_2_1` can check Google Search for current facts, places and logos at the same price.
- `quality` (one of: "high" | "low" | "medium"; default: null) — Default `medium`, the level every model takes. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` also take a cheaper draft level and a top level that adds detail, latency and credits. `IDEOGRAM_4_5` takes `low` / `medium` / `high` too.
- `transparent_background` (boolean; default: false) — Default `false`. `true` works on `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` only: they return a PNG with a transparent background (stickers, logos, product cut-outs) at the same price.
- `width` (integer; default: 1024) — Output width in pixels (default 1024). Used when `ratio` is not set.
- `height` (integer; default: 1024) — Output height in pixels (default 1024). Used when `ratio` is not set.
- `batch_mode` (boolean; default: false) — When several `image_assets` are given, edit each one separately (one result per image) instead of combining them into a single image. Default false.
- `number_of_images` (integer; default: 1) — How many images to generate (default 1).
- `sequential_generation` (boolean; default: false) — Generate the requested images one after another, each conditioned on the previous result (for consistent, story-like sequences) instead of independently. Default false.
- `lora_id` (string or null; default: null) — Deprecated: use `loras` instead. ID of a LoRA style template to apply (when `model=FLUX_KLEIN_LORA`). Browse available templates and their ids via GET /templates.
- `loras` (object or null; default: null) — LoRA style templates to apply when `model=FLUX_KLEIN_LORA`, as a map of LoRA id to a scale-settings object (`{high_scale?, low_scale?}`, both optional — not a bare number). Browse ids via GET /templates. All LoRAs must share the same model.
- `rewrite_prompt` (boolean; default: false) — For `SEEDREAM_5_PRO` only: let the provider rewrite/expand the prompt before generation (default `false`). Leave off for NSFW prompts — the rewriter can corrupt them and produce an image unrelated to what was asked.
- `mask_asset` (string or null; default: null) — For `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` / `IDEOGRAM_4_5` only: asset ID of a PNG mask the size of the first image. On a mask with transparency every painted pixel, any colour, marks the area to edit and transparent pixels are kept; on an opaque mask white marks the area and black keeps it. The mask does not change the price, takes one image slot and is not allowed with `batch_mode`. `GPT_IMAGE_2_5_FLARE` / `GPT_IMAGE_2_5_SUNBURST` read it as guidance: the change lands in the area, the border is approximate and pixels outside may shift slightly; at most 15 `image_assets`. `IDEOGRAM_4_5` edits only the area and needs part of the image left unpainted; at most 4 `image_assets`.
- `edit_precision` (one of: "high" | "regular"; default: null) — Default `regular`. `IDEOGRAM_4_5` takes `high` for a precise edit: it changes only what the prompt asks and restores every other pixel, at the same price.

**Outputs:** `image_assets` (array[string])

### collaber

Put two characters together in one frame: bring two reference subjects and an optional background/location photo; the tool combines them into a single scene (1-4 images). Strength: keeps both characters' likeness — a convenient preset for collabs and duets.

**Price** (credits per image, multiplied by `number_of_images`):

| `model` | `tier` | Credits |
|---|---|---|
| `GENERAL` | *any* | 1 |
| `SEEDREAM_5_PRO` | `1K` | 2 |
| `SEEDREAM_5_PRO` | `2K` | 3 |

Input fields:
- `asset_image_1` (string; required) — Asset ID of the first persona/subject.
- `asset_image_2` (string; required) — Asset ID of the second persona/subject.
- `location_asset` (string or null; default: null) — Optional asset ID of a location/background reference for the scene.
- `prompt` (string or null; default: null) — What the two subjects are doing together and the scene to place them in.
- `model` (one of: "GENERAL" | "SEEDREAM_5_PRO"; default: "GENERAL") — Generation model. `GENERAL` *(default)* — legacy Bytedance combiner, 8 aspect ratios. `SEEDREAM_5_PRO` — newest Seedream flagship: all 15 aspect ratios and a `tier` resolution switch (`1K` = 2 credits, `2K` = 3 credits).
- `ratio` (one of: "16:9" | "1:1" | "1:2" | "1:3" | "21:9" | "2:1" | "2:3" | "3:1" | "3:2" | "3:4" | "4:3" | "4:5" | "5:4" | "9:16" | "9:21"; default: "1:1") — Aspect ratio of the output (e.g. 1:1, 16:9, 9:16). `SEEDREAM_5_PRO` supports 15 ratios; `GENERAL` supports the original 8.
- `tier` (one of: "1K" | "2K"; default: "2K") — Output resolution tier for `SEEDREAM_5_PRO`: `1K` or `2K` (default `2K`). Ignored by `GENERAL`.
- `width` (integer; default: 1024) — Output width in pixels (used by `GENERAL` when `ratio` is not set; ignored by `SEEDREAM_5_PRO`).
- `height` (integer; default: 1024) — Output height in pixels (used by `GENERAL` when `ratio` is not set; ignored by `SEEDREAM_5_PRO`).
- `number_of_images` (integer; default: 1) — Number of images to generate, 1-4. Default 1.

**Outputs:** `image_assets` (array[string])

### couplegen

Paired photo to video: combine two character photos (Seedream) then animate (wan-2.2 i2v + LoRA)

**Price:** 10 credits.

Input fields:
- `left_asset` (string; required) — Left character photo asset ID
- `right_asset` (string; required) — Right character photo asset ID
- `lora_id` (string or null; default: null) — Deprecated: use `loras` instead. Paired preset (LoRA) ID.
- `loras` (object or null; default: null) — Paired presets (LoRA) to apply, as a map of LoRA id to a scale-settings object (`{high_scale?, low_scale?}`, both optional — not a bare number). The first entry's is_paired/combined_photo_prompt/duration settings are used. All LoRAs must share the same model.
- `duration` (one of: 5 | 8; default: null) — Clip length in seconds: 5 or 8. Defaults to the chosen preset's own duration.

**Outputs:** `video_asset` (string), `combined_image_asset` (string)

### video2video

Transfer motion or replace a character in a video using a reference video or an Instagram/TikTok URL; the original soundtrack can be kept. SFW and NSFW modes. Provide the source as exactly one of `video_asset`, `instagram_url` or `tiktok_url`; the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes read it only from `video_asset` or `ref_videos`, never from a link. Output: one video.

**Modes:**
- `kling_2_6_sfw` — Handles character replacement best (censored); billed per second.
- `replace_sfw` / `replace_nsfw` — Replace the person in the source video with your image's subject; `replace_nsfw` is uncensored.
- `animate_sfw` / `animate_nsfw` — Motion transfer / animation of your image; `animate_nsfw` is uncensored.
- `dreamactor_m2` *(trusted)* — Same character-replacement logic, uncensored.
- `seedance_2_0_sfw` / `seedance_2_0_nsfw` / `seedance_2_0_fast_sfw` / `seedance_2_0_fast_nsfw` / `seedance_2_0_mini_sfw` / `seedance_2_0_mini_nsfw` — Seedance 2.0 generation driven by the source video as a reference: a `prompt` is REQUIRED and refers to the source as `[Video 1]`; `image_asset` is OPTIONAL (added as `[Image 1]`). `duration` 5/6/8/10/12/15; native audio via `generate_audio`. The `_fast` and `_mini` variants are cheaper/faster; all variants support only 480p/720p.
- `seedance_2_5_sfw` / `seedance_2_5_nsfw` *(trusted; the nsfw entry is not in every region)* — The same shape with wider limits: 480p/720p/1080p, `duration` 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 24, 25, 26, 28 or 30 capped so that it plus the source video's length stays within 30 s, up to 30 images and 10 videos of references. `task_type` chooses what the source video is for: a reference for a new clip, a video to edit in place, or one to continue.
- `wan3_0_sfw` / `wan3_0_nsfw` *(the nsfw entry: trusted, not in every region)* — Wan 3.0 generation driven by the source video, same shape as the `seedance_2_0*` modes: `prompt` is REQUIRED and refers to the source as `[Video 1]`, `image_asset` is OPTIONAL (`[Image 1]`). `duration` 5/6/8/10/12/15/20/25/30 — capped so that it plus the source video's length stays within 30 s — resolution `480p`/`720p`/`1080p`, every ratio except `21:9`. Runs for 15-55 minutes (hours at 1080p) — poll, do not wait.
- `wan3_0_prime_sfw` / `wan3_0_prime_nsfw` *(the nsfw entry: trusted, not in every region)* — The same Wan 3.0 modes on a faster queue: same fields and results, about 40% quicker, roughly 10% dearer.
- `minimax_3_0` — MiniMax H3 Max driven by the source video, same shape as the `seedance_2_0*` modes: `prompt` is REQUIRED and refers to the source as `[Video 1]`, `image_asset` is OPTIONAL (`[Image 1]`). `duration` 5/6/8/10/12/15, resolution `480p`/`720p`/`1080p`, native audio always. Censored, and the source video is a reference here, so it must fit in 15 s — longer sources are refused rather than trimmed. A run takes seconds.

*Note:* the uncensored modes trade some quality and prompt understanding — you may need to change the input (the source video or the character) to get a good result on the first try. Modes marked *(trusted)* are available only to trusted accounts (or accounts with an NSFW content policy).

**Price:** depends on `mode` and the duration of the source video (`video_asset` / `instagram_url` / `tiktok_url`): `dreamactor_m2` *(trusted)* — 1 credit per second; `kling_2_6_sfw` — 2 credits per second (both capped at 30 seconds of source video); `wan3_0_sfw` / `wan3_0_nsfw` — 2.4 credits per second at 480p, 4.8 at 720p, 8 at 1080p, billed on `duration` plus the summed length of `ref_videos`; `wan3_0_prime_sfw` / `wan3_0_prime_nsfw` — the same modes on a faster queue at 2.625 credits per second at 480p, 5.3 at 720p, 9 at 1080p, billed the same way; the `seedance_2_0*` modes — billed the same way, about 1.4 credits per second at 480p and 3.1 at 720p, the `_fast` and `_mini` variants about a fifth less; `seedance_2_5_sfw` / `seedance_2_5_nsfw` — 1.54 credits per second at 480p, 3.46 at 720p and 11.79 at 1080p over `duration` plus the summed length of `ref_videos`, with at least 9 seconds billed and never less than the same output would cost without a source (so a 5-second source and a 5-second result cost 16 / 35 / 118 credits, and a 25-second result 65 / 145 / 496); a `task_type` of `edit` returns a clip as long as the source and is billed for twice its length; `minimax_3_0` — 1.25 credits per second at 480p, 2 at 720p, 4 at 1080p, billed the same way; other modes — at 480p flat 7 credits for videos up to 5 seconds, then 1.4 credits per second; at 720p flat 13 credits up to 5 seconds, then 2.8 credits per second; at 1080p always 2.8 credits per second.

Input fields:
- `image_asset` (string or null; default: null) — Asset ID of the image whose subject is animated or swapped in. Required for all modes except the `seedance_2_0*`, `wan3_0_*` and `minimax_3_0` modes, where it is an optional reference (`[Image 1]`).
- `video_asset` (string or null; default: null) — Asset ID of the source/driving video; with `instagram_url` and `tiktok_url`, one source only. On the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes `[Video 1]` is `video_asset` when it is set, otherwise `ref_videos[0]`; the remaining reference videos follow in order as `[Video 2]`, `[Video 3]` and so on.
- `instagram_url` (string or null; default: null) — Instagram post/reel URL used as the source video (one source only).
- `tiktok_url` (string or null; default: null) — TikTok post/reel URL used as the source video (one source only).
- `mode` (one of: "animate_nsfw" | "animate_sfw" | "dreamactor_m2" | "kling_2_6_sfw" | "replace_nsfw" | "replace_sfw" | "seedance_2_0_fast_nsfw" | "seedance_2_0_fast_sfw" | "seedance_2_0_mini_nsfw" | "seedance_2_0_mini_sfw" | "seedance_2_0_nsfw" | "seedance_2_0_sfw" | "seedance_2_5_nsfw" | "seedance_2_5_sfw" | "wan3_0_nsfw" | "wan3_0_prime_nsfw" | "wan3_0_prime_sfw" | "wan3_0_sfw" | "minimax_3_0" | "seedance_2_0" | "seedance_2_0_fast" | "seedance_2_0_mini" | "seedance_2_5" | "wan3_0" | "wan3_0_prime"; default: "replace_sfw") — How the image and source video are combined. `replace_sfw` / `replace_nsfw` — replace the person in the source video with your image's subject; `animate_sfw` / `animate_nsfw` — animate your image using the source video's motion; `kling_2_6_sfw` — Kling 2.6 driven animation; `dreamactor_m2` — DreamActor M2 driven animation; `seedance_2_0_sfw`/`seedance_2_0_nsfw`/`seedance_2_0_fast_sfw`/`seedance_2_0_fast_nsfw`/`seedance_2_0_mini_sfw`/`seedance_2_0_mini_nsfw` — Seedance 2.0 generation from the source video as a reference (requires `prompt` and a video in `video_asset` or `ref_videos`); `seedance_2_5_sfw`/`seedance_2_5_nsfw` — the same on Seedance 2.5, which also edits or extends the source video, see `task_type`; `wan3_0_sfw`/`wan3_0_nsfw` — Wan 3.0 generation from the source video as a reference (requires `prompt` and a video in `video_asset` or `ref_videos`); `wan3_0_prime_sfw`/`wan3_0_prime_nsfw` — the same on Wan 3.0's faster, slightly dearer queue; `minimax_3_0` — MiniMax H3 Max generation from the source video as a reference (requires `prompt` and a video in `video_asset` or `ref_videos`). Every `_sfw`/`_nsfw` pair above may also be named without the suffix — `wan3_0`, `wan3_0_prime`, `seedance_2_0`, `seedance_2_0_fast`, `seedance_2_0_mini`, `seedance_2_5` — and the half is then chosen from your account: the nsfw entry for a trusted account where the brand allows it, the sfw one otherwise.
- `resolution` (one of: "1080p" | "480p" | "720p"; default: "720p") — Output resolution: `480p` or `720p`. All Seedance 2.0 modes (`seedance_2_0_sfw`/`seedance_2_0_nsfw`/`seedance_2_0_fast_sfw`/`seedance_2_0_fast_nsfw`/`seedance_2_0_mini_sfw`/`seedance_2_0_mini_nsfw`) accept only `480p` or `720p`; the `seedance_2_5*` modes also accept `1080p`; all `wan3_0*` modes also accept `1080p` and default to `480p`; `minimax_3_0` accepts `480p`, `720p` or `1080p`.
- `keep_original_sound` (boolean; default: true) — Keep the source video's audio (only for `kling_2_6_sfw`). Default true.
- `prompt` (string; default: "") — Text prompt. REQUIRED for the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes; reference the source video as `[Video 1]` and the optional `image_asset` as `[Image 1]`; the short `[img1]`, `[vid1]`, `[audio1]` the app inserts are accepted too and mean `[Image 1]`, `[Video 1]`, `[Audio 1]`. On the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes `[Video 1]` is `video_asset` when it is set, otherwise `ref_videos[0]`; the remaining reference videos follow in order as `[Video 2]`, `[Video 3]` and so on. Ignored by other modes.
- `ratio` (one of: "16:9" | "1:1" | "21:9" | "3:4" | "4:3" | "9:16" | "adaptive"; default: "adaptive") — Aspect ratio (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` only): `adaptive`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`. The `wan3_0_*` modes reject `21:9`. On `seedance_2_5*` it is forced to `adaptive` when `task_type` is `edit` or `extend`. Default `adaptive`.
- `duration` (one of: -1 | 5 | 6 | 8 | 10 | 12 | 15 | 16 | 18 | 20 | 22 | 24 | 25 | 26 | 28 | 30; default: 5) — Output length in seconds (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` only). Seedance 2.0 and `minimax_3_0`: 5, 6, 8, 10, 12 or 15. `seedance_2_5*`: 5, 6, 8, 10, 12, 15, 16, 18, 20, 22, 24, 25, 26, 28 or 30, and `wan3_0_*`: also 20, 25 or 30 - both provided the value plus the source video's length, rounded up to whole seconds, stays within 30. Send `-1` when `task_type` is `edit`, where the result is exactly as long as the source; any listed value is also accepted there and ignored. No other mode or task type accepts `-1`. Default 5.
- `seed` (integer or null; default: null) — Seed for reproducibility (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` only). Default random.
- `generate_audio` (boolean; default: false) — Generate a native audio track (`seedance_2_0*`, `seedance_2_5*` and `wan3_0_*` only). Default false.
- `camera_fixed` (boolean; default: false) — Keep the camera fixed (`seedance_2_0_sfw`/`seedance_2_0_nsfw` only, ignored by `_fast`). Default false.
- `ref_images` (array[string] or null; default: null) — Reference image asset IDs (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0`), up to 9 counting `image_asset` (30 on the `seedance_2_5*` modes). Order matters: the prompt addresses them as `[Image N]`. `minimax_3_0` additionally caps images, videos and audios at 12 reference files in total.
- `ref_videos` (array[string] or null; default: null) — Source/reference video asset IDs (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0`), counted together with `video_asset`: at least 1, up to 3, 15 seconds in total - the `seedance_2_5*` modes take up to 10, 30 seconds in total, and exactly one when `task_type` is `edit` or `extend`. On the `seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0` modes `[Video 1]` is `video_asset` when it is set, otherwise `ref_videos[0]`; the remaining reference videos follow in order as `[Video 2]`, `[Video 3]` and so on.
- `ref_audios` (array[string] or null; default: null) — Reference audio asset IDs (`seedance_2_0*`, `seedance_2_5*`, `wan3_0_*` and `minimax_3_0`), up to 3, 15 seconds in total - the `seedance_2_5*` modes take up to 10, 30 seconds in total. `minimax_3_0` takes them only alongside at least one reference image or video.
- `task_type` (one of: "auto" | "edit" | "extend" | "reference"; default: null) — `seedance_2_5*` modes only: what the model does with the source video. `auto` (default) lets the model decide from the wording of the prompt - which can silently turn the run into an edit and refuse the requested length. `reference` drives a NEW clip from it. `edit` changes it in place (exactly one video; the result is as long as the source and is billed for twice its length). `extend` continues it by `duration` more seconds. `edit` and `extend` force `ratio` to `adaptive`, and `edit` ignores `duration`, which is sent as `-1`.

**Outputs:** `video_asset` (string), `audio_stripped` (boolean)

### lipsync

Make a character speak your audio (talking head): bring an audio file and a portrait first frame, and get a video in which the character talks or sings in sync. Up to 35 seconds of audio; image JPG/PNG under 5 MB. Use it to voice a character or avatar. Niche — used occasionally. Priced at 3 credits per second of audio.

**Price:** 3 credits per second of audio, measured from the uploaded `audio_asset` (audio longer than 35 seconds is rejected).

Input fields:
- `image_asset` (string; required) — Asset ID of the portrait image (JPG/PNG, under 5MB, up to 4096x4096).
- `audio_asset` (string; required) — Asset ID of the audio track to lip-sync to (under 35 seconds).
- `prompt` (string; default: "") — Optional text to guide expression/performance.
- `model` (one of: "GENERAL_NSFW" | "OMNIHUMAN"; default: "GENERAL_NSFW") — Lip-sync model; every value runs the same OmniHuman pipeline.

**Outputs:** `video_asset` (string)

### text_to_video 🔒

**🔒 Trusted account required** — available only to trusted accounts (granted automatically after your first credit purchase).

Generate a video from a text prompt alone (text-to-video): the tool generates a first frame and then animates it. NSFW-capable.

**Models:**
- `wan@2.7` *(default)* — Top quality, 720p/1080p, up to 15 s.
- `wan@2.2` — Budget option.
- `wan@3.0` / `wan@3.0-nsfw` *(the nsfw entry: trusted, not in every region)* — Direct text-to-video with native audio; 480p/720p/1080p, durations 5/6/8/10/12/15/20/25/30 s, prompts up to 20000 characters. No `21:9`. Generation takes 15-55 minutes (hours at 1080p/30 s).
- `wan@3.0-prime` / `wan@3.0-prime-nsfw` — The same pair on a faster queue: identical fields and results, about 40% quicker, roughly 10% dearer.
- `seedance_2_0` / `seedance_2_0_fast` / `seedance_2_0_mini` — Direct text-to-video (no first-frame step); native audio, fixed camera (non-fast), durations 5/6/8/10/12/15 s. All three are 480p/720p only; `seedance_2_0_mini` is the cheapest of the three.
- `seedance_2_5` *(trusted)* — The same, reaching further: 480p/720p/1080p and durations 5, 10, 15, 20, 25 or 30 s.
- `minimax@3.0` / `minimax@3.0-turbo` — Censored; direct text-to-video with native audio, 480p/720p/1080p, durations 5/6/8/10/12/15 s. Turbo is faster and half the price.

**Price:** depends on `model`, `duration` and `resolution`. `wan@2.2` (budget, resolution-independent): 10 credits at 5 s, 13 credits at 8 s. `wan@2.7` at 720p: 13 credits at 5 s, 26 at 10 s, 39 at 15 s; at 1080p: 17 credits at 5 s, 34 at 10 s, 51 at 15 s. `wan@3.0` and `wan@3.0-nsfw` bill per second at the same rate: 2.4 credits per second at 480p, 4.8 at 720p, 8 at 1080p (so 12-72, 24-144 and 40-240 credits for 5-30 s), the credit total rounded up. `wan@3.0-prime` and `wan@3.0-prime-nsfw` run the same model on a faster queue and bill 2.625 credits per second at 480p, 5.3 at 720p, 9 at 1080p (so 14-79, 27-159 and 45-270 credits for 5-30 s). `seedance_2_0` bills about 1.4 credits per second at 480p and 3.1 at 720p (7-21 and 16-46 credits for 5-15 s); `seedance_2_0_fast` and `seedance_2_0_mini` about 1.1 and 2.5 (6-17 and 13-37). `seedance_2_5` bills about 2.6 credits per second at 480p, 5.8 at 720p and 19.8 at 1080p (13-78, 29-174 and 100-595 credits for 5-30 s). `minimax@3.0` bills 1.25 credits per second at 480p, 2 at 720p and 4 at 1080p; `minimax@3.0-turbo` half of that (0.625 / 1 / 2), the credit total rounded up.

Input fields:
- `prompt` (string; required) — Text prompt
- `model` (one of: "minimax@3.0" | "minimax@3.0-turbo" | "seedance_2_0" | "seedance_2_0_fast" | "seedance_2_0_mini" | "seedance_2_5" | "wan@2.2" | "wan@2.7" | "wan@3.0" | "wan@3.0-nsfw" | "wan@3.0-prime" | "wan@3.0-prime-nsfw"; default: "wan@2.7") — Video model. `wan@2.7` (default) — top quality, durations 5/10/15 s, 720p or 1080p. `wan@2.2` — budget, durations 5/8 s. `wan@3.0` / `wan@3.0-nsfw` — direct text-to-video with native audio, durations 5/6/8/10/12/15/20/25/30 s, 480p/720p/1080p, no `21:9` ratio; the `-nsfw` entry skips content inspection and is limited to trusted accounts outside the openmov region. `wan@3.0-prime` / `wan@3.0-prime-nsfw` — the same pair on a faster, slightly dearer queue, same fields and limits. `seedance_2_0` / `seedance_2_0_fast` / `seedance_2_0_mini` — direct text-to-video, durations 5/6/8/10/12/15 s; all three are 480p or 720p only. `seedance_2_5` *(trusted)* — the same, 480p/720p/1080p and durations 5, 10, 15, 20, 25 or 30 s. `minimax@3.0` / `minimax@3.0-turbo` — censored direct text-to-video with native audio, durations 5/6/8/10/12/15 s, 480p/720p/1080p; turbo is half the price.
- `ratio` (one of: "16:9" | "1:1" | "21:9" | "3:4" | "4:3" | "9:16" | "adaptive"; default: "1:1") — Aspect ratio. wan@2.2/wan@2.7: 1:1, 16:9, 9:16, 4:3, 3:4. `wan@3.0*` also accept `adaptive` but reject `21:9`. Seedance 2.0 and `seedance_2_5` accept every value. `minimax@3.0*` accepts every value except `adaptive`, which it resolves to 16:9. Default 1:1.
- `duration` (one of: 5 | 6 | 8 | 10 | 12 | 15 | 16 | 18 | 20 | 22 | 24 | 25 | 26 | 28 | 30; default: 5) — Clip length in seconds; valid values are model-dependent: `wan@2.7` → 5, 10 or 15; `wan@2.2` → 5 or 8; `wan@3.0*` → 5, 6, 8, 10, 12, 15, 20, 25 or 30; Seedance 2.0 and `minimax@3.0*` → 5, 6, 8, 10, 12 or 15; `seedance_2_5` → 5, 10, 15, 20, 25 or 30. Default 5. Other model/duration combinations are rejected.
- `resolution` (one of: "1080p" | "480p" | "720p"; default: "720p") — Output resolution. `wan@2.7` → `720p` (default) or `1080p`; `wan@2.2` → `480p` or `720p` (default); `wan@3.0*` → `480p` (default), `720p` or `1080p`; Seedance 2.0 (`seedance_2_0` / `seedance_2_0_fast` / `seedance_2_0_mini`) → `480p` or `720p`; `seedance_2_5` → `480p`, `720p` (default) or `1080p`; `minimax@3.0` / `minimax@3.0-turbo` → `480p`, `720p` (default) or `1080p`.
- `seed` (integer or null; default: null) — Seed for reproducibility (Seedance 2.0, `seedance_2_5` and `minimax@3.0*` models). Default random.
- `generate_audio` (boolean; default: false) — Generate an audio track too (Seedance 2.0 models, `seedance_2_5` and `wan@3.0*`; `minimax@3.0*` always returns one, with or without this switch). Default false.
- `camera_fixed` (boolean; default: false) — Keep the camera fixed (Seedance 2.0, not the fast variant). Default false.

**Outputs:** `video_asset` (string), `audio_stripped` (boolean)

### video_upscaler

Bring a medium-quality video and get a sharper, higher-resolution result via BytePlus vCube. Pick a quality tier (`standard` — fast and affordable, or `pro` — premium model) and a target output resolution (`1080p`, `2k` or `4k`). Output is locked to 30fps. Priced per output second by tier x resolution x duration.

**Price:** depends on `mode` and `resolution` (BytePlus vCube engine): `standard` — $0.00689/s at 1080p, $0.01377/s at 2k, $0.02755/s at 4k; `pro` — roughly 10x standard ($0.06887/s at 1080p, $0.13774/s at 2k, $0.27548/s at 4k), converted to credits and floored at 1 credit. Output is locked to 30 fps.

Input fields:
- `video_asset` (string; required) — Asset ID of the video to upscale.
- `mode` (one of: "pro" | "standard"; default: null) — Quality tier: `standard` (fast, affordable) or `pro` (premium model, ~10x price). Default `standard`.
- `resolution` (one of: "1080p" | "2k" | "4k"; default: null) — Target output resolution: `1080p`, `2k` or `4k`. Higher costs more. Default `1080p`.

**Outputs:** `video_asset` (string)

### video_merger

Concatenate 2-5 video clips with transitions

**Price:** 1 credit.

Input fields:
- `clips` (array[object]; required) — Clips to concatenate: {asset_id, source_duration_sec, trim_start_sec, trim_end_sec}, or a bare asset id, which is what a workflow edge into this port carries; source_duration_sec is optional and probed automatically when omitted
- `transition` (one of: "cut" | "dissolve" | "fade" | "slide"; default: "cut") — cut | fade | slide | dissolve
- `keep_audio` (boolean; default: true) — Preserve audio tracks
- `fps` (integer; default: 30) — Output FPS (24 or 30)
- `width` (integer; default: 1280) — Output width
- `height` (integer; default: 720) — Output height

**Outputs:** `video_asset` (string)
