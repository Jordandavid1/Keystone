/** Turn an API failure into a sentence a person can act on, keeping the real cause. */
export function readableError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  // The API answers 401 when no session or API key is attached. Say so plainly.
  if (/\[401\]|Unauthorized/i.test(raw)) return 'you are not signed in, so the API refused the request.';
  return raw;
}
