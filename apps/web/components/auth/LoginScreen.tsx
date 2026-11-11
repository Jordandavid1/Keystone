'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AuthMode, CurrentUser, fetchAuthMode, fetchCurrentUser, register, signIn } from '@/lib/api';
import { heldCredential, setToken } from '@/lib/auth';
import { readableError } from '@/lib/errors';
import { cn } from '@/lib/utils';
import { KeystoneMark } from '../studio/KeystoneMark';
import { ApiKeyForm } from './ApiKeyForm';

type Mode = 'signin' | 'register' | 'key';

const MODES: { id: Mode; label: string }[] = [
  { id: 'signin', label: 'Sign in' },
  { id: 'register', label: 'Create account' },
  { id: 'key', label: 'API key' },
];

const FIELD =
  'h-10 w-full rounded-control border border-ks-line-strong bg-ks-abyss px-3 text-lead text-ks-ink placeholder:text-ks-ink-3 focus-visible:!shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ks-indigo';

function loginError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  if (/Invalid email or password/i.test(raw)) return "That email and password don't match an account.";
  if (/already exists/i.test(raw)) return 'An account with this email already exists. Sign in instead.';
  return raw;
}

/** /login — the studio's sign-in screen. Stores the bearer token the API issues, then returns to the studio. */
export function LoginScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authMode, setAuthMode] = useState<AuthMode | null>(null);
  const [modeError, setModeError] = useState<string | null>(null);
  const [current, setCurrent] = useState<CurrentUser | null>(null);

  useEffect(() => {
    fetchAuthMode()
      .then(setAuthMode)
      .catch((err) => setModeError(readableError(err)));
    if (heldCredential()) {
      fetchCurrentUser()
        .then(setCurrent)
        .catch(() => setCurrent(null));
    }
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = mode === 'register' ? await register(email.trim(), password, displayName.trim() || undefined) : await signIn(email.trim(), password);
      setToken(res.access_token);
      router.replace('/');
    } catch (err) {
      setError(loginError(err));
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-ks-abyss px-5 py-10 font-sans text-ks-ink">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 flex items-center gap-2.5">
          <KeystoneMark />
          <span className="text-[15px] font-semibold tracking-[0.04em]">KEYSTONE</span>
        </div>

        <h1 className="text-[28px] font-semibold leading-[1.15] tracking-[-0.02em]">
          {mode === 'register' ? 'Make your studio account.' : mode === 'key' ? 'Use an API key.' : 'Sign in to your studio.'}
        </h1>
        <p className="mt-2 text-lead text-ks-ink-2">
          Your assets, projects, personas and job history live with your account.
        </p>

        {current && (
          <div className="mt-6 flex items-center justify-between gap-3 rounded-panel border border-ks-line-strong bg-ks-chrome px-4 py-3">
            <p className="min-w-0 truncate text-body text-ks-ink-2">
              Already signed in as <span className="text-ks-ink">{current.email}</span>
            </p>
            <Button asChild size="sm" variant="ghost">
              <Link href="/">
                Studio <ArrowRight />
              </Link>
            </Button>
          </div>
        )}

        <div role="tablist" aria-label="How to sign in" className="mt-8 grid grid-cols-3 gap-1 rounded-control bg-ks-chrome p-1">
          {MODES.map((m) => (
            <button
              key={m.id}
              role="tab"
              aria-selected={mode === m.id}
              onClick={() => {
                setMode(m.id);
                setError(null);
              }}
              className={cn(
                'h-8 rounded-[6px] text-meta transition-colors',
                mode === m.id ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-3 hover:text-ks-ink',
              )}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="mt-6">
          {mode === 'key' ? (
            <ApiKeyForm onSaved={() => router.replace('/')} />
          ) : (
            <form onSubmit={submit} className="flex flex-col gap-4">
              {mode === 'register' && (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="ks-name" className="text-meta text-ks-ink-2">
                    Name <span className="text-ks-ink-3">(optional)</span>
                  </label>
                  <input id="ks-name" autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} className={FIELD} />
                </div>
              )}
              <div className="flex flex-col gap-1.5">
                <label htmlFor="ks-email" className="text-meta text-ks-ink-2">
                  Email
                </label>
                <input
                  id="ks-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={FIELD}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="ks-password" className="text-meta text-ks-ink-2">
                  Password
                </label>
                <input
                  id="ks-password"
                  type="password"
                  required
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={FIELD}
                />
              </div>
              {error && (
                <p role="alert" className="text-body text-ks-deny">
                  {error}
                </p>
              )}
              <Button type="submit" variant="run" size="lg" disabled={busy} className="mt-1">
                {busy ? (mode === 'register' ? 'Creating account…' : 'Signing in…') : mode === 'register' ? 'Create account' : 'Sign in'}
              </Button>
            </form>
          )}
        </div>

        <div className="mt-8 border-t border-ks-line pt-5 text-meta">
          {modeError ? (
            <p className="text-ks-deny">The studio API isn't reachable: {modeError}</p>
          ) : authMode?.dev_bypass ? (
            <p className="text-ks-hold">
              Dev bypass is on for this server.{' '}
              <Link href="/" className="underline underline-offset-2 hover:text-ks-ink">
                Continue without signing in
              </Link>
            </p>
          ) : (
            <Link href="/" className="text-ks-ink-3 hover:text-ks-ink">
              Back to the studio without signing in
            </Link>
          )}
        </div>
      </div>
    </main>
  );
}
