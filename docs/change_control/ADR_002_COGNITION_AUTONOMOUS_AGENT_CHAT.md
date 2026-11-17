# Architecture Decision Record (ADR) 002: Autonomous Cognition Agent, Direct LLM Chat & Live Internet Tool Execution

- **Date:** 2026-11-02
- **Target Invariant:** KEYSTONE_BIBLE.md §2, §10, §11, §37, §39
- **Status:** FOUNDER_APPROVED (Founder Explicit Directive: 2026-11-02)

## 1. Explicit Founder Approval
- **Approval Date:** 2026-11-02 (Founder Explicit Directive)
- **Basis:** Explicit Founder approval received via user prompt instruction (`Explicit Founder Approval` recorded in ADR 002).
- **Directive Scope:** Authorize conversational multi-turn cognition (`/v1/cognition/chat`) and autonomous multi-step agent execution (`/v1/cognition/agent-task`) with pinned model `huihui-ai/Huihui-Qwen3.8-27B-abliterated` and §39 Bible amendment, while preserving all 69 pre-built files in `docs/FILE_MANIFEST.txt`.

## 2. Architecture Decision Record
- **Context:** Per `KEYSTONE_BIBLE.md` §2, §10, and §11, the cognitive layer is locked to the abliterated checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated` running on Kaggle dual NVIDIA T4 GPUs. Previously, cognition was primarily exercised through batch heuristic proposal generation (`plan.v1` and `ProposedAction`). The platform requires an interactive capability where users can directly speak with the loaded LLM in real-time, ask questions, conduct research, and instruct the agent to autonomously execute tasks—including searching the live internet, scraping web information, synthesizing dialogue, and dispatching studio image generations.
- **Decision:**
  1. **Bible Amendment (§39):** Formally add Section 39 to `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` governing the Autonomous Cognition Agent, Direct LLM Chat, and Live Internet Tool Execution contracts.
  2. **Backend API Endpoints:** Implement `/v1/cognition/chat` for conversational multi-turn dialogue with `huihui-ai/Huihui-Qwen3.8-27B-abliterated` and `/v1/cognition/agent-task` for autonomous multi-step execution with live internet search and creative tool dispatch.
  3. **Containerized Tool Fabric:** Provide the agent with tool interfaces (`internet_search(query)`, `url_scrape(url)`, `generate_image(prompt, aspect, motion)`, `upscale_asset(asset_id, scale)`, `synthesize_speech(script, voice)`).
  4. **Workspace User Interface:** Deploy an interactive Chat & Autonomous Agent Console accessible via the VS Code Activity Bar (`Ctrl+Shift+A`), Left Sidebar Navigation, Topbar Telemetry Pill, Canvas View Mode, and Command Palette (`⌘K`).
- **Alternatives Considered & Rejected:** Restricting cognition solely to non-interactive `plan.v1` batch proposals or substituting alternative unapproved checkpoints (`DeepSeek`, `Llama`, `Mistral`, `Claude`, `GPT-4o`) was rejected per `KEYSTONE_BIBLE.md` §2 and §37.

## 3. Compatibility Impact Analysis
- **API Impact:** Additive routes (`/v1/cognition/chat`, `/v1/cognition/agent-task`); existing `/v1/plan` and `/v1/health` contracts remain backwards-compatible.
- **Client Impact:** Non-breaking additive Web UI modal/panel (`AgentChatModal`) and navigation triggers; existing `PromptAnatomy`, `ExecutionEnvelope`, and `HarnessResult` schemas remain intact.
- **State & Storage Impact:** Additive session/history handling without altering pre-built database migrations or pre-built asset storage formats.
- **Pre-Built File Immutability:** None of the 69 pre-built files in `docs/FILE_MANIFEST.txt` are modified.

## 4. KHF Regression Coverage
- **Regression Suite:** `scripts/verify_invariants.py`, `scripts/verify_change_control.py`, `npm test`, `node tests/e2e/runner.js`, and `tests/` pytest suite.
- **Test Scenarios:** Checkpoint pinning (`huihui-ai/Huihui-Qwen3.8-27B-abliterated`), pre-built 69-file manifest immutability, canonical Bible SHA-256 verification, and fail-closed explicit errors when cognition endpoints are unconfigured or unreachable.
- **Pre-Change vs Post-Change Verification:** Verified via `scripts/verify_invariants.py`, `scripts/verify_change_control.py`, `scripts/verify_alpha_gate.py`, and full repository test suites.

## 5. Migration Plan
- **Step 1:** Amend `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` with §39 and update `scripts/verify_invariants.py` with the updated canonical Bible SHA-256 and byte size.
- **Step 2:** Deploy additive FastAPI endpoints (`/v1/cognition/chat`, `/v1/cognition/agent-task`) and tool adapters wired to real cognition/tool services with no mock fallbacks.
- **Step 3:** Expose interactive Chat & Autonomous Agent Console in `apps/web`.

## 6. Rollback Plan
- **Trigger Conditions:** Any violation of `huihui-ai/Huihui-Qwen3.8-27B-abliterated` checkpoint pinning, regression in `/v1/plan` or `/v1/health`, or failure of `verify_invariants.py` / `verify_change_control.py`.
- **Immediate Reversion Steps:** Disable or unmount the additive `/v1/cognition/chat` and `/v1/cognition/agent-task` routes in `apps/api/src/routers/cognition.py` / `apps/api/src/server.py` and revert the corresponding UI triggers.
- **State Recovery:** No destructive schema changes are introduced; core platform state remains compatible with pre-ADR contracts.

## 7. Versioned Contract Updates
- **Canonical Bible Targets:** `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` (§39 amendment verified by `scripts/verify_invariants.py`).
- **API Endpoints Added:** `/v1/cognition/chat`, `/v1/cognition/agent-task`.
- **Verification Guard Update:** `scripts/verify_invariants.py` updated with canonical Bible SHA-256 (`1DA5FFE9D1467B7A4CF31F27F8B9D4CDE0B4096F1A922C6A3C214450FCC13A99`) and byte size (`41919`).
