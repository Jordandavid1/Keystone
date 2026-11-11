/**
 * Client-side credentials for the KEYSTONE API.
 *
 * Three ways in, all real:
 *  - Sign in (POST /v1/auth/login or /register) stores the bearer token it returns.
 *  - An API key entered in Settings is stored and sent as X-API-Key.
 *  - Dev bypass is a server switch (KEYSTONE_DEV_AUTH_BYPASS=1). The client sends
 *    no credentials and the server reports `auth_via: "dev_bypass"` from /v1/auth/me.
 *
 * A signed-in token wins over a saved key; the key is used when no token is held.
 */

const TOKEN_KEY = 'keystone.auth.token';
const API_KEY_KEY = 'keystone.auth.apiKey';
const CHANGE_EVENT = 'keystone-auth-change';

export type AuthVia = 'token' | 'api_key' | 'dev_bypass';

function read(key: string): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const v = window.localStorage.getItem(key);
    return v && v.trim() ? v : null;
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  if (typeof window === 'undefined') return;
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    /* storage unavailable (private mode); the credential lasts for this page only */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export const getToken = () => read(TOKEN_KEY);
export const getApiKey = () => read(API_KEY_KEY);
export const setToken = (token: string | null) => write(TOKEN_KEY, token);
export const setApiKey = (key: string | null) => write(API_KEY_KEY, key ? key.trim() : null);

/** Headers for an authenticated call. Empty when nothing is held (dev bypass or signed out). */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  if (token) return { Authorization: `Bearer ${token}` };
  const key = getApiKey();
  if (key) return { 'X-API-Key': key };
  return {};
}

/** Which credential the next request will carry, if any. */
export function heldCredential(): 'token' | 'api_key' | null {
  if (getToken()) return 'token';
  if (getApiKey()) return 'api_key';
  return null;
}

/** Called when the API rejects a bearer token: it has expired or been revoked. */
export function dropRejectedToken() {
  if (getToken()) setToken(null);
}

export function onAuthChange(fn: () => void): () => void {
  if (typeof window === 'undefined') return () => undefined;
  const storage = (e: StorageEvent) => {
    if (e.key === TOKEN_KEY || e.key === API_KEY_KEY) fn();
  };
  window.addEventListener(CHANGE_EVENT, fn);
  window.addEventListener('storage', storage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, fn);
    window.removeEventListener('storage', storage);
  };
}

/** Show a key without exposing it: first 8 characters, then an ellipsis. */
export function maskKey(key: string): string {
  return key.length <= 10 ? '••••' : `${key.slice(0, 8)}…`;
}
