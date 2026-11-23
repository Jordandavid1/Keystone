import { NextRequest } from 'next/server';

const BACKEND_ORIGIN = (process.env.KEYSTONE_API_ORIGIN || 'http://127.0.0.1:8000').replace(/\/+$/, '');

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
  'content-encoding',
]);

/** Forward /v1, /internal, and /admin requests using native fetch instead of http-proxy (avoids DEP0060 util._extend). */
export async function proxyToBackend(request: NextRequest): Promise<Response> {
  const { pathname, search } = request.nextUrl;
  const targetUrl = `${BACKEND_ORIGIN}${pathname}${search}`;

  const upstreamHeaders = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      upstreamHeaders.set(key, value);
    }
  });
  // Request uncompressed responses so Content-Type / binary media pass through unchanged.
  upstreamHeaders.set('accept-encoding', 'identity');
  if (!upstreamHeaders.has('x-forwarded-host')) {
    const host = request.headers.get('host');
    if (host) upstreamHeaders.set('x-forwarded-host', host);
  }
  const existingXff = request.headers.get('x-forwarded-for');
  const clientIp = (request as NextRequest & { ip?: string }).ip || request.headers.get('x-real-ip') || '127.0.0.1';
  upstreamHeaders.set('x-forwarded-for', existingXff ? `${existingXff}, ${clientIp}` : clientIp);

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  const init: RequestInit & { duplex?: 'half' } = {
    method: request.method,
    headers: upstreamHeaders,
    redirect: 'manual',
    cache: 'no-store',
  };
  if (hasBody && request.body) {
    init.body = request.body;
    init.duplex = 'half';
  }

  try {
    const upstream = await fetch(targetUrl, init);
    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
        responseHeaders.append(key, value);
      }
    });
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (err: any) {
    return Response.json(
      { detail: `Studio API proxy error connecting to ${BACKEND_ORIGIN}: ${err?.message || String(err)}` },
      { status: 502 },
    );
  }
}
