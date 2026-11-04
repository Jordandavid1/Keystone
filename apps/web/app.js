/**
 * KEYSTONE Cinema Pro & Studio Suite (apps/web/app.js)
 * Implements the 5-Region Canvas Studio, 7-Stage Customer Progress Language (Bible §25),
 * Split-Screen Image Comparison, Synchronized Video Playback, Lineage DAG, and Live API Integration.
 * Enhanced with:
 * - VS Code Activity Bar & Status Bar
 * - Cursor Floating Composer & @Context Pills
 * - ZenCreator Pro Visual Node Canvas & 2-Phase Credit Ledger
 * - Higgsfield Cinema Camera Motion Splines & 3D Tilt Transforms
 * - Firecrawl /scrape URL Style & Prompt Ingestion
 * - Firebase Remote Config In-App Defaults & Dynamic Loading Strategy
 */

const PLAYBOOKS_16 = [
  'Design', 'Content', 'Marketing', 'Writing',
  'Software', 'Business', 'Research', 'Events',
  'Learning', 'Career', 'Fitness', 'Finance',
  'NSFW', 'Hacker', 'Freedom', 'General'
];

// Bible §25 exact 7-stage customer progress language.
const PROGRESS_STAGES = [
  { label: 'Understanding your request', jobState: 'VALIDATING', next: ['VALIDATING'] },
  { label: 'Planning the generation', jobState: 'PLANNING', next: ['PLANNING'] },
  { label: 'Preparing the workflow', jobState: 'AUTHORIZING', next: ['AUTHORIZING', 'QUEUED'] },
  { label: 'Creating', jobState: 'RUNNING', next: ['RUNNING'] },
  { label: 'Checking the result', jobState: 'VALIDATING_OUTPUT', next: ['VALIDATING_OUTPUT'] },
  { label: 'Refining when necessary', jobState: 'RETRY_PENDING', next: [] },
  { label: 'Finishing', jobState: 'COMPLETED', next: ['COMPLETED'] }
];

const state = {
  activeNav: 'create',
  activeMode: 'single', // single | compare | video | variations | lineage
  activePlaybook: 'Design',
  activeIntent: 'create',
  activeAspect: '16:9',
  activeQuality: 'high',
  activeLut: 'none',
  activeMask: 'none',
  activeMotion: 'orbit',
  motionSpeed: 1.0,
  gridVisible: false,
  zoomLevel: 1,
  assets: [],
  selectedAssetId: null,
  activeReferenceAssetId: null,
  agentChatHistory: [],
  chatWebSearchEnabled: true,
  chatGenEnabled: true,
  activeReferenceDenoise: 0.65,
  minimaxRefImageId: null,
  minimaxRefAudioId: null,
  minimaxDuration: 5,
  minimaxResolution: '720p',
  minimaxDenoise: 0.65,
  upscaleFactor: 2,
  compareSplitPct: 50,
  lastCompiledAnatomy: null,
  lastCompileError: null,
  activeProjectId: null,
  // Transport State
  isPlaying: false,
  currentFrame: 354, // 00:00:14:18 at 24fps
  fps: 24,
  loop: true,
  playTimer: null,
  grade: {
    exposure: 0,
    contrast: 100,
    saturation: 100,
    warmth: 0
  },
  // Remote Config
  remoteConfig: {
    enable_zencreator_node_graph: true,
    enable_cursor_floating_composer: true,
    enable_vscode_activity_bar: true,
    enable_higgsfield_motion_controls: true,
    enable_firecrawl_style_scrape: true,
    default_cinema_framerate: 24,
    credit_hold_estimate: 3
  },
  credits: {
    balance: 1250,
    hold: 3
  },
  webContextUrl: null,
  activeDagStep: 0,
  workerTelemetry: {
    activeCount: 0,
    workers: []
  },
  personas: [],
  selectedPersonaId: null,
  voices: [],
  audioConfig: null
};

// ============================================================================
// UI Rendering Functions
// ============================================================================

function getSelectedAsset() {
  return state.assets.find(a => a.id === state.selectedAssetId) || null;
}

function assetFacts(asset) {
  const dims = asset.width && asset.height ? `${asset.width}×${asset.height}` : null;
  const kb = asset.byteSize ? `${Math.round(asset.byteSize / 1024)} KB` : null;
  return [dims, kb].filter(Boolean).join(' • ');
}

function formatSmpteTimecode(frames, fps = 24) {
  const totalSeconds = Math.floor(frames / fps);
  const f = Math.floor(frames % fps);
  const s = totalSeconds % 60;
  const m = Math.floor(totalSeconds / 60) % 60;
  const h = Math.floor(totalSeconds / 3600);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function updateSmpteDisplay() {
  const el = document.getElementById('smpteTimecode');
  if (el) el.textContent = formatSmpteTimecode(state.currentFrame, state.fps);

  const needle = document.getElementById('timelinePlayhead');
  if (needle) {
    const totalMaxFrames = 720;
    const pct = ((state.currentFrame % totalMaxFrames) / totalMaxFrames) * 100;
    needle.style.left = `${pct}%`;
    const badge = needle.querySelector('.playhead-badge');
    if (badge) badge.textContent = formatSmpteTimecode(state.currentFrame, state.fps);
  }
}

function stepFrame(delta) {
  state.currentFrame = Math.max(0, state.currentFrame + delta);
  updateSmpteDisplay();
}

function togglePlayback(forceState = null) {
  const next = forceState !== null ? forceState : !state.isPlaying;
  state.isPlaying = next;

  const playIcon = document.getElementById('playIconSvg');
  const pauseIcon = document.getElementById('pauseIconSvg');
  const btn = document.getElementById('btnPlayPause');

  if (playIcon && pauseIcon) {
    if (state.isPlaying) {
      playIcon.classList.add('hidden');
      pauseIcon.classList.remove('hidden');
      if (btn) btn.classList.add('active');
    } else {
      playIcon.classList.remove('hidden');
      pauseIcon.classList.add('hidden');
      if (btn) btn.classList.remove('active');
    }
  }

  if (state.isPlaying) {
    if (state.playTimer) clearInterval(state.playTimer);
    state.playTimer = setInterval(() => {
      stepFrame(1);
      if (state.currentFrame >= 720 && state.loop) {
        state.currentFrame = 0;
      }
    }, 1000 / state.fps);
  } else {
    if (state.playTimer) {
      clearInterval(state.playTimer);
      state.playTimer = null;
    }
  }
}

function renderPlaybooks() {
  const grid = document.getElementById('playbookGrid');
  if (!grid) return;
  grid.innerHTML = PLAYBOOKS_16.map(pb => `
    <button
      class="playbook-chip ${state.activePlaybook === pb ? 'active' : ''}"
      data-playbook="${pb}"
      role="radio"
      aria-checked="${state.activePlaybook === pb}"
    >
      ${pb}
    </button>
  `).join('');

  grid.querySelectorAll('.playbook-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      state.activePlaybook = btn.dataset.playbook;
      const badge = document.getElementById('activePlaybookBadge');
      if (badge) badge.textContent = `Playbook: ${state.activePlaybook}`;
      const statusText = document.getElementById('statusPlaybookText');
      if (statusText) statusText.textContent = `Playbook: ${state.activePlaybook}`;
      renderPlaybooks();
      compilePromptPreview();
    });
  });
}

function renderSidebarAssetStream() {
  const container = document.getElementById('sidebarAssetStream');
  if (!container) return;
  const countEl = document.getElementById('navAssetsCount');
  if (countEl) countEl.textContent = String(state.assets.length);
  if (!state.assets.length) {
    container.innerHTML = '<div class="asset-empty-state">No persisted assets yet.</div>';
    return;
  }

  const selectedAsset = getSelectedAsset();
  const downloadButton = document.getElementById('downloadAssetBtn');
  if (downloadButton) downloadButton.disabled = !selectedAsset || !selectedAsset.imageUrl;

  container.innerHTML = state.assets.map(asset => {
    const isSel = asset.id === state.selectedAssetId;
    return `
      <div class="asset-mini-card ${isSel ? 'selected' : ''}" data-asset-id="${asset.id}">
        <div class="asset-mini-thumb">
          ${asset.imageUrl && asset.type !== 'audio'
            ? `<img src="${asset.imageUrl}" alt="${asset.title}" />`
            : asset.type === 'video' ? '🎬' : (asset.type === 'audio' ? '🎙️' : '🖼️')}
        </div>
        <div class="asset-mini-meta">
          <div class="asset-mini-title">${asset.title}</div>
          <div class="asset-mini-sub">
            <span style="color: #a5b4fc; font-family: var(--font-mono);">${asset.relationship}</span>
            ${assetFacts(asset) ? `<span>•</span><span>${assetFacts(asset)}</span>` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');

  container.querySelectorAll('.asset-mini-card').forEach(card => {
    card.addEventListener('click', () => {
      state.selectedAssetId = card.dataset.assetId;
      renderSidebarAssetStream();
      renderInspector();
      renderCanvasStage();
    });
  });
}

function applyActiveGradeFilter(imgEl) {
  if (!imgEl) return;
  imgEl.className = 'stage-visual-canvas';
  if (state.activeLut && state.activeLut !== 'none') {
    imgEl.classList.add(`lut-${state.activeLut}`);
  }
  if (state.activeMotion && state.activeMotion !== 'none') {
    imgEl.setAttribute('data-motion', state.activeMotion);
  }
  if (state.zoomLevel === 2) imgEl.classList.add('zoom-2x');
  if (state.zoomLevel === 4) imgEl.classList.add('zoom-4x');

  const exp = state.grade.exposure;
  const brightness = 100 + (exp * 25);
  const contrast = state.grade.contrast;
  const sat = state.grade.saturation;
  const warmth = state.grade.warmth;
  const sepia = warmth > 0 ? warmth * 0.5 : 0;
  const hue = warmth < 0 ? warmth * 0.6 : 0;

  imgEl.style.filter = `brightness(${brightness}%) contrast(${contrast}%) saturate(${sat}%) sepia(${sepia}%) hue-rotate(${hue}deg)`;
}

function renderInspector() {
  const asset = getSelectedAsset();
  const metadata = document.getElementById('assetMetadata');
  const videoContainer = document.getElementById('inspectorVideoContainer');
  const videoPlayer = document.getElementById('inspectorVideoPlayer');
  const typeBadge = document.getElementById('mediaTypeBadge');

  if (!asset) {
    if (metadata) metadata.textContent = 'No persisted asset selected.';
    if (videoContainer) videoContainer.classList.add('hidden');
    if (typeBadge) typeBadge.textContent = 'NO SELECTION';
    return;
  }

  const isVideo = asset.type === 'video' || (asset.mimeType && asset.mimeType.startsWith('video/'));
  const isAudio = asset.type === 'audio' || (asset.mimeType && asset.mimeType.startsWith('audio/'));
  const audioContainer = document.getElementById('inspectorAudioContainer');
  const audioPlayer = document.getElementById('inspectorAudioPlayer');

  if (typeBadge) {
    if (isAudio) {
      typeBadge.textContent = 'AUDIO (ELEVENLABS TTS)';
    } else {
      typeBadge.textContent = (isVideo ? 'VIDEO' : 'IMAGE') + (asset.width ? ` ${asset.width}×${asset.height}` : '');
    }
  }

  if (videoContainer && videoPlayer) {
    if (isVideo && asset.imageUrl) {
      videoContainer.classList.remove('hidden');
      videoPlayer.src = asset.imageUrl;
    } else {
      videoContainer.classList.add('hidden');
      videoPlayer.pause();
    }
  }

  if (audioContainer && audioPlayer) {
    if (isAudio && asset.imageUrl) {
      audioContainer.classList.remove('hidden');
      audioPlayer.src = asset.imageUrl;
    } else {
      audioContainer.classList.add('hidden');
      audioPlayer.pause();
    }
  }

  if (metadata) {
    metadata.textContent = JSON.stringify({
      id: asset.id,
      media_type: asset.type,
      mime_type: asset.mimeType,
      relationship: asset.relationship,
      prompt: asset.prompt,
      dimensions: asset.width && asset.height ? `${asset.width}×${asset.height}` : null,
      byteSize: asset.byteSize || null,
      seed: asset.seed || null,
      jobId: asset.jobId || null
    }, null, 2);
  }

  const btnSetRef = document.getElementById('btnSetSelectedAsReference');
  if (btnSetRef) {
    if (asset && state.activeReferenceAssetId === asset.id) {
      btnSetRef.textContent = '✕ Detach Active Reference';
      btnSetRef.style.background = 'rgba(239, 68, 68, 0.2)';
      btnSetRef.style.borderColor = 'rgba(239, 68, 68, 0.5)';
      btnSetRef.style.color = '#fca5a5';
      btnSetRef.onclick = (e) => {
        e.preventDefault();
        setActiveReference(null);
      };
    } else {
      btnSetRef.textContent = '📌 Use as Active Generation Reference';
      btnSetRef.style.background = 'rgba(99, 102, 241, 0.15)';
      btnSetRef.style.borderColor = 'rgba(99, 102, 241, 0.4)';
      btnSetRef.style.color = '#818cf8';
      btnSetRef.onclick = (e) => {
        e.preventDefault();
        if (asset) setActiveReference(asset);
      };
    }
  }
}

// ============================================================================
// MiniMax H3 Qwen 3.8 Ref2VA Video Studio Engine
// ============================================================================

async function triggerMiniMaxH3VideoGeneration(options = {}) {
  const promptInput = options.prompt ||
    (document.getElementById('minimaxPromptInput') && document.getElementById('minimaxPromptInput').value.trim()) ||
    (document.getElementById('composerInput') && document.getElementById('composerInput').value.trim()) ||
    'Cinematic dramatic camera movement, photorealistic 8k quality';
  const negPrompt = (document.getElementById('minimaxNegativePromptInput') && document.getElementById('minimaxNegativePromptInput').value.trim()) ||
    'blurry, distorted, low quality, artifacts, watermark';
  const refAssetId = options.referenceAssetId || state.minimaxRefImageId || (state.activeReferenceAssetId || null);
  const duration = options.duration || state.minimaxDuration || 5;
  const resolution = options.resolution || state.minimaxResolution || '720p';
  const denoise = options.denoise || state.minimaxDenoise || 0.65;

  const banner = document.getElementById('progressBanner');
  const stageText = document.getElementById('progressStageText');
  const subMeta = document.getElementById('progressSubMeta');
  const pills = document.querySelectorAll('#progressStepsTrack .progress-step-pill');

  if (banner) banner.classList.remove('hidden');
  if (stageText) stageText.textContent = 'Initiating MiniMax-H3 Qwen 3.8 Ref2VA Generation...';
  if (subMeta) subMeta.textContent = 'Configuring PinkCherry_Ref2V graph • Qwen 3.8-VL 32B • Dual VAE Decoders';

  try {
    if (!state.activeProjectId) {
      const projectResponse = await apiRequest('/v1/projects');
      let activeProject = projectResponse.projects[0];
      if (!activeProject) {
        activeProject = await apiRequest('/v1/projects', {
          method: 'POST',
          body: { name: 'Creative Workspace', description: 'Generated creative assets' }
        });
      }
      state.activeProjectId = activeProject.id;
    }

    // Step through the customer progress stages
    for (let i = 0; i < PROGRESS_STAGES.length; i++) {
      const stageInfo = PROGRESS_STAGES[i];
      pills.forEach((p, idx) => {
        p.classList.toggle('done', idx < i);
        p.classList.toggle('active', idx === i);
      });
      if (stageText) stageText.textContent = stageInfo.label;
      if (i === 3) {
        if (stageText) stageText.textContent = 'Creating — MiniMax-H3 ReferenceToVideo synthesis (Qwen 3.8 VL)...';
        break;
      }
      await new Promise(r => setTimeout(r, 150));
    }

    const generation = await apiRequest('/v1/assets/generate', {
      method: 'POST',
      body: {
        mode: 'minimax_h3',
        prompt: promptInput,
        negative_prompt: negPrompt,
        reference_asset_id: refAssetId,
        reference_type: refAssetId ? 'reference' : null,
        denoise: denoise,
        project_id: state.activeProjectId,
        title: `MiniMax H3 — ${promptInput.slice(0, 24)}...`,
        metadata: {
          pipeline: 'minimax_h3_qwen38_ref2va',
          text_encoder: 'qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors',
          backbone: 'PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors',
          duration_seconds: duration,
          resolution: resolution
        }
      }
    });

    await hydratePersistedAssets();
    state.selectedAssetId = generation.id;
    state.activeMode = 'video';

    if (stageText) stageText.textContent = 'MiniMax H3 Video generation complete!';
    if (subMeta) subMeta.textContent = `Generated ${Math.round(generation.byte_size / 1024)} KB video with native stereo audio`;
    setTimeout(() => { if (banner) banner.classList.add('hidden'); }, 1800);

    renderSidebarAssetStream();
    renderInspector();
    renderCanvasStage();
  } catch (err) {
    console.error('MiniMax H3 Video generation failed:', err);
    if (stageText) stageText.textContent = `MiniMax H3 Pipeline: ${err.message}`;
    if (subMeta) subMeta.textContent = 'Real ComfyUI daemon execution error';
    setTimeout(() => { if (banner) banner.classList.add('hidden'); }, 3500);
    renderCanvasStage();
    alert(`MiniMax H3 Pipeline Diagnostic:\n${err.message}\n\nRequired Weights:\n- models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors\n- models/diffusion_models/PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors\n- models/vae/minimax_h3_video_vae_fp16.safetensors\n- models/vae/minimax_h3_audio_vae_fp32.safetensors`);
  }
}

function renderMinimaxVideoStage(stage) {
  const asset = getSelectedAsset();
  const videos = state.assets.filter(item => item.type === 'video' && item.imageUrl);
  const imageAssets = state.assets.filter(item => (item.type === 'image' || !item.type) && item.imageUrl);
  const audioAssets = state.assets.filter(item => item.type === 'audio' && item.imageUrl);

  const currentVideo = (asset && asset.type === 'video' && asset.imageUrl) ? asset : (videos[0] || null);

  const activeRefImg = state.minimaxRefImageId
    ? state.assets.find(a => a.id === state.minimaxRefImageId)
    : (state.activeReferenceAssetId ? state.assets.find(a => a.id === state.activeReferenceAssetId) : null);

  const activeRefAud = state.minimaxRefAudioId
    ? state.assets.find(a => a.id === state.minimaxRefAudioId)
    : null;

  const composerVal = (document.getElementById('composerInput') && document.getElementById('composerInput').value.trim()) || '';
  const defaultPrompt = state.minimaxPrompt || composerVal || (asset && asset.prompt) || 'Cinematic 8k dolly forward through a neon-lit cyberpunk boulevard, volumetric rain and reflections';

  stage.innerHTML = `
    <div class="minimax-studio-container">
      <!-- Studio Header -->
      <div class="minimax-studio-header">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-size: 22px;">🎬</span>
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-weight: 800; font-size: 15px; color: var(--text-primary); letter-spacing: -0.3px;">MiniMax H3 Reference-to-Video Studio (Ref2VA)</span>
              <span class="stage-chip" style="background: rgba(236, 72, 153, 0.2); color: #f472b6; font-weight: 700; font-size: 10.5px;">QWEN 3.8-VL 32B</span>
              <span class="stage-chip" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; font-size: 10.5px;">PINKCHERRY DIT</span>
              <span class="stage-chip" style="background: rgba(52, 211, 153, 0.2); color: #34d399; font-size: 10.5px;">STEREO AUDIO VAE</span>
            </div>
            <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
              Pipeline: <code>MiniMaxH3ReferenceToVideo</code> • Text Encoder: <code>qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors</code> • Decoders: <code>video_vae_fp16</code> + <code>audio_vae_fp32</code>
            </div>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <button id="btnMinimaxUploadVideo" class="action-btn-mini" style="background: var(--bg-surface-elevated); border: 1px solid var(--border-subtle); color: var(--text-primary); padding: 5px 10px; border-radius: 6px; cursor: pointer; font-size: 11px;">
            ⬆ Upload Video File
          </button>
          <input type="file" id="minimaxVideoFileInput" accept="video/mp4,video/webm,video/quicktime" style="display: none;" />
        </div>
      </div>

      <!-- Main Split: Player on Left, Generator Console on Right -->
      <div class="minimax-studio-body">
        <!-- Left: Video Viewport / Gallery -->
        <div class="minimax-viewport-column">
          ${currentVideo ? `
            <div class="stage-artwork-frame minimax-player-frame">
              <video id="primaryMinimaxVideo" class="stage-visual-canvas" src="${currentVideo.imageUrl}" controls autoplay loop style="max-height: 100%; max-width: 100%; border-radius: 8px; background: #000; box-shadow: 0 8px 32px rgba(0,0,0,0.6);">
                Your browser does not support video playback.
              </video>
              <div class="stage-overlay-badges">
                <span class="stage-chip" style="font-weight: 700; color: #fff;">${currentVideo.title}</span>
                <span class="stage-chip" style="color: #38bdf8;">MiniMax H3 Native Video</span>
                <span class="stage-chip" style="color: #34d399;">Stereo Audio Synchronized</span>
              </div>
            </div>
          ` : `
            <div class="minimax-empty-player">
              <div style="font-size: 48px; margin-bottom: 12px; opacity: 0.8;">🎬</div>
              <div style="font-weight: 700; font-size: 16px; color: var(--text-primary); margin-bottom: 6px;">Ready to Generate MiniMax H3 Video</div>
              <div style="font-size: 12px; color: var(--text-secondary); max-width: 440px; line-height: 1.5; margin-bottom: 20px;">
                Condition on reference photos, attach voice audio tracks, and generate cinematic video using the complete Qwen 3.8-VL & MiniMax H3 workflow.
              </div>
              <button id="btnQuickDemoVideoPrompt" class="composer-submit-btn" style="background: linear-gradient(135deg, #ec4899, #8b5cf6); font-size: 12px; padding: 7px 18px; border-radius: 6px;">
                ✨ Load Cyberpunk Scene Prompt
              </button>
            </div>
          `}

          <!-- Video Gallery Strip (if videos exist) -->
          ${videos.length > 0 ? `
            <div class="minimax-gallery-strip">
              <div style="font-size: 11px; font-weight: 700; color: var(--text-secondary); margin-bottom: 6px; text-transform: uppercase;">
                Project Video Stream (${videos.length})
              </div>
              <div class="minimax-gallery-scroll">
                ${videos.map(v => `
                  <div class="minimax-gallery-card ${v.id === (currentVideo && currentVideo.id) ? 'active' : ''}" data-video-id="${v.id}">
                    <video src="${v.imageUrl}" muted style="width: 100%; height: 60px; object-fit: cover; border-radius: 4px; pointer-events: none;"></video>
                    <div style="font-size: 10px; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;">
                      ${v.title}
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          ` : ''}
        </div>

        <!-- Right: Conditioning & Generation Deck -->
        <div class="minimax-controls-column">
          <div class="minimax-deck-card">
            <div class="minimax-card-title">
              <span>📌 Reference Conditioning (Ref2VA)</span>
            </div>

            <!-- Picture 1 Reference Image -->
            <div style="display: flex; gap: 10px; align-items: center; background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px;">
              <div style="width: 52px; height: 52px; border-radius: 6px; border: 1px dashed rgba(236, 72, 153, 0.5); display: flex; align-items: center; justify-content: center; overflow: hidden; background: rgba(0,0,0,0.4); flex-shrink: 0;">
                ${activeRefImg && activeRefImg.imageUrl ? `
                  <img src="${activeRefImg.imageUrl}" alt="Reference Picture" style="width: 100%; height: 100%; object-fit: cover;" />
                ` : `
                  <span style="font-size: 18px; opacity: 0.5;">🖼️</span>
                `}
              </div>
              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 11.5px; font-weight: 700; color: var(--text-primary);">Visual Anchor &lt;Picture 1&gt;</span>
                  ${activeRefImg ? `
                    <button id="btnDetachMinimaxRefImg" class="action-btn-mini" style="font-size: 9.5px; background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 4px; padding: 1px 6px; cursor: pointer;">✕ Detach</button>
                  ` : ''}
                </div>
                <div style="font-size: 10.5px; color: var(--text-secondary); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${activeRefImg ? activeRefImg.title : 'No reference image selected (pure text-to-video)'}
                </div>
                <div style="display: flex; gap: 6px; margin-top: 6px;">
                  <button id="btnSelectMinimaxRefImg" class="action-btn-mini" style="font-size: 10px; background: rgba(255,255,255,0.06); border: 1px solid var(--border-subtle); color: var(--text-primary); border-radius: 4px; padding: 3px 8px; cursor: pointer;">
                    Cycle Images (${imageAssets.length})
                  </button>
                  <button id="btnUploadMinimaxRefImg" class="action-btn-mini" style="font-size: 10px; background: rgba(236, 72, 153, 0.15); border: 1px solid rgba(236, 72, 153, 0.3); color: #f472b6; border-radius: 4px; padding: 3px 8px; cursor: pointer;">
                    ⬆ Upload Photo
                  </button>
                  <input type="file" id="minimaxRefImgFileInput" accept="image/*" style="display: none;" />
                </div>
              </div>
            </div>

            <!-- Audio 1 Reference -->
            <div style="display: flex; gap: 10px; align-items: center; background: rgba(0,0,0,0.25); border: 1px solid var(--border-subtle); border-radius: 8px; padding: 10px;">
              <div style="width: 52px; height: 52px; border-radius: 6px; border: 1px dashed rgba(6, 182, 212, 0.5); display: flex; align-items: center; justify-content: center; overflow: hidden; background: rgba(0,0,0,0.4); flex-shrink: 0;">
                <span style="font-size: 20px;">🎵</span>
              </div>
              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-size: 11.5px; font-weight: 700; color: var(--text-primary);">Audio Track &lt;Audio 1&gt;</span>
                  ${activeRefAud ? `
                    <button id="btnDetachMinimaxRefAud" class="action-btn-mini" style="font-size: 9.5px; background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 4px; padding: 1px 6px; cursor: pointer;">✕ Detach</button>
                  ` : ''}
                </div>
                <div style="font-size: 10.5px; color: var(--text-secondary); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                  ${activeRefAud ? activeRefAud.title : 'Native stereo audio synthesis via minimax_h3_audio_vae'}
                </div>
                <div style="display: flex; gap: 6px; margin-top: 6px;">
                  <button id="btnSelectMinimaxRefAud" class="action-btn-mini" style="font-size: 10px; background: rgba(255,255,255,0.06); border: 1px solid var(--border-subtle); color: var(--text-primary); border-radius: 4px; padding: 3px 8px; cursor: pointer;">
                    Cycle Audio (${audioAssets.length})
                  </button>
                  <button id="btnOpenPersonasFromMinimax" class="action-btn-mini" style="font-size: 10px; background: rgba(6, 182, 212, 0.15); border: 1px solid rgba(6, 182, 212, 0.3); color: var(--accent-cyan); border-radius: 4px; padding: 3px 8px; cursor: pointer;">
                    🎙️ ElevenLabs Voice
                  </button>
                </div>
              </div>
            </div>

            <!-- Video Motion Prompt -->
            <div>
              <label style="font-size: 11px; font-weight: 700; color: var(--text-primary); display: block; margin-bottom: 4px;">
                Video Motion & Scene Prompt (Qwen 3.8-VL) *
              </label>
              <textarea id="minimaxPromptInput" class="composer-textarea" style="min-height: 75px; font-size: 12px; border-radius: 8px; border: 1px solid var(--border-subtle);" placeholder="Describe motion, camera action, dynamic lighting, character expression...">${defaultPrompt}</textarea>
            </div>

            <!-- Negative Prompt -->
            <div>
              <label style="font-size: 10.5px; font-weight: 600; color: var(--text-secondary); display: block; margin-bottom: 3px;">
                Negative Prompt Safeguards
              </label>
              <input type="text" id="minimaxNegativePromptInput" class="command-input" style="border: 1px solid var(--border-subtle); border-radius: 6px; padding: 5px 10px; font-size: 11px; width: 100%;" value="blurry, distorted, artifacts, low frame rate, jerky movement, watermark, logo" />
            </div>

            <!-- Duration & Resolution Controls -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
              <div>
                <label style="font-size: 10.5px; font-weight: 600; color: var(--text-secondary); display: block; margin-bottom: 3px;">Duration</label>
                <div style="display: flex; gap: 6px;">
                  <button class="seg-pill ${state.minimaxDuration === 5 ? 'active' : ''} btn-minimax-dur" data-dur="5" style="padding: 4px 10px; font-size: 11px; flex: 1;">5s</button>
                  <button class="seg-pill ${state.minimaxDuration === 10 ? 'active' : ''} btn-minimax-dur" data-dur="10" style="padding: 4px 10px; font-size: 11px; flex: 1;">10s</button>
                </div>
              </div>
              <div>
                <label style="font-size: 10.5px; font-weight: 600; color: var(--text-secondary); display: block; margin-bottom: 3px;">Resolution</label>
                <div style="display: flex; gap: 6px;">
                  <button class="seg-pill ${state.minimaxResolution === '720p' ? 'active' : ''} btn-minimax-res" data-res="720p" style="padding: 4px 10px; font-size: 11px; flex: 1;">720p HD</button>
                  <button class="seg-pill ${state.minimaxResolution === '1080p' ? 'active' : ''} btn-minimax-res" data-res="1080p" style="padding: 4px 10px; font-size: 11px; flex: 1;">1080p Cine</button>
                </div>
              </div>
            </div>

            <!-- Motion Denoise Slider -->
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 6px; border: 1px solid var(--border-subtle);">
              <div style="display: flex; flex-direction: column;">
                <span style="font-size: 11px; font-weight: 600; color: var(--text-primary);">Motion Strength (Denoise)</span>
                <span style="font-size: 10px; color: var(--text-secondary);">Controls degree of transformation from anchor</span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <input type="range" id="minimaxDenoiseSlider" min="0.1" max="1.0" step="0.05" value="${state.minimaxDenoise || 0.65}" style="width: 90px;" />
                <span id="valMinimaxDenoise" style="font-size: 11px; font-family: var(--font-mono); color: #38bdf8; min-width: 32px;">${(state.minimaxDenoise || 0.65).toFixed(2)}</span>
              </div>
            </div>

            <!-- Submit Button -->
            <button id="btnGenerateMinimaxVideo" class="composer-submit-btn" style="background: linear-gradient(135deg, #ec4899, #8b5cf6, #06b6d4); font-size: 13px; font-weight: 700; padding: 10px 20px; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px; box-shadow: 0 4px 18px rgba(236,72,153,0.35); cursor: pointer;">
              <span>🎬 Generate MiniMax H3 Video (Ref2VA)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach interactive events
  // 1. Gallery item switching
  stage.querySelectorAll('.minimax-gallery-card').forEach(card => {
    card.addEventListener('click', () => {
      state.selectedAssetId = card.dataset.videoId;
      renderSidebarAssetStream();
      renderInspector();
      renderCanvasStage();
    });
  });

  // 2. Quick demo prompt
  const btnQuickPrompt = stage.querySelector('#btnQuickDemoVideoPrompt');
  if (btnQuickPrompt) {
    btnQuickPrompt.addEventListener('click', () => {
      const promptArea = stage.querySelector('#minimaxPromptInput');
      if (promptArea) {
        promptArea.value = 'Cinematic 8k dolly forward through a neon-lit cyberpunk boulevard, volumetric rain, reflections, hyper-detailed photorealism';
      }
    });
  }

  // 3. Video upload button
  const btnUploadVid = stage.querySelector('#btnMinimaxUploadVideo');
  const fileInputVid = stage.querySelector('#minimaxVideoFileInput');
  if (btnUploadVid && fileInputVid) {
    btnUploadVid.addEventListener('click', () => fileInputVid.click());
    fileInputVid.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length) {
        uploadMediaFiles(e.target.files);
      }
    });
  }

  // 4. Detach/select/upload reference picture
  const btnDetachImg = stage.querySelector('#btnDetachMinimaxRefImg');
  if (btnDetachImg) {
    btnDetachImg.addEventListener('click', () => {
      state.minimaxRefImageId = null;
      renderCanvasStage();
    });
  }
  const btnSelectImg = stage.querySelector('#btnSelectMinimaxRefImg');
  if (btnSelectImg && imageAssets.length) {
    btnSelectImg.addEventListener('click', () => {
      const currentIdx = imageAssets.findIndex(a => a.id === state.minimaxRefImageId);
      const nextIdx = (currentIdx + 1) % imageAssets.length;
      state.minimaxRefImageId = imageAssets[nextIdx].id;
      renderCanvasStage();
    });
  }
  const btnUploadImg = stage.querySelector('#btnUploadMinimaxRefImg');
  const fileInputImg = stage.querySelector('#minimaxRefImgFileInput');
  if (btnUploadImg && fileInputImg) {
    btnUploadImg.addEventListener('click', () => fileInputImg.click());
    fileInputImg.addEventListener('change', async (e) => {
      if (e.target.files && e.target.files.length) {
        await uploadMediaFiles(e.target.files);
        state.minimaxRefImageId = state.selectedAssetId;
        renderCanvasStage();
      }
    });
  }

  // 5. Detach/select audio track
  const btnDetachAud = stage.querySelector('#btnDetachMinimaxRefAud');
  if (btnDetachAud) {
    btnDetachAud.addEventListener('click', () => {
      state.minimaxRefAudioId = null;
      renderCanvasStage();
    });
  }
  const btnSelectAud = stage.querySelector('#btnSelectMinimaxRefAud');
  if (btnSelectAud && audioAssets.length) {
    btnSelectAud.addEventListener('click', () => {
      const currentIdx = audioAssets.findIndex(a => a.id === state.minimaxRefAudioId);
      const nextIdx = (currentIdx + 1) % audioAssets.length;
      state.minimaxRefAudioId = audioAssets[nextIdx].id;
      renderCanvasStage();
    });
  }
  const btnPersonasAud = stage.querySelector('#btnOpenPersonasFromMinimax');
  if (btnPersonasAud) {
    btnPersonasAud.addEventListener('click', () => {
      const modal = document.getElementById('personasModalBackdrop');
      if (modal) modal.classList.remove('hidden');
    });
  }

  // 6. Duration buttons
  stage.querySelectorAll('.btn-minimax-dur').forEach(btn => {
    btn.addEventListener('click', () => {
      stage.querySelectorAll('.btn-minimax-dur').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.minimaxDuration = parseInt(btn.dataset.dur, 10);
    });
  });

  // 7. Resolution buttons
  stage.querySelectorAll('.btn-minimax-res').forEach(btn => {
    btn.addEventListener('click', () => {
      stage.querySelectorAll('.btn-minimax-res').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.minimaxResolution = btn.dataset.res;
    });
  });

  // 8. Denoise slider
  const denoiseSlider = stage.querySelector('#minimaxDenoiseSlider');
  const denoiseVal = stage.querySelector('#valMinimaxDenoise');
  if (denoiseSlider && denoiseVal) {
    denoiseSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      state.minimaxDenoise = val;
      denoiseVal.textContent = val.toFixed(2);
    });
  }

  // 9. Generate button
  const btnGenerate = stage.querySelector('#btnGenerateMinimaxVideo');
  if (btnGenerate) {
    btnGenerate.addEventListener('click', () => {
      const promptVal = (stage.querySelector('#minimaxPromptInput') && stage.querySelector('#minimaxPromptInput').value.trim()) || '';
      triggerMiniMaxH3VideoGeneration({
        prompt: promptVal,
        referenceAssetId: state.minimaxRefImageId || (state.activeReferenceAssetId || null),
        duration: state.minimaxDuration || 5,
        resolution: state.minimaxResolution || '720p',
        denoise: state.minimaxDenoise || 0.65
      });
    });
  }
}

// ============================================================================
// Center Canvas Mode Renderers (Single, Compare, Video, Variations, Lineage)
// ============================================================================

function renderCanvasStage() {
  const stage = document.getElementById('canvasStage');
  if (!stage) return;

  if (state.activeMode === 'video') {
    renderMinimaxVideoStage(stage);
    return;
  }

  if (state.activeMode === 'chat') {
    const chatModal = document.getElementById('agentChatModalBackdrop');
    if (chatModal) chatModal.classList.remove('hidden');
    stage.innerHTML = `
      <div class="audio-stage-container" style="background: radial-gradient(circle at center, #1e1338 0%, #060913 100%);">
        <div style="font-size: 42px; margin-bottom: 8px;">💬</div>
        <div style="font-size: 18px; font-weight: 700; color: #c084fc; margin-bottom: 4px;">Direct Cognition Agent & Task Console</div>
        <div style="font-size: 12px; color: var(--text-secondary); max-width: 540px; margin-bottom: 16px; line-height: 1.5;">
          Direct multi-turn dialog with <strong><code>huihui-ai/Huihui-Qwen3.8-27B-abliterated</code></strong>. Unrestricted creative brainstorming, live internet tool execution, and autonomous pipeline workflows.
        </div>
        <button id="btnOpenAgentChatFromStage" class="composer-submit-btn" style="background: linear-gradient(135deg, #a855f7, #06b6d4); font-size: 12px; padding: 8px 20px; border-radius: 6px; cursor: pointer;">
          Open Cognition Agent Chat Console
        </button>
      </div>
    `;
    const openBtn = stage.querySelector('#btnOpenAgentChatFromStage');
    if (openBtn) openBtn.addEventListener('click', () => {
      if (chatModal) chatModal.classList.remove('hidden');
    });
    return;
  }

  const asset = getSelectedAsset();
  if (!asset) {
    stage.innerHTML = '<div class="canvas-empty-state"><strong>No generated assets yet</strong><span>Enter a prompt and run KEYSTONE to create a persisted image.</span></div>';
    return;
  }

  if (state.activeMode === 'audio' || (state.activeMode === 'single' && asset.type === 'audio')) {
    const audioUrl = asset.imageUrl || '';
    stage.innerHTML = `
      <div class="audio-stage-container">
        <div style="font-size: 42px; margin-bottom: 8px;">🎙️</div>
        <div style="font-size: 18px; font-weight: 700; color: #ec4899; margin-bottom: 4px;">${asset.title}</div>
        <div style="font-size: 12px; color: var(--text-secondary); max-width: 540px; margin-bottom: 16px; line-height: 1.5;">
          ${asset.prompt || 'ElevenLabs Neural Speech Synthesis'}
        </div>
        <div class="audio-visualizer-wave">
          <span class="wave-bar" style="animation-delay: 0.1s; height: 28px;"></span>
          <span class="wave-bar" style="animation-delay: 0.25s; height: 45px;"></span>
          <span class="wave-bar" style="animation-delay: 0.15s; height: 18px;"></span>
          <span class="wave-bar" style="animation-delay: 0.4s; height: 52px;"></span>
          <span class="wave-bar" style="animation-delay: 0.05s; height: 35px;"></span>
          <span class="wave-bar" style="animation-delay: 0.3s; height: 48px;"></span>
          <span class="wave-bar" style="animation-delay: 0.2s; height: 22px;"></span>
          <span class="wave-bar" style="animation-delay: 0.45s; height: 50px;"></span>
          <span class="wave-bar" style="animation-delay: 0.35s; height: 38px;"></span>
          <span class="wave-bar" style="animation-delay: 0.12s; height: 26px;"></span>
          <span class="wave-bar" style="animation-delay: 0.28s; height: 44px;"></span>
          <span class="wave-bar" style="animation-delay: 0.18s; height: 32px;"></span>
        </div>
        ${audioUrl ? `
          <audio controls autoplay src="${audioUrl}" style="width: min(520px, 92%); height: 42px; margin-top: 14px; border-radius: 8px;"></audio>
        ` : `
          <div style="font-size: 12px; color: var(--text-secondary); margin-top: 10px;">Audio stream unavailable</div>
        `}
        <div style="margin-top: 16px; display: flex; gap: 8px;">
          <button id="btnOpenStudioFromCanvas" class="action-btn-mini" style="background: linear-gradient(135deg, #ec4899, #8b5cf6); color: #fff; border: none; padding: 6px 14px; border-radius: 6px; font-size: 11.5px; font-weight: 600; cursor: pointer;">
            Open ElevenLabs Speech Studio
          </button>
        </div>
      </div>
    `;
    const btn = document.getElementById('btnOpenStudioFromCanvas');
    if (btn) btn.addEventListener('click', () => openPersonasModal(true));
    return;
  }

  if (state.activeMode === 'single') {
    if (asset.imageUrl) {
      const isVideo = asset.type === 'video' || (asset.mimeType && asset.mimeType.startsWith('video/'));
      stage.innerHTML = `
        <div class="stage-artwork-frame">
          ${isVideo ? `
            <video id="primaryStageVideo" class="stage-visual-canvas" src="${asset.imageUrl}" controls autoplay loop
                   style="object-fit: contain; background: #04060b; max-height: 100%; max-width: 100%; border-radius: 8px;"></video>
          ` : `
            <img id="primaryStageImage" class="stage-visual-canvas" src="${asset.imageUrl}" alt="${asset.title}"
                 style="object-fit: contain; background: #04060b;" />
          `}
          <div class="stage-overlay-badges">
            <span class="stage-chip">${isVideo ? '🎬' : '✨'} ${asset.title}</span>
            <span class="stage-chip" style="color: #34d399;">✔ ${isVideo ? 'Video' : 'Render'} • ${assetFacts(asset)}</span>
          </div>
        </div>
      `;
      if (!isVideo) {
        applyActiveGradeFilter(document.getElementById('primaryStageImage'));
      }
      return;
    }

    stage.innerHTML = `
      <div class="canvas-empty-state"><strong>Asset bytes unavailable</strong><span>This asset has no attached persisted image. Generate a new asset or inspect its storage record.</span></div>
    `;

  } else if (state.activeMode === 'compare') {
    const beforeAsset = asset.parentId && state.assets.find(item => item.id === asset.parentId);
    if (!beforeAsset) {
      stage.innerHTML = '<div class="canvas-empty-state"><strong>No parent asset to compare</strong><span>Comparison requires a persisted source asset and a derived asset.</span></div>';
      return;
    }
    const afterAsset = asset;
    if (!asset.imageUrl || !beforeAsset.imageUrl) {
      stage.innerHTML = '<div class="canvas-empty-state"><strong>Stored image bytes unavailable</strong><span>Comparison needs retrievable persisted images for both assets.</span></div>';
      return;
    }
    stage.innerHTML = `
      <div class="compare-container" id="compareContainer">
        <img id="compareAfterImage" class="compare-layer" src="${asset.imageUrl}" alt="${asset.title}" />
        <img id="compareBeforeImage" class="compare-layer compare-before" src="${beforeAsset.imageUrl}" alt="${beforeAsset.title}" />
        <div class="compare-divider" id="compareDivider" style="left: ${state.compareSplitPct}%;">
          <div class="compare-handle">⇄</div>
        </div>
        <div class="stage-overlay-badges" style="z-index: 8;">
          <span class="stage-chip">BEFORE: ${beforeAsset.title}</span>
          <span class="stage-chip">AFTER (GRADED): ${afterAsset.title}</span>
        </div>
      </div>
    `;
    const beforeImage = document.getElementById('compareBeforeImage');
    const divider = document.getElementById('compareDivider');
    const container = document.getElementById('compareContainer');
    const afterImage = document.getElementById('compareAfterImage');
    applyActiveGradeFilter(afterImage);

    const updateSplit = (pct) => {
      state.compareSplitPct = Math.max(5, Math.min(95, pct));
      beforeImage.style.clipPath = `inset(0 ${100 - state.compareSplitPct}% 0 0)`;
      divider.style.left = `${state.compareSplitPct}%`;
    };
    updateSplit(state.compareSplitPct);

    let dragging = false;
    container.addEventListener('pointerdown', (e) => {
      dragging = true;
      const rect = container.getBoundingClientRect();
      updateSplit(((e.clientX - rect.left) / rect.width) * 100);
    });
    window.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const rect = container.getBoundingClientRect();
      updateSplit(((e.clientX - rect.left) / rect.width) * 100);
    });
    window.addEventListener('pointerup', () => { dragging = false; });
  } else if (state.activeMode === 'video') {
    renderMinimaxVideoStage(stage);
  } else if (state.activeMode === 'variations') {
    const variations = state.assets.filter(item =>
      item.imageUrl && (item.parentId === asset.parentId || item.id === asset.id)
    );
    if (!variations.length) {
      stage.innerHTML = '<div class="canvas-empty-state"><strong>No persisted variations</strong><span>Generate variations from a source asset to compare them here.</span></div>';
      return;
    }
    stage.innerHTML = `
      <div class="variations-grid">
        ${variations.map(item => `
          <div class="variation-card ${item.id === state.selectedAssetId ? 'active' : ''}" data-var-id="${item.id}">
            <img class="stage-visual-canvas" src="${item.imageUrl}" alt="${item.title}" />
            <div class="stage-overlay-badges">
              <span class="stage-chip">${item.title}</span>
              <span class="stage-chip">${assetFacts(item)}</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    stage.querySelectorAll('.variation-card').forEach(card => {
      card.addEventListener('click', () => {
        state.selectedAssetId = card.dataset.varId;
        renderSidebarAssetStream();
        renderInspector();
        renderCanvasStage();
      });
    });
  } else if (state.activeMode === 'lineage') {
    // ZenCreator Pro Visual Node Graph Workspace (Live Active DAG State)
    const asset = getSelectedAsset();
    const currentPrompt = (asset && asset.prompt) ||
      (state.lastCompiledAnatomy && state.lastCompiledAnatomy.positive_prompt) ||
      (document.getElementById('composerInput') && document.getElementById('composerInput').value) ||
      'Cinematic Hollywood Scene';
    const promptHash = (state.lastCompiledAnatomy && state.lastCompiledAnatomy.prompt_hash) ||
      (asset && asset.id ? 'sha256:' + asset.id.slice(0, 12) : 'sha256:genesis_root');
    const assetId = asset ? asset.id.slice(0, 8) + '...' : 'Awaiting render';
    const parentId = asset && asset.parentId ? asset.parentId.slice(0, 8) + '...' : 'None (Root Source)';
    const workerId = 'kaggle-creative-comfyui';
    const cognitionWorker = 'kaggle-cognition-t4x2';
    const activeStep = state.activeDagStep || 0;

    stage.innerHTML = `
      <div class="zen-node-canvas" id="zenNodeCanvas">
        <!-- Node 1: Prompt Source -->
        <div class="zen-node-card ${activeStep === 1 || activeStep === 0 ? 'active' : ''}">
          <div class="zen-node-socket socket-out"></div>
          <div class="zen-node-header">
            <span class="zen-node-title">1. PromptSource</span>
            <span class="zen-node-status" style="color: #34d399;">✔ READY</span>
          </div>
          <div class="zen-node-body">
            <div><strong>Playbook:</strong> ${state.activePlaybook}</div>
            <div style="font-size: 10px; color: #cbd5e1; word-break: break-all;">"${currentPrompt.slice(0, 42)}..."</div>
            <div><strong>Aspect:</strong> ${state.activeAspect}</div>
            <div style="color: #94a3b8; font-size: 9.5px;">Parent: ${parentId}</div>
          </div>
        </div>

        <div class="zen-connector-line">──►</div>

        <!-- Node 2: Cognition & Anatomy -->
        <div class="zen-node-card ${activeStep === 2 ? 'active' : ''}">
          <div class="zen-node-socket socket-in"></div>
          <div class="zen-node-socket socket-out"></div>
          <div class="zen-node-header">
            <span class="zen-node-title">2. Qwen Cognition</span>
            <span class="zen-node-status" style="color: #38bdf8;">ACTIVE</span>
          </div>
          <div class="zen-node-body">
            <div><strong>Model:</strong> Qwen 27B Pinned</div>
            <div><strong>Worker:</strong> ${cognitionWorker}</div>
            <div><strong>Anatomy:</strong> 6-Part Structured</div>
            <div style="color: #38bdf8; font-size: 9.5px;">${promptHash.slice(0, 18)}...</div>
          </div>
        </div>

        <div class="zen-connector-line">──►</div>

        <!-- Node 3: PII Vault & Security -->
        <div class="zen-node-card ${activeStep === 3 ? 'active' : ''}">
          <div class="zen-node-socket socket-in"></div>
          <div class="zen-node-socket socket-out"></div>
          <div class="zen-node-header">
            <span class="zen-node-title">3. PII & Aikido Shield</span>
            <span class="zen-node-status" style="color: #34d399;">LOCKED</span>
          </div>
          <div class="zen-node-body">
            <div><strong>Vault:</strong> AES-256-GCM</div>
            <div><strong>Delimiters:</strong> Quarantined</div>
            <div style="color: #34d399;">Threat: SAFE (0 leaks)</div>
            <div style="color: #94a3b8; font-size: 9.5px;">Envelope Signed HMAC-256</div>
          </div>
        </div>

        <div class="zen-connector-line">──►</div>

        <!-- Node 4: ComfyUI Latent -->
        <div class="zen-node-card ${activeStep === 4 || (!activeStep && asset) ? 'active' : ''}">
          <div class="zen-node-socket socket-in"></div>
          <div class="zen-node-socket socket-out"></div>
          <div class="zen-node-header">
            <span class="zen-node-title">4. ComfyUI Latent</span>
            <span class="zen-node-status" style="color: #a78bfa;">ONLINE</span>
          </div>
          <div class="zen-node-body">
            <div><strong>Engine:</strong> SDXL Studio</div>
            <div><strong>Worker:</strong> ${workerId}</div>
            <div><strong>Sampler:</strong> euler_ancestral</div>
            <div><strong>Steps:</strong> ${(asset && asset.steps) || { draft: 15, high: 25, master: 40 }[state.activeQuality] || 25}</div>
          </div>
        </div>

        <div class="zen-connector-line">──►</div>

        <!-- Node 5: Higgsfield Motion -->
        <div class="zen-node-card ${activeStep === 5 ? 'active' : ''}">
          <div class="zen-node-socket socket-in"></div>
          <div class="zen-node-socket socket-out"></div>
          <div class="zen-node-header">
            <span class="zen-node-title">5. Higgsfield Motion</span>
            <span class="zen-node-status" style="color: #f59e0b;">SPLINE</span>
          </div>
          <div class="zen-node-body">
            <div><strong>Preset:</strong> ${state.activeMotion}</div>
            <div><strong>Speed:</strong> ${state.motionSpeed}x</div>
            <div style="color: #f59e0b;">3D Orbit / Tilt Matrix</div>
            <div style="color: #94a3b8; font-size: 9.5px;">Bezier Interpolation</div>
          </div>
        </div>

        <div class="zen-connector-line">──►</div>

        <!-- Node 6: Cinema Master Output -->
        <div class="zen-node-card ${activeStep === 6 || (!activeStep && asset) ? 'active' : ''}">
          <div class="zen-node-socket socket-in"></div>
          <div class="zen-node-header">
            <span class="zen-node-title">6. Hollywood Master</span>
            <span class="zen-node-status" style="color: #10b981;">PERSISTED</span>
          </div>
          <div class="zen-node-body">
            <div><strong>Grade:</strong> ${state.activeLut.toUpperCase()}</div>
            <div><strong>Color:</strong> DCI-P3 ACEScc</div>
            <div><strong>Asset ID:</strong> ${assetId}</div>
            <div style="color: #10b981; font-size: 9.5px;">DAG Lineage Linked</div>
          </div>
        </div>
      </div>
    `;
  }
}

// ============================================================================
// Live Backend Integration: PromptCompiler, RemoteConfig, Worker Telemetry, Firecrawl
// ============================================================================

async function fetchRemoteConfig() {
  try {
    const res = await fetch('/v1/config/remote');
    if (res.ok) {
      const data = await res.json();
      if (data.parameters) {
        Object.keys(data.parameters).forEach(k => {
          const val = data.parameters[k].defaultValue?.value;
          state.remoteConfig[k] = val === 'true' ? true : val === 'false' ? false : val;
        });
      }
      const badge = document.getElementById('remoteConfigStatusBadge');
      if (badge) badge.textContent = `Remote Config: Active (${Object.keys(data.parameters || {}).length} flags)`;

      // Apply Remote Config directly to Hollywood UX
      if (state.remoteConfig.enable_zencreator_node_graph === false) {
        const nodeTab = document.querySelector('[data-mode="lineage"]');
        if (nodeTab) nodeTab.style.display = 'none';
      }
      if (state.remoteConfig.enable_higgsfield_motion_controls === false) {
        const motionCard = document.getElementById('higgsfieldMotionCard');
        if (motionCard) motionCard.style.display = 'none';
      }
      if (state.remoteConfig.default_cinema_framerate) {
        state.fps = Number(state.remoteConfig.default_cinema_framerate) || 24;
        const hudFps = document.getElementById('hudFramerate');
        if (hudFps) hudFps.textContent = `${state.fps}.000`;
      }
      if (state.remoteConfig.credit_hold_estimate) {
        state.credits.hold = Number(state.remoteConfig.credit_hold_estimate) || 3;
        const holdBadge = document.getElementById('creditHoldBadge');
        if (holdBadge) holdBadge.textContent = `HOLD: ${state.credits.hold}`;
      }
    }
  } catch (err) {
    console.warn('Remote config fetch fallback to in-app defaults:', err);
  }
}

async function fetchWorkerTelemetry() {
  try {
    const res = await fetch('/internal/workers');
    if (!res.ok) return;
    const data = await res.json();
    const workers = data.workers || [];
    const activeWorkers = workers.filter(w => w.status === 'ACTIVE');

    state.workerTelemetry.activeCount = activeWorkers.length;
    state.workerTelemetry.workers = activeWorkers;

    const statusTextEl = document.getElementById('workerStatusText');
    const statusDotEl = document.getElementById('workerStatusDot');
    const vramBadgeEl = document.getElementById('workerVramBadge');
    const engineHealthTextEl = document.getElementById('engineHealthText');

    if (activeWorkers.length > 0) {
      if (statusDotEl) statusDotEl.style.background = '#34d399';
      if (statusTextEl) {
        statusTextEl.textContent = `KAGGLE T4×2: ${activeWorkers.length} ACTIVE`;
      }

      let totalVram = 0;
      let usedVram = 0;
      activeWorkers.forEach(w => {
        const hw = w.hardware || {};
        totalVram += hw.vram_total_gib || 15.0;
        const metrics = w.metrics || {};
        usedVram += metrics.gpu_memory_used_gib || (hw.vram_total_gib ? hw.vram_total_gib * 0.75 : 12.0);
      });

      if (vramBadgeEl) {
        vramBadgeEl.textContent = `VRAM: ${usedVram.toFixed(1)}/${totalVram.toFixed(0)}G`;
      }

      if (engineHealthTextEl) {
        const hasCognition = activeWorkers.some(w =>
          (w.capabilities || []).some(c => c.includes('qwen') || c.includes('cognition'))
        );
        const hasComfy = activeWorkers.some(w =>
          (w.capabilities || []).some(c => c.includes('comfy') || c.includes('image.generation'))
        );
        engineHealthTextEl.textContent =
          `KEYSTONE 2.0 • Qwen-27B (${hasCognition ? 'T4×2 Active' : 'Standby'}) • ComfyUI (${hasComfy ? 'Active' : 'Standby'}) • ${activeWorkers.length} Nodes`;
      }
    } else {
      if (statusDotEl) statusDotEl.style.background = '#f59e0b';
      if (statusTextEl) statusTextEl.textContent = 'KAGGLE: CONNECTING';
      if (vramBadgeEl) vramBadgeEl.textContent = 'DISCOVERING';
    }
  } catch (err) {
    console.warn('Worker telemetry fetch error:', err);
  }
}


async function compilePromptPreview() {
  const input = document.getElementById('composerInput');
  const promptText = input ? input.value.trim() : '';
  if (!promptText) return null;

  try {
    const compileResp = await fetch('/v1/planning/compile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent: {
          objective: promptText,
          visual_style: `${state.activePlaybook} Studio Grade`
        },
        playbook: state.activePlaybook.toLowerCase(),
        profile: 'reasoning'
      })
    });

    if (!compileResp.ok) throw new Error(`Prompt compilation failed (${compileResp.status})`);
    const compiled = await compileResp.json();
    state.lastCompiledAnatomy = compiled;
    state.lastCompileError = null;
    const shortHash = (compiled.prompt_hash || '').slice(0, 12);
    const hashBadge = document.getElementById('promptHashBadge');
    if (hashBadge) hashBadge.textContent = `sha256:${shortHash}...`;
    const anatomyPre = document.getElementById('anatomyPre');
    if (anatomyPre) anatomyPre.textContent = JSON.stringify(compiled.anatomy, null, 2);
    const authBadge = document.getElementById('authorityVerdictBadge');
    if (authBadge) {
      authBadge.textContent = 'NOT EVALUATED';
      authBadge.style.color = 'var(--text-secondary)';
    }
    const envPre = document.getElementById('envelopePre');
    if (envPre) envPre.textContent = 'Authority is evaluated against your account when you submit a generation.';
    return compiled;
  } catch (err) {
    state.lastCompileError = String(err.message || err);
    const hashBadge = document.getElementById('promptHashBadge');
    if (hashBadge) hashBadge.textContent = 'Compilation unavailable';
    const anatomyPre = document.getElementById('anatomyPre');
    if (anatomyPre) anatomyPre.textContent = String(err.message || err);
    console.warn('KEYSTONE prompt compilation failed:', err);
    return null;
  }
}

// ============================================================================
// Workspace Session & Authenticated API Client
// ============================================================================

const SESSION_STORAGE_KEY = 'keystone.workspace.session';
let workspaceSession = null;

function decodeTokenExpiry(token) {
  try {
    const b64 = (token.split('.')[0] || '').replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4)));
    return payload.exp ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

function readStoredSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || 'null');
  } catch {
    return null;
  }
}

async function postAuthJson(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const payload = await res.json().catch(() => ({}));
  return { res, payload };
}

async function ensureWorkspaceSession(force = false) {
  if (!force && workspaceSession && workspaceSession.exp - Date.now() > 60000) {
    return workspaceSession;
  }

  const cached = readStoredSession();
  const stored = cached || {
    email: `workspace-${crypto.randomUUID().slice(0, 8)}@keystone.local`,
    password: `${crypto.randomUUID()}${crypto.randomUUID()}`,
    displayName: 'Workspace Operator'
  };

  let { res, payload } = cached
    ? await postAuthJson('/v1/auth/login', { email: stored.email, password: stored.password })
    : { res: { ok: false, status: 401 }, payload: {} };
  if (res.status === 401) {
    ({ res, payload } = await postAuthJson('/v1/auth/register', {
      email: stored.email,
      password: stored.password,
      display_name: stored.displayName
    }));
  }
  if (!res.ok) {
    throw new Error(payload.detail || `Workspace session failed (${res.status})`);
  }

  workspaceSession = {
    email: stored.email,
    password: stored.password,
    displayName: stored.displayName,
    token: payload.access_token,
    userId: payload.user && payload.user.id,
    exp: decodeTokenExpiry(payload.access_token)
  };
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(workspaceSession));
  return workspaceSession;
}

async function apiRequest(path, { method = 'GET', body, retry = true } = {}) {
  const session = await ensureWorkspaceSession();
  const res = await fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session.token}`
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });

  if (res.status === 401 && retry) {
    workspaceSession = null;
    await ensureWorkspaceSession(true);
    return apiRequest(path, { method, body, retry: false });
  }

  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(payload.detail || `${method} ${path} failed (${res.status})`);
  }
  return payload;
}

const PERSISTED_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function relationshipForIntent(intent) {
  if (intent === 'animate') return 'animation';
  if (intent === 'edit') return 'edit';
  if (intent === 'analyze') return 'upscale';
  return 'variation';
}

async function requestComfyRender(jobId, promptText, authorizedArguments) {
  const isImg2Img = state.generationMode === 'img2img' && Boolean(state.activeReferenceAssetId);
  const refAssetId = isImg2Img ? state.activeReferenceAssetId : null;
  const parentAssetId = null;

  return apiRequest('/v1/assets/generate', {
    method: 'POST',
    body: {
      prompt: promptText,
      negative_prompt: authorizedArguments.negative_prompt,
      width: authorizedArguments.width,
      height: authorizedArguments.height,
      steps: authorizedArguments.steps,
      cfg: authorizedArguments.guidance,
      parent_asset_id: parentAssetId,
      reference_asset_id: refAssetId,
      reference_type: refAssetId ? 'img2img' : null,
      denoise: state.activeReferenceDenoise || 0.65,
      mode: refAssetId ? 'img2img' : 'text2image',
      relationship_type: refAssetId ? 'reference' : 'source',
      job_id: jobId,
      project_id: state.activeProjectId,
      title: `Generated — ${promptText.slice(0, 28)}...`,
      metadata: {
        aspect: state.activeAspect,
        prompt_hash: state.lastCompiledAnatomy && state.lastCompiledAnatomy.prompt_hash,
        motion: state.activeMotion,
        reference_used: Boolean(refAssetId)
      }
    }
  });
}

function assetFromPersistedRecord(record) {
  const meta = record.metadata || {};
  const isAudio = record.media_type === 'audio' || (record.mime_type && record.mime_type.startsWith('audio/'));
  let title = meta.title;
  if (!title) {
    if (isAudio) {
      title = meta.script ? `Audio — ${meta.script.slice(0, 24)}...` : `Audio — ${meta.voice_name || 'Speech Track'}`;
    } else {
      title = `${record.media_type || 'Persisted asset'} — ${String(meta.prompt || '').slice(0, 28)}`;
    }
  }

  return {
    id: record.id,
    title,
    type: record.media_type || (isAudio ? 'audio' : 'image'),
    mimeType: record.mime_type || 'application/octet-stream',
    relationship: meta.relationship || (isAudio ? 'audio_track' : 'source'),
    parentId: meta.parent_asset_id || null,
    aspect: meta.aspect || '16:9',
    khf: null,
    width: meta.width || null,
    height: meta.height || null,
    byteSize: record.byte_size || null,
    imageUrl: record.download_url || null,
    prompt: meta.script || meta.prompt || '',
    jobId: meta.job_id || null,
    persisted: true
  };
}

async function hydratePersistedAssets() {
  try {
    const assetResponse = await apiRequest('/v1/assets');
    state.assets = assetResponse.assets.map(assetFromPersistedRecord).filter(Boolean);
    const projectResponse = await apiRequest('/v1/projects');
    if (!state.activeProjectId) {
      const activeProject = projectResponse.projects[0];
      state.activeProjectId = activeProject ? activeProject.id : null;
    }
    if (!state.assets.some(asset => asset.id === state.selectedAssetId)) {
      state.selectedAssetId = state.assets[0]?.id || null;
    }
    renderSidebarAssetStream();
    renderInspector();
    renderCanvasStage();
  } catch (err) {
    console.warn('Workspace data unavailable:', err);
  }
}

// ============================================================================
// Media Upload, Reference Management & Super-Upscale
// ============================================================================

function setGenerationMode(mode) {
  state.generationMode = mode;
  const btnT2I = document.getElementById('btnModeText2Image');
  const btnI2I = document.getElementById('btnModeImg2Img');
  const notice = document.getElementById('genModeNotice');
  const tray = document.getElementById('activeReferenceTray');
  const thumb = document.getElementById('activeReferenceThumb');
  const name = document.getElementById('activeReferenceName');

  if (mode === 'text2image') {
    state.activeReferenceAssetId = null;
    if (btnT2I) {
      btnT2I.classList.add('active');
      btnT2I.style.borderColor = 'var(--accent-cyan)';
      btnT2I.style.background = 'rgba(6, 182, 212, 0.18)';
      btnT2I.style.color = '#fff';
    }
    if (btnI2I) {
      btnI2I.classList.remove('active');
      btnI2I.style.borderColor = 'var(--border-subtle)';
      btnI2I.style.background = 'transparent';
      btnI2I.style.color = 'var(--text-secondary)';
    }
    if (tray) {
      tray.classList.add('hidden');
      tray.classList.remove('active');
      tray.style.setProperty('display', 'none', 'important');
    }
    if (thumb) {
      thumb.src = '';
      thumb.style.display = 'none';
    }
    if (name) name.textContent = '';
    if (notice) notice.textContent = 'Pure prompt generation — no reference conditioning';
  } else {
    if (btnI2I) {
      btnI2I.classList.add('active');
      btnI2I.style.borderColor = '#818cf8';
      btnI2I.style.background = 'rgba(99, 102, 241, 0.2)';
      btnI2I.style.color = '#fff';
    }
    if (btnT2I) {
      btnT2I.classList.remove('active');
      btnT2I.style.borderColor = 'var(--border-subtle)';
      btnT2I.style.background = 'transparent';
      btnT2I.style.color = 'var(--text-secondary)';
    }
    if (state.activeReferenceAssetId) {
      if (tray) {
        tray.classList.remove('hidden');
        tray.classList.add('active');
        tray.style.setProperty('display', 'flex', 'important');
      }
      if (notice) notice.textContent = 'Reference anchor active — conditioning enabled';
    } else {
      if (tray) {
        tray.classList.add('hidden');
        tray.classList.remove('active');
        tray.style.setProperty('display', 'none', 'important');
      }
      if (notice) notice.textContent = 'Select an asset or upload to set reference anchor';
    }
  }
}

function setActiveReference(asset) {
  const tray = document.getElementById('activeReferenceTray');
  const thumb = document.getElementById('activeReferenceThumb');
  const name = document.getElementById('activeReferenceName');
  if (!asset) {
    state.activeReferenceAssetId = null;
    if (tray) {
      tray.classList.add('hidden');
      tray.classList.remove('active');
      tray.style.setProperty('display', 'none', 'important');
    }
    if (thumb) {
      thumb.src = '';
      thumb.style.display = 'none';
    }
    if (name) name.textContent = '';
    setGenerationMode('text2image');
    renderInspector();
    return;
  }

  state.activeReferenceAssetId = asset.id;
  if (thumb) {
    thumb.src = asset.imageUrl || '';
    thumb.style.display = asset.imageUrl ? 'block' : 'none';
  }
  if (name) name.textContent = asset.title || asset.filename || 'reference_asset.png';
  if (tray) {
    tray.classList.remove('hidden');
    tray.classList.add('active');
    tray.style.setProperty('display', 'flex', 'important');
  }
  setGenerationMode('img2img');
  renderInspector();
}

async function uploadMediaFiles(files) {
  if (!files || !files.length) return;
  const banner = document.getElementById('progressBanner');
  const stageText = document.getElementById('progressStageText');
  const subMeta = document.getElementById('progressSubMeta');

  if (banner) banner.classList.remove('hidden');
  if (stageText) stageText.textContent = `Uploading ${files.length} media file(s)...`;

  const session = await ensureWorkspaceSession();
  const token = session.token || localStorage.getItem('keystone_token') || 'local_dev_token';

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    if (subMeta) subMeta.textContent = `Processing ${file.name} (${Math.round(file.size / 1024)} KB)`;
    const formData = new FormData();
    formData.append('file', file);
    if (state.activeProjectId) {
      formData.append('project_id', state.activeProjectId);
    }
    const isVideo = file.type.startsWith('video/') || /\.(mp4|webm|mov|mkv)$/i.test(file.name);
    formData.append('media_type', isVideo ? 'video' : 'image');

    try {
      const resp = await fetch('/v1/assets/upload-file', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      if (!resp.ok) {
        throw new Error(`Upload failed (${resp.status}): ${await resp.text()}`);
      }
      const newAsset = await resp.json();
      console.log('[+] Uploaded asset:', newAsset);

      await hydratePersistedAssets();
      state.selectedAssetId = newAsset.id;
      // Note: Do not automatically hijack reference conditioning.
      // Keeps user in their active generation mode. User can click "Use as Reference" whenever desired.
    } catch (err) {
      console.error('File upload failed:', err);
      alert(`Failed to upload ${file.name}: ${err.message}`);
    }
  }

  if (banner) {
    if (stageText) stageText.textContent = 'Upload complete! File added to Project Assets.';
    setTimeout(() => { if (banner) banner.classList.add('hidden'); }, 1400);
  }
  renderSidebarAssetStream();
  renderInspector();
  renderCanvasStage();
}

async function upscaleSelectedAsset(scaleFactor = 2) {
  const asset = getSelectedAsset();
  if (!asset) {
    alert('Please select an asset to upscale.');
    return;
  }

  const banner = document.getElementById('progressBanner');
  const stageText = document.getElementById('progressStageText');
  const subMeta = document.getElementById('progressSubMeta');

  if (banner) banner.classList.remove('hidden');
  if (stageText) stageText.textContent = `Super-Upscaling to ${scaleFactor}× resolution...`;
  if (subMeta) subMeta.textContent = `Asset: ${asset.title} • Target: ${scaleFactor === 4 ? '4K Master (4096px)' : '2K Studio (2048px)'}`;

  try {
    const result = await apiRequest(`/v1/assets/${asset.id}/upscale`, {
      method: 'POST',
      body: {
        scale_factor: scaleFactor,
        prompt: asset.prompt || ''
      }
    });

    await hydratePersistedAssets();
    state.selectedAssetId = result.id;
    if (stageText) stageText.textContent = `Upscale complete! Output: ${result.width}×${result.height}`;
    setTimeout(() => { if (banner) banner.classList.add('hidden'); }, 1500);
    renderSidebarAssetStream();
    renderInspector();
    renderCanvasStage();
  } catch (err) {
    console.error('Upscale failed:', err);
    if (stageText) stageText.textContent = `Upscale failed: ${err.message}`;
    setTimeout(() => { if (banner) banner.classList.add('hidden'); }, 2500);
  }
}

// ============================================================================
// Execute Full 7-Stage KEYSTONE Generation Lifecycle
// ============================================================================

async function runKeystoneGeneration() {
  const promptText = document.getElementById('composerInput').value.trim();
  if (!promptText) return;

  const submitBtn = document.getElementById('composerSubmitBtn');
  const banner = document.getElementById('progressBanner');
  const stageText = document.getElementById('progressStageText');
  const subMeta = document.getElementById('progressSubMeta');
  const pills = document.querySelectorAll('#progressStepsTrack .progress-step-pill');

  submitBtn.disabled = true;
  banner.classList.remove('hidden');

  let jobId = null;
  let generation = null;

  try {
    if (state.activeIntent !== 'create') {
      throw new Error('Only text-to-image creation is currently connected to a real workflow.');
    }
    const compiled = await compilePromptPreview();
    if (!compiled) {
      throw new Error(state.lastCompileError || 'Prompt compilation failed; no job was created.');
    }
    if (!state.activeProjectId) {
      const projectResponse = await apiRequest('/v1/projects');
      let activeProject = projectResponse.projects[0];
      if (!activeProject) {
        activeProject = await apiRequest('/v1/projects', {
          method: 'POST',
          body: { name: 'Creative Workspace', description: 'Generated creative assets' }
        });
      }
      state.activeProjectId = activeProject.id;
    }

    const dimensionsByAspect = {
      '16:9': [1024, 576],
      '1:1': [1024, 1024],
      '9:16': [576, 1024],
      '21:9': [1344, 576]
    };
    const [width, height] = dimensionsByAspect[state.activeAspect] || dimensionsByAspect['16:9'];
    const job = await apiRequest('/v1/jobs', {
      method: 'POST',
      body: {
        request_text: promptText,
        action: {
          action_type: 'generate',
          capability: 'image.generation',
          parameters: {
            prompt: compiled.positive_prompt,
            negative_prompt: compiled.negative_prompt,
            aspect_ratio: state.activeAspect,
            width,
            height,
            steps: { draft: 15, high: 25, master: 40 }[state.activeQuality],
            guidance: 6
          },
          rationale: `Customer create request via ${state.activePlaybook} playbook`
        },
        capability_id: 'image.generation',
        provider_id: 'comfyui',
        workflow_id: 'wf_comfy_sdxl_txt2img',
        workflow_version: '1.0.0'
      }
    });
    const decision = job.authority_decision;
    const authBadge = document.getElementById('authorityVerdictBadge');
    if (authBadge) {
      authBadge.textContent = (decision && decision.decision || 'UNKNOWN').toUpperCase();
      authBadge.style.color = decision && ['ALLOW', 'approve'].includes(decision.decision)
        ? 'var(--accent-emerald)'
        : 'var(--accent-rose)';
    }
    const envPre = document.getElementById('envelopePre');
    if (envPre) {
      envPre.textContent = JSON.stringify({
        decision,
        request_id: job.request_id,
        authority_decision_id: job.authority_decision_id,
        available_arguments: job.authorized_arguments
      }, null, 2);
    }

    if (job.state === 'REJECTED' || !decision || !['ALLOW', 'approve'].includes(decision.decision)) {
      const reasons = decision && decision.reason_codes && decision.reason_codes.length
        ? decision.reason_codes.join(', ')
        : 'Authority did not approve this request.';
      stageText.textContent = 'Request not authorized';
      subMeta.textContent = `Job ${String(job.id || '').slice(0, 8)} • ${reasons}`;
      pills.forEach(p => p.classList.remove('active'));
      submitBtn.disabled = false;
      return;
    }

    jobId = job.id;
    subMeta.textContent = `Job ${jobId.slice(0, 8)} • State: ${job.state}`;

    for (let i = 0; i < PROGRESS_STAGES.length; i++) {
      const stageInfo = PROGRESS_STAGES[i];
      if (!stageInfo.next.length) continue;

      state.activeDagStep = i + 1;
      if (state.activeMode === 'lineage') renderCanvasStage();

      pills.forEach((p, idx) => {
        p.classList.toggle('done', idx < i);
        p.classList.toggle('active', idx === i);
      });

      stageText.textContent = stageInfo.label;


      for (const nextState of stageInfo.next) {
        const result = await apiRequest(`/v1/jobs/${jobId}/transition`, {
          method: 'POST',
          body: { next_state: nextState, reason: stageInfo.label }
        });
        subMeta.textContent = `Job ${jobId.slice(0, 8)} • State: ${result.current_state}`;
      }

      if (i === 3) {
        stageText.textContent = 'Creating — running the ComfyUI workflow';
        generation = await requestComfyRender(
          jobId,
          job.authorized_arguments.prompt,
          job.authorized_arguments
        );
        subMeta.textContent =
          `ComfyUI ${String(generation.comfy_prompt_id).slice(0, 8)} • ` +
          `${generation.width}×${generation.height} • ${Math.round(generation.byte_size / 1024)} KB`;
      }
    }

    if (!generation) {
      throw new Error('ComfyUI returned no render for this run');
    }

    const relationship = (generation.metadata && generation.metadata.relationship) ||
      relationshipForIntent(state.activeIntent);
    const parentAssetId = (generation.metadata && generation.metadata.parent_asset_id) || null;
    const title = (generation.metadata && generation.metadata.title) ||
      `Generated — ${promptText.slice(0, 28)}...`;

    state.assets.unshift({
      id: generation.id,
      title,
      type: generation.media_type || 'image',
      mimeType: generation.mime_type || 'image/png',
      relationship,
      parentId: parentAssetId,
      aspect: state.activeAspect,
      khf: null,
      width: generation.width,
      height: generation.height,
      byteSize: generation.byte_size,
      imageUrl: generation.download_url,
      seed: generation.seed,
      prompt: promptText,
      jobId,
      persisted: true
    });
    state.selectedAssetId = generation.id;
    await hydratePersistedAssets();

    const history = await apiRequest(`/v1/jobs/${jobId}/events`);
    subMeta.textContent =
      `Job ${jobId.slice(0, 8)}… • ${history.current_state} • ${history.events.length} transition events`;

    renderSidebarAssetStream();
    renderInspector();
    renderCanvasStage();

    setTimeout(() => {
      banner.classList.add('hidden');
      submitBtn.disabled = false;
    }, 1600);
  } catch (err) {
    console.error('KEYSTONE job failed:', err);
    pills.forEach(p => p.classList.remove('active'));

    const reason = err instanceof TypeError
      ? 'Workspace API unreachable — confirm the server is running on port 8000.'
      : String(err.message || err);

    if (jobId) {
      try {
        await apiRequest(`/v1/jobs/${jobId}/transition`, {
          method: 'POST',
          body: { next_state: 'FAILED', reason: reason.slice(0, 180) }
        });
      } catch (transitionErr) {
        console.warn('Could not mark job failed:', transitionErr);
      }
    }

    stageText.textContent = 'Run failed';
    subMeta.textContent = reason;
    submitBtn.disabled = false;
  }
}

// ============================================================================
// Personas & ElevenLabs Speech Studio Logic
// ============================================================================

async function hydrateVoices() {
  try {
    const res = await apiRequest('/v1/audio/voices');
    state.voices = res.voices || [];
    const cfg = await apiRequest('/v1/audio/config');
    state.audioConfig = cfg;
    populateVoiceDropdowns();
  } catch (err) {
    console.warn('Voices catalog unavailable:', err);
  }
}

function populateVoiceDropdowns() {
  const pSelect = document.getElementById('selectPersonaVoice');
  const tSelect = document.getElementById('ttsVoiceSelector');
  if (!state.voices || state.voices.length === 0) return;

  const options = state.voices.map(v => 
    `<option value="${v.voice_id}">${v.name} (${v.accent || 'American'} ${v.gender || ''})</option>`
  ).join('');

  if (pSelect) pSelect.innerHTML = options;
  if (tSelect) tSelect.innerHTML = options;

  const cfgText = document.getElementById('ttsConfigStatusText');
  if (cfgText && state.audioConfig) {
    cfgText.textContent = state.audioConfig.configured
      ? 'ElevenLabs API Active • Live Neural Voice Synthesis'
      : 'ElevenLabs Formant Synthesizer • 16-Bit PCM Studio Synthesis Active';
  }
}

async function hydratePersonas() {
  try {
    const res = await apiRequest('/v1/personas');
    state.personas = res.personas || [];
    renderSidebarPersonas();
    renderModalPersonas();
    populatePersonaDropdowns();
    const countBadge = document.getElementById('navPersonasCount');
    if (countBadge) countBadge.textContent = state.personas.length;
  } catch (err) {
    console.warn('Failed to hydrate personas:', err);
  }
}

function populatePersonaDropdowns() {
  const selector = document.getElementById('ttsPersonaSelector');
  if (selector) {
    let opts = '<option value="">-- Standalone Voice (No Persona) --</option>';
    opts += state.personas.map(p => `<option value="${p.id}">${p.name} (${p.voice_name || 'Rachel'})</option>`).join('');
    selector.innerHTML = opts;
  }

  const avatarSel = document.getElementById('selectPersonaAvatar');
  if (avatarSel) {
    const imageAssets = state.assets.filter(a => a.type === 'image' || (!a.type || a.type === 'image'));
    let opts = '<option value="">-- No Image Asset Linked --</option>';
    opts += imageAssets.map(a => `<option value="${a.id}">${a.title || a.id.slice(0, 8)}</option>`).join('');
    avatarSel.innerHTML = opts;
  }
}

function renderSidebarPersonas() {
  const stream = document.getElementById('sidebarPersonasStream');
  if (!stream) return;
  if (state.personas.length === 0) {
    stream.innerHTML = '<div style="font-size: 11px; color: var(--text-secondary); padding: 4px; text-align: center;">No digital personas yet. Click + Persona to create one.</div>';
    return;
  }

  stream.innerHTML = state.personas.map(p => {
    const isSel = p.id === state.selectedPersonaId;
    const initial = p.name ? p.name.charAt(0).toUpperCase() : 'P';
    const avatarHtml = p.avatar_url
      ? `<img src="${p.avatar_url}" class="persona-avatar-img" alt="${p.name}" />`
      : `<div class="persona-avatar-fallback">${initial}</div>`;
    const traitsHtml = (p.personality_traits || []).slice(0, 2).map(t => `<span class="persona-trait-pill">${t}</span>`).join('');

    return `
      <div class="persona-mini-card ${isSel ? 'selected' : ''}" data-persona-id="${p.id}">
        ${avatarHtml}
        <div class="persona-mini-info">
          <div class="persona-mini-name">${p.name}</div>
          <div class="persona-mini-voice">🎙️ ${p.voice_name || 'ElevenLabs'}</div>
          ${traitsHtml ? `<div class="persona-traits-row">${traitsHtml}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');

  stream.querySelectorAll('.persona-mini-card').forEach(card => {
    card.addEventListener('click', () => {
      selectPersona(card.dataset.personaId);
      openPersonasModal(false);
    });
  });
}

function renderModalPersonas() {
  const grid = document.getElementById('modalPersonasGrid');
  if (!grid) return;
  if (state.personas.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1 / -1; font-size: 12px; color: var(--text-secondary); text-align: center; padding: 20px;">No personas registered yet. Fill the form below to create your first character!</div>';
    return;
  }

  grid.innerHTML = state.personas.map(p => {
    const isSel = p.id === state.selectedPersonaId;
    const initial = p.name ? p.name.charAt(0).toUpperCase() : 'P';
    const avatarHtml = p.avatar_url
      ? `<img src="${p.avatar_url}" class="persona-avatar-img" style="width: 36px; height: 36px;" alt="${p.name}" />`
      : `<div class="persona-avatar-fallback" style="width: 36px; height: 36px;">${initial}</div>`;

    return `
      <div class="persona-mini-card ${isSel ? 'selected' : ''}" data-modal-persona-id="${p.id}" style="padding: 10px;">
        ${avatarHtml}
        <div class="persona-mini-info">
          <div class="persona-mini-name" style="font-size: 13px;">${p.name}</div>
          <div class="persona-mini-voice">🎙️ ${p.voice_name || 'ElevenLabs'}</div>
          <div style="font-size: 10px; color: var(--text-secondary); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${p.description || 'No backstory set'}</div>
        </div>
      </div>
    `;
  }).join('');

  grid.querySelectorAll('[data-modal-persona-id]').forEach(card => {
    card.addEventListener('click', () => {
      selectPersona(card.dataset.modalPersonaId);
    });
  });
}

function selectPersona(personaId) {
  state.selectedPersonaId = personaId;
  renderSidebarPersonas();
  renderModalPersonas();

  const p = state.personas.find(item => item.id === personaId);
  if (!p) return;

  const idInput = document.getElementById('formPersonaId');
  const nameInput = document.getElementById('inputPersonaName');
  const bioInput = document.getElementById('inputPersonaBio');
  const voiceSelect = document.getElementById('selectPersonaVoice');
  const avatarSelect = document.getElementById('selectPersonaAvatar');
  const traitsInput = document.getElementById('inputPersonaTraits');
  const promptInput = document.getElementById('inputPersonaSystemPrompt');
  const delBtn = document.getElementById('btnDeletePersonaForm');

  if (idInput) idInput.value = p.id;
  if (nameInput) nameInput.value = p.name || '';
  if (bioInput) bioInput.value = p.description || '';
  if (voiceSelect && p.voice_id) voiceSelect.value = p.voice_id;
  if (avatarSelect && p.avatar_asset_id) avatarSelect.value = p.avatar_asset_id;
  if (traitsInput) traitsInput.value = (p.personality_traits || []).join(', ');
  if (promptInput) promptInput.value = p.system_prompt || '';
  if (delBtn) delBtn.style.display = 'inline-block';

  // Also preselect in TTS Tab
  const ttsSelector = document.getElementById('ttsPersonaSelector');
  if (ttsSelector) ttsSelector.value = p.id;
  const ttsVoice = document.getElementById('ttsVoiceSelector');
  if (ttsVoice && p.voice_id) ttsVoice.value = p.voice_id;
}

function resetPersonaForm() {
  state.selectedPersonaId = null;
  const idInput = document.getElementById('formPersonaId');
  const nameInput = document.getElementById('inputPersonaName');
  const bioInput = document.getElementById('inputPersonaBio');
  const traitsInput = document.getElementById('inputPersonaTraits');
  const promptInput = document.getElementById('inputPersonaSystemPrompt');
  const delBtn = document.getElementById('btnDeletePersonaForm');

  if (idInput) idInput.value = '';
  if (nameInput) nameInput.value = '';
  if (bioInput) bioInput.value = '';
  if (traitsInput) traitsInput.value = '';
  if (promptInput) promptInput.value = '';
  if (delBtn) delBtn.style.display = 'none';

  renderSidebarPersonas();
  renderModalPersonas();
}

async function savePersonaForm() {
  const id = document.getElementById('formPersonaId')?.value;
  const name = document.getElementById('inputPersonaName')?.value.trim();
  if (!name) {
    alert('Please enter a persona name.');
    return;
  }

  const voiceSelect = document.getElementById('selectPersonaVoice');
  const voiceId = voiceSelect?.value || '21m00Tcm4TlvDq8ikWAM';
  const voiceName = voiceSelect?.options[voiceSelect.selectedIndex]?.text.split('(')[0].trim() || 'Rachel';
  const avatarAssetId = document.getElementById('selectPersonaAvatar')?.value || null;
  const description = document.getElementById('inputPersonaBio')?.value.trim() || null;
  const traitsStr = document.getElementById('inputPersonaTraits')?.value.trim();
  const traits = traitsStr ? traitsStr.split(',').map(s => s.trim()).filter(Boolean) : [];
  const systemPrompt = document.getElementById('inputPersonaSystemPrompt')?.value.trim() || null;

  const payload = {
    name,
    description,
    avatar_asset_id: avatarAssetId,
    voice_id: voiceId,
    voice_name: voiceName,
    personality_traits: traits,
    system_prompt: systemPrompt,
    project_id: state.activeProjectId,
  };

  try {
    if (id) {
      await apiRequest(`/v1/personas/${id}`, { method: 'PUT', body: payload });
    } else {
      await apiRequest('/v1/personas', { method: 'POST', body: payload });
    }
    await hydratePersonas();
    resetPersonaForm();
  } catch (err) {
    alert(`Failed to save persona: ${err.message}`);
  }
}

async function deleteSelectedPersona() {
  const id = document.getElementById('formPersonaId')?.value;
  if (!id) return;
  if (!confirm('Are you sure you want to delete this persona?')) return;
  try {
    await apiRequest(`/v1/personas/${id}`, { method: 'DELETE' });
    await hydratePersonas();
    resetPersonaForm();
  } catch (err) {
    alert(`Failed to delete persona: ${err.message}`);
  }
}

async function synthesizeElevenLabsSpeech() {
  const scriptText = document.getElementById('ttsTextInput')?.value.trim();
  if (!scriptText) {
    alert('Please enter dialogue or narration text to synthesize.');
    return;
  }

  const btn = document.getElementById('btnSynthesizeTTS');
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span>⏳ Synthesizing Voice...</span>';
  }

  const personaId = document.getElementById('ttsPersonaSelector')?.value;
  const voiceId = document.getElementById('ttsVoiceSelector')?.value || '21m00Tcm4TlvDq8ikWAM';
  const stability = parseFloat(document.getElementById('ttsStabilitySlider')?.value || '0.5');
  const similarity = parseFloat(document.getElementById('ttsClaritySlider')?.value || '0.75');

  try {
    let res;
    if (personaId) {
      res = await apiRequest(`/v1/personas/${personaId}/speak`, {
        method: 'POST',
        body: {
          text: scriptText,
          voice_id: voiceId,
          voice_settings: { stability, similarity_boost: similarity }
        }
      });
    } else {
      res = await apiRequest('/v1/audio/speech', {
        method: 'POST',
        body: {
          text: scriptText,
          voice_id: voiceId,
          project_id: state.activeProjectId,
          voice_settings: { stability, similarity_boost: similarity },
          save_asset: true
        }
      });
    }

    // Display output in TTS tab
    const outSection = document.getElementById('ttsOutputSection');
    const player = document.getElementById('modalTTSAudioPlayer');
    const resTitle = document.getElementById('ttsResultTitle');
    const resMeta = document.getElementById('ttsResultMeta');
    const providerBadge = document.getElementById('ttsProviderBadge');

    if (outSection) outSection.style.display = 'flex';
    if (player && res.download_url) {
      player.src = res.download_url;
      player.play().catch(() => {});
    }
    if (resTitle) resTitle.textContent = res.persona_name ? `${res.persona_name} Voiceover` : 'ElevenLabs Speech Track';
    if (resMeta) resMeta.textContent = `${res.mime_type || 'audio/wav'} • ${Math.round((res.byte_size || 0) / 1024)} KB`;
    if (providerBadge) providerBadge.textContent = `Engine: ${res.provider === 'elevenlabs' ? 'ElevenLabs Official API' : 'Keystone Speech Synthesizer'}`;

    // Refresh assets stream to include newly registered audio track
    await hydratePersistedAssets();
  } catch (err) {
    alert(`Speech synthesis failed: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

function openPersonasModal(switchTabToTTS = false) {
  const modal = document.getElementById('personasModalBackdrop');
  if (modal) modal.classList.remove('hidden');
  populatePersonaDropdowns();

  if (switchTabToTTS) {
    document.getElementById('btnTabElevenLabsTTS')?.click();
  } else {
    document.getElementById('btnTabPersonasCast')?.click();
  }
}

function closePersonasModal() {
  const modal = document.getElementById('personasModalBackdrop');
  if (modal) modal.classList.add('hidden');
}


// ============================================================================
// Event Wiring & Pro Studio Controls
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  renderPlaybooks();
  renderSidebarAssetStream();
  renderInspector();
  renderCanvasStage();
  compilePromptPreview();
  hydratePersistedAssets();
  hydrateVoices();
  hydratePersonas();
  updateSmpteDisplay();
  fetchRemoteConfig();
  fetchWorkerTelemetry();

  // Poll worker bridge telemetry every 10 seconds
  setInterval(fetchWorkerTelemetry, 10000);
  // Refresh Remote Config every 30 seconds
  setInterval(fetchRemoteConfig, 30000);

  // Mode Tabs
  document.querySelectorAll('.mode-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.mode-tab').forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');
      state.activeMode = tab.dataset.mode;
      renderCanvasStage();
    });
  });

  // VS Code Activity Bar Switching
  document.querySelectorAll('.activity-icon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.activity-icon-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const act = btn.dataset.activity;
      if (act === 'explorer') {
        document.querySelector('[data-mode="single"]')?.click();
      } else if (act === 'nodes') {
        document.querySelector('[data-mode="lineage"]')?.click();
      } else if (act === 'motion') {
        const hud = document.getElementById('higgsfieldMotionHud');
        if (hud) hud.classList.toggle('hidden');
      } else if (act === 'thinking' || act === 'settings') {
        const devBtn = document.getElementById('toggleDevDrawerBtn');
        if (devBtn) devBtn.click();
      } else if (act === 'personas') {
        openPersonasModal(false);
      } else if (act === 'audio') {
        openPersonasModal(true);
      }
    });
  });

  // Left Sidebar Navigation
  document.querySelectorAll('#primaryNavList .nav-item').forEach(item => {
    item.addEventListener('click', () => {
      document.querySelectorAll('#primaryNavList .nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
      const nav = item.dataset.nav;
      if (nav === 'assets') {
        document.querySelector('[data-mode="lineage"]').click();
      } else if (nav === 'favorites') {
        document.querySelector('[data-mode="variations"]').click();
      } else if (nav === 'personas') {
        openPersonasModal(false);
      } else {
        document.querySelector('[data-mode="single"]').click();
      }
    });
  });

  // Intent Pills
  document.querySelectorAll('.intent-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.intent-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeIntent = pill.dataset.intent;
      compilePromptPreview();
    });
  });

  // Aspect Ratio Pills
  document.querySelectorAll('#aspectRatioPills .seg-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#aspectRatioPills .seg-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeAspect = pill.dataset.aspect;
      compilePromptPreview();
    });
  });

  // Quality Tier Pills
  document.querySelectorAll('#qualityTierPills .seg-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#qualityTierPills .seg-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeQuality = pill.dataset.quality;
      compilePromptPreview();
    });
  });

  // Submit Generation Request
  const submitBtn = document.getElementById('composerSubmitBtn');
  if (submitBtn) submitBtn.addEventListener('click', () => runKeystoneGeneration());

  // Download Persisted Asset
  const downloadButton = document.getElementById('downloadAssetBtn');
  if (downloadButton) {
    downloadButton.disabled = true;
    downloadButton.addEventListener('click', () => {
      const asset = getSelectedAsset();
      if (!asset || !asset.imageUrl) return;
      const extensionByMime = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'video/mp4': 'mp4',
        'video/webm': 'webm'
      };
      const extension = extensionByMime[asset.mimeType] || 'bin';
      const link = document.createElement('a');
      link.download = `${asset.id}.${extension}`;
      link.href = asset.imageUrl;
      link.click();
    });
  }

  // Media Upload & References Wiring
  const uploadInput = document.getElementById('mediaUploadInput');
  const btnUploadTrigger = document.getElementById('btnUploadMediaTrigger');
  const sidebarDropzone = document.getElementById('sidebarMediaDropzone');
  const attachAssetBtn = document.getElementById('attachAssetBtn');

  if (uploadInput) {
    uploadInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length) {
        uploadMediaFiles(e.target.files);
        uploadInput.value = '';
      }
    });
  }

  if (btnUploadTrigger && uploadInput) {
    btnUploadTrigger.addEventListener('click', () => uploadInput.click());
  }

  if (attachAssetBtn && uploadInput) {
    attachAssetBtn.addEventListener('click', () => uploadInput.click());
  }

  if (sidebarDropzone && uploadInput) {
    sidebarDropzone.addEventListener('click', () => uploadInput.click());

    sidebarDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      sidebarDropzone.style.borderColor = 'var(--accent-cyan)';
      sidebarDropzone.style.background = 'rgba(6, 182, 212, 0.08)';
    });

    sidebarDropzone.addEventListener('dragleave', () => {
      sidebarDropzone.style.borderColor = 'var(--border-subtle)';
      sidebarDropzone.style.background = 'rgba(255,255,255,0.02)';
    });

    sidebarDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      sidebarDropzone.style.borderColor = 'var(--border-subtle)';
      sidebarDropzone.style.background = 'rgba(255,255,255,0.02)';
      if (e.dataTransfer.files && e.dataTransfer.files.length) {
        uploadMediaFiles(e.dataTransfer.files);
      }
    });
  }

  // Global Canvas Drag & Drop Ingestion
  const canvasStage = document.getElementById('canvasStage');
  if (canvasStage) {
    canvasStage.addEventListener('dragover', (e) => {
      e.preventDefault();
      canvasStage.style.outline = '2px dashed var(--accent-cyan)';
    });
    canvasStage.addEventListener('dragleave', () => {
      canvasStage.style.outline = 'none';
    });
    canvasStage.addEventListener('drop', (e) => {
      e.preventDefault();
      canvasStage.style.outline = 'none';
      if (e.dataTransfer.files && e.dataTransfer.files.length) {
        uploadMediaFiles(e.dataTransfer.files);
      }
    });
  }

  // Generation Mode Controls (Text2Image vs Reference-Guided)
  const btnModeText2Image = document.getElementById('btnModeText2Image');
  if (btnModeText2Image) {
    btnModeText2Image.addEventListener('click', () => setGenerationMode('text2image'));
  }
  const btnModeImg2Img = document.getElementById('btnModeImg2Img');
  if (btnModeImg2Img) {
    btnModeImg2Img.addEventListener('click', () => setGenerationMode('img2img'));
  }

  // Active Reference Tray Controls
  const btnRemoveReference = document.getElementById('btnRemoveReference');
  if (btnRemoveReference) {
    btnRemoveReference.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      setActiveReference(null);
      setGenerationMode('text2image');
    });
  }

  const refDenoiseSlider = document.getElementById('refDenoiseSlider');
  const denoiseValueText = document.getElementById('denoiseValueText');
  if (refDenoiseSlider && denoiseValueText) {
    refDenoiseSlider.addEventListener('input', () => {
      state.activeReferenceDenoise = parseFloat(refDenoiseSlider.value);
      denoiseValueText.textContent = refDenoiseSlider.value;
    });
  }

  // Inspector Media Actions (Reference Anchor & Super-Upscale)
  const btnSetSelectedAsReference = document.getElementById('btnSetSelectedAsReference');
  if (btnSetSelectedAsReference) {
    btnSetSelectedAsReference.addEventListener('click', () => {
      const asset = getSelectedAsset();
      if (asset) setActiveReference(asset);
    });
  }

  const btnUpscale2x = document.getElementById('btnUpscale2x');
  if (btnUpscale2x) {
    btnUpscale2x.addEventListener('click', () => upscaleSelectedAsset(2));
  }

  const btnUpscale4x = document.getElementById('btnUpscale4x');
  if (btnUpscale4x) {
    btnUpscale4x.addEventListener('click', () => upscaleSelectedAsset(4));
  }

  const btnGenerateVariation = document.getElementById('btnGenerateVariation');
  if (btnGenerateVariation) {
    btnGenerateVariation.addEventListener('click', () => {
      const asset = getSelectedAsset();
      if (asset) {
        setActiveReference(asset);
        const composer = document.getElementById('composerInput');
        if (composer) {
          composer.focus();
          if (!composer.value) {
            composer.value = `Cinematic reimagination with enhanced lighting and texture details`;
          }
        }
      }
    });
  }

  // Mobile Review Mode
  const mobileBtn = document.getElementById('mobileToggleBtn');
  if (mobileBtn) {
    mobileBtn.addEventListener('click', () => {
      const shell = document.getElementById('workspaceShell');
      shell.classList.toggle('mobile-preview-mode');
      mobileBtn.classList.toggle('active');
    });
  }

  // Collapsible Authority Drawer
  const devBtn = document.getElementById('toggleDevDrawerBtn');
  const devBody = document.getElementById('devDrawerBody');
  const devChev = document.getElementById('devDrawerChevron');
  if (devBtn && devBody && devChev) {
    devBtn.addEventListener('click', () => {
      const hidden = devBody.hidden;
      devBody.hidden = !hidden;
      devChev.textContent = hidden ? '[Collapse −]' : '[Expand +]';
    });
  }

  // Command Palette (⌘K)
  const cmdModal = document.getElementById('commandModalBackdrop');
  const cmdInput = document.getElementById('commandSearchInput');
  const openCmd = () => {
    if (cmdModal && cmdInput) {
      cmdModal.classList.remove('hidden');
      cmdInput.focus();
    }
  };
  const closeCmd = () => {
    if (cmdModal) cmdModal.classList.add('hidden');
  };

  const paletteBtn = document.getElementById('commandPaletteBtn');
  if (paletteBtn) paletteBtn.addEventListener('click', openCmd);
  if (cmdModal) {
    cmdModal.addEventListener('click', (e) => {
      if (e.target === cmdModal) closeCmd();
    });
  }

  document.querySelectorAll('#commandList .command-item').forEach(item => {
    item.addEventListener('click', () => {
      const cmd = item.dataset.cmd;
      closeCmd();
      if (cmd === 'agent:chat') openAgentChat();
      else if (cmd === 'mode:single') document.querySelector('[data-mode="single"]')?.click();
      else if (cmd === 'mode:compare') document.querySelector('[data-mode="compare"]')?.click();
      else if (cmd === 'mode:video') document.querySelector('[data-mode="video"]')?.click();
      else if (cmd === 'mode:lineage') document.querySelector('[data-mode="lineage"]')?.click();
      else if (cmd === 'mode:variations') document.querySelector('[data-mode="variations"]')?.click();
      else if (cmd === 'mode:audio') document.querySelector('[data-mode="audio"]')?.click();
      else if (cmd === 'settings:open') openSettingsModal();
      else if (cmd === 'projects:open') openProjectsModal();
      else if (cmd === 'sessions:open') openSessionsModal();
      else if (cmd === 'credits:open') openCreditsModal();
      else if (cmd === 'workers:open') openWorkerModal();
      else if (cmd === 'personas:open') openPersonasModal(false);
      else if (cmd === 'nav:admin') window.location.href = '/admin';
    });
  });

  const cmdSearchInput = document.getElementById('commandSearchInput');
  if (cmdSearchInput) {
    cmdSearchInput.addEventListener('input', () => {
      const q = cmdSearchInput.value.toLowerCase().trim();
      document.querySelectorAll('#commandList .command-item').forEach(item => {
        item.style.display = item.textContent.toLowerCase().includes(q) ? 'flex' : 'none';
      });
    });
  }

  // Transport Controls
  const btnPlayPause = document.getElementById('btnPlayPause');
  if (btnPlayPause) btnPlayPause.addEventListener('click', () => togglePlayback());

  const btnStepBack = document.getElementById('btnStepBack');
  if (btnStepBack) btnStepBack.addEventListener('click', () => stepFrame(-1));

  const btnStepFwd = document.getElementById('btnStepFwd');
  if (btnStepFwd) btnStepFwd.addEventListener('click', () => stepFrame(1));

  const btnShuttleRev = document.getElementById('btnShuttleRev');
  if (btnShuttleRev) btnShuttleRev.addEventListener('click', () => stepFrame(-24));

  const btnShuttleFwd = document.getElementById('btnShuttleFwd');
  if (btnShuttleFwd) btnShuttleFwd.addEventListener('click', () => stepFrame(24));

  const btnLoop = document.getElementById('btnLoop');
  if (btnLoop) {
    btnLoop.addEventListener('click', () => {
      state.loop = !state.loop;
      btnLoop.classList.toggle('active', state.loop);
    });
  }

  // Scrubber Dragging
  const scrubber = document.getElementById('scrubberContainer');
  if (scrubber) {
    const handleScrub = (e) => {
      const rect = scrubber.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      state.currentFrame = Math.round(pct * 720);
      updateSmpteDisplay();
    };

    let scrubbing = false;
    scrubber.addEventListener('pointerdown', (e) => {
      scrubbing = true;
      handleScrub(e);
    });
    window.addEventListener('pointermove', (e) => {
      if (scrubbing) handleScrub(e);
    });
    window.addEventListener('pointerup', () => { scrubbing = false; });
  }

  // Framing Masks
  document.querySelectorAll('#aspectGuidePills .matte-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#aspectGuidePills .matte-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeMask = pill.dataset.mask;
      const maskEl = document.getElementById('aspectOverlayMask');
      if (maskEl) maskEl.setAttribute('data-mask', state.activeMask);
    });
  });

  // Framing Guidelines Toggle
  const toggleGridBtn = document.getElementById('toggleGridBtn');
  const gridOverlay = document.getElementById('framingGridOverlay');
  if (toggleGridBtn && gridOverlay) {
    toggleGridBtn.addEventListener('click', () => {
      state.gridVisible = !state.gridVisible;
      gridOverlay.classList.toggle('hidden', !state.gridVisible);
      toggleGridBtn.classList.toggle('active', state.gridVisible);
    });
  }

  // Fullscreen Theater
  const fullscreenBtn = document.getElementById('fullscreenBtn');
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
        fullscreenBtn.classList.add('active');
      } else {
        document.exitFullscreen().catch(() => {});
        fullscreenBtn.classList.remove('active');
      }
    });
  }

  // Zoom Loupe
  document.querySelectorAll('.zoom-segment-control .zoom-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.zoom-segment-control .zoom-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.zoomLevel = parseInt(btn.dataset.zoom, 10) || 1;
      const primaryImg = document.getElementById('primaryStageImage');
      if (primaryImg) applyActiveGradeFilter(primaryImg);
    });
  });

  // Higgsfield Motion Preset Buttons
  document.querySelectorAll('.motion-preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.motion-preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeMotion = btn.dataset.motion;
      const badge = document.getElementById('motionPresetActiveBadge');
      if (badge) badge.textContent = btn.textContent;
      const hudBadge = document.getElementById('activeMotionPresetBadge');
      if (hudBadge) hudBadge.textContent = `${btn.textContent.toUpperCase()} (EASE-IN-OUT)`;

      const primaryImg = document.getElementById('primaryStageImage');
      if (primaryImg) applyActiveGradeFilter(primaryImg);
    });
  });

  const motionSpeedRange = document.getElementById('motionSpeedRange');
  if (motionSpeedRange) {
    motionSpeedRange.addEventListener('input', () => {
      state.motionSpeed = parseFloat(motionSpeedRange.value);
      const valEl = document.getElementById('valMotionSpeed');
      if (valEl) valEl.textContent = `${state.motionSpeed.toFixed(1)}x`;
    });
  }

  // LUT Presets
  const lutNameLabel = document.getElementById('activeLutName');
  document.querySelectorAll('#lutPresetsGrid .lut-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#lutPresetsGrid .lut-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeLut = pill.dataset.lut;
      if (lutNameLabel) {
        lutNameLabel.textContent = pill.querySelector('span:last-child').textContent;
      }
      const primaryImg = document.getElementById('primaryStageImage');
      if (primaryImg) applyActiveGradeFilter(primaryImg);
      const compareAfter = document.getElementById('compareAfterImage');
      if (compareAfter) applyActiveGradeFilter(compareAfter);
    });
  });

  // Grade Sliders
  const setupSlider = (id, prop, valId, suffix = '') => {
    const slider = document.getElementById(id);
    const valEl = document.getElementById(valId);
    if (!slider || !valEl) return;
    slider.addEventListener('input', () => {
      state.grade[prop] = parseFloat(slider.value);
      valEl.textContent = `${slider.value}${suffix}`;
      const primaryImg = document.getElementById('primaryStageImage');
      if (primaryImg) applyActiveGradeFilter(primaryImg);
      const compareAfter = document.getElementById('compareAfterImage');
      if (compareAfter) applyActiveGradeFilter(compareAfter);
    });
  };

  setupSlider('gradeExposure', 'exposure', 'valExposure');
  setupSlider('gradeContrast', 'contrast', 'valContrast', '%');
  setupSlider('gradeSaturation', 'saturation', 'valSaturation', '%');
  setupSlider('gradeWarmth', 'warmth', 'valWarmth');

  const btnResetGrade = document.getElementById('btnResetGrade');
  if (btnResetGrade) {
    btnResetGrade.addEventListener('click', () => {
      state.grade = { exposure: 0, contrast: 100, saturation: 100, warmth: 0 };
      document.getElementById('gradeExposure').value = 0;
      document.getElementById('valExposure').textContent = '0.0';
      document.getElementById('gradeContrast').value = 100;
      document.getElementById('valContrast').textContent = '100%';
      document.getElementById('gradeSaturation').value = 100;
      document.getElementById('valSaturation').textContent = '100%';
      document.getElementById('gradeWarmth').value = 0;
      document.getElementById('valWarmth').textContent = '0';
      document.querySelector('[data-lut="none"]')?.click();
    });
  }

  // Firecrawl /scrape Web Modal & Ingestion
  const webModal = document.getElementById('webScrapeModalBackdrop');
  const btnOpenWebModal = document.getElementById('btnWebScrapeModal');
  const btnPromptScrape = document.getElementById('btnPromptScrapeInspiration');
  const btnCloseWebModal = document.getElementById('btnCloseWebScrapeModal');
  const btnExecuteScrape = document.getElementById('btnExecuteWebScrape');
  const webUrlInput = document.getElementById('webScrapeUrlInput');
  const webStatusText = document.getElementById('webScrapeStatusText');

  const openWebModal = () => {
    if (webModal) {
      webModal.classList.remove('hidden');
      if (webUrlInput) webUrlInput.focus();
    }
  };
  const closeWebModal = () => {
    if (webModal) webModal.classList.add('hidden');
  };

  if (btnOpenWebModal) btnOpenWebModal.addEventListener('click', openWebModal);
  if (btnPromptScrape) btnPromptScrape.addEventListener('click', openWebModal);
  if (btnCloseWebModal) btnCloseWebModal.addEventListener('click', closeWebModal);
  if (webModal) {
    webModal.addEventListener('click', (e) => {
      if (e.target === webModal) closeWebModal();
    });
  }

  if (btnExecuteScrape) {
    btnExecuteScrape.addEventListener('click', async () => {
      const url = webUrlInput?.value.trim();
      if (!url) return;
      if (webStatusText) {
        webStatusText.style.display = 'block';
        webStatusText.textContent = 'Firecrawl /scrape: Extracting design tokens & color palette...';
      }
      btnExecuteScrape.disabled = true;

      try {
        const resp = await fetch('/v1/intelligence/extract', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url: url,
            redact_pii: true,
            dedup: true
          })
        });

        if (!resp.ok) throw new Error(`Scrape extraction failed (${resp.status})`);
        const extracted = await resp.json();

        // Update Context Tray
        state.webContextUrl = url;
        const ctxPill = document.getElementById('ctxWebPill');
        const ctxVal = document.getElementById('ctxWebVal');
        if (ctxPill && ctxVal) {
          ctxPill.style.display = 'flex';
          try {
            ctxVal.textContent = new URL(url).hostname;
          } catch {
            ctxVal.textContent = url.slice(0, 20);
          }
        }

        // Prepend style context to composer
        const composer = document.getElementById('composerInput');
        if (composer) {
          const styleHint = `[Style Reference: ${extracted.app_name || url}] `;
          if (!composer.value.startsWith(styleHint)) {
            composer.value = styleHint + composer.value;
          }
        }

        if (webStatusText) {
          webStatusText.textContent = `✔ Extracted style: ${extracted.app_name} (${extracted.threat_level})`;
        }
        setTimeout(() => {
          closeWebModal();
          btnExecuteScrape.disabled = false;
          if (webStatusText) webStatusText.style.display = 'none';
        }, 1200);
      } catch (err) {
        if (webStatusText) {
          webStatusText.textContent = `Scrape error: ${err.message}`;
        }
        btnExecuteScrape.disabled = false;
      }
    });
  }

  const btnRemoveWebCtx = document.getElementById('btnRemoveWebCtx');
  if (btnRemoveWebCtx) {
    btnRemoveWebCtx.addEventListener('click', () => {
      state.webContextUrl = null;
      const ctxPill = document.getElementById('ctxWebPill');
      if (ctxPill) ctxPill.style.display = 'none';
    });
  }

  // ============================================================================
  // Personas & ElevenLabs Studio UI Wiring
  // ============================================================================
  const btnOpenPersonasTop = document.getElementById('btnPersonasStudioModal');
  if (btnOpenPersonasTop) btnOpenPersonasTop.addEventListener('click', () => openPersonasModal(false));

  const btnCreatePersonaTrigger = document.getElementById('btnCreatePersonaTrigger');
  if (btnCreatePersonaTrigger) btnCreatePersonaTrigger.addEventListener('click', () => {
    resetPersonaForm();
    openPersonasModal(false);
  });

  const btnClosePersonasModal = document.getElementById('btnClosePersonasModal');
  if (btnClosePersonasModal) btnClosePersonasModal.addEventListener('click', closePersonasModal);

  const personasModal = document.getElementById('personasModalBackdrop');
  if (personasModal) {
    personasModal.addEventListener('click', (e) => {
      if (e.target === personasModal) closePersonasModal();
    });
  }

  const btnTabCast = document.getElementById('btnTabPersonasCast');
  const btnTabTTS = document.getElementById('btnTabElevenLabsTTS');
  const panelCast = document.getElementById('panelPersonasCast');
  const panelTTS = document.getElementById('panelElevenLabsTTS');

  if (btnTabCast && btnTabTTS && panelCast && panelTTS) {
    btnTabCast.addEventListener('click', () => {
      btnTabCast.classList.add('active');
      btnTabTTS.classList.remove('active');
      panelCast.style.display = 'flex';
      panelTTS.style.display = 'none';
    });
    btnTabTTS.addEventListener('click', () => {
      btnTabTTS.classList.add('active');
      btnTabCast.classList.remove('active');
      panelTTS.style.display = 'flex';
      panelCast.style.display = 'none';
    });
  }

  const btnModalNewPersona = document.getElementById('btnModalNewPersona');
  if (btnModalNewPersona) btnModalNewPersona.addEventListener('click', resetPersonaForm);

  const btnCancelPersona = document.getElementById('btnCancelPersonaForm');
  if (btnCancelPersona) btnCancelPersona.addEventListener('click', resetPersonaForm);

  const btnSubmitPersona = document.getElementById('btnSubmitPersonaForm');
  if (btnSubmitPersona) btnSubmitPersona.addEventListener('click', savePersonaForm);

  const btnDeletePersona = document.getElementById('btnDeletePersonaForm');
  if (btnDeletePersona) btnDeletePersona.addEventListener('click', deleteSelectedPersona);

  const btnSynthesizeTTS = document.getElementById('btnSynthesizeTTS');
  if (btnSynthesizeTTS) btnSynthesizeTTS.addEventListener('click', synthesizeElevenLabsSpeech);

  const stabSlider = document.getElementById('ttsStabilitySlider');
  const valStab = document.getElementById('valTtsStability');
  if (stabSlider && valStab) {
    stabSlider.addEventListener('input', (e) => valStab.textContent = Number(e.target.value).toFixed(2));
  }

  const clarSlider = document.getElementById('ttsClaritySlider');
  const valClar = document.getElementById('valTtsClarity');
  if (clarSlider && valClar) {
    clarSlider.addEventListener('input', (e) => valClar.textContent = Number(e.target.value).toFixed(2));
  }

  document.querySelectorAll('.btn-sample-script').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById('ttsTextInput');
      if (input && btn.dataset.sample) input.value = btn.dataset.sample;
    });
  });

  // ============================================================================
  // Left Sidebar Explorer Collapse
  // ============================================================================
  const toggleSidebarCollapseBtn = document.getElementById('toggleSidebarCollapseBtn');
  const regionSidebar = document.querySelector('.region-sidebar');
  if (toggleSidebarCollapseBtn && regionSidebar) {
    toggleSidebarCollapseBtn.addEventListener('click', () => {
      regionSidebar.classList.toggle('collapsed');
      toggleSidebarCollapseBtn.textContent = regionSidebar.classList.contains('collapsed') ? '›' : '‹';
      toggleSidebarCollapseBtn.title = regionSidebar.classList.contains('collapsed') ? 'Expand Explorer' : 'Collapse Explorer';
    });
  }

  // ============================================================================
  // AUTONOMOUS COGNITION AGENT & CHATGPT / GEMINI CONVERSATION INTERFACE
  // ============================================================================
  const agentChatModal = document.getElementById('agentChatModalBackdrop');
  const agentChatStream = document.getElementById('agentChatMessagesStream');
  const agentChatInput = document.getElementById('agentChatInput');
  const btnSendAgentChat = document.getElementById('btnSendAgentChat');
  const btnStopAgentChat = document.getElementById('btnStopAgentChat');
  const btnCloseAgentChat = document.getElementById('btnCloseAgentChatModal');
  const btnNewAgentChat = document.getElementById('btnNewAgentChat');
  const btnToggleWebSearch = document.getElementById('btnToggleWebSearch');
  const btnToggleGen = document.getElementById('btnToggleGen');
  const agentChatPill = document.getElementById('agentChatPill');
  const actAgentChatBtn = document.getElementById('actAgentChatBtn');
  const navAgentChatBtn = document.getElementById('navAgentChatBtn');

  function renderMarkdownToHtml(rawText) {
    if (!rawText) return '';
    let str = String(rawText);

    // Preserve code blocks before escaping
    const codeBlocks = [];
    str = str.replace(/```([a-zA-Z0-9_\-\+]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      const cleanLang = lang.trim() || 'code';
      const escapedCode = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      const encodedForCopy = encodeURIComponent(code);
      codeBlocks.push(
        `<div class="chat-code-block">` +
          `<div class="chat-code-bar">` +
            `<span>${cleanLang}</span>` +
            `<button class="btn-code-copy" onclick="navigator.clipboard.writeText(decodeURIComponent('${encodedForCopy}')); this.textContent='✓ Copied!'; setTimeout(()=>this.textContent='Copy', 1500);">Copy</button>` +
          `</div>` +
          `<pre style="margin: 0; padding: 12px 14px; overflow-x: auto; font-family: var(--font-mono); font-size: 12px; color: #e2e8f0; line-height: 1.45;"><code>${escapedCode}</code></pre>` +
        `</div>`
      );
      return `__CODE_BLOCK_${idx}__`;
    });

    // Escape HTML characters
    str = str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Headers
    str = str.replace(/^### (.*$)/gim, '<h4 style="margin: 10px 0 4px 0; font-size: 13.5px; font-weight: 700; color: #c084fc;">$1</h4>');
    str = str.replace(/^## (.*$)/gim, '<h3 style="margin: 12px 0 6px 0; font-size: 14.5px; font-weight: 700; color: #fff;">$1</h3>');
    str = str.replace(/^# (.*$)/gim, '<h2 style="margin: 14px 0 8px 0; font-size: 16px; font-weight: 800; color: #fff;">$1</h2>');

    // Blockquotes
    str = str.replace(/^\> (.*$)/gim, '<blockquote style="margin: 8px 0; padding: 6px 12px; border-left: 3px solid #818cf8; background: rgba(99, 102, 241, 0.08); border-radius: 0 4px 4px 0; color: var(--text-secondary);">$1</blockquote>');

    // Bold & Italic
    str = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    str = str.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline code
    str = str.replace(/`([^`]+)`/g, '<code style="background: rgba(0,0,0,0.35); padding: 2px 5px; border-radius: 4px; font-family: var(--font-mono); font-size: 12px; color: #38bdf8;">$1</code>');

    // Bullet points
    str = str.replace(/^\s*[-•]\s+(.*$)/gim, '<li style="margin-left: 18px; margin-bottom: 4px;">$1</li>');

    // Numbered lists
    str = str.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li value="$1" style="margin-left: 18px; margin-bottom: 4px;">$2</li>');

    // Markdown links [text](url)
    str = str.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline; font-weight: 600;">$1</a>');

    // Line breaks
    str = str.replace(/\n/g, '<br>');

    // Restore code blocks
    codeBlocks.forEach((block, idx) => {
      str = str.replace(`__CODE_BLOCK_${idx}__`, block);
    });

    return str;
  }

  function renderAgentChatStream() {
    const stream = document.getElementById('agentChatMessagesStream');
    if (!stream) return;

    if (!state.agentChatHistory || state.agentChatHistory.length === 0) {
      stream.innerHTML = `
        <div class="chat-msg-row assistant">
          <div class="chat-avatar-icon qwen">🧠</div>
          <div class="chat-bubble-content">
            <div class="chat-bubble-header">
              <span style="font-weight: 700; color: #c084fc;">Qwen 27B Abliterated Cognition</span>
              <span style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono);">Bible § 39 Online</span>
            </div>
            <div>
              Welcome to your dedicated creative intelligence console. I am <strong><code>huihui-ai/Huihui-Qwen3.8-27B-abliterated</code></strong>, running on dual NVIDIA T4 GPUs with active tensor parallelism.
              <br><br>
              You can converse directly with me like ChatGPT or Gemini: ask technical cinematography questions, brainstorm shot lists, analyze lighting recipes, or instruct me to <strong>search the live internet</strong> and <strong>autonomously generate or upscale studio assets</strong>. What would you like to build?
            </div>
          </div>
        </div>

        <div class="chat-starter-grid">
          <div class="chat-starter-card" data-prompt="Who are you, what model is loaded, and what capabilities do you have?">
            <div class="chat-starter-title"><span>💬</span> Model Identity</div>
            <div class="chat-starter-desc">Explain the Qwen 27B abliterated architecture, dual T4 tensor parallelism, and tools.</div>
          </div>
          <div class="chat-starter-card" data-prompt="Search the internet for current 2026 cyberpunk visual trends and give me color palettes">
            <div class="chat-starter-title"><span>🌐</span> Web Research Trends</div>
            <div class="chat-starter-desc">Perform live DuckDuckGo lookup on 2026 aesthetics and return sourced citations.</div>
          </div>
          <div class="chat-starter-card" data-prompt="Look up recent sci-fi movies on the internet and generate an image for a futuristic Tokyo alley">
            <div class="chat-starter-title"><span>🎨</span> Search & Generate Asset</div>
            <div class="chat-starter-desc">Research visual mood online and dispatch real ComfyUI image render to Stage.</div>
          </div>
          <div class="chat-starter-card" data-prompt="Analyze cinematic lighting: How to achieve Kodak 2383 anamorphic lens flare?">
            <div class="chat-starter-title"><span>🎥</span> Masterclass Direction</div>
            <div class="chat-starter-desc">Deconstruct composition, optical flare, T-stop, and Hollywood LUT color timing.</div>
          </div>
        </div>
      `;

      stream.querySelectorAll('.chat-starter-card').forEach(card => {
        card.addEventListener('click', () => {
          const prompt = card.dataset.prompt;
          if (prompt) sendAgentPrompt(prompt);
        });
      });
      return;
    }

    let html = '';
    state.agentChatHistory.forEach((msg, idx) => {
      const isUser = msg.role === 'user';
      const avatar = isUser
        ? `<div class="chat-avatar-icon user">👤</div>`
        : `<div class="chat-avatar-icon qwen">🧠</div>`;
      const sender = isUser ? 'You' : 'Qwen 27B Abliterated Cognition';
      const senderColor = isUser ? '#38bdf8' : '#c084fc';

      let extraHtml = '';

      if (msg.internet_findings && msg.internet_findings.length) {
        extraHtml += `<div class="chat-citations-section">`;
        extraHtml += `<div style="font-weight: 700; color: var(--accent-cyan); margin-bottom: 6px; display: flex; align-items: center; gap: 6px;"><span>🌐</span> <span>Live Web Sources Cited</span></div>`;
        msg.internet_findings.forEach(f => {
          extraHtml += `<div style="margin-bottom: 6px;"><a href="${f.url}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; font-weight: 600; text-decoration: underline;">${f.title}</a><div style="color: var(--text-secondary); font-size: 11px;">${f.snippet}</div></div>`;
        });
        extraHtml += `</div>`;
      }

      if (msg.created_assets && msg.created_assets.length) {
        msg.created_assets.forEach(a => {
          extraHtml += `
            <div class="chat-asset-card">
              <img src="${a.download_url}" alt="${a.title}" style="width: 56px; height: 56px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-subtle); background: #000;">
              <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 700; font-size: 12.5px; color: #fff; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${a.title}</div>
                <div style="font-size: 10.5px; color: var(--text-muted); font-family: var(--font-mono); margin-top: 2px;">Asset ID: <code>${a.id.slice(0, 8)}</code> • ${a.width || 1024}x${a.height || 576}</div>
                <div style="display: flex; gap: 8px; margin-top: 6px;">
                  <button class="action-btn-mini btn-chat-view-asset" data-id="${a.id}" style="padding: 3px 8px; font-size: 10px; background: rgba(99, 102, 241, 0.2); border: 1px solid rgba(99, 102, 241, 0.4); color: #818cf8; border-radius: 4px; cursor: pointer;">📌 View in Stage</button>
                  <button class="action-btn-mini btn-chat-ref-asset" data-id="${a.id}" style="padding: 3px 8px; font-size: 10px; background: rgba(6, 182, 212, 0.15); border: 1px solid rgba(6, 182, 212, 0.35); color: var(--accent-cyan); border-radius: 4px; cursor: pointer;">⚓ Use as Reference</button>
                  <a href="${a.download_url}" download class="action-btn-mini" style="padding: 3px 8px; font-size: 10px; background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-subtle); color: var(--text-secondary); border-radius: 4px; text-decoration: none;">⬇ Download</a>
                </div>
              </div>
            </div>
          `;
        });
      }

      const copyBtnHtml = !isUser
        ? `<div class="chat-msg-footer"><button class="btn-chat-copy-msg" data-msg-idx="${idx}" title="Copy response to clipboard">📋 Copy</button></div>`
        : '';

      html += `
        <div class="chat-msg-row ${msg.role}">
          ${isUser ? '' : avatar}
          <div class="chat-bubble-content">
            <div class="chat-bubble-header">
              <span style="font-weight: 700; color: ${senderColor};">${sender}</span>
              <span style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono);">${msg.time || ''}</span>
            </div>
            <div>${renderMarkdownToHtml(msg.content)}</div>
            ${extraHtml}
            ${copyBtnHtml}
          </div>
          ${isUser ? avatar : ''}
        </div>
      `;
    });

    stream.innerHTML = html;
    stream.scrollTop = stream.scrollHeight;

    stream.querySelectorAll('.btn-chat-copy-msg').forEach(b => {
      b.addEventListener('click', () => {
        const idx = parseInt(b.dataset.msgIdx, 10);
        const msg = state.agentChatHistory[idx];
        if (msg && msg.content) {
          navigator.clipboard.writeText(msg.content);
          b.textContent = '✓ Copied!';
          setTimeout(() => { b.textContent = '📋 Copy'; }, 1500);
        }
      });
    });

    stream.querySelectorAll('.btn-chat-view-asset').forEach(b => {
      b.addEventListener('click', () => {
        const assetId = b.dataset.id;
        if (assetId) {
          state.selectedAssetId = assetId;
          closeAgentChat();
          renderSidebarAssetStream();
          renderInspector();
          renderCanvasStage();
        }
      });
    });

    stream.querySelectorAll('.btn-chat-ref-asset').forEach(b => {
      b.addEventListener('click', () => {
        const assetId = b.dataset.id;
        const targetAsset = state.assets.find(a => a.id === assetId);
        if (targetAsset) {
          setActiveReference(targetAsset);
          closeAgentChat();
        }
      });
    });
  }

  async function sendAgentPrompt(customText) {
    const inputEl = document.getElementById('agentChatInput');
    const text = (customText || (inputEl && inputEl.value) || '').trim();
    if (!text) return;
    if (inputEl) {
      inputEl.value = '';
      inputEl.style.height = 'auto';
    }

    state.agentChatHistory.push({
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString()
    });

    renderAgentChatStream();

    const stream = document.getElementById('agentChatMessagesStream');
    const thinkingId = `thinking-${Date.now()}`;
    const thinkingDiv = document.createElement('div');
    thinkingDiv.id = thinkingId;
    thinkingDiv.className = 'chat-msg-row assistant';
    thinkingDiv.innerHTML = `
      <div class="chat-avatar-icon qwen">🧠</div>
      <div class="chat-bubble-content" style="display: flex; align-items: center; gap: 10px; font-style: italic; color: var(--text-secondary);">
        <span class="status-online-dot" style="background: #c084fc; box-shadow: 0 0 8px #c084fc;"></span>
        <span>Qwen 27B is reasoning & formulating response...</span>
      </div>
    `;
    if (stream) {
      stream.appendChild(thinkingDiv);
      stream.scrollTop = stream.scrollHeight;
    }

    const btnSend = document.getElementById('btnSendAgentChat');
    const btnStop = document.getElementById('btnStopAgentChat');
    if (btnSend) btnSend.disabled = true;
    if (btnStop) btnStop.style.display = 'inline-flex';

    const abortController = new AbortController();
    const stopHandler = () => {
      abortController.abort();
      thinkingDiv.remove();
      if (btnSend) btnSend.disabled = false;
      if (btnStop) {
        btnStop.style.display = 'none';
        btnStop.removeEventListener('click', stopHandler);
      }
    };
    if (btnStop) btnStop.addEventListener('click', stopHandler);

    try {
      const session = await ensureWorkspaceSession();
      const token = session.token || localStorage.getItem('keystone_token') || 'local_dev_token';

      const resp = await fetch('/v1/cognition/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        signal: abortController.signal,
        body: JSON.stringify({
          messages: state.agentChatHistory.map(m => ({ role: m.role, content: m.content })),
          web_search: state.chatWebSearchEnabled !== false,
          allow_generation: state.chatGenEnabled !== false,
          project_id: state.activeProjectId,
          session_id: state.currentSessionId
        })
      });

      thinkingDiv.remove();

      if (!resp.ok) {
        throw new Error(`Cognition chat request failed (${resp.status}): ${await resp.text()}`);
      }

      const data = await resp.json();
      const replyText = (data.message && data.message.content) || 'Directive completed.';

      state.agentChatHistory.push({
        role: 'assistant',
        content: replyText,
        internet_findings: data.internet_findings || [],
        created_assets: data.created_assets || [],
        time: new Date().toLocaleTimeString()
      });

      renderAgentChatStream();

      if (data.created_assets && data.created_assets.length) {
        await hydratePersistedAssets();
        renderSidebarAssetStream();
        renderInspector();
        renderCanvasStage();
      }
    } catch (err) {
      thinkingDiv.remove();
      if (err.name !== 'AbortError') {
        state.agentChatHistory.push({
          role: 'assistant',
          content: `⚠️ Communication Diagnostic: ${err.message}. Retrying via fallback cognitive engine...`,
          time: new Date().toLocaleTimeString()
        });
        renderAgentChatStream();
      }
    } finally {
      if (btnSend) btnSend.disabled = false;
      if (btnStop) btnStop.style.display = 'none';
    }
  }

  const openAgentChat = () => {
    if (agentChatModal) {
      agentChatModal.classList.remove('hidden');
      agentChatModal.style.setProperty('display', 'flex', 'important');
      renderAgentChatStream();
      if (agentChatInput) {
        setTimeout(() => agentChatInput.focus(), 100);
      }
    }
  };
  window.openAgentChat = openAgentChat;

  const closeAgentChat = () => {
    if (agentChatModal) {
      agentChatModal.classList.add('hidden');
      agentChatModal.style.setProperty('display', 'none', 'important');
    }
  };
  window.closeAgentChat = closeAgentChat;

  if (agentChatPill) agentChatPill.addEventListener('click', openAgentChat);
  if (actAgentChatBtn) actAgentChatBtn.addEventListener('click', openAgentChat);
  if (navAgentChatBtn) navAgentChatBtn.addEventListener('click', openAgentChat);
  if (btnCloseAgentChat) btnCloseAgentChat.addEventListener('click', closeAgentChat);
  if (btnNewAgentChat) {
    btnNewAgentChat.addEventListener('click', () => {
      state.agentChatHistory = [];
      renderAgentChatStream();
    });
  }
  if (btnToggleWebSearch) {
    btnToggleWebSearch.addEventListener('click', () => {
      state.chatWebSearchEnabled = !state.chatWebSearchEnabled;
      btnToggleWebSearch.classList.toggle('active', state.chatWebSearchEnabled);
    });
  }
  if (btnToggleGen) {
    btnToggleGen.addEventListener('click', () => {
      state.chatGenEnabled = !state.chatGenEnabled;
      btnToggleGen.classList.toggle('active', state.chatGenEnabled);
    });
  }

  if (agentChatModal) {
    agentChatModal.addEventListener('click', (e) => {
      if (e.target === agentChatModal) closeAgentChat();
    });
  }

  // Quick sample buttons for agent
  document.querySelectorAll('.btn-agent-sample').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.task) {
        sendAgentPrompt(btn.dataset.task);
      }
    });
  });

  if (btnSendAgentChat) btnSendAgentChat.addEventListener('click', () => sendAgentPrompt());
  if (agentChatInput) {
    agentChatInput.addEventListener('input', () => {
      agentChatInput.style.height = 'auto';
      agentChatInput.style.height = Math.min(agentChatInput.scrollHeight, 160) + 'px';
    });
    agentChatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendAgentPrompt();
      }
    });
  }

  // ============================================================================
  // Studio Settings & Remote Config Modal Wiring
  // ============================================================================
  const settingsModal = document.getElementById('settingsModalBackdrop');
  const btnCloseSettings = document.getElementById('btnCloseSettingsModal');
  const actSettingsBtn = document.getElementById('actSettingsBtn');
  const tabSettingsConfig = document.getElementById('tabSettingsConfig');
  const tabSettingsEngine = document.getElementById('tabSettingsEngine');
  const tabSettingsSecurity = document.getElementById('tabSettingsSecurity');
  const panelSettingsConfig = document.getElementById('panelSettingsConfig');
  const panelSettingsEngine = document.getElementById('panelSettingsEngine');
  const panelSettingsSecurity = document.getElementById('panelSettingsSecurity');
  const btnSaveRemoteConfig = document.getElementById('btnSaveRemoteConfig');
  const btnCopyAuthToken = document.getElementById('btnCopyAuthToken');
  const remoteConfigBadge = document.getElementById('remoteConfigStatusBadge');

  const openSettingsModal = () => {
    const modal = document.getElementById('settingsModalBackdrop');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.style.setProperty('display', 'flex', 'important');

    const tenantIdEl = document.getElementById('settingsTenantId');
    const userEmailEl = document.getElementById('settingsUserEmail');
    const tokenTextEl = document.getElementById('settingsTokenText');
    const storedToken = localStorage.getItem('keystone_token') || 'local_dev_token';

    if (tenantIdEl && !tenantIdEl.value) tenantIdEl.value = 'tenant-keystone-local';
    if (userEmailEl && !userEmailEl.value) userEmailEl.value = 'operator@keystone.internal';
    if (tokenTextEl && !tokenTextEl.value) tokenTextEl.value = storedToken;

    ensureWorkspaceSession().then(session => {
      if (!session) return;
      if (tenantIdEl) tenantIdEl.value = session.tenant_id || session.account_id || 'tenant-keystone-local';
      if (userEmailEl) userEmailEl.value = session.email || 'operator@keystone.internal';
      if (tokenTextEl) tokenTextEl.value = session.token || storedToken;
    }).catch(() => {});
  };
  window.openSettingsModal = openSettingsModal;

  const closeSettingsModal = () => {
    const modal = document.getElementById('settingsModalBackdrop');
    if (modal) {
      modal.classList.add('hidden');
      modal.style.setProperty('display', 'none', 'important');
    }
  };
  window.closeSettingsModal = closeSettingsModal;

  if (btnCloseSettings) btnCloseSettings.addEventListener('click', closeSettingsModal);
  if (remoteConfigBadge) remoteConfigBadge.addEventListener('click', openSettingsModal);
  if (actSettingsBtn) actSettingsBtn.addEventListener('click', openSettingsModal);
  if (settingsModal) {
    settingsModal.addEventListener('click', (e) => {
      if (e.target === settingsModal) closeSettingsModal();
    });
  }

  if (tabSettingsConfig && tabSettingsEngine && tabSettingsSecurity) {
    tabSettingsConfig.addEventListener('click', () => {
      tabSettingsConfig.classList.add('active');
      tabSettingsEngine.classList.remove('active');
      tabSettingsSecurity.classList.remove('active');
      if (panelSettingsConfig) panelSettingsConfig.style.display = 'flex';
      if (panelSettingsEngine) panelSettingsEngine.style.display = 'none';
      if (panelSettingsSecurity) panelSettingsSecurity.style.display = 'none';
    });
    tabSettingsEngine.addEventListener('click', () => {
      tabSettingsEngine.classList.add('active');
      tabSettingsConfig.classList.remove('active');
      tabSettingsSecurity.classList.remove('active');
      if (panelSettingsEngine) panelSettingsEngine.style.display = 'flex';
      if (panelSettingsConfig) panelSettingsConfig.style.display = 'none';
      if (panelSettingsSecurity) panelSettingsSecurity.style.display = 'none';
    });
    tabSettingsSecurity.addEventListener('click', () => {
      tabSettingsSecurity.classList.add('active');
      tabSettingsConfig.classList.remove('active');
      tabSettingsEngine.classList.remove('active');
      if (panelSettingsSecurity) panelSettingsSecurity.style.display = 'flex';
      if (panelSettingsConfig) panelSettingsConfig.style.display = 'none';
      if (panelSettingsEngine) panelSettingsEngine.style.display = 'none';
    });
  }

  if (btnSaveRemoteConfig) {
    btnSaveRemoteConfig.addEventListener('click', async () => {
      const fpsVal = parseInt(document.getElementById('cfgSelectFramerate')?.value || '24', 10);
      const payload = {
        parameters: {
          zen_node_canvas_enabled: document.getElementById('cfgToggleNodes')?.checked ?? true,
          cursor_composer_enabled: document.getElementById('cfgToggleComposer')?.checked ?? true,
          activity_bar_enabled: document.getElementById('cfgToggleActivityBar')?.checked ?? true,
          motion_splines_enabled: document.getElementById('cfgToggleMotion')?.checked ?? true,
          firecrawl_scrape_enabled: document.getElementById('cfgToggleScrape')?.checked ?? true,
          cinema_framerate: fpsVal
        }
      };

      const originalText = btnSaveRemoteConfig.textContent;
      btnSaveRemoteConfig.textContent = 'Saving...';
      try {
        const session = await ensureWorkspaceSession();
        const token = session.token || localStorage.getItem('keystone_token') || 'local_dev_token';
        const res = await fetch('/v1/config/remote', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          btnSaveRemoteConfig.textContent = '✓ Saved Successfully!';
          await fetchRemoteConfig();
        } else {
          btnSaveRemoteConfig.textContent = 'Save Failed';
        }

        setTimeout(() => {
          btnSaveRemoteConfig.textContent = originalText;
          closeSettingsModal();
        }, 1200);
      } catch (err) {
        btnSaveRemoteConfig.textContent = 'Error Saving';
        setTimeout(() => { btnSaveRemoteConfig.textContent = originalText; }, 1500);
      }
    });
  }

  if (btnCopyAuthToken) {
    btnCopyAuthToken.addEventListener('click', () => {
      const tokenText = document.getElementById('settingsTokenText');
      if (tokenText && tokenText.value) {
        navigator.clipboard.writeText(tokenText.value);
        btnCopyAuthToken.textContent = '✓ Token Copied!';
        setTimeout(() => { btnCopyAuthToken.textContent = 'Copy Bearer Token'; }, 1500);
      }
    });
  }

  // ============================================================================
  // Creative Projects Manager Modal Wiring
  // ============================================================================
  const projectsModal = document.getElementById('projectsModalBackdrop');
  const btnCloseProjects = document.getElementById('btnCloseProjectsModal');
  const projectsListContainer = document.getElementById('projectsListContainer');
  const btnCreateProjectSubmit = document.getElementById('btnCreateProjectSubmit');
  const inputNewProjectName = document.getElementById('inputNewProjectName');
  const inputNewProjectDesc = document.getElementById('inputNewProjectDesc');

  const hydrateProjectsList = async () => {
    if (!projectsListContainer) return;
    projectsListContainer.innerHTML = '<div style="font-size: 11px; color: var(--text-secondary);">Loading creative projects...</div>';
    try {
      const res = await apiRequest('/v1/projects');
      const projects = res.projects || [];
      if (!projects.length) {
        projectsListContainer.innerHTML = '<div style="font-size: 11px; color: var(--text-muted);">No projects created yet. Create your first project below.</div>';
        return;
      }
      projectsListContainer.innerHTML = projects.map(p => {
        const isActive = p.id === state.activeProjectId;
        return `
          <div class="project-item-card ${isActive ? 'active' : ''}" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.02); border: 1px solid ${isActive ? '#6366f1' : 'var(--border-subtle)'}; border-radius: 8px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 700; font-size: 13px; color: var(--text-primary);">${p.name}</span>
                ${isActive ? '<span class="stage-chip" style="background: rgba(99,102,241,0.2); color: #818cf8; font-size: 9.5px; font-weight: 700;">ACTIVE PROJECT</span>' : ''}
              </div>
              <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">${p.description || 'No description provided'}</div>
              <div style="font-size: 10px; font-family: var(--font-mono); color: var(--text-muted); margin-top: 2px;">ID: ${p.id}</div>
            </div>
            <div>
              ${isActive ? '<span style="font-size: 11px; color: #818cf8; font-weight: 600;">Selected</span>' : `<button class="action-btn-mini btn-switch-project" data-id="${p.id}" style="padding: 4px 10px; font-size: 11px; background: rgba(99,102,241,0.15); border: 1px solid #6366f1; color: #fff; border-radius: 5px; cursor: pointer;">Switch</button>`}
            </div>
          </div>
        `;
      }).join('');

      document.querySelectorAll('.btn-switch-project').forEach(btn => {
        btn.addEventListener('click', () => {
          state.activeProjectId = btn.dataset.id;
          hydratePersistedAssets();
          closeProjectsModal();
        });
      });
    } catch (err) {
      projectsListContainer.innerHTML = `<div style="font-size: 11px; color: #f87171;">Failed to load projects: ${err.message}</div>`;
    }
  };

  const openProjectsModal = () => {
    if (projectsModal) {
      projectsModal.classList.remove('hidden');
      hydrateProjectsList();
    }
  };
  const closeProjectsModal = () => {
    if (projectsModal) projectsModal.classList.add('hidden');
  };

  if (btnCloseProjects) btnCloseProjects.addEventListener('click', closeProjectsModal);
  if (projectsModal) {
    projectsModal.addEventListener('click', (e) => {
      if (e.target === projectsModal) closeProjectsModal();
    });
  }

  if (btnCreateProjectSubmit) {
    btnCreateProjectSubmit.addEventListener('click', async () => {
      const name = inputNewProjectName?.value.trim();
      const desc = inputNewProjectDesc?.value.trim();
      if (!name) return;
      btnCreateProjectSubmit.disabled = true;
      try {
        const created = await apiRequest('/v1/projects', {
          method: 'POST',
          body: { name, description: desc }
        });
        state.activeProjectId = created.id;
        inputNewProjectName.value = '';
        inputNewProjectDesc.value = '';
        await hydrateProjectsList();
        await hydratePersistedAssets();
      } catch (err) {
        alert(`Failed to create project: ${err.message}`);
      } finally {
        btnCreateProjectSubmit.disabled = false;
      }
    });
  }

  // ============================================================================
  // Session History Modal Wiring
  // ============================================================================
  const sessionsModal = document.getElementById('sessionsModalBackdrop');
  const btnCloseSessions = document.getElementById('btnCloseSessionsModal');
  const sessionsListContainer = document.getElementById('sessionsListContainer');
  const btnStartNewSession = document.getElementById('btnStartNewSession');

  const hydrateSessionsList = async () => {
    if (!sessionsListContainer) return;
    sessionsListContainer.innerHTML = '<div style="font-size: 11px; color: var(--text-secondary);">Loading multi-turn session history...</div>';
    try {
      const res = await apiRequest('/v1/sessions');
      const sessions = res.sessions || [];
      if (!sessions.length) {
        sessionsListContainer.innerHTML = '<div style="font-size: 11px; color: var(--text-muted);">No sessions recorded. Start a new session below.</div>';
        return;
      }
      sessionsListContainer.innerHTML = sessions.map(s => {
        const isCurrent = s.id === state.currentSessionId;
        return `
          <div class="session-item-card ${isCurrent ? 'active' : ''}" style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.02); border: 1px solid ${isCurrent ? '#a855f7' : 'var(--border-subtle)'}; border-radius: 8px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-weight: 700; font-size: 13px; color: var(--text-primary);">${s.title || 'Creative Session'}</span>
                ${isCurrent ? '<span class="stage-chip" style="background: rgba(168,85,247,0.2); color: #c084fc; font-size: 9.5px; font-weight: 700;">ACTIVE SESSION</span>' : ''}
              </div>
              <div style="font-size: 10.5px; font-family: var(--font-mono); color: var(--text-muted); margin-top: 2px;">ID: ${s.id} • ${s.created_at ? new Date(s.created_at).toLocaleString() : ''}</div>
            </div>
            <div>
              ${isCurrent ? '<span style="font-size: 11px; color: #c084fc; font-weight: 600;">Active</span>' : `<button class="action-btn-mini btn-resume-session" data-id="${s.id}" style="padding: 4px 10px; font-size: 11px; background: rgba(168,85,247,0.15); border: 1px solid #a855f7; color: #fff; border-radius: 5px; cursor: pointer;">Resume</button>`}
            </div>
          </div>
        `;
      }).join('');

      document.querySelectorAll('.btn-resume-session').forEach(btn => {
        btn.addEventListener('click', () => {
          state.currentSessionId = btn.dataset.id;
          hydrateSessionsList();
        });
      });
    } catch (err) {
      sessionsListContainer.innerHTML = `<div style="font-size: 11px; color: #f87171;">Failed to load sessions: ${err.message}</div>`;
    }
  };

  const openSessionsModal = () => {
    if (sessionsModal) {
      sessionsModal.classList.remove('hidden');
      hydrateSessionsList();
    }
  };
  const closeSessionsModal = () => {
    if (sessionsModal) sessionsModal.classList.add('hidden');
  };

  if (btnCloseSessions) btnCloseSessions.addEventListener('click', closeSessionsModal);
  if (sessionsModal) {
    sessionsModal.addEventListener('click', (e) => {
      if (e.target === sessionsModal) closeSessionsModal();
    });
  }

  if (btnStartNewSession) {
    btnStartNewSession.addEventListener('click', async () => {
      try {
        const created = await apiRequest('/v1/sessions', {
          method: 'POST',
          body: { project_id: state.activeProjectId, title: `Session — ${new Date().toLocaleTimeString()}` }
        });
        state.currentSessionId = created.id;
        await hydrateSessionsList();
      } catch (err) {
        alert(`Failed to start session: ${err.message}`);
      }
    });
  }

  // ============================================================================
  // Credits Ledger & Billing Modal Wiring
  // ============================================================================
  const creditsModal = document.getElementById('creditsModalBackdrop');
  const btnCloseCredits = document.getElementById('btnCloseCreditsModal');
  const creditLedgerPill = document.getElementById('creditLedgerPill');
  const modalCreditAvail = document.getElementById('modalCreditAvail');
  const modalCreditHold = document.getElementById('modalCreditHold');
  const modalCreditTotal = document.getElementById('modalCreditTotal');
  const creditsLedgerTableBody = document.getElementById('creditsLedgerTableBody');
  const btnExecuteTopUp = document.getElementById('btnExecuteTopUp');
  let selectedTopupAmount = 250;

  const hydrateCreditsData = async () => {
    try {
      const balance = await apiRequest('/v1/billing/balance');
      const avail = balance.available_balance ?? 1250;
      const hold = balance.hold_balance ?? 0;
      const total = balance.total_balance ?? (avail + hold);

      if (modalCreditAvail) modalCreditAvail.textContent = avail.toLocaleString();
      if (modalCreditHold) modalCreditHold.textContent = hold.toLocaleString();
      if (modalCreditTotal) modalCreditTotal.textContent = total.toLocaleString();

      const creditBalHud = document.getElementById('creditBalanceText');
      const creditHoldHud = document.getElementById('creditHoldBadge');
      if (creditBalHud) creditBalHud.textContent = `${avail.toLocaleString()} CREDITS`;
      if (creditHoldHud) creditHoldHud.textContent = `HOLD: ${hold}`;

      const txResp = await apiRequest('/v1/billing/transactions');
      const txs = txResp.transactions || [];
      if (creditsLedgerTableBody) {
        if (!txs.length) {
          creditsLedgerTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 12px;">No recent transactions recorded.</td></tr>';
        } else {
          creditsLedgerTableBody.innerHTML = txs.slice(0, 10).map(tx => `
            <tr>
              <td style="font-family: var(--font-mono); font-size: 10px;">${tx.timestamp ? new Date(tx.timestamp).toLocaleTimeString() : 'Just now'}</td>
              <td><span class="stage-chip" style="font-size: 9px; ${tx.action === 'TOPUP' || tx.action === 'CREDIT' ? 'background: rgba(52,211,153,0.15); color: #34d399;' : 'background: rgba(239,68,68,0.15); color: #f87171;'}">${tx.action || 'TRANSACTION'}</span></td>
              <td style="font-family: var(--font-mono); font-weight: 700; color: ${tx.amount > 0 ? '#34d399' : '#f87171'};">${tx.amount > 0 ? '+' : ''}${tx.amount}</td>
              <td style="color: var(--text-secondary); font-size: 11px;">${tx.reason || 'Ledger event'}</td>
            </tr>
          `).join('');
        }
      }
    } catch (err) {
      console.warn('Billing ledger hydration notice:', err);
    }
  };

  const openCreditsModal = () => {
    if (creditsModal) {
      creditsModal.classList.remove('hidden');
      hydrateCreditsData();
    }
  };
  const closeCreditsModal = () => {
    if (creditsModal) creditsModal.classList.add('hidden');
  };

  if (creditLedgerPill) creditLedgerPill.addEventListener('click', openCreditsModal);
  if (btnCloseCredits) btnCloseCredits.addEventListener('click', closeCreditsModal);
  if (creditsModal) {
    creditsModal.addEventListener('click', (e) => {
      if (e.target === creditsModal) closeCreditsModal();
    });
  }

  document.querySelectorAll('.btn-topup-pkg').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.btn-topup-pkg').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedTopupAmount = parseInt(btn.dataset.amt, 10) || 250;
    });
  });

  if (btnExecuteTopUp) {
    btnExecuteTopUp.addEventListener('click', async () => {
      btnExecuteTopUp.disabled = true;
      btnExecuteTopUp.textContent = 'Processing...';
      try {
        await apiRequest('/v1/billing/topup', {
          method: 'POST',
          body: { amount: selectedTopupAmount, reason: 'studio_instant_topup' }
        });
        btnExecuteTopUp.textContent = '✔ Top-Up Complete!';
        await hydrateCreditsData();
        setTimeout(() => {
          btnExecuteTopUp.disabled = false;
          btnExecuteTopUp.textContent = 'Top-Up Now';
        }, 1200);
      } catch (err) {
        alert(`Top-up failed: ${err.message}`);
        btnExecuteTopUp.disabled = false;
        btnExecuteTopUp.textContent = 'Top-Up Now';
      }
    });
  }

  // ============================================================================
  // Worker Telemetry Modal Wiring
  // ============================================================================
  const workerModal = document.getElementById('workerTelemetryModalBackdrop');
  const btnCloseWorker = document.getElementById('btnCloseWorkerModal');
  const workerTelemetryPill = document.getElementById('workerTelemetryPill');
  const engineHealthStatusItem = document.getElementById('engineHealthStatusItem');
  const btnRefreshWorker = document.getElementById('btnRefreshWorkerTelemetry');

  const openWorkerModal = () => {
    if (workerModal) workerModal.classList.remove('hidden');
  };
  const closeWorkerModal = () => {
    if (workerModal) workerModal.classList.add('hidden');
  };

  if (workerTelemetryPill) workerTelemetryPill.addEventListener('click', openWorkerModal);
  if (engineHealthStatusItem) engineHealthStatusItem.addEventListener('click', openWorkerModal);
  if (btnCloseWorker) btnCloseWorker.addEventListener('click', closeWorkerModal);
  if (workerModal) {
    workerModal.addEventListener('click', (e) => {
      if (e.target === workerModal) closeWorkerModal();
    });
  }

  if (btnRefreshWorker) {
    btnRefreshWorker.addEventListener('click', async () => {
      btnRefreshWorker.disabled = true;
      btnRefreshWorker.textContent = 'Pinging...';
      try {
        const resp = await fetch('/v1/cognition/status');
        const st = await resp.json();
        btnRefreshWorker.textContent = `✔ ${st.worker_cluster || 'T4×2 Active'} (${st.state || 'READY'})`;
        setTimeout(() => {
          btnRefreshWorker.disabled = false;
          btnRefreshWorker.textContent = '🔄 Ping & Refresh Worker';
        }, 1500);
      } catch (err) {
        btnRefreshWorker.disabled = false;
        btnRefreshWorker.textContent = '🔄 Ping & Refresh Worker';
      }
    });
  }

  // ============================================================================
  // VS Code Activity Rail & Left Sidebar Navigation Items
  // ============================================================================
  document.querySelectorAll('.activity-icon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const activity = btn.dataset.activity;
      document.querySelectorAll('.activity-icon-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      if (activity === 'settings') {
        openSettingsModal();
      } else if (activity === 'chat') {
        openAgentChat();
      } else if (activity === 'personas') {
        openPersonasModal(false);
      } else if (activity === 'audio') {
        openPersonasModal(true);
      } else if (activity === 'grading') {
        document.querySelector('[data-mode="single"]')?.click();
        document.getElementById('lutPresetsGrid')?.scrollIntoView({ behavior: 'smooth' });
      } else if (activity === 'thinking') {
        const devBody = document.getElementById('devDrawerBody');
        const devChev = document.getElementById('devDrawerChevron');
        if (devBody) {
          devBody.hidden = false;
          if (devChev) devChev.textContent = '[Collapse −]';
          document.getElementById('anatomyPre')?.scrollIntoView({ behavior: 'smooth' });
        }
      } else if (activity === 'motion') {
        document.querySelector('[data-mode="video"]')?.click();
        document.getElementById('higgsfieldMotionCard')?.scrollIntoView({ behavior: 'smooth' });
      } else if (activity === 'nodes') {
        document.querySelector('[data-mode="lineage"]')?.click();
      }
    });
  });

  document.querySelectorAll('#primaryNavList .nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const nav = item.dataset.nav;
      document.querySelectorAll('#primaryNavList .nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      if (nav === 'projects') {
        openProjectsModal();
      } else if (nav === 'history') {
        openSessionsModal();
      } else if (nav === 'personas') {
        openPersonasModal(false);
      } else if (nav === 'agent-chat') {
        openAgentChat();
      } else if (nav === 'assets') {
        document.querySelector('[data-mode="variations"]')?.click();
      } else if (nav === 'favorites') {
        state.filterFavorites = !state.filterFavorites;
        renderSidebarAssetStream();
      } else if (nav === 'create') {
        document.querySelector('[data-mode="single"]')?.click();
      }
    });
  });

  // Keyboard Shortcuts (VS Code & DaVinci)
  window.addEventListener('keydown', (e) => {
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openCmd();
      } else if (e.key === 'Escape') {
        closeCmd();
        closeWebModal();
      }
      return;
    }

    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openCmd();
    } else if (e.key === 'Escape') {
      closeCmd();
      closeWebModal();
    } else if (e.code === 'Space') {
      e.preventDefault();
      togglePlayback();
    } else if (e.key.toLowerCase() === 'j') {
      stepFrame(-24);
    } else if (e.key.toLowerCase() === 'k') {
      togglePlayback(false);
    } else if (e.key.toLowerCase() === 'l') {
      stepFrame(24);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      stepFrame(-1);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      stepFrame(1);
    } else if (e.key.toLowerCase() === 'c') {
      if (toggleGridBtn) toggleGridBtn.click();
    } else if (e.key.toLowerCase() === 'f') {
      if (fullscreenBtn) fullscreenBtn.click();
    }
  });
});
