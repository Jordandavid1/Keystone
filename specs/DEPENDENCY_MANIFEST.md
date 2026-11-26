# Dependency Manifest & 10-Phase Ratification Build Order

**Authority:** KEYSTONE Bible v2 (§23, §32, §33) & ADR-005  
**Rule:** All models and serving engines are operator-configured behind `CapabilityManifest` and disclosed here; quantization (GGUF/int8/fp8) is sanctioned per Bible v2 §2 Invariant 6 and judged by real evaluators (§13).

---

## 1. Staged Dependency & Runtime Manifest

| Layer | Required Dependency / Asset | Notes |
|---|---|---|
| **Durable Data & Vector Memory** | PostgreSQL 16+ with `pgvector` extension + Alembic | System of record for all 27 Bible v2 §21 tables (`recipes`, `recipe_embeddings`, `style_rules`, `personas`, `credit_ledger`, etc.) |
| **Queue & Transient Coordination** | Redis (+ Celery / async worker queue) | Replaces all process-RAM dicts (`_JOB_EVENTS`, `generation_progress`, `nonce_cache`, `worker_bridge`, `credits_ledger`) |
| **Media Processing** | `ffmpeg` / `ffprobe` | Video `extend` frame extraction & segment stitching, deterministic validation (duration/codec/integrity), frame sampling for temporal evaluator |
| **ComfyUI Workflow Zoo (9 Graphs)** | Image Create (SDXL / FLUX slot), Image Edit/Inpaint, Image Vary, Deterministic Grade Post-Process, Neural ESRGAN Image Upscale, Video T2V, Video I2V, Video Ref2V, Video V2V + Extend-Chain & Stitch + Video Upscale | Neural ESRGAN only (bicubic is a defect per §23.2); all workflows accept Gate-signed Envelope v2 |
| **Video Weights** | MiniMax-H3 / PinkCherry v1.8 (`bf16` / `int8`) + MiniMax-H3 Video/Audio VAEs + Turbo LoRAs + Qwen3-VL 32B text encoder + TAEH3 + 3D-Conv Latent Upscaler | Active video core (§23.2); commercial license audit required prior to production gate (§23.5, §34) |
| **Image Weights** | SDXL-class checkpoint (FLUX slot held for operator upgrade) + Real-ESRGAN / 4x-UltraSharp neural upscaler | Must be staged alongside video weights on GPU workers so `Create`/`Edit`/`Vary`/`Upscale` work live |
| **Cognition + Vision + Embeddings** | Permissive `OBLITERATED` Qwen 27B-class (`Q8_0.gguf` on `llama.cpp` or `vLLM`) + Qwen-VL multimodal critique + local Qwen-embedding-class model | Behind `CognitiveProvider`; **zero external closed/aligned LLM or embedding vendors** (Invariant 2 closure) |
| **Evaluation Engines** | Deterministic probe (`Pillow`/`ffprobe`), OCR engine (`Tesseract` / `PaddleOCR`-class), VLM critique (local Qwen-VL), SSIM + optical flow (`temporal.py`), Identity embedding matcher (`identity.py`) | Tier-A always; Tier-B budgeted per §13.3 |
| **Voice / Speech** | ElevenLabs API + POSIX-compatible local TTS fallback | Replaces Windows-only PowerShell SAPI fallback so Linux/Cloud Run containers work |
| **Content Credentials** | C2PA signing library (`c2pa-python`) + dedicated env-held signing key | Stamps every generated asset at persist time (§43); signing key separate from `KEYSTONE_ENVELOPE_SECRET` |
| **Payments & Age Gate (M2/M3)** | Stripe (SFW tier ONLY) + Adult-friendly processor (CCBill/Epoch-class) or crypto rails (UNRESTRICTED tier ONLY) + Age verification (stage 1 attestation → stage 2 card/Yoti/Veriff-class) | Processor provenance written on every `credit_ledger` row (§27, §40.9) |
| **GPU Compute Workers** | Colab Pro / dedicated GPU hosts (Tier 0 → Tier 1 → Tier 2) | Hardware specifics live in `docs/runbooks/`, not Bible canon (§24) |

---

## 2. Ten-Phase Build Order (Phase C: PR1–PR10)

| Phase / PR | Scope | Verification Gate |
|---|---|---|
| **Phase 0 (`O0`–`O17` + Pre-PR1)** | Tag `bible-v1-final`, retire v1 freeze/PASS-dicts/oracle, commit ADR-004/005 + Bible v2, housekeeping (`LICENSE`, `openapi.yaml`, runbook, docs), archive intelligence/BigQuery (D13), add `.dockerignore`, strip `.env` from `keystone-desktop.spec`, operational key rotation (`generate new -> update .env -> verify -> revoke old -> rebuild desktop exe`) | `verify_invariants.py` (`bible_sync`, `license_policy`, `banned_strings`, `change_control` blocking green) |
| **PR1 (Migrations)** | Alembic setup + PostgreSQL (+`pgvector`) migrations for all 27 tables (incl. `personas`, `projects.deleted_at`, `content_mode`, `age_verified`, `mature`, `credit_ledger` processor provenance, `recipes`, `recipe_embeddings`, `style_rules`) | Fresh migration upgrade/downgrade + ORM round-trip test |
| **PR2 (Envelope v2)** | `ExecutionEnvelope` v2 with `content_mode`, `age_verified`, `floor_verdict`, env-held `KEYSTONE_ENVELOPE_SECRET`, delete hardcoded secrets, Redis-backed nonce replay cache | Real signature/tamper/replay/mode-mismatch tests |
| **PR3 (Gate + Stage-1 Age Gate + Security Wall)** | `apps/api/src/services/gate.py`, Tier-A deterministic/floor watchdog, durable DB `authority_decisions`/`audit_events`, **Stage-1 age verification (`POST /v1/account/age-verification` + `PATCH /v1/account/content-mode`)**, admin RBAC (`require_admin`), `require_service_token` on `/internal/*`, close all IDORs & SSRF, `envelope=null -> 400` *(optional split: PR3a security wall / PR3b Gate)* | Gate, Stage-1 age attestation & Security Wall HTTP/DB integration tests |
| **PR4 (Image Core + Consolidation)** | Fix `assets.py:478`, consolidate to 1 Python PromptCompiler & 1 ComfyUI client, stage SDXL/FLUX & ESRGAN workflows, wire `Create`/`Edit`/`Vary`/`Upscale` through Gate | Live/real-boundary image gen/edit/upscale tests |
| **PR5 (Video Suite + Grade)** | Wire `t2v`/`i2v`/`ref2v`/`v2v` + `extend` chain & `ffmpeg` stitch + deterministic grade lane + video upscale through Gate | Video & grade integration tests |
| **PR6 (Personas + UX Parity)** | Fix `PersonasModal` unwrap crash & avatar IDOR, wire `as: persona_id` + `depicts` lineage + every `specs/UX_PARITY.md` control (`MotionPad`, Look sliders, Settings, Sessions, multimodal `AnalysisPane`, Agent Chat persistence/assets), retire legacy SPA | Parity ledger 100% `PORTED-WIRED`/`OWNER-DROPPED`; flip `no_duplicate_engines` blocking |
| **PR7 (Tier-B Evaluators)** | Build `services/harness/src/evaluators/` (OCR, mode-aware VLM critique, temporal, identity), wire bounded retry loop & operator-review escalation | ADR-005 evaluator fixture tests (corrupt, OCR, persona-drift, mode-rubric, retry exhaustion) |
| **PR8 (Memory & Recipes)** | Local Qwen embeddings registered in `CapabilityManifest` + `pgvector` retrieval (`tenant+project+mode` scoped), `GET /v1/recipes`, `POST /v1/recipes/{id}/replay`, two-run promotion | ADR-005 memory tests; **flip `manifest_accounting` blocking** |
| **PR9 (Receipts, Stage-2 Age Gate, C2PA)** | Immutable DB `credit_ledger` (hold→settle→release, VRAM-minute metering, dual-rail SFW/UNRESTRICTED processor provenance), **Stage-2 card/processor age verification** & billing-side gating, C2PA asset stamping | Billing idempotency, Stage-2 age gate, C2PA manifest verification |
| **PR10 (Real Acceptance Suite + Final OpenAPI)** | Rebuild `verify_alpha_gate.py` & `tests/acceptance/` against real HTTP/DB/worker boundaries (all §34/§35/ADR-005 criteria), **final `openapi.yaml` regeneration** matching all shipped routes, complete Docker/Cloud Run fixes (`requirements.txt`, real legal docs) | Full Phase D verification + `verify_invariants.py --strict` green |
