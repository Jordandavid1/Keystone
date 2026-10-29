# KEYSTONE UX Research Synthesis & Architectural Blueprint (F21 & F22)

**Status**: FINAL / AUTHORITATIVE  
**Spec Alignment**: KEYSTONE Bible §25 (Premium Creative Workspace), §26 (Admin Workspace), & R4 Benchmark Research Mandate  
**Evidence Sources**: Live Firecrawl captures in `.firecrawl/`, `docs/zencreator-recon.md`, and `apps/api/src/intelligence_router.py` (`TARGETS_CATALOG`).

---

## 1. Executive Summary

KEYSTONE's customer-facing experience is **not** a fragmented grid of raw model playgrounds or technical parameter dumps. Per **KEYSTONE Bible §25**, KEYSTONE is a **unified, canvas-first creative workspace** where:
1. **The creative asset is visually primary.**
2. **Natural-language conversation supports the canvas.**
3. **Ordinary users interact via creative intents (`Create`, `Edit`, `Animate`, `Analyze`) and 13 Domain Playbooks**, while KEYSTONE's embedded cognition (`huihui-ai/Huihui-Qwen3.8-27B-abliterated`), PromptCompiler, and Authority Engine own model selection, 6-part `PromptAnatomy` compilation, and execution.

To design a category-defining UX, we analyzed 6 benchmark platforms across generative media, motion control, node orchestration, privacy-first inference, and enterprise creative suites.

---

## 2. Six-Target Benchmark Matrix

| Target Platform | Core Domain | Captured Surface & Artifacts | Key UX Strengths | Critical UX Weaknesses |
|---|---|---|---|---|
| **1. Hugging Face Spaces** | Open Model Hub & Gradio Sandboxes | `target_huggingface` (`GradioApp`, `PromptInputGroup`, `DiffusionGallery`) | Immediate parameter transparency; side-by-side output galleries; zero-friction model testing. | Exposes raw technical knobs (`CFG scale`, `sampler_name`, `seed`) as primary UI; zero project state or lineage DAG; cluttered form-first layout. |
| **2. Higgsfield Cinema AI** | Generative Video & Camera Motion | `target_higgsfield` (`MotionStudio`, `KeyframeTimeline`, `SplineMotionEditor`) | Cinema-grade dark UI; tactile camera motion curves; synchronized frame scrubbing and motion presets. | Siloed to motion/video only; lacks multi-domain prompt compilation or unified image-to-video lineage trees. |
| **3. ZenCreator Pro** | Multi-Tool Creator Studio & Async API | Live Firecrawl scrape (`.firecrawl/pro-html/`, `zencreator-home.md`, `zc-tools-catalog.json`, 17 tools) | Clean credit transparency ("Credits never expire", `1-6` credit pre-hold validation); async poll progression (`queued` → `processing` → `succeeded`); rich specialized workflows (Photo Shoot, Virtual Try-On, Lip Sync, Upscaler, Variations). | Presents 17 separate tool cards (`by_prompt`, `videogen`, `faceswap`, etc.) requiring users to pick tools and models (`FLUX`, `WAN`, `SEEDREAM`) manually rather than expressing unified intent. |
| **4. Venice AI** | Privacy-First Zero-Log Inference | `target_venice` (`ZeroLogAppWrapper`, `EncryptedPromptCanvas`, `PiiScrubberWidget`) | Explicit privacy/security indicators in the composer; trust-building badge showing local/ephemeral PII protection. | Chat-centric rather than canvas-first; lacks multimodal lineage and split-screen visual comparison. |
| **5. Adobe Firefly** | Enterprise Creative Suite & Inpainting | `target_adobe` (`InpaintingCanvas`, `GenerativeFillModal`, non-destructive layers) | Best-in-class 5-region studio ergonomics; central viewport dominance; contextual floating action bar; progressive disclosure in the right inspector. | Heavyweight modal flows; lacks transparent prompt-anatomy inspection or autonomous quality-retry visibility. |
| **6. Grok Studio** | Real-Time Reasoning & Split Canvas | `target_grok` (`ReasoningStream`, side-by-side artifact canvas, low-latency dark mode) | High-contrast obsidian aesthetic; live streaming reasoning trace; effortless toggle between conversation and artifact inspection. | Weak multimodal asset management; no visual lineage DAG or frame-synchronized video comparison. |

---

## 3. Synthesis: What KEYSTONE Adopts, Improves, and Rejects

### ✅ Patterns Adopted
1. **Adobe Firefly's 5-Region Studio Ergonomics**:
   - **Top Bar**: Product & active project identity, global `⌘K` command palette, real-time credit balance (Available / Held), and Workspace Switcher.
   - **Left Sidebar**: Modes & navigation (`Create`, `Projects`, `Assets`, `History`, `Favorites`, plus `13 Domain Playbooks`).
   - **Center Canvas**: Dominant dark-obsidian stage supporting single-asset inspection, **Split-Screen Image Comparison** (interactive curtain slider), **Synchronized Dual-Video Playback**, **Variations Grid**, and **Interactive Lineage DAG**.
   - **Right Inspector**: Asset metadata, KHF multidimensional quality scores, customer-level style/aspect controls, and a collapsible **Developer / Authority Mode** drawer.
   - **Bottom Composer**: Floating glassmorphic natural-language bar with drag/drop/paste asset trays and 1-click intent pills (`Create`, `Edit`, `Animate`, `Analyze`).
2. **Higgsfield's Cinema-First Dark Palette & Motion Polish**:
   - Deep obsidian surfaces (`#07080C`, `#0D0F17`, `#131622`) with subtle hairline borders (`rgba(255,255,255,0.07)`) so vibrant user artwork pops without chromatic distraction.
3. **Venice AI's Inline Security & PII Shield Badges**:
   - Live indicator in the bottom composer showing **Aikido `<untrusted_content>` Containment** and **AES-256-GCM PII Vault Scrubbing** status before any prompt reaches cognition.
4. **ZenCreator Pro's Two-Phase Credit Transparency**:
   - Real-time display of estimated credit holds before execution and instant settlement confirmation upon completion—never charging for failed runs.

### 🚀 Patterns Improved Upon by KEYSTONE
1. **Human-Centric 7-Stage Progress Language (Improving on Grok & ZenCreator polling)**:
   - Instead of raw terminal logs or opaque spinners, KEYSTONE maps its 13-state `JobStateMachine` directly to the exact 7-stage customer progress language mandated in **Bible §25**:
     1. *Understanding your request* (`CREATED` / `VALIDATING`)
     2. *Planning the generation* (`PLANNING` — Qwen 27B Cognition & `plan.v1`)
     3. *Preparing the workflow* (`AUTHORIZING` / `QUEUED` — Authority Engine & HMAC Envelope)
     4. *Creating* (`RUNNING` — Kaggle T4×2 Creative Worker)
     5. *Checking the result* (`VALIDATING_OUTPUT` — KHF Quality Harness)
     6. *Refining when necessary* (`RETRY_PENDING` / `REPLAN_REQUIRED` — Bounded Auto-Refinement)
     7. *Finishing* (`COMPLETED` — Lineage DAG & Signed URL persistence)
2. **Collapsible Prompt Anatomy & Authority Evidence (Improving on Hugging Face)**:
   - Ordinary users never have to write negative prompts or tune CFG scales. However, expanding the **"KEYSTONE Intelligence & Developer Mode"** drawer in the Right Inspector reveals the live 6-part `PromptAnatomy` (`Role`, `Task`, `Context`, `Constraints`, `OutputFormat`, `Reasoning`), the deterministic SHA-256 prompt hash, the `ProposedAction` JSON, and the HMAC-SHA256 `ExecutionEnvelope` signature.
3. **Interactive Lineage DAG on Canvas (Improving on all 6 targets)**:
   - Every upload, edit, variation, animation, and upscale is linked in a live interactive node tree (`Original Upload → Edit A → Animation A`), allowing 1-click time travel and side-by-side comparison between any ancestor and descendant.

### ❌ Anti-Patterns Rejected
1. **Rejected: Model-Picker Dropdowns in Customer UI (Bible §2 Invariant 3 & §17)**:
   - Unlike Hugging Face and ZenCreator Pro, KEYSTONE **never** asks the user to choose between `FLUX`, `Wan 2.1`, `ComfyUI`, or `Qwen`. Users select intents (`Create`, `Edit`, `Animate`, `Analyze`) and creative goals; KEYSTONE's Authority Engine routes to the optimal capability.
2. **Rejected: Form-Heavy Left Sidebars**:
   - No wall of 20 sliders blocking the viewport. Customer controls are concise (Aspect Ratio, Quality Tier, Creative Playbook), with technical parameters tucked inside collapsible advanced drawers.
3. **Rejected: Unbounded Retries or Silent Double-Charging**:
   - Automatic quality refinement is strictly bounded (`max_attempts=3`) and surfaced gracefully as *"Refining when necessary"* with full KHF score evidence available on demand.

---

## 4. Design System & Visual Tokens

| Token Category | Token Name | Value / Specification | Purpose |
|---|---|---|---|
| **Canvas Surfaces** | `--bg-abyss` | `#06070B` | Primary center canvas backdrop for maximum contrast |
| **Panel Surfaces** | `--bg-surface-1` | `#0C0E16` | Left sidebar, top bar, and right inspector background |
| **Elevated Cards** | `--bg-surface-2` | `#131724` | Asset cards, lineage nodes, and inspector sections |
| **Glass Composer** | `--bg-glass` | `rgba(19, 23, 36, 0.82)` + `backdrop-filter: blur(20px)` | Floating bottom composer & command palette |
| **Primary Accent** | `--accent-keystone` | `#6366F1` → `#8B5CF6` (Indigo-Violet gradient) | Primary CTAs, active intent pills, and cognition pulse |
| **Authority / Verified** | `--accent-emerald` | `#10B981` | Approved envelopes, KHF pass verdicts, PII Vault active |
| **Refinement / Hold** | `--accent-amber` | `#F59E0B` | Bounded auto-refinement & held credits indicator |
| **Danger / Deny** | `--accent-rose` | `#F43F5E` | Aikido injection block, authority denial, error alerts |
| **Typography** | `--font-sans` / `--font-mono` | `'Inter', system-ui` / `'JetBrains Mono', monospace` | Clean UI hierarchy + cryptographic hash/envelope inspection |
