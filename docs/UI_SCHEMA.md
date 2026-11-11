# KEYSTONE Studio — UI/UX Schema

**Status:** Implemented on branch `feat/elite-studio-ui` (apps/web).
**Governs:** the customer studio at `apps/web` (Bible §25). Admin workspace (§26) is a separate app and is out of scope here except for the operator link.
**Inputs:** `docs/UX_RESEARCH_SYNTHESIS.md` (authoritative blueprint), `docs/KEYSTONE_BIBLE.md` §2, §17, §19, §22, §25, §27, §39.
**Rule zero:** no placeholders. Every surface renders real data from `lib/api.ts`, a real empty state that says what to do next, a real loading state, or a real error from the API. Nothing is mocked.

---

## 0. Subject, audience, primary job

| | |
|---|---|
| Subject | A cinema-grade studio where people turn an intent ("make", "change", "move", "explain") into finished images and video. |
| Audience | Creators and studios who want directed results, not model plumbing. Developers and operators get a separate drawer. |
| Primary job | Get from an idea to a reviewed, downloadable asset in one place — then branch from it (edit, animate, vary, upscale) without losing the thread (lineage). |

The asset is the hero. Everything else is a frame around it.

---

## 1. Design plan (frontend-design pass 1)

### 1.1 Palette — six named values

| Name | Hex | Role |
|---|---|---|
| **Abyss** | `#06070B` | The stage. The darkest value on screen, so artwork carries all of the colour. |
| **Chrome** | `#0C0E16` | Top bar, sidebar, inspector. One step up from the stage, flush (no cards). |
| **Raised** | `#131724` | Inputs, popovers, the composer body, lineage nodes. (`Lift #1A1F30` is its hover.) |
| **Ink** | `#ECEEF4` | Primary text. Secondary `#A3A9B8`, tertiary `#7A8196` (≥4.5:1 on Chrome). |
| **Keystone** | `#6366F1 → #8B5CF6` | The only accent. Used for exactly three things: the run button, the active intent, the cognition pulse. |
| **Signals** | Verified `#10B981` · Hold `#F59E0B` · Deny `#F43F5E` | Engine/authority state, credit holds and refinement, errors. Never decorative. |

Hairlines: `rgba(255,255,255,.07)` default, `.12` strong. Glass (composer, palette): `rgba(19,23,36,.82)` + `blur(20px)`.

All six come from Synthesis §4; this schema adds only the ink ramp and the hover step.

### 1.2 Type

* **Inter** (Synthesis §4) for all UI. One family; hierarchy comes from size and weight, not from mixing faces.
* **JetBrains Mono** only where character-exact reading matters: timecode, prompt hash, envelope/JSON in Developer mode. Not for labels.
* Scale (≈1.2 ratio, 14px base): `micro 11` · `meta 12` · `body 13.5` · `lead 15` · `title 18` · `stage 34`.
* Weights: 400 body, 500 controls, 600 titles. Sentence case everywhere — no all-caps labels, no tracked eyebrows.
* Numbers (credits, durations, counts) use tabular figures.

### 1.3 Layout concept

Five regions (Synthesis §3, Bible §25). The stage takes every pixel the chrome doesn't need; the composer floats *on* the stage, not under it, so the asset and the instruction share one field of view.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ◆ KEYSTONE  Project ▾        [ Search assets, playbooks, commands   ⌘K ]   ● Engine  ⚡ Credits  ⋯ │ 52
├────┬──────────────┬─────────────────────────────────────────────┬───────────┤
│ ✦  │ Create       │ Single · Compare · Variations · Lineage   ◧ │ Result    │
│ ▦  │  Playbooks   │                                             │  meta     │
│ ⏱  │  ───────     │      ┌───────────────────────────────┐      │ Controls  │
│ ♥  │ Assets grid  │      │                               │      │  aspect   │
│ ▢  │              │      │     ASSET  (or honest empty   │      │  quality  │
│    │              │      │      / progress / error)      │      │  motion   │
│    │              │      │                               │      │ ▸ Look    │
│    │              │      └───────────────────────────────┘      │ ▸ Advanced│
│    │              │        [ Edit  Animate  Vary  Upscale ⤓ ]   │ ▸ Develop.│
│    │              │   ╭─────────────────────────────────────╮   │           │
│ ⚙  │              │   │ Create  Edit  Animate  Analyze      │   │           │
│    │              │   │ [ref] Describe what you want…  [Run]│   │           │
│    │              │   │ ● Your engine · est. 1 credit        │   │           │
│    │              │   ╰─────────────────────────────────────╯   │           │
└────┴──────────────┴─────────────────────────────────────────────┴───────────┘
 60     280                      fluid (≥ 560)                        320
```

Alternatives considered:

```
A) Composer as a full-width bottom dock       B) Chat column left of stage (Grok)
┌────┬─────────────────┬────┐                 ┌────┬────────┬────────────┬────┐
│    │      stage      │    │                 │    │  chat  │   stage    │    │
├────┴─────────────────┴────┤                 │    │        │            │    │
│ composer ............ run │                 └────┴────────┴────────────┴────┘
└───────────────────────────┘
```

A steals a permanent strip from the stage and separates instruction from result. B makes conversation primary, which Bible §25 ("conversation supports the canvas") rejects. Chosen: floating composer on the stage; conversation appears as a split pane only when the user asks to Analyze or opens the agent.

Alignment: chrome is left-aligned and dense; the stage is centred (the frame is the subject); the composer is centred on the stage with left-aligned text inside.

### 1.4 Principles

1. **Asset first.** Abyss stage, flush chrome, no card stacks around it. The brightest pixels on screen should be the user's work.
2. **Intents, not engines.** Create / Edit / Animate / Analyze + Playbooks. The router (`lib/intents.ts`) chooses the capability; customers never pick a model.
3. **Honest time.** Progress shows the job stage the system can actually prove, with elapsed time. No timers pretending to be stages.
4. **Progressive disclosure.** Inspector: Result → Controls → Look → Advanced → Developer. Each deeper section is collapsed until asked for.
5. **One bold move.** The stage itself carries the drama: when a run is in flight, the empty frame becomes a lit slate that names the current stage in 34px type with a single exposure sweep along its lower edge. Everything else stays quiet.
6. **Every state is directed.** Empty, loading, error, offline — each says what happened and what to do.

---

## 2. Plan review against the brief (pass 1 → revisions)

| Plan item | Generic-default check | Decision |
|---|---|---|
| Near-black + single accent | This is calibration trait #2. | **Kept** — the owner's brief pins it ("Higgsfield-led, obsidian"), and Synthesis §4 fixes the exact values. The brief wins. Distinctiveness comes from the stage treatment, not the palette. |
| Inter + JetBrains Mono | Inter is a default face; mono-for-labels is trait #5. | **Kept Inter** because Synthesis §4 specifies it. **Revised mono**: restricted to timecode/hash/JSON only; removed from every badge and label the old UI used it for. Owner may want a display face for the wordmark/stage headline — flagged in §11. |
| Old UI: ALL-CAPS badges ("TOTAL FREEDOM MODE", "ENGINE: OFFLINE", "REFERENCE ANCHOR") | Trait #5. | **Removed.** Sentence case, plain words ("Engine offline", "Reference"). |
| Old UI: 8-pill telemetry HUD (FPS, "10-BIT HDR", "DCI-P3 ACEScc", spectrum meter) | Decoration posing as data; the HDR/ACES labels were static strings, i.e. placeholders. | **Removed.** Top bar shows only real state: project, engine, credits. |
| Old UI: 17-tool grid + model dropdowns in inspector | Violates Bible §2/§17 and Synthesis "Rejected #1". | **Removed from customer UI.** Tools/models live in Developer mode only, read-only, showing what the router chose. |
| Inspector as stacked rounded cards | Trait #4 (SaaS-card kit). | **Revised** to flush sections divided by hairlines with disclosure rows. Radius hierarchy instead of one radius everywhere: frame 6 · control 8 · panel 12 · composer 18 · chips full. |
| Progress as a floating card over the canvas | Common, and it hides the asset. | **Revised**: progress lives *in* the stage (the slate) when nothing is on stage, and as a slim strip on the frame's lower edge when a previous asset is still showing. |
| "Spend boldness in one place" | — | The stage slate (principle 5). The rest of the UI uses no gradients except the run button. |

---

## 3. Component architecture

```
app/
  layout.tsx                  fonts (next/font: Inter, JetBrains Mono), legacy.css then globals.css
  page.tsx                    <StudioProvider><StudioShell/></StudioProvider>
  globals.css                 token layer (CSS custom properties) + Tailwind
  legacy.css                  previous stylesheet, kept for the existing modals; re-pointed at the tokens
lib/
  api.ts                      HTTP client (existing) + fetchAssets, fetchAssetLineage, fetchJobs, fetchJobEvents, typed engine/ledger
  types.ts                    domain types (+ Intent, JobState, CustomerStage, Generation, EngineStatus, LedgerState, StudioControls)
  intents.ts                  INTENTS table + routeIntent(): intent × context → capability (tool) + preflight problems
  progress.ts                 JobState (13, Bible §19) → 7 customer stages (Bible §25); status vocabulary
  lineage.ts                  build DAG {nodes, edges, depth} from assets' parentId (+ server lineage ids)
  utils.ts                    cn()
  studio/
    store.tsx                 StudioProvider: useReducer state + typed actions; selectors
    useBootstrap.ts           engine, ledger, playbooks, personas, projects, assets — initial load + 15s status poll
    useGeneration.ts          run(intent) — compile → request → record Generation → ingest outputs → lineage
    useShortcuts.ts           ⌘K, ⌘↵, Alt+1..4 intents, [ / ] panels, Esc
components/
  StudioShell.tsx             5-region grid, breakpoints, overlays, modals host, file input, drag-drop
  TopBar.tsx                  Wordmark · ProjectSwitcher · CommandTrigger · EngineIndicator · CreditMeter · AccountMenu
  ActivityBar.tsx             → the nav rail (Create, Assets, History, Favorites, Projects; Agent; Settings)
  LeftSidebar.tsx             panel host for the rail
    sidebar/CreatePanel.tsx   Playbooks (attach/detach, use-cases), Personas
    sidebar/AssetsPanel.tsx   asset grid (all | favorites), upload drop zone, filter by type
    sidebar/HistoryPanel.tsx  this session's generations with status + server jobs list
  CenterCanvas.tsx            canvas header (view switch, inspector toggle) + view router
    canvas/StageFrame.tsx     single asset (image/video/audio), zoom, framing guides, aspect mask
    canvas/StageSlate.tsx     the empty / in-flight / error slate (the one bold element)
    canvas/ProgressStrip.tsx  7-stage strip + status + elapsed
    canvas/CompareView.tsx    image curtain (pointer + keyboard) | synchronized dual video
    canvas/VariationsView.tsx side-by-side gallery of a generation's outputs / siblings
    canvas/LineageView.tsx    interactive DAG (SVG edges, depth columns), click to time-travel, compare with parent
    canvas/ContextBar.tsx     floating action bar for the selected asset (Adobe pattern)
    canvas/VideoTransport.tsx timecode, play/step/loop, scrubber, matte
    canvas/AnalysisPane.tsx   split artifact view for Analyze results (Grok pattern)
  RightInspector.tsx          progressive-disclosure inspector
    inspector/Section.tsx     disclosure section primitive
    inspector/ResultSection.tsx, ControlsSection.tsx, LookSection.tsx, DeveloperSection.tsx
    inspector/MotionPad.tsx   tactile camera-motion control (Higgsfield pattern)
  FloatingComposer.tsx        IntentSwitch · AttachmentTray · PromptField · TrustLine · CostLine · RunButton
  PipelineBuilder.tsx         kept; reachable from Developer mode as a canvas view
  Modals/*                    kept (Projects, Sessions, Credits, Settings, Personas, WebScrape, Worker, AgentChat); CommandPalette rebuilt
  ui/*                        shadcn primitives (button, tooltip, slider, toggle-group, scroll-area, separator, dropdown-menu, collapsible, popover, tabs)
```

### 3.1 Responsibilities (one line each)

| Component | Owns | Never does |
|---|---|---|
| StudioShell | layout, responsive mode, overlay state, global drop/paste | business logic |
| TopBar | identity, project switch, palette trigger, engine + credit truth | invent telemetry |
| Nav rail / LeftSidebar | where you are (Create/Assets/History/Favorites/Projects) | expose tools/models |
| CenterCanvas | which view; what's on stage | own generation state |
| StageSlate | empty, in-flight, failed states of the stage | show sample media |
| ContextBar | verbs on the selected asset | run without the user's click |
| RightInspector | metadata + customer controls + disclosure of advanced/developer | show model pickers to customers |
| FloatingComposer | the instruction: intent, text, attachments, cost, trust, run | choose the capability (router does) |
| intents.ts | capability routing + preflight | call the network |
| useGeneration | the run lifecycle and its records | fake progress |

---

## 4. Design tokens (implemented in `app/globals.css` + `tailwind.config.ts`)

### 4.1 Colour tokens

| Token | Value | Tailwind |
|---|---|---|
| `--ks-abyss` | `#06070B` | `bg-ks-abyss` |
| `--ks-chrome` | `#0C0E16` | `bg-ks-chrome` |
| `--ks-raised` | `#131724` | `bg-ks-raised` |
| `--ks-lift` | `#1A1F30` | `bg-ks-lift` |
| `--ks-line` / `--ks-line-strong` | `rgba(255,255,255,.07)` / `.12` | `border-ks-line` |
| `--ks-ink` / `-2` / `-3` | `#ECEEF4` / `#A3A9B8` / `#7A8196` | `text-ks-ink` … |
| `--ks-indigo` / `--ks-violet` | `#6366F1` / `#8B5CF6` | `bg-ks-indigo` |
| `--ks-verified` / `--ks-hold` / `--ks-deny` | `#10B981` / `#F59E0B` / `#F43F5E` | `text-ks-verified` … |
| shadcn semantic (`--background`, `--primary`, …) | HSL of the above | `bg-background`, `text-primary` … |
| legacy bridge (`--bg-surface-1`, `--text-primary`, …) | aliases of the above | used by `legacy.css` modals |

### 4.2 Type scale

| Role | Size / line | Weight | Use |
|---|---|---|---|
| `stage` | 34 / 38, −0.025em | 600 | slate headline (stage name / empty invitation) |
| `title` | 18 / 24 | 600 | panel titles, modal titles |
| `lead` | 15 / 22 | 400 | composer text, slate sub-line |
| `body` | 13.5 / 20 | 400–500 | default UI |
| `meta` | 12 / 16 | 400–500 | secondary lines, chips |
| `micro` | 11 / 14 | 500 | counts, timestamps |
| mono | 12 / 16 | 500 | timecode, hashes, JSON |

### 4.3 Spacing, sizing, radii, elevation

* 4px base grid; region paddings 12/16; composer inner 12.
* Sizes: rail 60 · panel 280 · inspector 320 · top bar 52 · composer max-width 760.
* Radii by hierarchy: frame 6 · control 8 · panel 12 · composer 18 · chip full.
* Elevation: chrome has none (flush, hairline-separated). Only floating things get shadow: composer, context bar, popovers (`shadow-float`); the stage frame gets `shadow-frame`.

### 4.4 Motion

| Token | Value | Use |
|---|---|---|
| `quick` | 120ms | hover/press |
| `base` | 200ms | disclosure, view switch |
| `settle` | 320ms | asset arrival on stage |
| `shutter` easing | `cubic-bezier(.2,.8,.2,1)` | everything user-triggered |
| `exposure-sweep` | 1.8s loop | the one ambient motion: in-flight run |
| `cognition-pulse` | 1.6s loop | engine/cognition activity dot |

`prefers-reduced-motion` collapses all of it to instant.

---

## 5. State model

### 5.1 Where state lives

| State | Location | Why |
|---|---|---|
| Intent, prompt, attachments, playbook, use-case, web context | `store` (`composer` slice) | composer, inspector and router all read it |
| Customer controls (aspect, quality, results, strength, motion, duration, look) | `store` (`controls`) | inspector writes, router/useGeneration read |
| Assets, selected id, compare id, favourites | `store` (`library`) | sidebar, canvas, inspector, lineage share it |
| Generations (run records) | `store` (`runs`) | history panel, progress strip, variations |
| View, panel, panel/inspector open, developer mode | `store` (`ui`) | shell + canvas + palette |
| Engine status, ledger, playbooks, personas, projects, active project | `store` (`system`) via `useBootstrap` | top bar, composer preflight, create panel |
| Zoom, compare split %, video time, disclosure open | component-local | purely presentational |

No global state library is added — a typed `useReducer` + context is sufficient and keeps the dependency surface flat.

### 5.2 Core records

```ts
type Intent = 'create' | 'edit' | 'animate' | 'analyze';
type JobState = 'CREATED'|'VALIDATING'|'PLANNING'|'AUTHORIZING'|'QUEUED'|'RUNNING'|'VALIDATING_OUTPUT'
              |'RETRY_PENDING'|'REPLAN_REQUIRED'|'COMPLETED'|'FAILED'|'CANCELLED'|'REJECTED';
type RunStatus = 'queued' | 'processing' | 'succeeded' | 'failed';      // ZenCreator vocabulary

interface Generation {
  id: string;                 // server generation_id once known, client id before
  intent: Intent;
  capability: GenerativeToolId; // chosen by the router; shown only in Developer mode
  prompt: string;             // what the user typed
  compiledPrompt: string;     // what was sent (playbook + web + look + text)
  referenceIds: string[];
  playbookId?: string | null;
  status: RunStatus;
  jobState: JobState;         // best-known Bible §19 state
  startedAt: number; finishedAt?: number;
  outputIds: string[];
  text?: string | null;       // Analyze / cognition output
  error?: string | null;      // the API's own message
  estimatedCredits: number;   // from the capability catalog × results
}
```

### 5.3 Data flow: intent → generation → result → lineage

```
Composer (intent, prompt, attachments)            Inspector (controls)
        │                                                │
        └──────────────► routeIntent(intent, ctx) ◄──────┘
                          │  capability + problems[]
                          ▼
             problems? ──yes──► composer shows the fix ("Add the image you want to edit")
                          │no
                          ▼
   useGeneration.run():  dispatch RUN_STARTED {status: queued, jobState: VALIDATING}
                          │  compilePrompt(playbook, web, look, text)
                          │  POST /v1/zencreator/generate {tool, input}
                          │  dispatch RUN_PROGRESS {status: processing, jobState: RUNNING}
                          ▼
             ┌──── response ────┐
             │                  │
          outputs[]           error
             │                  │
  ASSETS_ADDED (parentId =    RUN_FAILED {error: API message, jobState: FAILED}
  first reference)              → slate shows message + "Try again" (re-runs same record)
  RUN_SUCCEEDED {outputIds,
  jobState: COMPLETED}
             │
  select first output; view → single (or variations if >1)
             │
  lineage: parentId edge local → LineageView; GET /v1/assets/{id}/lineage
  enriches ancestor/descendant highlighting when the asset is server-persisted
```

**Live progress.** `/v1/zencreator/generate` still answers synchronously, but it now takes a client-chosen `job_id` and records each step of the §19 machine as it actually reaches it. While the request is in flight, `useGeneration` polls `GET /v1/zencreator/jobs/{job_id}` every 500 ms. Each reported state maps through `progress.ts` onto the 7 customer stages, and the server's own words for the step ("Generating with the language model") appear under the track. On failure the track stops at the stage where the job failed. If a server never reports the id, the run says so ("This server doesn't report live progress") instead of guessing.

### 5.4 Stage mapping (`lib/progress.ts`)

| Customer stage (Bible §25) | Job states (Bible §19) |
|---|---|
| Understanding your request | CREATED, VALIDATING |
| Planning the generation | PLANNING |
| Preparing the workflow | AUTHORIZING, QUEUED |
| Creating | RUNNING |
| Checking the result | VALIDATING_OUTPUT |
| Refining when necessary | RETRY_PENDING, REPLAN_REQUIRED |
| Finishing | COMPLETED |
| (terminal, shown as error) | FAILED, CANCELLED, REJECTED |

### 5.5 Intent routing (`lib/intents.ts`)

| Intent | Context | Capability | Preflight problem |
|---|---|---|---|
| Create | no reference | `by_prompt` | needs a description |
| Create | image reference | `by_ref` | — |
| Edit | image on stage or attached | `image_editor` | "Add or select the image you want to edit." |
| Animate | image reference | `videogen` | needs a description of the motion |
| Animate | video reference | `video2video` | — |
| Animate | nothing attached | `text_to_video` | — |
| Analyze | anything / nothing | `run_any_llm` (asset ids attached) | needs a question |
| Context bar: Upscale | image / video | `upscaler` / `video_upscaler` | — |
| Context bar: Variation | image | `by_ref` (reference = selection) | — |

The engine's own report (`GET /v1/zencreator/engine` → `unwired_tools`) feeds preflight: if the routed capability is not wired, the composer says so *before* the run ("The image engine isn't connected yet, so this run will return an error"). The run stays allowed — the status poll is 15s old at worst.

---

## 6. Five-region layout spec + responsive behaviour

| Region | Desktop ≥1280 | 1024–1279 | 768–1023 | <768 (mobile) |
|---|---|---|---|---|
| Top bar (52) | full | full | search collapses to icon | wordmark, engine dot, credits, menu |
| Nav rail (60) | docked | docked | docked | becomes bottom tab bar (Create · Assets · History · Review) |
| Panel (280) | docked, `[` toggles | docked | overlay sheet | full-height sheet from tab bar |
| Stage | fluid, min 560 | fluid | fluid | full width |
| Inspector (320) | docked, `]` toggles | overlay sheet from the right | overlay sheet | "Review" tab sheet |
| Composer | floats on stage, max 760, bottom 20 | same | same | docked above tab bar, full width |
| Context bar | floats above composer | same | same | horizontal scroll row |

Bible §25 mobile emphasis — create, converse, review, approve, download, share — maps to: composer, Analyze/agent, Review sheet, favourite, download, Web Share API (shown only where the browser supports it).

---

## 7. Key flows

### 7.1 Create
1. Stage slate invites: "Describe the first frame." Composer has focus, intent = Create.
2. Optional: attach a Playbook (sidebar → Create), a reference (drop/paste/attach), web context (globe).
3. Inspector → Controls: aspect, quality (Draft / High / Master), results per run (1/2/4).
4. Run (Enter or ⌘↵). Slate turns into the in-flight slate; history panel gains a row.
5. Result lands on stage (settle motion). >1 output → Variations view side-by-side.

### 7.2 Edit
1. Select an asset → context bar → Edit (or switch intent to Edit; the selection becomes the reference).
2. Inspector shows "How much to change": Subtle / Balanced / Bold (maps to strength; exact value under Advanced).
3. Run → output's parent = source. Compare is one click (context bar → Compare with source).

### 7.3 Animate
1. Select an image → Animate. Inspector shows the **Motion pad**: a 3×3 tactile grid of camera moves (tilt/pan/push/pull/orbit/drone) + speed and duration.
2. Run → video lands on stage with the transport (timecode, step, loop, matte).

### 7.4 Analyze
1. Switch to Analyze, ask a question (selected asset is attached automatically).
2. The canvas splits: asset left, answer right (Grok artifact pattern). Close returns to single view.

### 7.5 Async progress
`queued → processing → succeeded | failed`, rendered as the slate/strip with the 7 customer stages, elapsed time, and on failure the API's message verbatim plus "Try again". Refinement attempts (RETRY_PENDING / REPLAN_REQUIRED) render in amber as "Refining when necessary" when the job API reports them.

### 7.6 Split-screen compare
* Image: curtain. Drag anywhere, arrow keys move 2%, Shift+arrow 10%, Home/End snap. Labels "Before"/"After" name which asset is which (titles in tooltips).
* Video: two players, one transport; the right follows the left (drift correction >50ms).
* Pick the "before" side from the context bar (Compare with source / with previous) or from Lineage.

### 7.7 Lineage DAG
* Columns by depth (root uploads/creations on the left), edges as curves from parent to child.
* Click a node to put it on stage (time travel). Selected node's ancestry is highlighted; server lineage (`/v1/assets/{id}/lineage`) augments it when available.
* Node menu: Compare with parent, Use as reference.

---

## 8. Accessibility & quality floor

* Visible focus on everything (2px indigo outline, 2px offset). All icon buttons have labels + tooltips.
* Compare curtain is a `role="slider"` with `aria-valuenow`.
* Colour is never the only signal: statuses carry words.
* Tertiary text ≥ 4.5:1 on Chrome. Reduced motion respected globally.
* Keyboard: ⌘K palette, ⌘↵/Enter run, Alt+1–4 intents, `[` `]` panels, Space/J/K/L/←/→ transport only when a video is on stage and focus isn't in a field.

---

## 9. How to run

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000, proxies /v1 to 127.0.0.1:8000
npm run build      # production build (passes on feat/elite-studio-ui)
```

For local development without signing in, start the API with `KEYSTONE_DEV_AUTH_BYPASS=1` (loopback requests only; never on a deployed server). Otherwise sign in at `/login`, or paste an API key in Settings → Account & API keys.

The UI is fully usable without the API: every region shows its real offline, empty or error state. For live data, start the API from the repo root, for example
`python -m uvicorn apps.api.src.server:app --port 8000` in an environment with `requirements.txt` installed plus `greenlet`, which SQLAlchemy asyncio needs and the file doesn't list.

---

## 10. Self-critique (frontend-design pass 2, after running it)

I ran the built studio against the local API (engine not configured, no session) at 1440×900 and 390×844, then fixed what didn't hold up.

| What I saw | Why it was wrong | Change |
|---|---|---|
| The "engine isn't connected" notice appeared twice, on the slate and in the composer. | It said the same thing in two places, and the slate is the one place reserved for the work. | The slate now repeats only the blocking fact (API unreachable). Routing notices live in the composer, next to the button they affect. |
| Playbook descriptions in the left panel were cut off at the right edge instead of wrapping. | Radix ScrollArea wraps its content in `display: table`, which ignores the panel width. | `ScrollArea` viewport forces its child to `display: block`. Text now wraps and clamps to 2 lines. |
| On a phone, the 34px headline overflowed the 16:9 slate. | An `overflow: hidden` aspect box loses its automatic minimum height. | The slate frame is `min-h-fit`, and the headline steps down to 26px below `sm`. |
| On a phone, the prompt field first rendered several lines tall. | Auto-grow measured before the final width settled. | The field re-measures on resize. |
| A rectangular focus ring sat inside the rounded composer and command palette. | The legacy stylesheet adds a box-shadow ring to every focused `textarea`/`input`. It fought the composer's shape. | Those two fields drop the inner ring. The whole composer border turns indigo instead (`focus-within`), so focus stays visible. |
| Asset and job panels showed `API Error [401]: Unauthorized: Missing Authorization header or X-API-Key`. | That's true but unreadable, and it gave no next step. | `lib/errors.ts` says "you are not signed in, so the API refused the request" and notes that results from this session still appear. Other errors pass through verbatim. |
| None of the tints showed: selected states, the failed-run border, the attached-playbook panel. | The `ks.*` Tailwind colours were bare `var(--ks-x)`, so Tailwind silently dropped every opacity modifier (`bg-ks-indigo/10`, `border-ks-deny/30`; 22 classes in all). | `globals.css` now also exposes channel triplets (`--ks-indigo-rgb`), and the config uses `rgb(var(--ks-x-rgb) / <alpha-value>)`. The hex variables stay the source the rest of the CSS reads. |
| Use-case suggestions were centred, wrapped pills. | Two-line pills read as buttons with no clear edge. | They are now left-aligned, control-radius rows. |
| A long failure message filled the History panel. | History is for scanning, and the full message is already on the stage. | History clamps it to 3 lines, with the full text in the tooltip. |

**Contrast check.** These are the WCAG ratios of each ink colour on the three surfaces it sits on: Abyss `#06070B` / Chrome `#0C0E16` / Raised `#131724`.

| Colour | Abyss | Chrome | Raised |
|---|---|---|---|
| ink-3 `#7A8196` | 5.19 | 4.96 | 4.60 |
| ink-2 `#A3A9B8` | 8.56 | 8.19 | 7.59 |
| ink `#ECEEF4` | 17.4 | 16.6 | 15.4 |
| hold `#F59E0B` | 9.4 | 9.0 | 8.3 |
| deny `#F43F5E` | 5.5 | 5.3 | 4.9 |

All of these pass AA for body text. Indigo `#6366F1` measures 4.0–4.5, so it is only used for icons, borders and fills, which need 3:1. It is never used for text.

**Still generic, consciously accepted.**
- The inspector is a stack of collapsible sections. That's the Adobe progressive-disclosure pattern the synthesis adopts, so I kept it.
- The left panel is a list. It is a list of real playbooks from the API, so I didn't dress it up as cards.

**Where the boldness is spent.** It goes in one place: the stage slate. That's the hairline frame at the chosen ratio, the 34px stage headline, and the exposure sweep while a run is in flight. Everything around it stays quiet chrome.

**Not visually verified.** These need media assets. Sign-in now works (§11), but no image or video engine is connected locally, so nothing could be generated or rendered:
- Compare
- Variations
- Lineage
- the video transport
- the context bar

They compile and are wired to the real endpoints, but I didn't see them render with media.

---

## 11. Owner decisions and open questions

### Resolved (owner decisions, 11 Nov 2026)

1. **Sign-in: all three paths built.** `lib/api.ts` attaches credentials to every call: a bearer token first, otherwise a saved API key.
   - **Login screen** at `/login`: sign in, create account, or API key. It stores the token from `POST /v1/auth/login` or `/register` and returns to the studio.
     - Tokens last as long as the API issues them for (currently 1 hour).
     - A token the API rejects is dropped automatically, and the studio falls back to the saved key or the signed-out state.
   - **API key** in Settings → Account & API keys (also on the login screen).
     - A pasted key is checked against `/v1/auth/me` and stored only if the server accepts it.
     - Signed-in users can also create a key there with `POST /v1/auth/api-keys`. The raw key is shown once, because the server keeps only its hash.
   - **Dev bypass** is a server switch: `KEYSTONE_DEV_AUTH_BYPASS=1` where the API runs.
     - It applies only to credential-less requests from loopback. The original client in `X-Forwarded-For` must also be loopback, because the Next proxy makes every request look local.
     - Those requests run as a real local account, `dev@keystone.local`.
     - `GET /v1/auth/mode` and `/v1/auth/me` (`auth_via`) tell the UI that it's on. The account button turns amber and reads "Dev bypass (local only)".
   - **Panels.** Assets, server jobs, projects and personas load only once signed in. Otherwise they show the real "Sign in to see …" state with Sign in and Use an API key actions.
   - **Ownership.** Uploads and generations made while signed in are owned by that account, so they appear in its asset list. Signed-out use keeps the shared studio account it always had.
2. **Intent routing stays client-side.** This was chosen for speed: `lib/intents.ts` maps Create/Edit/Animate/Analyze to a tool id. Per Bible §17 it can move to the server later (an `intent_hint` on `/generate` that the server resolves). The UI contract wouldn't change.
3. **Progress is real.** Server changes, kept minimal:
   - `apps/api/src/jobs/generation_progress.py` is an in-process registry. Every move is checked with the canonical `transition()`, and finished records are dropped after an hour.
   - `/generate` accepts an optional UUID `job_id`, or mints one, and returns `job_id` and `job_state`. A failure returns `X-Keystone-Job-Id`.
   - `GET /v1/zencreator/jobs/{job_id}` returns the current state, an event list with reasons, and the error.
   - The LLM call now runs in a worker thread, so progress polls are answered while it works.
   - What the server records: CREATED → VALIDATING → PLANNING (prompt compiled with or without a playbook) → AUTHORIZING (billing off on the local engine, so no hold) → QUEUED → RUNNING → VALIDATING_OUTPUT → COMPLETED or FAILED.
   - **Limits.** The registry lives in process memory, so it doesn't survive an API restart and isn't shared across multiple API workers. Moving it into the `jobs` table is the durable follow-up. That table needs request and authority-decision records, so it was out of scope here.
4. **Animate / offline warning: the engine's own signal is trusted as-is.** It is decided in `routeIntent`:
   - When the routed tool is in `engine.unwired_tools`, the composer says the engine for it isn't connected. That's the case for Animate without a reference, which routes to `text_to_video`.
   - Otherwise, when `engine.online` is false, it says the engine is offline. That covers Animate with a reference, which routes to `videogen`.
   - No other change.

### Still open

5. **Trust indicator.** The composer shows only what the client can verify: engine status, plus "Web text redacted" when web context is attached. No endpoint reports Aikido/PII-vault status, so the UI doesn't claim it.
6. **Display face.** Inter is used everywhere, per the synthesis doc. A display face for the wordmark and stage headline would add character. Your call.
7. **Favorites persistence.** Favorites last for the session only. Is there meant to be a server field for them?
8. **Approve / feedback.** The mobile "Review" tab opens the inspector. There's no approve or feedback action yet. Generations now have job ids, but `user_feedback` references the `jobs` table, which these in-memory jobs don't live in.
9. **Billing.** The balance endpoint reports `local_engine` with a null balance, so the UI says "Billing off". Credit estimates appear only when billing returns a number.
10. **Research inputs.** Mobbin needs a paid plan, so it wasn't used. The Higgsfield app captures in the reference set are blank (behind login), and the Venice, ZenCreator and Grok captures are marketing or sign-in pages.
11. **Token storage.** Tokens and keys are kept in `localStorage`. That's simple and survives reloads, but any script on the page can read it. An httpOnly-cookie session would be the hardening step if the studio is ever served beyond local use.
