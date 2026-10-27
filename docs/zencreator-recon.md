# ZenCreator: surface recon

Status: substantially complete on the public surface. Deepest coverage is the live API probe (authenticated, now rotated out) and the on-disk page scrape cache. Page-quality and MCP-depth gaps remain.

## 1. Hosts and what each serves

| Host | What it is | Access from this environment |
|---|---|---|
| `zencreator.com` | Marketing site (EN). Links to `/solutions/*`, `/products/*`, `/ai-university/*`, `/models`, `/prompts`, `/mcp`, `/pricing`, legal pages. | Cloudflare returns 403 to plain curl and read_url. Firecrawl scrape worked. |
| `zencreator.pro` | Main product and marketing host. Sitemap lists 348 URLs here (EN + `/es`). App links point to `zencreator.pro/tools`. | Public 200 with a browser UA. A full set of scraped Pro HTML pages is already on disk in `.firecrawl/pro-html/`. |
| `api.zencreator.pro` | Public REST API, `/api/public/v1/*`. Also serves `openapi.json`, `skill.md`, and docs. | Docs, spec, and tool catalog are public and live-verified. `GET /api/public/v1/tools` without a key returns 401. |
| `mcp.zencreator.pro` | MCP server (HTTP transport, `/mcp`). Docs linked from the homepage and `zencreator.pro/mcp`. | Confirmed reachable (scraped page on disk), tool-level list not yet extracted. |
| `storage.zencreator.pro` | Asset CDN surfaced only through generation results. | Visible only by executing a generation. |
| `app.zencreator.pro` | Logged-in app and API key management (`/api-keys`). | Not inspected. Behind login. |

## 2. Site map (from sitemap and link graph)

- `robots.txt` on `zencreator.com`: Cloudflare Content Signals. `search=yes`, `ai-train=no`, `use=reference`. Training crawlers (Amazonbot, Applebot-Extended, and many others) are disallowed.
- `sitemap.xml` (single file, no index): 348 `zencreator.pro` URLs. Sections by count: `/es/*` (168 Spanish mirror), `ai-university` (43), `models` (33), `solutions` (24), `products` (20), `prompts` (15), `services` (6), `studio`, `events`, `ai-generators`, `use-cases`, `unrestricted-ai*`, `uncensored-*`, `technologies`, `terms-and-conditions`, `pricing`, `privacy-policy`, `data-deletion`, `affiliate-program`, `report-abuse`, `about-us`, `features`, `tech`, `studio/*`.
- Homepage `zencreator.com` link graph: 52 unique internal links, including `/pricing`, `/about-us`, `/studio`, `/products/zencreator/content-creation/*` (7 product pages), `/solutions/*` (11), `/unrestricted-ai`, `/nsfw-ai-*`, `/affiliate-program`, `/report-abuse`, `/data-deletion`, `/refund-policy`, `/content-policy`, `/privacy-policy`.
- A substantial scrape of `zencreator.pro` pages is already on disk in `.firecrawl/pro-html/`: pricing, models, solutions, products, prompts, services, `ai-university/guides/*`, the Spanish mirror under `/es/*`, studio, features, technologies, events, and legal pages.

Product tools named on the homepage: AI Content Generator, Image Generator, Video Generator, Photo Editor, Influencer Generator, Influencer Video, Image-to-Video, Video-to-Video, Lip Sync (OmniHuman 1.5), Virtual Try-On, Face Generation, Upscaler, Variations, Collabs, Photo Shoot, Editor/Combiner, Text-to-Image, Image-to-Image.

Content-policy and "uncensored/NSFW" positioning is central to the marketing. Treat that as a first-class product fact.

## 3. Public API (`https://api.zencreator.pro`, OpenAPI 3.1.0, v1.0.0)

Auth: `Authorization: Bearer zc_live_<key_id>_<secret>`. Scopes: `read` and `generate`. Keys are created at `app.zencreator.pro/api-keys` and shown once. Create a key with `read` scope for inspection; `generate` is needed to POST generations.

Endpoints (12 paths, from the OpenAPI spec and confirmed live):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/public/v1/tools` | Returns `{"tools":{id->tool}}`. Tool has `name`, `description`, `input_schema`, `output_schema`, and tool-level pricing (`price`, `pricing` string, `is_starting_price`). |
| GET | `/api/public/v1/tools/{tool_name}` | Same shape, single tool. |
| POST | `/api/public/v1/generations` | Body: `{tool, input, metadata?,...}`. Returns 201 with `{id, status:"queued", created_at}`. |
| GET | `/api/public/v1/generations/{generation_id}` | Poll. Returns `{id, status, progress, error}`. |
| GET | `/api/public/v1/generations/{generation_id}/result` | Returns `{id, status, text?, outputs?[].{asset_id, url, download_url}, error}`. |
| POST | `/api/public/v1/assets` | Multipart form, not JSON (400 `\"Invalid multipart/form-data\"` with JSON). |
| GET | `/api/public/v1/balance` | Returns `{"credits": <int>}` (live: `{"credits":3}`). |
| GET | `/api/public/v1/loras` | Returns a body; 422 with `{"error":{"code":"bad_request",...}}` when called wrong (call-side not fully determined). |
| GET | `/api/public/v1/templates` | Paged envelope `{"templates":[...],"pagination":{page, limit, total, total_pages}}`. Live: 614 total, page 1 of 62, 10/page. |
| GET | `/api/public/v1/templates/{template_id}` | Single template. |
| GET | `/api/public/v1/photoshoot-categories` | List, empty at capture time. |
| GET | `/api/public/v1/transactions` | List, empty at capture time. |

Behavior (from spec, docs, and live probe):
- Generations are async. Status flow: `queued` → `processing` → `succeeded` | `partial` | `failed`. Live poll cadence of ~4s reached `succeeded` in 4 rounds.
- `input` is validated against the tool's `input_schema` before credits are charged. Invalid input returns 422 with a code/message shape.
- Credits are charged on acceptance and refunded automatically if a generation fails.
- Idempotency keys are supported for safe retries.
- The result envelope has both `outputs` (modern) and `text` (legacy; null for image tools).
- Storage is served by `storage.zencreator.pro`, not the API host: preview `https://storage.zencreator.pro/preview_<uuid-no-dashes>.webp`, download `https://storage.zencreator.pro/<hex>.jpeg`.

Tool catalog (live):
- 17 tools, keyed by numeric ids in `/api/public/v1/tools`, with `name` fields: `run_any_llm`, `upscaler`, `faceswap`, `by_prompt`, `by_ref`, `photoshoot`, `facegen`, `carousel`, `videogen`, `image_editor`, `collaber`, `couplegen`, `video2video`, `lipsync`, `text_to_video`, `video_upscaler`, `video_merger`.
- Each tool has `input_schema` (JSON Schema with per-model constraints like `maxLengthByModel` and `unsupportedByModel`) and `output_schema`.
- `by_prompt`: price 1, pricing `1-6`, not a starting price. Model enum (17): FLUX_KLEIN_NSFW, GENERAL_NSFW, GENERAL_SFW, GPT_IMAGE_2_5_FLARE, GPT_IMAGE_2_5_SUNBURST, IDEOGRAM_4_5, KREA_2, NANO_BANANA, NANO_BANANA_2_1, QWEN_IMAGE, QWEN_IMAGE_PRO, SEEDREAM_5, SEEDREAM_5_PRO, WAN, WAN_2_7_IMAGE, WAN_2_7_IMAGE_PRO, Z_IMAGE_SPICY.
- Model family behaviour is documented inside the `by_prompt` tool `description`: censored vs uncensored-but-not-built-for-full-NSFW vs built-for-full-NSFW, with which models are "trusted"-gated for NSFW behaviour.
- Full catalog captured in `.firecrawl/zc-tools-catalog.json` (keyed by `name`).

Machine-readable artifacts (public, no auth):
- `https://api.zencreator.pro/api/public/openapi.json` (~144 KB). Saved in `.firecrawl/zc-openapi-clean.json`.
- `https://api.zencreator.pro/api/public/skill.md` (~81 KB). Saved in `.firecrawl/zc-skill.md`.
- Docs page (~98 KB). Saved in `.firecrawl/zc-api-docs.md`.

## 4. Private / authenticated boundary (as observed)

- Every `/api/public/v1/*` route requires a Bearer key. Unauthenticated calls return 401; `GET /api/public/v1/tools` returns 401 without a key.
- Key issuance, the dashboard, and billing live on `app.zencreator.pro` behind login, unreachable without credentials.
- Scopes split reads (`read`) from spend (`generate`). The live probe used a key that could POST a generation.
- `POST /api/public/v1/assets` wants multipart, not JSON (400 `\"Invalid multipart/form-data\"` with JSON).
- Hidden endpoints beyond `/api/public/*` are not discoverable from outside. This recon documents only the reachable surface, not admin, webhook, or any non-`/public` routes.

## 5. Live probe (authenticated, now rotated out)

Flow exercised with a read/generate key:
- POST `by_prompt` → 201 `queued`
- poll → `processing(0%)` → `succeeded(100%)`
- GET result → `outputs[].download_url` on `storage.zencreator.pro`
- Seen: `GET /api/public/v1/balance` → `{\"credits\":3}`; `GET /api/public/v1/transactions` → empty; `GET /api/public/v1/templates` → paged with 614 total.

Full notes in `.firecrawl/zc-live-probe.md`. The key used for this probe is no longer in `.env` and should be rotated at `app.zencreator.pro/api-keys`.

## 6. Gaps (not done)

- Page-text extraction and semantic indexing of the on-disk Pro HTML set were not rebuilt from scratch in this session, and are not used lower in the dossier. The cache exists; a fresh parse would turn it into a structured inventory.
- The MCP server's tool list was not extracted from `zencreator.pro/mcp` / `mcp.zencreator.pro`. A scraped MCP page is on disk; the tool surface needs a dedicated pass.
- The Spanish mirror is on disk but not analysed. It appears to duplicate the EN content.
- Cloudflare blocks direct curl to `zencreator.com`. Firecrawl was used for that host.
- Non-`/public` API routes were not probed.

## 7. Security note

The key used in the live probe was handed to me directly and has been removed from `.env` after use. Treat it as secret and rotate it at `app.zencreator.pro/api-keys`. Keep `.env` out of version control; do not commit live keys.

## 8. Local artifacts

`.firecrawl/` is a working cache (untracked; safe to delete). Contents captured in this session:
- Public surface: `zencreator-home.md`, `zc-sitemap.xml`, `zc-urls.txt`, `zc-robots.txt`, `zc-com-links.json`, `zc-openapi.json`, `zc-openapi-clean.json`, `zc-api-docs.md`, `zc-skill.md`, `zc-tools-catalog.json`, `zc-tool-by_prompt.json`.
- Live probe (authenticated, rotated out): `zc-gen-create.json`, `zc-gen-poll.json`, `zc-gen-result.json`, `zc-balance.json`, `zc-transactions.json`, `zc-assets-smoke.json`, `zc-loras.json`, `zc-photoshoot.json`, `zc-templates.json`, `zc-live-probe.md`.

A pre-existing full scrape of `zencreator.pro` is already on disk under `.firecrawl/pro-html/` and was added to git by someone before this session; it is the bulk of the "in its entirety" page inventory.

Docs:
- `docs/zencreator-recon.md` (this file).

## 9. Git state at handoff

- New tracked doc: `docs/zencreator-recon.md`.
- Untouched by this session but pre-existing extra work in the tree: `.agents/teamwork/*`, `KAGGLE_SETUP/scripts/probe_hardware.py`, `apps/api/src/server.py`, `packages/contracts/src/models.py`, and `keystone.db` show modifications in the working tree.
