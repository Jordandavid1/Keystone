import { proxyToBackend } from '@/lib/backendProxy';

export const dynamic = 'force-dynamic';

export {
  proxyToBackend as GET,
  proxyToBackend as POST,
  proxyToBackend as PUT,
  proxyToBackend as PATCH,
  proxyToBackend as DELETE,
  proxyToBackend as OPTIONS,
  proxyToBackend as HEAD,
};
