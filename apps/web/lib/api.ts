import { StudioAsset, GenerativeToolId, CanonicalPlaybook } from './types';

const API_BASE = '';

function formatApiError(status: number, payload: any, fallback: string): string {
  const detail = payload?.detail ?? payload?.error?.message ?? payload?.message;
  if (typeof detail === 'string' && detail.trim()) return `API Error [${status}]: ${detail}`;
  if (Array.isArray(detail)) {
    const joined = detail.map((item) => item?.msg || JSON.stringify(item)).join('; ');
    return `API Error [${status}]: ${joined}`;
  }
  if (detail && typeof detail === 'object') return `API Error [${status}]: ${JSON.stringify(detail)}`;
  return `API Error [${status}]: ${fallback}`;
}

export async function apiRequest<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let payload: any = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(formatApiError(response.status, payload, response.statusText));
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

/**
 * Execute a generative tool (any of the 17 tools in the catalog).
 * Errors from the engine — including "no engine configured" — are thrown, never replaced with fake media.
 */
export async function executeGenerativeTool(
  tool: GenerativeToolId,
  input: Record<string, any>
): Promise<{
  generation_id: string;
  status: string;
  outputs?: StudioAsset[];
  text?: string;
  error?: string;
}> {
  const res = await apiRequest('/v1/zencreator/generate', {
    method: 'POST',
    body: JSON.stringify({ tool, input, async_mode: false }),
  });

  const outputs: StudioAsset[] = (res.outputs || []).map((out: any, idx: number) => ({
    id: out.asset_id || `out_${Date.now()}_${idx}`,
    title: `${tool.toUpperCase()} Output`,
    type: out.type || (tool.includes('video') ? 'video' : 'image'),
    url: out.download_url || out.url || '',
    downloadUrl: out.download_url || out.url || '',
    previewUrl: out.preview_url || out.download_url || out.url || '',
    width: out.width,
    height: out.height,
    byteSize: out.byte_size,
    mimeType: out.mime_type || (tool.includes('video') ? 'video/mp4' : 'image/png'),
    toolUsed: tool,
    prompt: input.positive_prompt || input.prompt || '',
    parentId: input.ref_asset_id || input.reference_asset_id || null,
    createdAt: Date.now(),
  }));

  return {
    generation_id: res.generation_id,
    status: res.status,
    outputs,
    text: res.text,
    error: res.error,
  };
}

/**
 * Upload an asset file (image, video, audio)
 */
export async function uploadMediaFile(file: File): Promise<StudioAsset> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await apiRequest('/v1/zencreator/upload', {
    method: 'POST',
    body: formData,
  });

  const isVideo = file.type.startsWith('video');
  const isAudio = file.type.startsWith('audio');
  const localPreview = URL.createObjectURL(file);
  const remoteUrl = res.download_url || res.url || '';

  return {
    id: res.asset_id || res.id,
    title: file.name,
    type: isVideo ? 'video' : isAudio ? 'audio' : 'image',
    url: remoteUrl || localPreview,
    downloadUrl: remoteUrl || localPreview,
    previewUrl: localPreview || remoteUrl,
    byteSize: file.size,
    mimeType: file.type,
    createdAt: Date.now(),
  };
}

export async function fetchCreditBalance(): Promise<number | null> {
  const data = await apiRequest('/v1/zencreator/balance');
  if (data == null || data.balance == null) return null;
  const value = Number(data.balance);
  return Number.isFinite(value) ? value : null;
}

export async function fetchPlaybooks(): Promise<CanonicalPlaybook[]> {
  const data = await apiRequest('/v1/zencreator/playbooks');
  return data.playbooks || [];
}

export async function fetchEngineStatus(): Promise<{ online: boolean; llm?: any; comfy?: any }> {
  return apiRequest('/v1/zencreator/engine');
}

export async function scrapeWebUrl(url: string): Promise<any> {
  return apiRequest('/v1/intelligence/extract', {
    method: 'POST',
    body: JSON.stringify({ url, redact_pii: true, dedup: true }),
  });
}

export async function fetchCreditLedger(): Promise<{
  balance: number | null;
  currency?: string;
  status?: string;
  note?: string;
  hold?: number | null;
  total?: number | null;
  events?: { timestamp?: string; action?: string; amount?: number | string; reason?: string }[];
}> {
  return apiRequest('/v1/zencreator/balance');
}

export async function fetchCognitionStatus(): Promise<any> {
  return apiRequest('/v1/cognition/status');
}

export async function chatWithCognition(payload: {
  messages: { role: string; content: string }[];
  temperature?: number;
  max_tokens?: number;
  web_search?: boolean;
  allow_generation?: boolean;
  session_id?: string | null;
  project_id?: string | null;
}): Promise<any> {
  return apiRequest('/v1/cognition/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchProjects(): Promise<any[]> {
  const data = await apiRequest('/v1/projects');
  return data.projects || [];
}

export async function createProject(name: string, description?: string): Promise<any> {
  return apiRequest('/v1/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description: description || null }),
  });
}

export async function deleteProject(projectId: string): Promise<any> {
  return apiRequest('/v1/projects/' + encodeURIComponent(projectId), { method: 'DELETE' });
}

export async function fetchSessions(projectId?: string | null): Promise<any[]> {
  const query = projectId ? '?project_id=' + encodeURIComponent(projectId) : '';
  const data = await apiRequest('/v1/sessions' + query);
  return data.sessions || [];
}

export async function createSession(title: string, projectId?: string | null): Promise<any> {
  return apiRequest('/v1/sessions', {
    method: 'POST',
    body: JSON.stringify({ title, project_id: projectId || null }),
  });
}

export async function fetchSessionMessages(sessionId: string): Promise<any[]> {
  const data = await apiRequest('/v1/sessions/' + encodeURIComponent(sessionId) + '/messages');
  return data.messages || [];
}

export async function fetchWorkers(): Promise<any> {
  return apiRequest('/internal/workers');
}

export async function fetchAudioConfig(): Promise<any> {
  return apiRequest('/v1/audio/config');
}

export async function synthesizeSpeech(payload: {
  text: string;
  voice_id?: string;
  voice_settings?: Record<string, any>;
  save_asset?: boolean;
}): Promise<any> {
  return apiRequest('/v1/audio/speech', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchCurrentUser(): Promise<any> {
  return apiRequest('/v1/auth/me');
}

export async function fetchPersonas(): Promise<any[]> {
  const data = await apiRequest('/v1/personas');
  return data.personas || [];
}

export async function fetchAudioVoices(): Promise<any[]> {
  const data = await apiRequest('/v1/audio/voices');
  return data.voices || [];
}
