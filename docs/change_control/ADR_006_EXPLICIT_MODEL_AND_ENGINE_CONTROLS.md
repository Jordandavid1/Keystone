# ADR-006: Restore Explicit Creative Tool & Model Selection and Active ComfyUI / MiniMax-H3 Engine Controls

- **Status:** Accepted
- **Date:** 2026-11-25
- **Authority:** Founder Direct Order (KEYSTONE Bible v2 §37)

## 1. Explicit Founder Approval

Explicitly approved and mandated by Founder on 2026-11-25: remove the unauthorized §25 restriction hiding raw model names and model-picker dropdowns, restore full explicit tool/job/model selection across all creative pipelines (including PinkCherry v1.8 / MiniMax-H3 and uncensored image/video/cognition models), and convert the ComfyUI / Engine UI from passive read-only telemetry into a live, active operational control and launch panel with zero placeholders or simulated state.

## 2. Written Architecture Decision Record

1. **Bible v2 §2.7, §23.1, §25, and §40.10 Update:** Repeals the "never expose raw model names or model-picker dropdowns" clause. Both intent-first shortcuts and explicit creative tool + model selection (`models`, `defaultModel`, MiniMax-H3 Ref2VA, Wan, Seedream, Flux, Obliteratus Qwen3.8-27B) are first-class in the Studio UI.
2. **Full 18+1 Tool & Job Wiring:** Wires every catalog tool (`minimax_h3`, `by_prompt`, `by_ref`, `image_editor`, `faceswap`, `photoshoot`, `facegen`, `carousel`, `collaber`, `couplegen`, `upscaler`, `videogen`, `text_to_video`, `video2video`, `extend`, `lipsync`, `video_upscaler`, `video_merger`, `run_any_llm`) in both the Studio UI (`FloatingComposer`, `CreatePanel`, `RightInspector`, `toolsCatalog.ts`) and `/v1/zencreator/generate` through the Gate (`ExecutionEnvelope v2`) and real ComfyUI / Audio / Cognition execution.
3. **Active ComfyUI & Cognition Engine Control Panel:** Upgrades `SettingsModal.tsx` (Engine & Infrastructure tab) and `WorkerTelemetryModal.tsx` with live endpoint/key/model configuration, local ComfyUI process launch & health probe (`POST /v1/zencreator/engine/configure` and `POST /v1/zencreator/engine/launch`), and automatic startup wiring when KEYSTONE launches.

## 3. Compatibility Impact Analysis

- Preserves all 15 Alpha Gate criteria (§34), ExecutionEnvelope v2 signing, Gate floor checks, 30/60/100/120 Hz video generation, and admin RBAC walls on `/v1/creative/comfy/configure`.
- Studio engine management for local/operator sessions exposes explicit studio engine lifecycle endpoints while keeping SSRF blocks on cloud metadata endpoints (`169.254.169.254`).

## 4. KHF Regression Coverage

- Covered by `tests/acceptance/test_bible_acceptance.py`, `tests/test_pr3_gate_and_security.py`, `tests/test_pr6_personas_and_parity.py`, `tests/test_video_120hz_fps.py`, `tests/test_no_placeholders_invariants.py`, and `scripts/verify_invariants.py --strict`.

## 5. Migration Plan

1. Synchronize `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` byte-identically.
2. Restore `models`, `defaultModel`, and `minimax_h3` in `apps/web/lib/toolsCatalog.ts` and `apps/web/lib/types.ts`, and wire explicit tool + model pickers in `FloatingComposer.tsx`, `CreatePanel.tsx`, `RightInspector.tsx`, and `intents.ts`.
3. Wire all remaining creative job routes in `apps/api/src/routers/zencreator.py` to real ComfyUI / TTS / FFmpeg workflows with zero placeholders.
4. Add live ComfyUI daemon auto-launch/connect and interactive Engine Control UI in `SettingsModal.tsx` and `WorkerTelemetryModal.tsx`.

## 6. Rollback Plan

Revert commit via `git revert` if any regression is observed in `scripts/verify_alpha_gate.py`.

## 7. Versioned Contract Updates

- `CapabilityManifest` v1 and `ExecutionEnvelope` v2 remain backward-compatible; `selected_model` / `model` parameter passes cleanly inside `arguments` and `ToolGenerationRequest.input` through the Gate.
- `openapi.yaml` regenerated from live FastAPI routes.
