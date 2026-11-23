import {
  AccountInfo,
  CanonicalPlaybook,
  ContentMode,
  EngineStatus,
  GenerativeToolId,
  InternetFinding,
  Persona,
  RecipeSummary,
  SessionMessage,
  SessionSummary,
  StudioAsset,
} from './types';
import { authHeaders, dropRejectedToken } from './auth';

const API_BASE = '';

const DIRECT_UPLOAD_MIMES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
  'video/mp4',
  'video/webm',
  'audio/mpeg',
  'audio/wav',
  'audio/ogg',
]);

function formatApiError(status: number, payload: any, fallback: string): string {
  const detail = payload?.detail ?? payload?.error?.message ?? payload?.message;
  if (typeof detail === 'string' && detail.trim()) return `API Error [${status}]: ${detail}`;
  if (Array.isArray(detail)) {
    const joined = detail.map((item) => item?.msg || JSON.stringify(item)).join('; ');
    return `API Error [${status}]: ${joined}`;
  }
  if (detail && typeof detail === 'object') {
    const msg = detail.message || detail.code || JSON.stringify(detail);
    return `API Error [${status}]: ${msg}`;
  }
  return `API Error [${status}]: ${fallback}`;
}

/** An API failure that keeps the HTTP status and any job id the server attached. */
export class ApiError extends Error {
  status: number;
  jobId: string | null;
  code: string | null;
  constructor(message: string, status: number, jobId: string | null = null, code: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.jobId = jobId;
    this.code = code;
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
    if (response.status === 401 && sentToken && headers.get('Authorization')?.startsWith('Bearer ')) {
      dropRejectedToken();
    }
    const code = typeof payload?.detail === 'object' ? payload?.detail?.code || null : null;
    throw new ApiError(
      formatApiError(response.status, payload, response.statusText),
      response.status,
      response.headers.get('X-Keystone-Job-Id'),
      code,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

function mediaTypeOf(raw: any): 'image' | 'video' | 'audio' {
  const t = String(raw?.media_type || raw?.asset_type || raw?.type || raw?.mime_type || '').toLowerCase();
  if (t.includes('video')) return 'video';
  if (t.includes('audio')) return 'audio';
  return 'image';
}

export function mapPersistedAsset(a: any): StudioAsset {
  const meta = a?.metadata || {};
  return {
    id: a.id,
    title: meta.title || meta.filename || meta.original_filename || a.filename || `${mediaTypeOf(a)} ${String(a.id).slice(0, 8)}`,
    type: mediaTypeOf(a),
    url: a.download_url || a.url || '',
    downloadUrl: a.download_url || a.url || '',
    previewUrl: meta.preview_url || a.download_url || a.url || '',
    width: a.width ?? meta.width,
    height: a.height ?? meta.height,
    byteSize: a.byte_size ?? a.size_bytes,
    mimeType: a.mime_type,
    toolUsed: meta.tool || meta.capability,
    prompt: meta.prompt,
    parentId: a.parent_id || meta.parent_id || meta.parent_asset_id || meta.source_asset_id || null,
    projectId: a.project_id ?? meta.project_id ?? null,
    mature: Boolean(a.mature ?? meta.mature),
    personaId: a.persona_id ?? meta.persona_id ?? null,
    personaVersion: a.persona_version ?? meta.persona_version ?? null,
    c2paManifest: a.c2pa_manifest ?? meta.c2pa_manifest ?? null,
    createdAt: a.created_at ? (typeof a.created_at === 'number' ? a.created_at : Date.parse(a.created_at)) : Date.now(),
  };
}

/**
 * Execute a generative tool (all studio capabilities).
 * Errors from the engine are thrown, never replaced with fake media.
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
    id: out.asset_id || out.id || `out_${Date.now()}_${idx}`,
    title: out.title || `${tool.toUpperCase()} Output`,
    type: out.type || (tool.includes('video') || tool === 'extend' ? 'video' : 'image'),
    url: out.download_url || out.url || '',
    downloadUrl: out.download_url || out.url || '',
    previewUrl: out.preview_url || out.download_url || out.url || '',
    width: out.width,
    height: out.height,
    byteSize: out.byte_size,
    mimeType: out.mime_type || (tool.includes('video') || tool === 'extend' ? 'video/mp4' : 'image/png'),
    toolUsed: tool,
    prompt: input.positive_prompt || input.prompt || '',
    parentId: out.parent_id || input.ref_asset_id || input.reference_asset_id || input.video_asset_id || null,
    projectId: out.project_id ?? input.project_id ?? null,
    mature: Boolean(out.mature ?? (input.content_mode === 'unrestricted')),
    personaId: out.persona_id ?? input.as ?? input.persona_id ?? null,
    personaVersion: out.persona_version ?? null,
    c2paManifest: out.c2pa_manifest ?? null,
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

/** Upload an asset file (image, video, audio), scoping to projectId when possible. */
export async function uploadMediaFile(file: File, projectId?: string | null): Promise<StudioAsset> {
  const formData = new FormData();
  formData.append('file', file);
  const mimeLower = (file.type || '').split(';')[0].trim().toLowerCase();
  const useAssetsUpload = Boolean(projectId && DIRECT_UPLOAD_MIMES.has(mimeLower));
  if (useAssetsUpload && projectId) {
    formData.append('project_id', projectId);
  }

  const res = await apiRequest(useAssetsUpload ? '/v1/assets/upload-file' : '/v1/zencreator/upload', {
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
    projectId: res.project_id ?? projectId ?? null,
    mature: Boolean(res.mature),
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

export interface CognitionChatResult {
  id?: string;
  model?: string;
  served_model?: string;
  message?: { role: string; content: string };
  text?: string;
  compiled_prompt?: string;
  prompt_hash?: string;
  internet_findings?: InternetFinding[];
  created_assets?: any[];
  generation_error?: string | null;
  session_persist_error?: string | null;
  latency_ms?: number;
}

export async function chatWithCognition(
  payload: {
    messages: { role: string; content: string }[];
    temperature?: number;
    max_tokens?: number;
    web_search?: boolean;
    allow_generation?: boolean;
    session_id?: string | null;
    project_id?: string | null;
    as?: string | null;
    persona_id?: string | null;
  },
  signal?: AbortSignal,
): Promise<CognitionChatResult> {
  return apiRequest('/v1/cognition/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...(signal ? { signal } : {}),
  });
}

export async function analyzeWithCognition(
  payload: {
    asset_id?: string | null;
    prompt?: string;
    session_id?: string | null;
    project_id?: string | null;
    playbook_id?: string | null;
    as?: string | null;
    persona_id?: string | null;
  },
  signal?: AbortSignal,
): Promise<{
  analysis?: string;
  text?: string;
  asset_id?: string | null;
  content_mode?: ContentMode;
  error?: string;
}> {
  return apiRequest('/v1/cognition/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
    ...(signal ? { signal } : {}),
  });
}

/* ---------------------------------------------------------------------------
 * Account, Stage-1 Age Verification & Content Mode
 * ------------------------------------------------------------------------- */

export async function fetchAccount(): Promise<AccountInfo> {
  return apiRequest('/v1/account');
}

export async function verifyAccountAge(
  confirmedAdult18Plus: boolean,
  method = 'attestation',
): Promise<{ age_verified: boolean; age_verified_at?: string; age_verification_method?: string }> {
  return apiRequest('/v1/account/age-verification', {
    method: 'POST',
    body: JSON.stringify({ confirmed_adult_18_plus: confirmedAdult18Plus, method }),
  });
}

export async function updateContentMode(payload: {
  content_mode: ContentMode;
  project_id?: string | null;
  session_id?: string | null;
}): Promise<{ target_type: string; target_id: string; content_mode: ContentMode }> {
  return apiRequest('/v1/account/content-mode', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

/* ---------------------------------------------------------------------------
 * Projects & Sessions
 * ------------------------------------------------------------------------- */

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

export async function fetchSessions(projectId?: string | null): Promise<SessionSummary[]> {
  const query = projectId ? '?project_id=' + encodeURIComponent(projectId) : '';
  const data = await apiRequest('/v1/sessions' + query);
  return data.sessions || [];
}

export async function fetchSession(sessionId: string): Promise<SessionSummary> {
  return apiRequest('/v1/sessions/' + encodeURIComponent(sessionId));
}

export async function createSession(title: string, projectId?: string | null): Promise<SessionSummary> {
  return apiRequest('/v1/sessions', {
    method: 'POST',
    body: JSON.stringify({ title, project_id: projectId || null }),
  });
}

export async function fetchSessionMessages(sessionId: string): Promise<SessionMessage[]> {
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
  project_id?: string | null;
  as?: string | null;
  persona_id?: string | null;
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

/* ---------------------------------------------------------------------------
 * Personas CRUD + Speak (Bible v2 §41)
 * ------------------------------------------------------------------------- */

export async function fetchPersonas(opts?: {
  projectId?: string | null;
  contentMode?: ContentMode | null;
}): Promise<Persona[]> {
  const params = new URLSearchParams();
  if (opts?.projectId) params.set('project_id', opts.projectId);
  if (opts?.contentMode) params.set('content_mode', opts.contentMode);
  const qs = params.toString() ? `?${params.toString()}` : '';
  const data = await apiRequest('/v1/personas' + qs);
  return data.personas || [];
}

export async function createPersona(payload: {
  name: string;
  description?: string | null;
  project_id?: string | null;
  avatar_asset_id?: string | null;
  reference_assets?: string[];
  identity_adapter?: string;
  voice_id?: string | null;
  voice_name?: string | null;
  voice_settings?: Record<string, any>;
  personality_traits?: string[];
  system_prompt?: string | null;
  mature?: boolean;
}): Promise<Persona> {
  const res = await apiRequest<any>('/v1/personas', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.persona ?? res;
}

export async function updatePersona(
  personaId: string,
  payload: {
    name?: string;
    description?: string | null;
    avatar_asset_id?: string | null;
    reference_assets?: string[];
    identity_adapter?: string;
    voice_id?: string | null;
    voice_name?: string | null;
    voice_settings?: Record<string, any>;
    personality_traits?: string[];
    system_prompt?: string | null;
  },
): Promise<Persona> {
  const res = await apiRequest<any>('/v1/personas/' + encodeURIComponent(personaId), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  return res.persona ?? res;
}

export async function deletePersona(personaId: string): Promise<{ status: string; deleted_persona_id?: string }> {
  return apiRequest('/v1/personas/' + encodeURIComponent(personaId), { method: 'DELETE' });
}

export async function speakAsPersona(
  personaId: string,
  payload: {
    text: string;
    voice_id?: string;
    voice_settings?: Record<string, any>;
    project_id?: string | null;
  },
): Promise<{
  status: string;
  asset_id: string;
  audio_url?: string;
  download_url?: string;
  voice_used?: string | null;
  warning?: string | null;
  warnings?: string[];
  persona_id?: string | null;
  persona_version?: number | null;
  mature?: boolean;
  character_count?: number;
  metadata?: Record<string, any>;
}> {
  return apiRequest('/v1/personas/' + encodeURIComponent(personaId) + '/speak', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchAudioVoices(): Promise<any[]> {
  const data = await apiRequest('/v1/audio/voices');
  return data.voices || [];
}

/* ---------------------------------------------------------------------------
 * Assets, Lineage & C2PA Credentials
 * ------------------------------------------------------------------------- */

/** Persisted assets for the tenant (GET /v1/assets). */
export async function fetchAssets(
  projectId?: string | null,
  contentMode?: ContentMode | null,
): Promise<StudioAsset[]> {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (contentMode) params.set('content_mode', contentMode);
  const qs = params.toString() ? `?${params.toString()}` : '';
  const data = await apiRequest('/v1/assets' + qs);
  return (data.assets || []).filter((a: any) => a && a.id && a.download_url).map(mapPersistedAsset);
}

/** Fetch a single asset with a freshly signed download_url. */
export async function fetchAsset(assetId: string): Promise<StudioAsset> {
  const data = await apiRequest('/v1/assets/' + encodeURIComponent(assetId));
  return mapPersistedAsset(data);
}

export interface AssetLineageResponse {
  ancestors: string[];
  descendants: string[];
  depicts?: { id?: string; persona_id?: string | null; persona_version?: number | null; mature?: boolean; job_id?: string | null }[];
  edges?: { parent_asset_id?: string | null; child_asset_id?: string; relationship_type?: string; persona_id?: string | null; persona_version?: number | null }[];
}

export async function fetchAssetLineage(assetId: string): Promise<AssetLineageResponse> {
  const data = await apiRequest('/v1/assets/' + encodeURIComponent(assetId) + '/lineage');
  return {
    ancestors: data.ancestors || [],
    descendants: data.descendants || [],
    depicts: data.depicts || [],
    edges: data.edges || [],
  };
}

/** Fetch C2PA Content Credentials manifest for an asset (gracefully returns null if not available yet). */
export async function fetchAssetCredentials(assetId: string): Promise<Record<string, any> | null> {
  try {
    return await apiRequest('/v1/assets/' + encodeURIComponent(assetId) + '/credentials');
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 501)) return null;
    throw err;
  }
}

/* ---------------------------------------------------------------------------
 * Recipes (Bible v2 §42 — UI hooks ready for PR8)
 * ------------------------------------------------------------------------- */

export async function fetchRecipes(
  projectId?: string | null,
  contentMode?: ContentMode | null,
): Promise<RecipeSummary[]> {
  const params = new URLSearchParams();
  if (projectId) params.set('project_id', projectId);
  if (contentMode) params.set('content_mode', contentMode);
  const qs = params.toString() ? `?${params.toString()}` : '';
  try {
    const data = await apiRequest('/v1/recipes' + qs);
    return data.recipes || [];
  } catch (err) {
    if (err instanceof ApiError && (err.status === 404 || err.status === 501)) return [];
    throw err;
  }
}

export async function replayRecipe(recipeId: string): Promise<any> {
  return apiRequest('/v1/recipes/' + encodeURIComponent(recipeId) + '/replay', {
    method: 'POST',
    body: JSON.stringify({}),
  });
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
