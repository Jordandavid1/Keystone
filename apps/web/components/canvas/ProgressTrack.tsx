'use client';

import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { CUSTOMER_STAGES, isRefining, stageIndexOf } from '@/lib/progress';
import { Generation } from '@/lib/types';

export function useElapsed(run: Generation | null): number {
  const [now, setNow] = useState(() => Date.now());
  const active = !!run && (run.status === 'queued' || run.status === 'processing');
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(t);
  }, [active]);
  if (!run) return 0;
  return (run.finishedAt || now) - run.startedAt;
}

/**
 * The seven Bible §25 stages as a segmented track, driven by the server's job
 * state. Only stages the job has actually reached are lit; a failed run shows
 * the stage it stopped in.
 */
export function ProgressTrack({ run, className }: { run: Generation; className?: string }) {
  const failed = run.status === 'failed';
  const idx = failed ? (run.failedAt ? stageIndexOf(run.failedAt) : -1) : stageIndexOf(run.jobState);
  const refining = isRefining(run.jobState);
  return (
    <ol className={cn('flex w-full gap-1', className)} aria-label="Progress">
      {CUSTOMER_STAGES.map((label, i) => {
        const done = idx > i || run.status === 'succeeded';
        const current = idx === i && run.status !== 'succeeded';
        return (
          <li key={label} className="relative h-[3px] flex-1 overflow-hidden rounded-full bg-white/[0.08]" title={label}>
            <span className="sr-only">
              {label}: {done ? 'done' : current ? (failed ? 'stopped here' : 'in progress') : 'not started'}
            </span>
            {done && <span className="absolute inset-0 bg-ks-ink-2" />}
            {current && failed && <span className="absolute inset-0 bg-ks-deny" />}
            {current && !failed && (
              <span
                className={cn(
                  'absolute inset-0 animate-cognition-pulse',
                  refining ? 'bg-ks-hold' : 'bg-[image:var(--ks-accent-gradient)]',
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Where a failed run stopped, in customer language, when the server told us. */
export function stoppedAt(run: Generation): string | null {
  if (run.status !== 'failed' || !run.failedAt) return null;
  const idx = stageIndexOf(run.failedAt);
  return idx >= 0 ? CUSTOMER_STAGES[idx] : null;
}

export function stageLabel(run: Generation): string {
  if (run.status === 'failed') return 'Stopped';
  if (run.status === 'succeeded') return 'Finished';
  const idx = stageIndexOf(run.jobState);
  return idx >= 0 ? CUSTOMER_STAGES[idx] : 'Stopped';
}
