'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Copy, LogIn, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ApiKeySummary, createApiKey, listApiKeys } from '@/lib/api';
import { setApiKey, setToken } from '@/lib/auth';
import { readableError } from '@/lib/errors';
import { useStudio } from '@/lib/studio/store';
import { ApiKeyForm } from './ApiKeyForm';

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2 border-b border-ks-line pb-5 last:border-0">
      <h3 className="text-body font-semibold text-ks-ink">{title}</h3>
      {children}
    </section>
  );
}

/** Settings → Account: the three ways in (sign-in, API key, dev bypass) and key management. */
export function AccountSettings() {
  const { state } = useStudio();
  const { session } = state.system;
  const signedIn = session.status === 'signed_in' && !!session.user;

  const [keys, setKeys] = useState<ApiKeySummary[] | null>(null);
  const [keysError, setKeysError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<{ raw: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!signedIn) {
      setKeys(null);
      return;
    }
    listApiKeys()
      .then((k) => (setKeys(k), setKeysError(null)))
      .catch((err) => setKeysError(readableError(err)));
  }, [signedIn, session.user?.id, created]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setKeysError(null);
    try {
      const res = await createApiKey(name.trim());
      setCreated({ raw: res.raw_key, name: res.name });
      setName('');
      setCopied(false);
    } catch (err) {
      setKeysError(readableError(err));
    } finally {
      setCreating(false);
    }
  };

  const devBypassOn = !!session.mode?.dev_bypass;

  return (
    <div className="flex flex-col gap-5 px-[22px] py-[18px] font-sans">
      <Block title="Signed in as">
        {session.status === 'checking' ? (
          <p className="text-meta text-ks-ink-3">Checking…</p>
        ) : signedIn ? (
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-body text-ks-ink">{session.user!.display_name || session.user!.email}</div>
              <div className="truncate text-meta text-ks-ink-3">
                {session.user!.email} ·{' '}
                {session.via === 'dev_bypass' ? 'dev bypass' : session.via === 'api_key' ? 'API key' : 'password sign-in'}
              </div>
            </div>
            {session.via === 'token' && (
              <Button size="sm" variant="ghost" onClick={() => setToken(null)}>
                <LogOut /> Sign out
              </Button>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <p className="text-meta text-ks-ink-2">
              {session.status === 'error' ? `Couldn't check: ${session.error}` : session.error || 'Not signed in.'}
            </p>
            <Button asChild size="sm" variant="outline">
              <Link href="/login">
                <LogIn /> Sign in
              </Link>
            </Button>
          </div>
        )}
      </Block>

      <Block title="API key">
        <ApiKeyForm />
      </Block>

      {signedIn && (
        <Block title="Create a key">
          <form onSubmit={create} className="flex gap-2">
            <label htmlFor="ks-key-name" className="sr-only">
              Key name
            </label>
            <input
              id="ks-key-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name it, e.g. the laptop it's for"
              className="h-9 min-w-0 flex-1 rounded-control border border-ks-line-strong bg-ks-abyss px-3 text-body text-ks-ink placeholder:text-ks-ink-3 focus-visible:!shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ks-indigo"
            />
            <Button type="submit" variant="outline" disabled={creating || !name.trim()}>
              {creating ? 'Creating…' : 'Create key'}
            </Button>
          </form>
          {created && (
            <div className="rounded-control border border-ks-hold/40 bg-ks-hold/[0.06] p-3">
              <p className="text-meta text-ks-hold">Copy “{created.name}” now. The server keeps only its hash, so it can't be shown again.</p>
              <div className="ks-num mt-2 break-all text-body text-ks-ink">{created.raw}</div>
              <div className="mt-2 flex gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigator.clipboard?.writeText(created.raw).then(() => setCopied(true))}
                >
                  <Copy /> {copied ? 'Copied' : 'Copy'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setApiKey(created.raw)}>
                  Use it in this browser
                </Button>
              </div>
            </div>
          )}
          {keysError && <p className="text-meta text-ks-deny">{keysError}</p>}
          {keys && keys.length > 0 && (
            <ul className="flex flex-col text-meta">
              {keys.map((k) => (
                <li key={k.id} className="flex items-center justify-between gap-2 py-1">
                  <span className="truncate text-ks-ink-2">{k.name}</span>
                  <span className="ks-num shrink-0 text-ks-ink-3">
                    {k.key_prefix}… {k.status && k.status !== 'active' ? `· ${k.status}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {keys && keys.length === 0 && !created && <p className="text-meta text-ks-ink-3">No keys on this account yet.</p>}
        </Block>
      )}

      <Block title="Dev bypass">
        <p className="text-meta text-ks-ink-2">
          {session.mode == null
            ? "The server didn't say whether dev bypass is on."
            : devBypassOn
              ? 'On for this server. Requests from this machine that carry no session or key run as the local developer account.'
              : 'Off for this server.'}
        </p>
        <p className="text-meta text-ks-ink-3">
          Set <span className="ks-num">KEYSTONE_DEV_AUTH_BYPASS=1</span> where the API runs to turn it on. It only applies to requests from the same machine. Never set it on a deployed server.
        </p>
      </Block>
    </div>
  );
}
