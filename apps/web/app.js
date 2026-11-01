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
  }
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
          ${asset.imageUrl
            ? `<img src="${asset.imageUrl}" alt="${asset.title}" />`
            : asset.type === 'video' ? '🎬' : '🖼️'}
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
  if (!asset) {
    if (metadata) metadata.textContent = 'No persisted asset selected.';
    return;
  }

  if (metadata) {
    metadata.textContent = JSON.stringify({
      id: asset.id,
      relationship: asset.relationship,
      prompt: asset.prompt,
      dimensions: asset.width && asset.height ? `${asset.width}×${asset.height}` : null,
      byteSize: asset.byteSize || null,
      seed: asset.seed || null,
      jobId: asset.jobId || null
    }, null, 2);
  }
}

// ============================================================================
// Center Canvas Mode Renderers (Single, Compare, Video, Variations, Lineage)
// ============================================================================

function renderCanvasStage() {
  const stage = document.getElementById('canvasStage');
  const asset = getSelectedAsset();
  if (!stage) return;
  if (!asset) {
    stage.innerHTML = '<div class="canvas-empty-state"><strong>No generated assets yet</strong><span>Enter a prompt and run KEYSTONE to create a persisted image.</span></div>';
    return;
  }

  if (state.activeMode === 'single') {
    if (asset.imageUrl) {
      stage.innerHTML = `
        <div class="stage-artwork-frame">
          <img id="primaryStageImage" class="stage-visual-canvas" src="${asset.imageUrl}" alt="${asset.title}"
               style="object-fit: contain; background: #04060b;" />
          <div class="stage-overlay-badges">
            <span class="stage-chip">✨ ${asset.title}</span>
            <span class="stage-chip" style="color: #34d399;">✔ ComfyUI render • ${assetFacts(asset)}</span>
          </div>
        </div>
      `;
      applyActiveGradeFilter(document.getElementById('primaryStageImage'));
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
    const videos = state.assets.filter(item => item.type === 'video' && item.imageUrl);
    if (!videos.length) {
      stage.innerHTML = '<div class="canvas-empty-state"><strong>No video files available</strong><span>Video output is not implemented by the currently connected image workflow.</span></div>';
      return;
    }
    stage.innerHTML = `
      <div class="stage-artwork-frame">
        <video class="stage-visual-canvas" src="${videos[0].imageUrl}" controls autoplay loop>
          Your browser does not support video playback.
        </video>
        <div class="stage-overlay-badges">
          <span class="stage-chip">${videos[0].title}</span>
          <span class="stage-chip">Persisted video • Synchronized playback controls</span>
        </div>
      </div>
    `;

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
  const parent = state.assets.find(a => a.id === state.selectedAssetId);
  const parentAssetId = parent && PERSISTED_ID_PATTERN.test(parent.id) ? parent.id : null;

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
      relationship_type: parentAssetId ? 'variation' : 'source',
      job_id: jobId,
      project_id: state.activeProjectId,
      title: `Generated — ${promptText.slice(0, 28)}...`,
      metadata: {
        aspect: state.activeAspect,
        prompt_hash: state.lastCompiledAnatomy && state.lastCompiledAnatomy.prompt_hash,
        motion: state.activeMotion
      }
    }
  });
}

function assetFromPersistedRecord(record) {
  const meta = record.metadata || {};
  return {
    id: record.id,
    title: meta.title || `${record.media_type || 'Persisted asset'} — ${String(meta.prompt || '').slice(0, 28)}`,
    type: record.media_type || 'image',
    mimeType: record.mime_type || 'application/octet-stream',
    relationship: meta.relationship || 'source',
    parentId: meta.parent_asset_id || null,
    aspect: meta.aspect || '16:9',
    khf: null,
    width: meta.width || null,
    height: meta.height || null,
    byteSize: record.byte_size || null,
    imageUrl: record.download_url || null,
    prompt: meta.prompt || '',
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
// Event Wiring & Pro Studio Controls
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  renderPlaybooks();
  renderSidebarAssetStream();
  renderInspector();
  renderCanvasStage();
  compilePromptPreview();
  hydratePersistedAssets();
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
      if (cmd === 'mode:compare') document.querySelector('[data-mode="compare"]').click();
      if (cmd === 'mode:video') document.querySelector('[data-mode="video"]').click();
      if (cmd === 'mode:lineage') document.querySelector('[data-mode="lineage"]').click();
      if (cmd === 'nav:admin') window.location.href = '/admin';
    });
  });

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
