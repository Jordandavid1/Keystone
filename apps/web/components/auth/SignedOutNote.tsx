'use client';

import React from 'react';
import Link from 'next/link';
import { KeyRound, LogIn } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useStudio } from '@/lib/studio/store';

/**
 * The real signed-out state for account-scoped panels (assets, jobs, projects, personas).
 * Says what's missing and offers the two ways in. While the check runs, it shows nothing.
 */
export function SignedOutNote({ what, compact = false }: { what: string; compact?: boolean }) {
  const { state, dispatch } = useStudio();
  const { session } = state.system;
  if (session.status === 'checking' || session.status === 'signed_in') return null;

  const openKey = () => {
    dispatch({ type: 'UI', patch: { settingsTab: 'account' } });
    dispatch({ type: 'OPEN_MODAL', modal: 'settings' });
  };

  if (session.status === 'error') {
    return (
      <div className="px-4 text-meta text-ks-deny">
        Couldn't check your sign-in: {session.error}
      </div>
    );
  }

  return (
    <div className="px-4">
      <p className="text-meta text-ks-ink-2">
        {session.error ? `${session.error} ` : ''}Sign in to see {what}.
        {!compact && ' Results you make in this session still appear here.'}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Button asChild size="sm" variant="outline">
          <Link href="/login">
            <LogIn /> Sign in
          </Link>
        </Button>
        <Button size="sm" variant="ghost" onClick={openKey}>
          <KeyRound /> Use an API key
        </Button>
      </div>
    </div>
  );
}
