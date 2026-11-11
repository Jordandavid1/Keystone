'use client';

import React from 'react';
import Link from 'next/link';
import { KeyRound, LogIn, LogOut, Wrench } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { setApiKey, setToken } from '@/lib/auth';
import { useStudio } from '@/lib/studio/store';
import { cn } from '@/lib/utils';

const VIA_LABEL = {
  token: 'Signed in',
  api_key: 'Using an API key',
  dev_bypass: 'Dev bypass (local only)',
} as const;

/** Top-bar identity: who the API thinks you are, and how. */
export function AccountMenu() {
  const { state, dispatch } = useStudio();
  const { session } = state.system;

  const openAccount = () => {
    dispatch({ type: 'UI', patch: { settingsTab: 'account' } });
    dispatch({ type: 'OPEN_MODAL', modal: 'settings' });
  };

  if (session.status === 'checking') return null;

  if (session.status !== 'signed_in' || !session.user) {
    return (
      <Button asChild variant="outline" size="sm" className="shrink-0">
        <Link href="/login">
          <LogIn /> <span className="max-sm:hidden">Sign in</span>
        </Link>
      </Button>
    );
  }

  const user = session.user;
  const name = user.display_name || user.email;
  const initial = (name || '?').trim().charAt(0).toUpperCase();
  const via = session.via || 'token';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={`Account: ${name}`}
          className={cn(
            'flex size-8 shrink-0 items-center justify-center rounded-full border text-meta font-semibold text-ks-ink transition-colors hover:bg-ks-lift',
            via === 'dev_bypass' ? 'border-ks-hold/60' : 'border-ks-line-strong',
          )}
        >
          {via === 'dev_bypass' ? <Wrench className="size-3.5 text-ks-hold" /> : initial}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="font-normal">
          <div className="truncate text-body text-ks-ink">{name}</div>
          {user.display_name && <div className="truncate text-meta text-ks-ink-3">{user.email}</div>}
          <div className={cn('mt-1 text-meta', via === 'dev_bypass' ? 'text-ks-hold' : 'text-ks-ink-2')}>{VIA_LABEL[via]}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={openAccount}>
          <KeyRound className="size-3.5" /> Account and API keys
        </DropdownMenuItem>
        {via === 'token' && (
          <DropdownMenuItem onSelect={() => setToken(null)}>
            <LogOut className="size-3.5" /> Sign out
          </DropdownMenuItem>
        )}
        {via === 'api_key' && (
          <DropdownMenuItem onSelect={() => setApiKey(null)}>
            <LogOut className="size-3.5" /> Forget this API key
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
