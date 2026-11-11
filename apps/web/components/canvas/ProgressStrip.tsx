'use client';

import React from 'react';
import { formatElapsed } from '@/lib/progress';
import { Generation } from '@/lib/types';
import { ProgressTrack, stageLabel, useElapsed } from './ProgressTrack';

/** Compact progress shown over the stage when an earlier asset is still on screen. */
export function ProgressStrip({ run }: { run: Generation }) {
  const elapsed = useElapsed(run);
  return (
    <div
      role="status"
      aria-live="polite"
      className="ks-glass pointer-events-auto flex w-[min(520px,calc(100%-32px))] flex-col gap-2 rounded-panel px-3.5 py-2.5 shadow-float"
    >
      <div className="flex items-center gap-2 text-meta">
        <span className="size-1.5 animate-cognition-pulse rounded-full bg-ks-violet" aria-hidden="true" />
        <span className="font-medium text-ks-ink">{stageLabel(run)}</span>
        <span className="truncate text-ks-ink-3">{run.prompt}</span>
        <span className="ks-num ml-auto shrink-0 text-ks-ink-3">{formatElapsed(elapsed)}</span>
      </div>
      <ProgressTrack run={run} />
      {run.progress === 'live' && run.stepNote && <p className="truncate text-micro text-ks-ink-3">{run.stepNote}</p>}
    </div>
  );
}
