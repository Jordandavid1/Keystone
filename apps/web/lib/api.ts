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
