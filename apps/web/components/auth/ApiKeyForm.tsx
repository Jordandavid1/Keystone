'use client';

import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { verifyApiKey } from '@/lib/api';
import { getApiKey, maskKey, onAuthChange, setApiKey } from '@/lib/auth';
import { readableError } from '@/lib/errors';

/**
 * Paste a KEYSTONE API key, check it against /v1/auth/me, and keep it in this browser.
 * Nothing is saved until the server accepts the key.
 */
export function ApiKeyForm({ onSaved }: { onSaved?: () => void }) {
  const [saved, setSaved] = useState<string | null>(null);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [okFor, setOkFor] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setSaved(getApiKey());
    sync();
    return onAuthChange(sync);
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const key = value.trim();
    if (!key) return;
    setBusy(true);
    setError(null);
    setOkFor(null);
    try {
      const user = await verifyApiKey(key);
      setApiKey(key);
      setValue('');
      setOkFor(user.email);
      onSaved?.();
    } catch (err) {
      setError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {saved && (
        <div className="flex items-center justify-between gap-2 rounded-control border border-ks-line-strong bg-ks-raised px-3 py-2">
          <div className="min-w-0">
            <div className="text-meta text-ks-ink-3">Saved in this browser</div>
            <div className="ks-num truncate text-body text-ks-ink">{maskKey(saved)}</div>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={() => setApiKey(null)}>
            Remove
          </Button>
        </div>
      )}
      <form onSubmit={save} className="flex flex-col gap-2">
        <label htmlFor="ks-api-key" className={saved ? 'text-meta text-ks-ink-2' : 'sr-only'}>
          {saved ? 'Replace with another key' : 'API key'}
        </label>
        <div className="flex gap-2">
          <input
            id="ks-api-key"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Paste a key"
            className="h-9 min-w-0 flex-1 rounded-control border border-ks-line-strong bg-ks-abyss px-3 text-body text-ks-ink placeholder:text-ks-ink-3 focus-visible:!shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ks-indigo"
          />
          <Button type="submit" disabled={busy || !value.trim()}>
            {busy ? 'Checking…' : 'Check and save'}
          </Button>
        </div>
      </form>
      {error && <p className="text-meta text-ks-deny">That key wasn't accepted: {error}</p>}
      {okFor && <p className="text-meta text-ks-verified">Key accepted for {okFor}.</p>}
      <p className="text-meta text-ks-ink-3">
        The key is stored in this browser and sent as <span className="ks-num">X-API-Key</span>. If you're also signed in, your session is used first.
      </p>
    </div>
  );
}
