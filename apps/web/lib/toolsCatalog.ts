import { GenerativeToolId, PlaybookTemplate } from './types';

export interface ToolDefinition {
  id: GenerativeToolId;
  name: string;
  category: 'Image Generation' | 'Image Modification' | 'Video Generation' | 'Video Enhancement' | 'Cognition & Audio';
  description: string;
  badge: string;
  icon: string;
  credits: number;
  supportsAspectRatios: boolean;
  supportsTiers: boolean;
  inputsRequired: {
    refAsset?: boolean;
    characterAssets?: boolean;
    faceRef?: boolean;
    bodyRef?: boolean;
    videoAsset?: boolean;
    audioAsset?: boolean;
    clips?: boolean;
    maskAsset?: boolean;
  };
  defaultParameters: Record<string, any>;
}

/**
 * Customer-facing capability catalog (Bible v2 §25):
 * Exposes creative intents and capabilities only — never raw model names or model-picker dropdowns.
 */
export const TOOLS_CATALOG: Record<GenerativeToolId, ToolDefinition> = {
  by_prompt: {
    id: 'by_prompt',
    name: 'Text-to-Image',
    category: 'Image Generation',
    description: 'Generate high-fidelity imagery from natural language prompts.',
    badge: 'Create',
    icon: 'Sparkles',
    credits: 1,
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {},
    defaultParameters: {
      ratio: '16:9',
      tier: '2K',
      quality: 'high',
      thinking_level: 'minimal',
      web_search: false,
      transparent_background: false,
      negative_prompt: '',
      batch_size: 1,
    },
  },

  by_ref: {
    id: 'by_ref',
    name: 'Reference-to-Image',
    category: 'Image Generation',
    description: 'Recreate a reference photo scene, lighting, and composition with character and pose guidance.',
    badge: 'Reference',
    icon: 'Image',
    credits: 2,
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
      characterAssets: true,
    },
    defaultParameters: {
      strength: 0.85,
      keep_pose: true,
      ratio: '16:9',
      tier: '2K',
      batch_size: 1,
    },
  },

  image_editor: {
    id: 'image_editor',
    name: 'AI Image Editor & Inpaint',
    category: 'Image Modification',
    description: 'Edit, inpaint, composite, and transform existing images by instruction prompt.',
    badge: 'Edit',
    icon: 'Scissors',
    credits: 2,
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
      maskAsset: false,
    },
    defaultParameters: {
      edit_precision: 'high',
      batch_mode: false,
      sequential_generation: false,
      tier: '2K',
    },
  },

  faceswap: {
    id: 'faceswap',
    name: 'AI Face Swap & Fusion',
    category: 'Image Modification',
    description: 'Preserve character identity onto any reference scene while matching lighting and angle.',
    badge: 'Identity Swap',
    icon: 'UserCheck',
    credits: 2,
    supportsAspectRatios: false,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
      faceRef: true,
    },
    defaultParameters: {
      swap_type: 'face',
      tier: '2K',
    },
  },

  photoshoot: {
    id: 'photoshoot',
    name: 'AI Studio Photoshoot',
    category: 'Image Generation',
    description: 'Produce a cohesive batch of editorial photos for a persona using face and body references.',
    badge: 'Editorial Studio',
    icon: 'Camera',
    credits: 3,
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      faceRef: true,
      bodyRef: true,
    },
    defaultParameters: {
      category_id: 'studio_editorial',
      image_count: 4,
      ratio: '3:4',
    },
  },

  facegen: {
    id: 'facegen',
    name: 'Parametric Face Synthesizer',
    category: 'Image Generation',
    description: 'Design a consistent character identity from parametric attributes.',
    badge: 'Persona DNA',
    icon: 'Dna',
    credits: 2,
    supportsAspectRatios: false,
    supportsTiers: true,
    inputsRequired: {},
    defaultParameters: {
      gender: 'Female',
      age: '26-35',
      origin: 'European',
      body_type: 'Fit',
      eye_color: 'Hazel',
      hair_color: 'Brunette',
      hair_style: 'Long Wavy',
      makeup: 'Natural',
      tier: '2K',
    },
  },

  carousel: {
    id: 'carousel',
    name: '360° Multi-Angle Views',
    category: 'Image Modification',
    description: 'Generate consistent turnaround camera angles of any subject or character photo.',
    badge: 'Multi-Angle',
    icon: 'RotateCw',
    credits: 2,
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
    },
    defaultParameters: {
      number_of_images: 4,
      ratio: '1:1',
      tier: '2K',
    },
  },

  collaber: {
    id: 'collaber',
    name: 'AI Duo & Collab Scene',
    category: 'Image Generation',
    description: 'Compose two character personas together into a single cohesive scene with preserved likeness.',
    badge: 'Duo Collab',
    icon: 'Users',
    credits: 2,
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      characterAssets: true,
    },
    defaultParameters: {
      ratio: '16:9',
      tier: '2K',
      number_of_images: 1,
    },
  },

  couplegen: {
    id: 'couplegen',
    name: 'Couples Photo to Video',
    category: 'Video Generation',
    description: 'Combine two character photos into a joint frame, then animate into a smooth cinematic video.',
    badge: 'Photo to Video',
    icon: 'Heart',
    credits: 10,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      characterAssets: true,
    },
    defaultParameters: {
      duration: 5,
      fps: 30,
    },
  },

  upscaler: {
    id: 'upscaler',
    name: 'Super-Resolution Detail Restoration',
    category: 'Image Modification',
    description: 'Apply color look grading and upscale images to 2K or 4K resolution with detail restoration.',
    badge: 'Upscale',
    icon: 'Maximize2',
    credits: 2,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      refAsset: true,
    },
    defaultParameters: {
      target_resolution: '4k',
      detail: 'high',
      noise_scale: 0.1,
    },
  },

  videogen: {
    id: 'videogen',
    name: 'Image-to-Video Animation',
    category: 'Video Generation',
    description: 'Animate a still photo into a cinema-grade video clip with camera motion and speed controls.',
    badge: 'Animate',
    icon: 'Film',
    credits: 7,
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      refAsset: true,
    },
    defaultParameters: {
      duration: 5,
      fps: 30,
      resolution: '720p',
      ratio: '16:9',
      generate_audio: true,
      camera_fixed: false,
      prompt_extend: true,
    },
  },

  text_to_video: {
    id: 'text_to_video',
    name: 'Direct Text-to-Video',
    category: 'Video Generation',
    description: 'Generate video sequences straight from a text prompt with camera control.',
    badge: 'Animate T2V',
    icon: 'Video',
    credits: 10,
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {},
    defaultParameters: {
      duration: 5,
      fps: 30,
      resolution: '720p',
      ratio: '16:9',
      generate_audio: true,
    },
  },

  video2video: {
    id: 'video2video',
    name: 'Video-to-Video Motion Transfer',
    category: 'Video Generation',
    description: 'Transfer motion or restyle an existing video clip while preserving timing and soundtrack.',
    badge: 'Motion Transfer',
    icon: 'Repeat',
    credits: 12,
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      videoAsset: true,
      refAsset: true,
    },
    defaultParameters: {
      resolution: '720p',
      keep_original_sound: true,
      duration: 5,
      fps: 30,
    },
  },

  extend: {
    id: 'extend',
    name: 'Video Shot Extension',
    category: 'Video Generation',
    description: 'Continue an existing video shot seamlessly from its final frame with camera motion.',
    badge: 'Extend',
    icon: 'Film',
    credits: 7,
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      videoAsset: true,
    },
    defaultParameters: {
      duration: 5,
      fps: 30,
      resolution: '720p',
      ratio: '16:9',
    },
  },

  lipsync: {
    id: 'lipsync',
    name: 'Talking Head & LipSync',
    category: 'Video Generation',
    description: 'Sync a portrait face photo with an audio track to produce realistic speech and lip movement.',
    badge: 'Talking Head',
    icon: 'Mic',
    credits: 3,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      refAsset: true,
      audioAsset: true,
    },
    defaultParameters: {
      fps: 30,
    },
  },

  video_upscaler: {
    id: 'video_upscaler',
    name: 'AI Video Super-Resolution',
    category: 'Video Enhancement',
    description: 'Grade and upscale video clips to high resolution with frame enhancement.',
    badge: 'Video Upscale',
    icon: 'Tv',
    credits: 5,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      videoAsset: true,
    },
    defaultParameters: {
      mode: 'standard',
      resolution: '1080p',
      fps: 30,
    },
  },

  video_merger: {
    id: 'video_merger',
    name: 'Multi-Clip Video Sequencer',
    category: 'Video Enhancement',
    description: 'Assemble and concatenate multiple video clips with smooth transitions.',
    badge: 'Timeline Sequencer',
    icon: 'Sliders',
    credits: 1,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      clips: true,
    },
    defaultParameters: {
      transition: 'dissolve',
      fps: 30,
      keep_audio: true,
    },
  },

  run_any_llm: {
    id: 'run_any_llm',
    name: 'Creative Cognition & Vision Analysis',
    category: 'Cognition & Audio',
    description: 'Inspect assets, plan shots, and expand creative prompts via KEYSTONE cognition.',
    badge: 'Analyze',
    icon: 'Brain',
    credits: 1,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {},
    defaultParameters: {
      max_tokens: 2048,
      system_prompt:
        'You are KEYSTONE Creative Prompt Cognition. Expand user ideas into rich cinematic details with camera, lighting, and composition specifics.',
    },
  },
};

export const OPTIONAL_PLAYBOOKS: PlaybookTemplate[] = [
  {
    id: 'freedom',
    name: 'Freedom & Open Canvas',
    description: 'Unconstrained creative freedom across intents, framing, and resolution.',
    icon: 'Infinity',
    starterPrompt: '',
    recommendedTool: 'by_prompt',
    defaultAspect: '16:9',
    parameters: { guidance: 6.5, steps: 30 },
  },
  {
    id: 'design',
    name: 'Industrial & Digital Design',
    description: 'Industrial design prototypes, UI/UX systems, architectural visualization, and product rendering.',
    icon: 'Layers',
    starterPrompt: '',
    recommendedTool: 'by_prompt',
    defaultAspect: '16:9',
    parameters: { quality: 'master' },
  },
  {
    id: 'content',
    name: 'Social Media & Content Creation',
    description: 'Reels, visual hooks, thumbnails, and dynamic multi-angle brand assets.',
    icon: 'Smartphone',
    starterPrompt: '',
    recommendedTool: 'videogen',
    defaultAspect: '9:16',
    parameters: { duration: 5 },
  },
  {
    id: 'cinema',
    name: 'Hollywood Cinema & Film',
    description: 'Anamorphic widescreen shots, cinematic camera tracks, and film color grading.',
    icon: 'Clapperboard',
    starterPrompt: '',
    recommendedTool: 'by_prompt',
    defaultAspect: '21:9',
    parameters: { quality: 'master' },
  },
  {
    id: 'portrait',
    name: 'Digital Persona & Avatar',
    description: 'Consistent character faces, portrait headshots, fashion photoshoots, and talking avatars.',
    icon: 'User',
    starterPrompt: '',
    recommendedTool: 'by_prompt',
    defaultAspect: '3:4',
    parameters: { quality: 'high' },
  },
];
