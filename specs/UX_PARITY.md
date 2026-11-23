# UX Parity Matrix — Lead Sheet for Bible v2 §25.9 Legacy Feature Ledger

**Authority:** KEYSTONE Bible v2 (§25.9 Port Parity Rule) & ADR-004 (D6) / ADR-005 (§5)  
**Rule:** The Next.js Studio (`apps/web/app/**`) is the single customer UI. Retirement of the legacy static HTML/JS SPA (`apps/web/index.html`, `apps/web/app.js`, `apps/web/legacy/`) requires **every row** below to reach `PORTED-WIRED` (verified end-to-end against real backend effects) or `OWNER-DROPPED` with a recorded reason. No control may ship as a UI-only no-op.

---

| Legacy Element / Control | Target v2 Disposition | Current Status (Pre-PR6) | Required Backend / UI Wiring |
|---|---|---|---|
| **MotionPad** (camera motion / speed) | `PORTED-WIRED` | `NO-OP` (dropped by `zencreator.py` / `h3.py`) | Wire `camera_motion` & `motion_speed` through Gate → H3 `ref2va`/`i2v` workflow parameters & compiled prompt |
| **Look sliders** (exposure / contrast / saturation / warmth) | `PORTED-WIRED` | `CSS-ONLY` (ignored by backend) | Wire to deterministic post-process grade lane (§23.2) executed before neural ESRGAN upscale |
| **5 Settings flags** (`SettingsModal` toggles) | `PORTED-WIRED` | `NO-OP` (`localStorage` unread) | Remap & wire to real user/workspace preferences: quality tier, eval budget, default content mode, replay-default seed, output prefs |
| **SessionsModal selection** | `PORTED-WIRED` | `DEAD-BINDING` (`onSelectSession` omitted) | Wire active session switcher + persisted message history + memory-context display |
| **StageFrame broken-asset reset** | `PORTED-WIRED` | `BUG` (sticks on error across selection) | Key `StageFrame` by `asset.id` + reset broken state + add actionable retry/recovery UI |
| **AnalysisPane** | `PORTED-REAL` | `TEXT-ONLY` (ignores selected media) | Wire true multimodal vision inspection via `analyze` intent (Qwen-VL via Gate) |
| **Agent Chat** (`created_assets`, `internet_findings`, persistence) | `PORTED-WIRED` | `DROPPED / BROKEN` (`role="assistant"` rejected; `session_id` unsent) | Fix `MessageRepository` role contract, send `session_id`, render returned `created_assets`, citations, and errors inline + dispatch `ASSETS_ADDED` |
| **PersonasModal** (create/edit/delete/speak + `as: persona_id`) | `FIXED + §41` | `CRASH` (response unwrap bug L92 + avatar IDOR) | Unwrap `res.persona`, close avatar cross-tenant IDOR, wire full CRUD, voice binding, versioned `depicts` lineage, and `as: persona_id` selector on composer |
| **Primary Intents** (`Create`, `Edit`, `Vary`, `Upscale`, `Animate`, `Extend`, `Speak`) | `PORTED-WIRED` | `15/17 503` on Next.js; crash on legacy image gen | Route all intents through single Gate → real ComfyUI / H3 / ESRGAN / TTS lanes; remove raw model-picker dropdowns from customer UI (`toolsCatalog.ts`) |
| **Content Mode Toggle & Age Gate** (§40.10) | `NEW-CANON` | `NOT_BUILT` | Single deliberate workspace/session `SFW | UNRESTRICTED` switch behind 18+ age gate; filter `mature=true` assets out of SFW default views |
| **Canvas / drag / keyboard / compare / lineage / cinema transport** | `PORTED-WIRED` | `PARTIAL` (lineage lost on reload; no HTTP Range seek) | Persist `project_id` & `AssetRelationship` edges on every generation; add HTTP `Range` support on `/v1/assets/{id}/content`; preserve design-system upgrade |
| **Memory / Recipe Replay & C2PA Badge** (§42, §43) | `NEW-CANON` | `NOT_BUILT` | Surface "similar proven recipe" affordance + replay action + C2PA badge toggle per view/export |
