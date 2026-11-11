import { StudioAsset, GenerativeToolId, CanonicalPlaybook, EngineStatus } from './types';
import { authHeaders, dropRejectedToken } from './auth';

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

/** An API failure that keeps the HTTP status and any job id the server attached. */
export class ApiError extends Error {
  status: number;
  jobId: string | null;
  constructor(message: string, status: number, jobId: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.jobId = jobId;
  }
}

export interface ApiRequestOptions extends RequestInit {
  /** Send no stored credentials (sign-in, registration, key checks). Default: send them. */
  anonymous?: boolean;
}

export async function apiRequest<T = any>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
  const { anonymous, ...init } = options;
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = new Headers(init.headers || {});

  if (!headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  const sentToken = !anonymous && !headers.has('Authorization') && !headers.has('X-API-Key');
  if (sentToken) {
    for (const [k, v] of Object.entries(authHeaders())) headers.set(k, v);
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let payload: any = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    // An expired or revoked bearer token is dropped so the studio falls back to
    // the saved API key (if any) or the signed-out state, instead of retrying it forever.
    if (response.status === 401 && sentToken && headers.get('Authorization')?.startsWith('Bearer ')) {
      dropRejectedToken();
    }
    throw new ApiError(formatApiError(response.status, payload, response.statusText), response.status, response.headers.get('X-Keystone-Job-Id'));
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
  input: Record<string, any>,
  jobId?: string,
): Promise<{
  generation_id: string;
  status: string;
  outputs?: StudioAsset[];
  text?: string;
  error?: string;
  job_id?: string | null;
  job_state?: string | null;
}> {
  const res = await apiRequest('/v1/zencreator/generate', {
    method: 'POST',
    body: JSON.stringify({ tool, input, async_mode: false, ...(jobId ? { job_id: jobId } : {}) }),
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
    job_id: res.job_id || null,
    job_state: res.job_state || res.state || null,
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

export async function fetchEngineStatus(): Promise<EngineStatus> {
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

export interface CurrentUser {
  id: string;
  email: string;
  display_name?: string | null;
  status?: string;
  auth_via?: 'token' | 'api_key' | 'dev_bypass' | 'unknown';
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  return apiRequest('/v1/auth/me');
}

export interface AuthMode {
  password: boolean;
  api_key: boolean;
  dev_bypass: boolean;
}

export async function fetchAuthMode(): Promise<AuthMode> {
  return apiRequest('/v1/auth/mode', { anonymous: true });
}

export interface AuthResult {
  access_token: string;
  token_type: string;
  user: { id: string; email: string; display_name?: string | null; status?: string };
}

export async function signIn(email: string, password: string): Promise<AuthResult> {
  return apiRequest('/v1/auth/login', { method: 'POST', anonymous: true, body: JSON.stringify({ email, password }) });
}

export async function register(email: string, password: string, displayName?: string): Promise<AuthResult> {
  return apiRequest('/v1/auth/register', {
    method: 'POST',
    anonymous: true,
    body: JSON.stringify({ email, password, ...(displayName ? { display_name: displayName } : {}) }),
  });
}

/** Check a key before saving it: asks /v1/auth/me with only that key. */
export async function verifyApiKey(key: string): Promise<CurrentUser> {
  return apiRequest('/v1/auth/me', { anonymous: true, headers: { 'X-API-Key': key.trim() } });
}

export interface ApiKeySummary {
  id: string;
  name: string;
  key_prefix: string;
  status?: string;
  created_at?: string | null;
}

export async function listApiKeys(): Promise<ApiKeySummary[]> {
  const data = await apiRequest('/v1/auth/api-keys');
  return data.api_keys || [];
}

/** Returns the raw key once; the server only keeps its hash. */
export async function createApiKey(name: string): Promise<{ id: string; name: string; raw_key: string; key_prefix: string }> {
  return apiRequest('/v1/auth/api-keys', { method: 'POST', body: JSON.stringify({ name }) });
}

export async function fetchPersonas(): Promise<any[]> {
  const data = await apiRequest('/v1/personas');
  return data.personas || [];
}

export async function fetchAudioVoices(): Promise<any[]> {
  const data = await apiRequest('/v1/audio/voices');
  return data.voices || [];
}

/* ---------------------------------------------------------------------------
 * Studio schema additions (docs/UI_SCHEMA.md §5)
 * ------------------------------------------------------------------------- */

function mediaTypeOf(raw: any): 'image' | 'video' | 'audio' {
  const t = String(raw?.media_type || raw?.type || raw?.mime_type || '').toLowerCase();
  if (t.includes('video')) return 'video';
  if (t.includes('audio')) return 'audio';
  return 'image';
}

/** Persisted assets for the tenant (GET /v1/assets). */
export async function fetchAssets(projectId?: string | null): Promise<StudioAsset[]> {
  const query = projectId ? '?project_id=' + encodeURIComponent(projectId) : '';
  const data = await apiRequest('/v1/assets' + query);
  return (data.assets || [])
    .filter((a: any) => a && a.id && a.download_url)
    .map((a: any) => {
      const meta = a.metadata || {};
      return {
        id: a.id,
        title: meta.title || meta.filename || meta.original_filename || `${mediaTypeOf(a)} ${String(a.id).slice(0, 8)}`,
        type: mediaTypeOf(a),
        url: a.download_url,
        downloadUrl: a.download_url,
        previewUrl: meta.preview_url || a.download_url,
        width: meta.width,
        height: meta.height,
        byteSize: a.byte_size,
        mimeType: a.mime_type,
        toolUsed: meta.tool || meta.capability,
        prompt: meta.prompt,
        parentId: meta.parent_id || meta.parent_asset_id || null,
        createdAt: a.created_at ? Date.parse(a.created_at) : Date.now(),
      } as StudioAsset;
    });
}

export async function fetchAssetLineage(assetId: string): Promise<{ ancestors: string[]; descendants: string[] }> {
  const data = await apiRequest('/v1/assets/' + encodeURIComponent(assetId) + '/lineage');
  return { ancestors: data.ancestors || [], descendants: data.descendants || [] };
}

export interface JobSummary {
  id: string;
  state: string;
  capability_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export async function fetchJobs(): Promise<JobSummary[]> {
  const data = await apiRequest('/v1/jobs');
  return data.jobs || [];
}

export interface GenerationJobEvent {
  state: string;
  at: number;
  reason?: string;
}

export interface GenerationJob {
  job_id: string;
  tool: string;
  current_state: string;
  terminal: boolean;
  error: string | null;
  created_at: number;
  updated_at: number;
  events: GenerationJobEvent[];
}

/** Live progress of a studio generation, by the job id sent with /generate. */
export async function fetchGenerationJob(jobId: string): Promise<GenerationJob> {
  return apiRequest('/v1/zencreator/jobs/' + encodeURIComponent(jobId));
}

export async function fetchJobEvents(jobId: string): Promise<{ current_state: string; events: { state: string; reason?: string }[] }> {
  return apiRequest('/v1/jobs/' + encodeURIComponent(jobId) + '/events');
}
