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

export type CanvasViewMode = 'single' | 'compare' | 'video' | 'variations' | 'lineage' | 'pipeline';

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
