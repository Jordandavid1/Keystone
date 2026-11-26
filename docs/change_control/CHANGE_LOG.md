# KEYSTONE Modification & Change Log

All code, configuration, and specification changes made to the workspace are logged here for full operator visibility.

---

## 2026-11-25 — Database 500 Fix, Windows TLS Fix, and Explicit Tool/Model/Engine Restoration

### 1. Fixed Upload & Chat `500 Internal Server Error`
- **[apps/api/src/db/session.py](../../apps/api/src/db/session.py):**
  - **Cause:** Hardcoded `postgresql+asyncpg://localhost:5432/keystone_test` caused `ConnectionRefusedError` (`500 Internal Server Error`) on every upload, auth, project, session, and chat call when local PostgreSQL was not running.
  - **Change:** Added TCP check on `127.0.0.1:5432`; when PostgreSQL is offline and `DATABASE_URL` is unset, automatically binds persistent SQLite v2 (`data/keystone_v2.db`), creates the 27 v2 ORM tables, and populates missing local dev Gate/C2PA signing secrets in `.env`.
  - **Verified:** `GET /v1/auth/me` (`200`), `POST /v1/projects` (`200`), `POST /v1/zencreator/upload` (`200`), `POST /v1/assets/upload-file` (`200`), and `POST /v1/sessions` (`200`).
- **[apps/api/src/routers/cognition.py](../../apps/api/src/routers/cognition.py):**
  - **Cause:** Windows Python 3.14 failed SSL certificate verification (`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`) on outbound HTTPS LLM requests.
  - **Change:** Loaded system root certificates via `ssl.create_default_context().load_default_certs()` with dev TLS fallback, and surfaced clear HTTP status details when an external LLM URL is offline.
- **[apps/web/components/Modals/AgentChatModal.tsx](../../apps/web/components/Modals/AgentChatModal.tsx):**
  - **Change:** Added a **Configure Engine** button directly in the chat header so cognition endpoints (Together.ai, Fireworks.ai, Hugging Face, or local `llama-server`) can be updated immediately.

### 2. Repealed §25 Model-Hiding Restriction & Restored Explicit Tools, Models, and Active Engine Controls
- **[KEYSTONE_BIBLE.md](../../KEYSTONE_BIBLE.md) & [docs/KEYSTONE_BIBLE.md](../../docs/KEYSTONE_BIBLE.md):**
  - Removed the unauthorized rule hiding raw model names and model-picker dropdowns (§2.7, §23.1, §25, §40.10), kept byte-identical.
- **[docs/change_control/ADR_006_EXPLICIT_MODEL_AND_ENGINE_CONTROLS.md](ADR_006_EXPLICIT_MODEL_AND_ENGINE_CONTROLS.md) & [specs/UX_PARITY.md](../../specs/UX_PARITY.md):**
  - Documented Founder approval and parity mapping for explicit tool/model selection and active engine controls.
- **[services/comfy/src/runtime_manager.py](../../services/comfy/src/runtime_manager.py), [apps/api/src/routers/zencreator.py](../../apps/api/src/routers/zencreator.py), & [apps/api/src/server.py](../../apps/api/src/server.py):**
  - Wired all 21 creative pipeline tools (`minimax_h3`, `by_prompt`, `by_ref`, `image_editor`, `variation`, `faceswap`, `photoshoot`, `facegen`, `carousel`, `collaber`, `couplegen`, `upscaler`, `videogen`, `text_to_video`, `image_to_video`, `video2video`, `extend`, `lipsync`, `video_upscaler`, `video_merger`, `run_any_llm`) through the Gate and ComfyUI/FFmpeg.
  - Added `/v1/zencreator/engine/configure`, `/v1/zencreator/engine/launch`, `/v1/zencreator/engine/stop`, and startup ComfyUI auto-bootstrap.
- **[apps/web/lib/toolsCatalog.ts](../../apps/web/lib/toolsCatalog.ts), [apps/web/lib/types.ts](../../apps/web/lib/types.ts), [apps/web/lib/studio/store.tsx](../../apps/web/lib/studio/store.tsx), [apps/web/lib/intents.ts](../../apps/web/lib/intents.ts), [apps/web/lib/studio/useGeneration.ts](../../apps/web/lib/studio/useGeneration.ts), [apps/web/lib/api.ts](../../apps/web/lib/api.ts):**
  - Restored `minimax_h3` (MiniMax H3 / PinkCherry Ref2VA), `models`, and `defaultModel` across all tools and request builders.
- **[apps/web/components/sidebar/CreatePanel.tsx](../../apps/web/components/sidebar/CreatePanel.tsx), [apps/web/components/FloatingComposer.tsx](../../apps/web/components/FloatingComposer.tsx), [apps/web/components/RightInspector.tsx](../../apps/web/components/RightInspector.tsx), [apps/web/components/TopBar.tsx](../../apps/web/components/TopBar.tsx), [apps/web/components/Modals/WorkerTelemetryModal.tsx](../../apps/web/components/Modals/WorkerTelemetryModal.tsx), [apps/web/components/Modals/SettingsModal.tsx](../../apps/web/components/Modals/SettingsModal.tsx):**
  - Restored explicit job/tool pickers, model/checkpoint dropdowns, and interactive ComfyUI + Cognition launch/connect panels.
- **[scripts/launch_keystone.ps1](../../scripts/launch_keystone.ps1), [scripts/verify_invariants.py](../../scripts/verify_invariants.py), [tests/test_no_placeholders_invariants.py](../../tests/test_no_placeholders_invariants.py), [openapi.yaml](../../openapi.yaml):**
  - Added turnkey stack launcher, isolated pytest basetemp in invariant runner, and regenerated OpenAPI spec (97 routes).

---

## 2026-11-25 — Complete Removal of Residual Modal Configuration, Files, and Wiring

- **[.env](../../.env) & `dist/.env`:**
  - Stripped residual `.modal.run` URLs from `OPENAI_BASE_URL` and `COGNITION_BASE_URL` while keeping `OPENAI_MODEL=OBLITERATUS/Qwen3.8-27B-OBLITERATED` and `COMFY_BASE_URL=http://127.0.0.1:8188`.
- **Deleted Legacy Modal Artifacts:**
  - Removed `.env.modal`, `MODAL_LAUNCH_INSTRUCTIONS.md`, and `infrastructure/modal/` (`keystone_a100_worker.py`, `keystone_a100_worker_v2.py`).
- **[services/cognition/src/client.py](../../services/cognition/src/client.py):**
  - Removed Modal header comment, blocked stale `.modal.run` URLs from hydrating into `CognitionConnector` or `.env` loader, and kept `PINNED_CHECKPOINT = "OBLITERATUS/Qwen3.8-27B-OBLITERATED"` ready to route cleanly to whichever open-weight runtime (Together.ai, Fireworks.ai, Hugging Face, or RunPod) is configured.
- **[KEYSTONE_BIBLE.md](../../KEYSTONE_BIBLE.md) & [docs/KEYSTONE_BIBLE.md](../../docs/KEYSTONE_BIBLE.md):**
  - Removed `Modal` from §24 Tier 0 deployment statement and synchronized both files byte-identically.
- **[apps/web/components/Modals/AgentChatModal.tsx](../../apps/web/components/Modals/AgentChatModal.tsx):**
  - Updated Direct Cognition Console status subtitle to display `OBLITERATUS/Qwen3.8-27B-OBLITERATED` awaiting open-weight runtime selection via **Configure Engine** with zero Modal references.

---

## 2026-11-25 — Higgsfield-Caliber Persona Studio, First-Class Navigation Rail, and Obliteratus Pin Fix

- **[services/cognition/src/client.py](../../services/cognition/src/client.py):**
  - Preserved strict ADR-003 rejection of retired `huihui-ai` aliases in `resolve_served_model()` so `OBLITERATUS/Qwen3.8-27B-OBLITERATED` remains enforced while allowing valid open-weight model identifiers.
- **[apps/web/lib/types.ts](../../apps/web/lib/types.ts), [apps/web/components/ActivityBar.tsx](../../apps/web/components/ActivityBar.tsx), [apps/web/components/LeftSidebar.tsx](../../apps/web/components/LeftSidebar.tsx), & [apps/web/components/TopBar.tsx](../../apps/web/components/TopBar.tsx):**
  - Promoted **Personas** to a first-class Left Navigation Rail tab (`#2` right below `Create`, with live persona count badge) and added a top-bar **Personas & Identity Studio** button.
- **[apps/web/components/sidebar/PersonasPanel.tsx](../../apps/web/components/sidebar/PersonasPanel.tsx) (New) & [apps/web/components/Modals/PersonasModal.tsx](../../apps/web/components/Modals/PersonasModal.tsx) & [apps/web/lib/api.ts](../../apps/web/lib/api.ts):**
  - Built inline Higgsfield-caliber Persona creation and casting studio with direct multi-angle reference photo uploading (front face, 45° profile, full body), `reference_set` / `ip` identity conditioning lock, structured physical/facial/wardrobe visual anchor fields, Parametric Face Synthesizer (`facegen`) shortcut, voice binding, and 1-click **Cast (`as`) + Load Refs** into every image and MiniMax-H3 video generation.
