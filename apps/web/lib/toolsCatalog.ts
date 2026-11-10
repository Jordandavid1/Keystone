import { GenerativeToolId, PlaybookTemplate } from './types';

export interface ToolDefinition {
  id: GenerativeToolId;
  name: string;
  category: 'Image Generation' | 'Image Modification' | 'Video Generation' | 'Video Enhancement' | 'Cognition & Audio';
  description: string;
  badge: string;
  icon: string;
  credits: number;
  models?: string[];
  defaultModel?: string;
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

export const TOOLS_CATALOG: Record<GenerativeToolId, ToolDefinition> = {
  by_prompt: {
    id: 'by_prompt',
    name: 'Text-to-Image',
    category: 'Image Generation',
    description: 'Generate high-fidelity imagery from natural language prompts. Uncensored and SFW flagship models.',
    badge: 'Flagship Core',
    icon: 'Sparkles',
    credits: 1,
    models: [
      'SEEDREAM_5_PRO',
      'QWEN_IMAGE_PRO',
      'WAN_2_7_IMAGE_PRO',
      'FLUX_KLEIN_NSFW',
      'Z_IMAGE_SPICY',
      'NANO_BANANA_2_1',
      'GPT_IMAGE_2_5_SUNBURST',
      'IDEOGRAM_4_5',
      'GENERAL_NSFW'
    ],
    defaultModel: 'SEEDREAM_5_PRO',
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
      batch_size: 1
    }
  },

  by_ref: {
    id: 'by_ref',
    name: 'Reference-to-Image',
    category: 'Image Generation',
    description: 'Recreate a reference photo\'s scene, lighting, and composition for your character with pose preservation.',
    badge: 'Img2Img Ref',
    icon: 'Image',
    credits: 2,
    models: ['SEEDREAM_5_PRO'],
    defaultModel: 'SEEDREAM_5_PRO',
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
      characterAssets: true
    },
    defaultParameters: {
      strength: 0.85,
      keep_pose: true,
      ratio: '16:9',
      tier: '2K',
      batch_size: 1
    }
  },

  image_editor: {
    id: 'image_editor',
    name: 'AI Image Editor & Inpaint',
    category: 'Image Modification',
    description: 'Edit, inpaint, composite, and transform existing images by instruction prompt with optional mask selection.',
    badge: 'Brush & Inpaint',
    icon: 'Scissors',
    credits: 2,
    models: [
      'SEEDREAM_5_PRO',
      'GPT_IMAGE_2_5_SUNBURST',
      'NANO_BANANA_2_1',
      'IDEOGRAM_4_5',
      'QWEN_IMAGE_PRO',
      'FLUX_KLEIN_NSFW',
      'GENERAL_NSFW'
    ],
    defaultModel: 'SEEDREAM_5_PRO',
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
      maskAsset: false
    },
    defaultParameters: {
      edit_precision: 'high',
      batch_mode: false,
      sequential_generation: false,
      tier: '2K'
    }
  },

  faceswap: {
    id: 'faceswap',
    name: 'AI Face Swap & Fusion',
    category: 'Image Modification',
    description: 'Swap a character\'s face onto any reference scene while preserving lighting, angle, and facial features.',
    badge: 'Identity Swap',
    icon: 'UserCheck',
    credits: 2,
    models: ['SEEDREAM_5_PRO', 'FULL_HEAD', 'MULEROUTER_FACE'],
    defaultModel: 'SEEDREAM_5_PRO',
    supportsAspectRatios: false,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true,
      faceRef: true
    },
    defaultParameters: {
      swap_type: 'face', // face | head | person
      tier: '2K'
    }
  },

  photoshoot: {
    id: 'photoshoot',
    name: 'AI Studio Photoshoot',
    category: 'Image Generation',
    description: 'Produce a batch of varied, organic editorial photos of one persona using face and body references.',
    badge: 'Editorial Studio',
    icon: 'Camera',
    credits: 3,
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      faceRef: true,
      bodyRef: true
    },
    defaultParameters: {
      category_id: 'studio_editorial',
      image_count: 4,
      ratio: '3:4'
    }
  },

  facegen: {
    id: 'facegen',
    name: 'Parametric Face Synthesizer',
    category: 'Image Generation',
    description: 'Design a pristine new character identity from parametric attributes (ethnicity, age, eyes, hair, beard, makeup).',
    badge: 'DNA Creator',
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
      tier: '2K'
    }
  },

  carousel: {
    id: 'carousel',
    name: '360° Multi-Angle Views',
    category: 'Image Modification',
    description: 'Generate consistent 3D turnaround camera angles of any subject or character photo.',
    badge: 'Multi-Angle',
    icon: 'RotateCw',
    credits: 2,
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      refAsset: true
    },
    defaultParameters: {
      number_of_images: 4,
      ratio: '1:1',
      tier: '2K'
    }
  },

  collaber: {
    id: 'collaber',
    name: 'AI Duo & Collab Scene',
    category: 'Image Generation',
    description: 'Place two independent character personas together into a single cohesive scene with preserved likeness.',
    badge: 'Duo Collab',
    icon: 'Users',
    credits: 2,
    models: ['SEEDREAM_5_PRO', 'GENERAL'],
    defaultModel: 'SEEDREAM_5_PRO',
    supportsAspectRatios: true,
    supportsTiers: true,
    inputsRequired: {
      characterAssets: true
    },
    defaultParameters: {
      ratio: '16:9',
      tier: '2K',
      number_of_images: 1
    }
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
      characterAssets: true
    },
    defaultParameters: {
      duration: 5
    }
  },

  upscaler: {
    id: 'upscaler',
    name: 'Super-Resolution Detail Restoration',
    category: 'Image Modification',
    description: 'Enhance and upscale images to 2K, 4K, 6K, or 8K resolution using diffusion restoration.',
    badge: 'Clarity 8K',
    icon: 'Maximize2',
    credits: 2,
    models: ['seedvr2_7b', 'seedvr2_3b'],
    defaultModel: 'seedvr2_7b',
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      refAsset: true
    },
    defaultParameters: {
      target_resolution: '4k',
      detail: 'high',
      noise_scale: 0.1
    }
  },

  videogen: {
    id: 'videogen',
    name: 'Image-to-Video Animation',
    category: 'Video Generation',
    description: 'Animate a still photo into a cinema-grade video clip with native synced audio, camera motions, and physics.',
    badge: 'Cinema Motion',
    icon: 'Film',
    credits: 7,
    models: [
      'wan@3.0',
      'wan@3.0-nsfw',
      'wan@2.7',
      'kling@2.6',
      'seedance_2_0',
      'seedance_2_5',
      'minimax@3.0',
      'grok@4.1'
    ],
    defaultModel: 'wan@3.0',
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      refAsset: true
    },
    defaultParameters: {
      duration: 5,
      resolution: '720p',
      ratio: '16:9',
      generate_audio: true,
      camera_fixed: false,
      prompt_extend: true
    }
  },

  text_to_video: {
    id: 'text_to_video',
    name: 'Direct Text-to-Video',
    category: 'Video Generation',
    description: 'Generate video sequences straight from a text prompt with native sound effects and camera control.',
    badge: 'Direct T2V',
    icon: 'Video',
    credits: 10,
    models: [
      'wan@3.0',
      'wan@2.7',
      'seedance_2_0',
      'seedance_2_5',
      'minimax@3.0'
    ],
    defaultModel: 'wan@3.0',
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {},
    defaultParameters: {
      duration: 5,
      resolution: '720p',
      ratio: '16:9',
      generate_audio: true
    }
  },

  video2video: {
    id: 'video2video',
    name: 'Video-to-Video Motion Transfer',
    category: 'Video Generation',
    description: 'Transfer motion or swap a character into an existing video clip while keeping the original soundtrack.',
    badge: 'Motion Transfer',
    icon: 'Repeat',
    credits: 12,
    models: [
      'kling_2_6_sfw',
      'replace_sfw',
      'replace_nsfw',
      'animate_sfw',
      'animate_nsfw',
      'dreamactor_m2',
      'seedance_2_0',
      'wan3_0',
      'minimax_3_0'
    ],
    defaultModel: 'kling_2_6_sfw',
    supportsAspectRatios: true,
    supportsTiers: false,
    inputsRequired: {
      videoAsset: true,
      refAsset: true
    },
    defaultParameters: {
      mode: 'kling_2_6_sfw',
      resolution: '720p',
      keep_original_sound: true,
      duration: 5
    }
  },

  lipsync: {
    id: 'lipsync',
    name: 'Talking Head & LipSync',
    category: 'Video Generation',
    description: 'Sync a portrait face photo with an audio track to produce realistic speech, gestures, and lip movement.',
    badge: 'Talking Head',
    icon: 'Mic',
    credits: 3,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      refAsset: true,
      audioAsset: true
    },
    defaultParameters: {
      model: 'OMNIHUMAN'
    }
  },

  video_upscaler: {
    id: 'video_upscaler',
    name: 'AI Video Super-Resolution',
    category: 'Video Enhancement',
    description: 'Upscale and sharpen video clips to 1080p, 2K, or 4K with frame enhancement at locked 30 FPS.',
    badge: 'Video 4K',
    icon: 'Tv',
    credits: 5,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      videoAsset: true
    },
    defaultParameters: {
      mode: 'standard', // standard | pro
      resolution: '1080p' // 1080p | 2k | 4k
    }
  },

  video_merger: {
    id: 'video_merger',
    name: 'Multi-Clip Video Sequencer',
    category: 'Video Enhancement',
    description: 'Assemble and concatenate 2-5 generated video clips with transitions (dissolve, cut, fade, slide).',
    badge: 'Timeline Sequencer',
    icon: 'Sliders',
    credits: 1,
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {
      clips: true
    },
    defaultParameters: {
      transition: 'dissolve',
      fps: 24,
      keep_audio: true
    }
  },

  run_any_llm: {
    id: 'run_any_llm',
    name: 'Uncensored LLM Cognition',
    category: 'Cognition & Audio',
    description: 'Consult uncensored language & vision models (Grok, Hermes-3 405B, Qwen 27B) for prompt engineering and planning.',
    badge: 'AI Cognition',
    icon: 'Brain',
    credits: 1,
    models: ['grok', 'hermes-3-405b', 'euryale-70b', 'qwen-27b'],
    defaultModel: 'grok',
    supportsAspectRatios: false,
    supportsTiers: false,
    inputsRequired: {},
    defaultParameters: {
      max_tokens: 2048,
      system_prompt: 'You are KEYSTONE Creative Prompt Cognition. Expand user ideas into rich cinematic details with camera, lighting, and composition specifics.'
    }
  }
};

export const OPTIONAL_PLAYBOOKS: PlaybookTemplate[] = [
  {
    id: 'freedom',
    name: 'Freedom & YOLO (Open Canvas)',
    description: 'Unconstrained creative freedom. Complete access to every model, parameter, resolution, and seed.',
    icon: 'Infinity',
    starterPrompt: 'A hyper-detailed cinematic portrait under dramatic neon volumetric lighting, shallow depth of field, 8k resolution, raw photo aesthetic.',
    recommendedTool: 'by_prompt',
    defaultAspect: '16:9',
    parameters: { guidance: 6.5, steps: 30 }
  },
  {
    id: 'design',
    name: 'Industrial & Digital Design',
    description: 'Industrial design prototypes, UI/UX systems, architectural visualization, and high-craft product rendering.',
    icon: 'Layers',
    starterPrompt: 'Minimalist ergonomic luxury headphone design, matte obsidian finish with brushed titanium accents, soft studio rim lighting, 8k.',
    recommendedTool: 'by_prompt',
    defaultAspect: '16:9',
    parameters: { quality: 'master' }
  },
  {
    id: 'content',
    name: 'Social Media & Content Creation',
    description: 'Eye-catching reels, viral visual hooks, thumbnails, and dynamic multi-angle brand assets.',
    icon: 'Smartphone',
    starterPrompt: 'Dynamic fashion model walking down a futuristic rain-slicked Tokyo street, neon reflection puddles, 9:16 vertical video style.',
    recommendedTool: 'videogen',
    defaultAspect: '9:16',
    parameters: { duration: 5 }
  },
  {
    id: 'cinema',
    name: 'Hollywood Cinema & Film',
    description: 'Anamorphic widescreen shots, cinematic camera tracks, Kodak 2383 film look, and Hollywood color grading.',
    icon: 'Clapperboard',
    starterPrompt: 'Wide cinematic establishing shot of a remote desert research outpost during golden hour, dust particles caught in sunlight, 2.39:1 anamorphic.',
    recommendedTool: 'by_prompt',
    defaultAspect: '21:9',
    parameters: { quality: 'master' }
  },
  {
    id: 'portrait',
    name: 'Digital Persona & Avatar',
    description: 'Consistent character faces, portrait headshots, fashion photoshoots, and talking avatars.',
    icon: 'User',
    starterPrompt: 'Studio beauty portrait, high detailed skin texture, catchlights in eyes, soft beauty dish lighting, 85mm portrait lens.',
    recommendedTool: 'by_prompt',
    defaultAspect: '3:4',
    parameters: { quality: 'high' }
  }
];
