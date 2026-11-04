# Architecture Decision Record (ADR) 002: Autonomous Cognition Agent, Direct LLM Chat & Live Internet Tool Execution

## Status
APPROVED (Founder Explicit Directive: 2026-11-02)

## Context
Per KEYSTONE_BIBLE.md §2, §10, and §11, the cognitive layer is locked to the abliterated checkpoint `huihui-ai/Huihui-Qwen3.8-27B-abliterated` running on Kaggle dual NVIDIA T4 GPUs. Previously, cognition was primarily exercised through batch heuristic proposal generation (`plan.v1` and `ProposedAction`). 

The platform requires an interactive capability where users can directly speak with the loaded LLM in real-time, ask questions, conduct research, and instruct the agent to autonomously execute tasks—including searching the live internet, scraping web information, synthesizing dialogue, and dispatching studio image generations.

## Decision
1. **Bible Amendment (§39)**:
   Formally add Section 39 to `KEYSTONE_BIBLE.md` and `docs/KEYSTONE_BIBLE.md` governing the Autonomous Cognition Agent, Direct LLM Chat, and Live Internet Tool Execution contracts.
2. **Backend API Endpoints**:
   Implement `/v1/cognition/chat` for conversational multi-turn dialogue with `huihui-ai/Huihui-Qwen3.8-27B-abliterated` and `/v1/cognition/agent-task` for autonomous multi-step execution with live internet search and creative tool dispatch.
3. **Containerized Tool Fabric**:
   Provide the agent with tool interfaces:
   - `internet_search(query)`: Live web information discovery.
   - `url_scrape(url)`: Single-page token and style extraction.
   - `generate_image(prompt, aspect, motion)`: Autonomous studio generation.
   - `upscale_asset(asset_id, scale)`: 2x/4K super-resolution dispatch.
   - `synthesize_speech(script, voice)`: Voice audio synthesis.
4. **Workspace User Interface**:
   Deploy an interactive Chat & Autonomous Agent Console accessible via the VS Code Activity Bar (`Ctrl+Shift+A`), Left Sidebar Navigation, Topbar Telemetry Pill, Canvas View Mode, and Command Palette (`⌘K`).

## Invariant Analysis & Change-Control Compliance (§37)
1. **Explicit Founder Approval**: Received via user prompt instruction.
2. **Checkpoint Pinning Preservation**: All conversational cognition and agent tasks remain strictly pinned to `huihui-ai/Huihui-Qwen3.8-27B-abliterated`. No prohibited model substitutions.
3. **Pre-Built File Immutability**: None of the 69 pre-built files in `docs/FILE_MANIFEST.txt` are modified.
4. **Verification Guard Update**: Update `scripts/verify_invariants.py` with the updated canonical Bible SHA-256 and byte size.
5. **KHF Regression & Acceptance**: All existing test suites (`npm test`, `runner.js`) maintain 100% green pass rate.
