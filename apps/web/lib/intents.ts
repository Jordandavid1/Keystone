/**
 * Intent routing — docs/UI_SCHEMA.md §5.5.
 * Customers express an intent; this module chooses the capability. Customers never pick a model:
 * no `model` key is sent, so the engine's own default applies (Bible §2, §17).
 */
import { TOOLS_CATALOG } from './toolsCatalog';
import {
  CanonicalPlaybook,
  EngineStatus,
  GenerativeToolId,
  Intent,
  StudioAsset,
  StudioControls,
} from './types';

export interface IntentDefinition {
  id: Intent;
  label: string;
  /** Placeholder for the prompt field — an instruction, not sample content. */
  prompt: string;
  /** Run button label; the same verb is used in the history row and toast. */
  verb: string;
  shortcut: string;
}

export const INTENTS: IntentDefinition[] = [
  { id: 'create', label: 'Create', prompt: 'Describe what you want to see', verb: 'Create', shortcut: 'Alt 1' },
  { id: 'edit', label: 'Edit', prompt: 'Say what should change in this image', verb: 'Apply edit', shortcut: 'Alt 2' },
  { id: 'animate', label: 'Animate', prompt: 'Describe the motion and the shot', verb: 'Animate', shortcut: 'Alt 3' },
  { id: 'analyze', label: 'Analyze', prompt: 'Ask about this asset or your idea', verb: 'Ask', shortcut: 'Alt 4' },
];

export const INTENT_BY_ID: Record<Intent, IntentDefinition> = Object.fromEntries(
  INTENTS.map((i) => [i.id, i]),
) as Record<Intent, IntentDefinition>;

export interface RouteContext {
  intent: Intent;
  prompt: string;
  references: StudioAsset[];
  engine: EngineStatus | null;
}

export interface RouteResult {
  capability: GenerativeToolId;
  /** Blocking problems — the run button stays disabled and the composer shows the fix. */
  problems: string[];
  /** Non-blocking notices shown before the run. */
  notices: string[];
}

export function routeIntent({ intent, prompt, references, engine }: RouteContext): RouteResult {
  const ref = references[0] || null;
  const problems: string[] = [];
  const notices: string[] = [];
  let capability: GenerativeToolId;

  switch (intent) {
    case 'create':
      capability = ref && ref.type === 'image' ? 'by_ref' : 'by_prompt';
      if (!prompt.trim()) problems.push('Describe what you want to see.');
      break;
    case 'edit':
      capability = 'image_editor';
      if (!ref || ref.type !== 'image') problems.push('Add or select the image you want to edit.');
      if (!prompt.trim()) problems.push('Say what should change.');
      break;
    case 'animate':
      capability = !ref ? 'text_to_video' : ref.type === 'video' ? 'video2video' : 'videogen';
      if (!prompt.trim()) problems.push('Describe the motion and the shot.');
      break;
    case 'analyze':
    default:
      capability = 'run_any_llm';
      if (!prompt.trim()) problems.push('Ask a question.');
      break;
  }

  if (engine && Array.isArray(engine.unwired_tools) && engine.unwired_tools.includes(capability)) {
    const kind = TOOLS_CATALOG[capability].category.startsWith('Video') ? 'video' : intent === 'analyze' ? 'cognition' : 'image';
    notices.push(`The ${kind} engine for this isn't connected yet, so the run will return an error.`);
  } else if (engine && !engine.online) {
    notices.push('Your engine is offline. Runs will fail until it is connected.');
  }

  return { capability, problems, notices };
}

/** Direct capabilities used by context-bar verbs. */
export function upscaleCapability(asset: StudioAsset): GenerativeToolId {
  return asset.type === 'video' ? 'video_upscaler' : 'upscaler';
}

const QUALITY_TIER: Record<StudioControls['quality'], string> = { draft: '1K', high: '2K', master: '4K' };

export const LOOK_LABELS: Record<string, string> = {
  none: 'Natural',
  kodak2383: 'Kodak 2383 print',
  arrilogc: 'Arri LogC',
  bleach: 'Bleach bypass',
  bladerunner: 'Neon noir',
  matrix: 'Green monolith',
  technicolor: 'Three-strip Technicolor',
  tealorange: 'Teal and orange',
};

export function formatPlaybookContext(playbook: CanonicalPlaybook): string {
  const ctx = playbook.domain_context || {};
  const skills = (playbook.skills || [])
    .map((skill) => `- ${skill.name || skill.id}: ${skill.description || skill.capability || ''}`)
    .filter((line) => line.trim() !== '- :')
    .join('\n');
  return [
    `Playbook: ${playbook.label} (${playbook.id})`,
    `Intended outcome: ${playbook.outcome}`,
    ctx.system_framing ? `System framing: ${ctx.system_framing}` : '',
    ctx.domain_brief ? `Domain brief: ${ctx.domain_brief}` : '',
    ctx.default_visual_style ? `Default visual style: ${ctx.default_visual_style}` : '',
    ctx.default_environment ? `Default environment: ${ctx.default_environment}` : '',
    ctx.quality_standard ? `Quality standard: ${ctx.quality_standard}` : '',
    skills ? `Bound skills and workflows:\n${skills}` : '',
  ]
    .filter(Boolean)
    .join('\n');
}

export interface WebContext {
  url: string;
  title: string;
  summary: string;
  styleHint: string;
}

export function compilePrompt(args: {
  text: string;
  playbook: CanonicalPlaybook | null;
  web: WebContext | null;
  lut: string;
  useCase: string | null;
}): string {
  const sections: string[] = [];
  if (args.playbook) sections.push(formatPlaybookContext(args.playbook));
  if (args.web) sections.push(`${args.web.styleHint}\n${args.web.summary}`.trim());
  if (args.lut && args.lut !== 'none') sections.push('Look: ' + (LOOK_LABELS[args.lut] || args.lut));
  if (args.useCase) sections.push(args.useCase);
  sections.push(args.text.trim());
  return sections.filter(Boolean).join('\n\n');
}

/** Build the request body for a capability from customer-level controls only. */
export function buildInput(args: {
  capability: GenerativeToolId;
  compiledPrompt: string;
  controls: StudioControls;
  references: StudioAsset[];
  playbook: CanonicalPlaybook | null;
  web: WebContext | null;
  extra?: Record<string, any>;
}): Record<string, any> {
  const { capability, compiledPrompt, controls, references, playbook, web } = args;
  const def = TOOLS_CATALOG[capability];
  const defaults = { ...(def.defaultParameters || {}) };
  delete (defaults as any).model;

  const input: Record<string, any> = {
    ...defaults,
    prompt: compiledPrompt,
    positive_prompt: compiledPrompt,
  };

  if (def.supportsAspectRatios) input.ratio = controls.aspect;
  if (def.supportsTiers) input.tier = QUALITY_TIER[controls.quality];
  input.quality = controls.quality;
  if ('batch_size' in defaults) input.batch_size = controls.results;

  if (def.category.startsWith('Video')) {
    input.camera_motion = controls.motion;
    input.motion_speed = controls.motionSpeed;
    if ('duration' in defaults || capability === 'videogen' || capability === 'text_to_video' || capability === 'video2video') {
      input.duration = controls.duration;
    }
  }

  if (references.length) {
    input.denoise = controls.strength;
    input.ref_asset_id = references[0].id;
    input.reference_asset_id = references[0].id;
    if (references.length > 1) input.reference_asset_ids = references.map((r) => r.id);
    if (capability === 'couplegen' || capability === 'collaber') input.character_assets = references.map((r) => r.id);
  }

  input.lut = controls.look.lut;
  input.grade = {
    exposure: controls.look.exposure,
    contrast: controls.look.contrast,
    saturation: controls.look.saturation,
    warmth: controls.look.warmth,
  };

  if (playbook) {
    input.playbook_id = playbook.id;
    input.playbook_context = formatPlaybookContext(playbook);
  }
  if (web) input.web_context_url = web.url;

  return { ...input, ...(args.extra || {}) };
}

export function estimateCredits(capability: GenerativeToolId, controls: StudioControls): number {
  const def = TOOLS_CATALOG[capability];
  const multiplier = 'batch_size' in (def.defaultParameters || {}) ? controls.results : 1;
  return def.credits * multiplier;
}
