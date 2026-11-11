/**
 * Canonical Types for KEYSTONE Studio Next.js Creative Workspace
 * Supports the complete 17-tool generative pipeline from .firecrawl (ZenCreator & ComfyUI).
 */

export type GenerativeToolId =
  | 'by_prompt'        // Text-to-Image
  | 'by_ref'           // Reference-to-Image / Img2Img
  | 'image_editor'     // Inpainting / Composition / Selective Edit
  | 'faceswap'         // AI Face Swap & Fusion
  | 'photoshoot'       // AI Studio Photoshoot (Curated or Custom)
  | 'facegen'          // Parametric Persona Synthesizer
  | 'carousel'         // 360° Multi-Angle View Generator
  | 'collaber'         // Duo / Collaborative Multi-Character Scene
  | 'couplegen'        // Couples Photo to Video
  | 'upscaler'         // Super-Resolution Detail Restoration
  | 'videogen'         // Image-to-Video Animation
  | 'text_to_video'    // Direct Text-to-Video
  | 'video2video'      // Video Motion & Style Transfer
  | 'lipsync'          // Talking Head & Audio LipSync
  | 'video_upscaler'   // AI Video Super-Resolution
  | 'video_merger'     // Multi-Clip Video Sequencer & Transitions
  | 'run_any_llm';     // Uncensored LLM Cognition & Brainstorming

export type CanvasViewMode = 'single' | 'compare' | 'video' | 'variations' | 'lineage' | 'pipeline' | 'analysis';

export type AspectRatio =
  | '16:9'
  | '1:1'
  | '9:16'
  | '21:9'
  | '4:3'
  | '3:4'
  | '2:3'
  | '3:2'
  | '1:2'
  | '2:1'
  | '4:5'
  | '5:4';

export type QualityTier = 'draft' | 'high' | 'master';

export interface StudioAsset {
  id: string;
  title: string;
  type: 'image' | 'video' | 'audio';
  url: string;
  downloadUrl?: string;
  previewUrl?: string;
  width?: number;
  height?: number;
  byteSize?: number;
  mimeType?: string;
  aspectRatio?: string;
  toolUsed?: GenerativeToolId | string;
  prompt?: string;
  parentId?: string | null;
  createdAt: number;
}

export interface PipelineStep {
  id: string;
  tool: GenerativeToolId;
  label: string;
  enabled: boolean;
  inputAssets: string[]; // asset IDs
  parameters: Record<string, any>;
  outputAsset?: StudioAsset | null;
  status: 'idle' | 'running' | 'completed' | 'failed';
  error?: string;
}

export interface PlaybookTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  starterPrompt: string;
  recommendedTool: GenerativeToolId;
  defaultAspect: AspectRatio;
  parameters: Record<string, any>;
}

export interface CanonicalPlaybook {
  id: string;
  label: string;
  keywords: string[];
  outcome: string;
  criticalSlots: { id: string; why: string; assumption: string }[];
  path: { title: string; objective: string; doneWhen: string }[];
  domain_context: Record<string, any>;
  use_cases: Record<string, any>[];
  skills: { id?: string; name?: string; capability?: string; adapter?: string; description?: string }[];
}

export interface GenerationState {
  isGenerating: boolean;
  currentStageText: string;
  currentStageIndex: number; // 0 to 6
  jobId?: string | null;
  error?: string | null;
}

/* ---------------------------------------------------------------------------
 * Studio schema types (docs/UI_SCHEMA.md §5)
 * ------------------------------------------------------------------------- */

export type Intent = 'create' | 'edit' | 'animate' | 'analyze';

/** Bible §19 job state machine. */
export type JobState =
  | 'CREATED'
  | 'VALIDATING'
  | 'PLANNING'
  | 'AUTHORIZING'
  | 'QUEUED'
  | 'RUNNING'
  | 'VALIDATING_OUTPUT'
  | 'RETRY_PENDING'
  | 'REPLAN_REQUIRED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'REJECTED';

export type RunStatus = 'queued' | 'processing' | 'succeeded' | 'failed';

export interface Generation {
  id: string;
  intent: Intent;
  capability: GenerativeToolId;
  label: string;
  prompt: string;
  compiledPrompt: string;
  referenceIds: string[];
  playbookId?: string | null;
  status: RunStatus;
  jobState: JobState;
  startedAt: number;
  finishedAt?: number;
  outputIds: string[];
  text?: string | null;
  error?: string | null;
  estimatedCredits: number;
  /** Original request, kept so "Try again" re-sends exactly the same thing. */
  request: { tool: GenerativeToolId; input: Record<string, any> };
  /** Job id sent with /generate; progress is read from GET /v1/zencreator/jobs/{jobId}. */
  jobId?: string | null;
  /** 'live' once the server has reported a state for this job; 'unavailable' if it never did. */
  progress?: 'pending' | 'live' | 'unavailable';
  /** The server's own words for the step it is on (latest event reason). */
  stepNote?: string | null;
  /** The last state reached before a failure, so the track can show where it stopped. */
  failedAt?: JobState | null;
}

export interface EngineStatus {
  online: boolean;
  llm?: { configured?: boolean; endpoint_present?: boolean; model?: string | null };
  comfy?: Record<string, any>;
  wired_tools?: string[];
  unwired_tools?: string[];
}

export interface LedgerState {
  balance: number | null;
  hold?: number | null;
  currency?: string;
  status?: string;
  note?: string;
}

/** Ids match the values the engine already receives as `camera_motion`. */
export type MotionPreset =
  | 'pan-left'
  | 'pan-right'
  | 'tilt-up'
  | 'tilt-down'
  | 'zoom-in'
  | 'zoom-out'
  | 'orbit'
  | 'drone';

export interface LookState {
  lut: string;
  exposure: number;
  contrast: number;
  saturation: number;
  warmth: number;
}

export interface StudioControls {
  aspect: AspectRatio;
  quality: QualityTier;
  results: 1 | 2 | 4;
  strength: number; // 0.1–0.95, edit / reference influence
  motion: MotionPreset;
  motionSpeed: number; // 0.2–2
  duration: number; // seconds
  look: LookState;
}

export type SidebarPanel = 'create' | 'assets' | 'history' | 'favorites';
