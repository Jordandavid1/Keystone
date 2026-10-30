'use strict';

/* KEYSTONE premium creative workspace — Wave 1 shell (Bible §25).
   Talks to the real API; no seeded assets and no fabricated results. */

const TOKEN_KEY = 'keystone.token';
const ACTIVE_ASSET_KEY = 'keystone.activeAsset';
const ACTIVE_JOB_KEY = 'keystone.activeJob';

const STAGE_LABELS = [
  'Understanding your request',
  'Planning the generation',
  'Preparing the workflow',
  'Creating',
  'Checking the result',
  'Refining when necessary',
  'Finishing',
];

const state = {
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: null,
  projectId: null,
  sessionId: null,
  assets: [],
  activeAsset: null,
  intent: 'create',
  attachments: [],
  jobId: null,
  jobState: null,
  stage: -1,
  authMode: 'login',
  stream: null,
};

const $ = (id) => document.getElementById(id);

const ui = {
  authScreen: $('authScreen'),
  authForm: $('authForm'),
  authEmail: $('authEmail'),
  authPassword: $('authPassword'),
  authSubmit: $('authSubmit'),
  authError: $('authError'),
  authToggle: $('authToggle'),
  authSub: $('authSub'),
  app: $('app'),
  projectName: $('projectName'),
  sessionLabel: $('sessionLabel'),
  accountEmail: $('accountEmail'),
  metaRuntime: $('metaRuntime'),
  assetList: $('assetList'),
  canvasEmpty: $('canvasEmpty'),
  canvasImage: $('canvasImage'),
  canvasVideo: $('canvasVideo'),
  canvasFrame: $('canvasFrame'),
  metaAsset: $('metaAsset'),
  metaType: $('metaType'),
  metaSize: $('metaSize'),
  metaCreated: $('metaCreated'),
  metaId: $('metaId'),
  downloadBtn: $('downloadBtn'),
  favoriteBtn: $('favoriteBtn'),
  advancedToggle: $('advancedToggle'),
  advancedBody: $('advancedBody'),
  advancedChevron: $('advancedChevron'),
  composer: $('composer'),
  composerInput: $('composerInput'),
  runBtn: $('runBtn'),
  attachBtn: $('attachBtn'),
  fileInput: $('fileInput'),
  attachments: $('attachments'),
  composerHint: $('composerHint'),
  progress: $('progress'),
  progressLabel: $('progressLabel'),
  progressState: $('progressState'),
  stages: $('stages'),
};

/* -------------------------------------------------------------------- http */

function authHeaders(extra) {
  return Object.assign({ Authorization: `Bearer ${state.token}` }, extra || {});
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: authHeaders(options.headers),
  });

  if (response.status === 401) {
    signOut();
    throw new Error('Your session expired. Sign in again.');
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `${options.method || 'GET'} ${path} failed (${response.status})`);
  }
  return payload;
}

function contentUrl(assetId) {
  return `/v1/assets/${assetId}/content?token=${encodeURIComponent(state.token)}`;
}

function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function hint(message, isError = false) {
  ui.composerHint.textContent = message;
  ui.composerHint.classList.toggle('error', isError);
}

/* --------------------------------------------------------------------- auth */

function setAuthMode(mode) {
  state.authMode = mode;
  const registering = mode === 'register';
  ui.authSub.textContent = registering ? 'Create your KEYSTONE account' : 'Sign in to your workspace';
  ui.authSubmit.textContent = registering ? 'Create account' : 'Sign in';
  ui.authToggle.textContent = registering ? 'I already have an account' : 'Create an account instead';
  ui.authPassword.autocomplete = registering ? 'new-password' : 'current-password';
  ui.authError.hidden = true;
}

ui.authToggle.addEventListener('click', () => setAuthMode(state.authMode === 'login' ? 'register' : 'login'));

ui.authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  ui.authError.hidden = true;
  ui.authSubmit.disabled = true;

  const endpoint = state.authMode === 'register' ? '/v1/auth/register' : '/v1/auth/login';
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: ui.authEmail.value.trim(), password: ui.authPassword.value }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `Sign-in failed (${response.status})`);

    state.token = payload.token;
    state.user = payload.user;
    localStorage.setItem(TOKEN_KEY, payload.token);
    ui.authPassword.value = '';
    await enterWorkspace();
  } catch (err) {
    ui.authError.textContent = String(err.message || err);
    ui.authError.hidden = false;
  } finally {
    ui.authSubmit.disabled = false;
  }
});

function signOut() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ACTIVE_ASSET_KEY);
  localStorage.removeItem(ACTIVE_JOB_KEY);
  state.token = '';
  state.user = null;
  if (state.stream) state.stream.close();
  ui.app.hidden = true;
  ui.authScreen.hidden = false;
  setAuthMode('login');
}

$('logoutBtn').addEventListener('click', signOut);

/* --------------------------------------------------------------- workspace */

async function enterWorkspace() {
  if (!state.user) state.user = await api('/v1/me');

  ui.authScreen.hidden = true;
  ui.app.hidden = false;
  ui.accountEmail.textContent = state.user.email;

  const overview = await api('/v1/projects');

  let project = overview.projects[0];
  if (!project) {
    project = await api('/v1/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'First project' }),
    });
  }
  state.projectId = project.id;
  ui.projectName.textContent = project.name;

  let session = overview.sessions.find((s) => s.project_id === project.id);
  if (!session) {
    session = await api('/v1/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: project.id }),
    });
  }
  state.sessionId = session.id;
  ui.sessionLabel.textContent = `session ${session.id.slice(0, 8)}`;

  state.assets = overview.assets;
  renderAssets();
  await refreshRuntimeStatus();

  const remembered = localStorage.getItem(ACTIVE_ASSET_KEY);
  const target = state.assets.find((a) => a.id === remembered) || state.assets[0];
  if (target) await selectAsset(target.id);

  const rememberedJob = localStorage.getItem(ACTIVE_JOB_KEY);
  if (rememberedJob) {
    try {
      const job = await api(`/v1/jobs/${rememberedJob}`);
      state.jobId = job.id;
      showProgress();
      openJobStream(job.id);
    } catch {
      localStorage.removeItem(ACTIVE_JOB_KEY);
    }
  }
}

function renderAssets() {
  ui.assetList.innerHTML = '';

  if (state.assets.length === 0) {
    const note = document.createElement('div');
    note.className = 'empty-note';
    note.textContent = 'No assets yet. Upload an image or video to begin.';
    ui.assetList.appendChild(note);
    return;
  }

  for (const asset of state.assets) {
    const button = document.createElement('button');
    button.className = `asset-item${state.activeAsset && state.activeAsset.id === asset.id ? ' active' : ''}`;
    button.type = 'button';

    if (asset.media_type === 'image') {
      const img = document.createElement('img');
      img.className = 'asset-thumb';
      img.src = contentUrl(asset.id);
      img.alt = '';
      button.appendChild(img);
    } else {
      const chip = document.createElement('div');
      chip.className = 'asset-thumb video';
      chip.textContent = '▶';
      button.appendChild(chip);
    }

    const name = document.createElement('div');
    name.className = 'asset-name';
    const title = document.createElement('b');
    title.textContent = asset.filename;
    const sub = document.createElement('span');
    sub.textContent = `${asset.media_type} · ${formatBytes(asset.byte_size)}`;
    name.appendChild(title);
    name.appendChild(sub);
    button.appendChild(name);

    button.addEventListener('click', () => selectAsset(asset.id));
    ui.assetList.appendChild(button);
  }
}

async function refreshRuntimeStatus() {
  if (!ui.metaRuntime) return;
  try {
    const health = await fetch('/v1/health').then((r) => r.json());
    const creative = health.creative || {};
    ui.metaRuntime.textContent = creative.configured
      ? `H3 connected · ${new URL(creative.base_url).host}`
      : 'H3 not connected — add KEYSTONE_COMFY_URL to .env';
  } catch {
    ui.metaRuntime.textContent = 'runtime status unavailable';
  }
}

async function refreshAssets() {
  const overview = await api('/v1/projects');
  state.assets = overview.assets;
  renderAssets();
}

async function selectAsset(assetId) {
  const asset = await api(`/v1/assets/${assetId}`);
  state.activeAsset = asset;
  localStorage.setItem(ACTIVE_ASSET_KEY, asset.id);

  ui.canvasEmpty.hidden = true;
  if (asset.media_type === 'video') {
    ui.canvasImage.hidden = true;
    ui.canvasVideo.hidden = false;
    ui.canvasVideo.src = contentUrl(asset.id);
  } else {
    ui.canvasVideo.hidden = true;
    ui.canvasImage.hidden = false;
    ui.canvasImage.src = contentUrl(asset.id);
  }

  ui.metaAsset.textContent = asset.filename;
  ui.metaType.textContent = asset.mime_type;
  ui.metaSize.textContent = formatBytes(asset.byte_size);
  ui.metaCreated.textContent = new Date(asset.created_at).toLocaleString();
  ui.metaId.textContent = asset.id;
  ui.downloadBtn.disabled = false;
  ui.favoriteBtn.disabled = false;

  renderAssets();
}

/* ------------------------------------------------------------------ uploads */

async function uploadFiles(files) {
  const list = Array.from(files || []);
  if (list.length === 0) return;

  for (const file of list) {
    if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) {
      hint(`${file.name}: only images and videos are supported.`, true);
      continue;
    }
    if (file.size > 50 * 1024 * 1024) {
      hint(`${file.name} exceeds the 50 MB limit.`, true);
      continue;
    }

    hint(`Uploading ${file.name}…`);
    const form = new FormData();
    form.append('file', file);
    if (state.projectId) form.append('project_id', state.projectId);

    try {
      const asset = await api('/v1/assets/upload', { method: 'POST', body: form });
      state.assets.unshift({
        id: asset.id,
        filename: asset.filename,
        mime_type: asset.mime_type,
        media_type: asset.media_type,
        byte_size: asset.byte_size,
        created_at: asset.created_at,
      });
      state.attachments.push(asset);
      const dropped = state.attachments.length > 2;
      if (dropped) state.attachments = state.attachments.slice(-2);
      renderAttachments();
      await selectAsset(asset.id);
      hint(
        dropped
          ? `${asset.filename} uploaded. H3 takes two references; the two newest are attached.`
          : `Uploaded ${asset.filename}.`
      );
    } catch (err) {
      hint(String(err.message || err), true);
    }
  }
}

function renderAttachments() {
  ui.attachments.innerHTML = '';
  ui.attachments.hidden = state.attachments.length === 0;

  state.attachments.forEach((asset, index) => {
    const wrap = document.createElement('div');
    wrap.className = 'attachment';

    if (asset.media_type === 'image') {
      const img = document.createElement('img');
      img.src = contentUrl(asset.id);
      img.alt = asset.filename;
      wrap.appendChild(img);
    } else {
      const chip = document.createElement('div');
      chip.className = 'file-chip';
      chip.textContent = 'video';
      wrap.appendChild(chip);
    }

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '×';
    remove.title = `Remove ${asset.filename}`;
    remove.addEventListener('click', () => {
      state.attachments.splice(index, 1);
      renderAttachments();
    });
    wrap.appendChild(remove);
    ui.attachments.appendChild(wrap);
  });
}

ui.attachBtn.addEventListener('click', () => ui.fileInput.click());
$('emptyUploadBtn').addEventListener('click', () => ui.fileInput.click());
ui.fileInput.addEventListener('change', async () => {
  await uploadFiles(ui.fileInput.files);
  ui.fileInput.value = '';
});

['dragenter', 'dragover'].forEach((type) => {
  ui.canvasFrame.addEventListener(type, (event) => {
    event.preventDefault();
    ui.canvasFrame.classList.add('dragging');
  });
});
['dragleave', 'drop'].forEach((type) => {
  ui.canvasFrame.addEventListener(type, (event) => {
    event.preventDefault();
    ui.canvasFrame.classList.remove('dragging');
  });
});
ui.canvasFrame.addEventListener('drop', (event) => uploadFiles(event.dataTransfer.files));

window.addEventListener('paste', (event) => {
  const files = Array.from(event.clipboardData?.files || []);
  if (files.length) uploadFiles(files);
});

/* -------------------------------------------------------------------- jobs */

function showProgress() {
  ui.progress.hidden = false;
  ui.stages.innerHTML = '';

  STAGE_LABELS.forEach((label, index) => {
    const item = document.createElement('li');
    item.className = 'stage';
    item.dataset.index = String(index);
    item.innerHTML = `<span class="stage-dot"></span><span>${label}</span>`;
    ui.stages.appendChild(item);
  });
}

function setStage(index, stateName, label) {
  const items = Array.from(ui.stages.querySelectorAll('.stage'));
  items.forEach((item, i) => {
    item.classList.toggle('done', i < index);
    item.classList.toggle('active', i === index);
  });
  if (label) ui.progressLabel.textContent = label;
  ui.progressState.textContent = stateName;
}

function openJobStream(jobId) {
  if (state.stream) state.stream.close();
  state.jobId = jobId;
  state.stage = -1;
  localStorage.setItem(ACTIVE_JOB_KEY, jobId);
  showProgress();
  setStage(0, 'CREATED', 'Job accepted');

  const stream = new EventSource(`/v1/jobs/${jobId}/events?token=${encodeURIComponent(state.token)}`);
  state.stream = stream;

  stream.onmessage = async (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }

    if (payload.terminal) {
      state.jobState = payload.state;
      ui.progressState.textContent = payload.state;
      if (payload.state === 'COMPLETED') {
        ui.progressLabel.textContent = 'Finished';
        Array.from(ui.stages.querySelectorAll('.stage')).forEach((item) => {
          item.classList.remove('active');
          item.classList.add('done');
        });
        hint(payload.detail || 'Job completed.');
        if (payload.output_asset_id) {
          try {
            await refreshAssets();
            await selectAsset(payload.output_asset_id);
          } catch (err) {
            hint(String(err.message || err), true);
          }
        }
      } else {
        hint(`Job ended ${payload.state}.`, true);
      }
      localStorage.removeItem(ACTIVE_JOB_KEY);
      stream.close();
      state.stream = null;
      return;
    }

    const index = STAGE_LABELS.indexOf(payload.label);
    state.stage = index >= 0 ? index : Math.min(state.stage + 1, STAGE_LABELS.length - 1);
    setStage(state.stage, payload.state, payload.label);
  };

  stream.onerror = () => {
    // EventSource reconnects on its own; surface only if the job is unknown.
    ui.progressState.textContent = 'reconnecting';
  };
}

/* ----------------------------------------------------------------- composer */

function autoGrow() {
  ui.composerInput.style.height = 'auto';
  ui.composerInput.style.height = `${Math.min(ui.composerInput.scrollHeight, 160)}px`;
}

ui.composerInput.addEventListener('input', autoGrow);
ui.composerInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    submitMessage();
  }
});

document.querySelectorAll('.intent').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.intent').forEach((b) => b.classList.remove('active'));
    button.classList.add('active');
    state.intent = button.dataset.intent;
  });
});

ui.composer.addEventListener('submit', (event) => {
  event.preventDefault();
  submitMessage();
});

async function submitMessage() {
  const content = ui.composerInput.value.trim();
  if (!content) {
    hint('Write a request first.', true);
    ui.composerInput.focus();
    return;
  }
  if (!state.sessionId) {
    hint('No session is open. Reload the workspace.', true);
    return;
  }

  ui.runBtn.disabled = true;
  hint('Submitting…');

  const assetIds = state.attachments.length
    ? state.attachments.map((a) => a.id)
    : state.activeAsset
      ? [state.activeAsset.id]
      : [];

  try {
    const response = await api(`/v1/sessions/${state.sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, intent: state.intent, asset_ids: assetIds }),
    });

    ui.composerInput.value = '';
    autoGrow();
    state.attachments = [];
    renderAttachments();
    openJobStream(response.job_id);
  } catch (err) {
    hint(String(err.message || err), true);
  } finally {
    ui.runBtn.disabled = false;
  }
}

/* ---------------------------------------------------------------- inspector */

ui.advancedToggle.addEventListener('click', () => {
  const open = ui.advancedBody.hidden;
  ui.advancedBody.hidden = !open;
  ui.advancedToggle.setAttribute('aria-expanded', String(open));
  ui.advancedChevron.textContent = open ? '−' : '+';
});

ui.downloadBtn.addEventListener('click', () => {
  if (!state.activeAsset) return;
  const link = document.createElement('a');
  link.href = contentUrl(state.activeAsset.id);
  link.download = state.activeAsset.filename;
  link.click();
});

ui.favoriteBtn.addEventListener('click', () => {
  hint('Favorites are not persisted yet (Bible Wave 6).');
});

document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach((b) => b.classList.remove('active'));
    item.classList.add('active');
    const view = item.dataset.view;
    if (view === 'projects' || view === 'history') {
      hint(`${view[0].toUpperCase()}${view.slice(1)} view arrives with the next epic; assets are listed on the left.`);
    }
  });
});

$('newProjectBtn').addEventListener('click', async () => {
  const name = prompt('Project name');
  if (!name) return;
  try {
    const project = await api('/v1/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const session = await api('/v1/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: project.id }),
    });
    state.projectId = project.id;
    state.sessionId = session.id;
    ui.projectName.textContent = project.name;
    ui.sessionLabel.textContent = `session ${session.id.slice(0, 8)}`;
    state.assets = [];
    state.activeAsset = null;
    renderAssets();
    ui.canvasImage.hidden = true;
    ui.canvasVideo.hidden = true;
    ui.canvasEmpty.hidden = false;
    hint(`Switched to ${project.name}.`);
  } catch (err) {
    hint(String(err.message || err), true);
  }
});

/* -------------------------------------------------------------------- boot */

(async function boot() {
  setAuthMode('login');
  if (!state.token) return;

  try {
    state.user = await api('/v1/me');
    await enterWorkspace();
  } catch {
    signOut();
  }
})();
