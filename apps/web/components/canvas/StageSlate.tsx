'use client';

import React from 'react';
import { RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatElapsed } from '@/lib/progress';
import { AspectRatio, Generation, Intent } from '@/lib/types';
import { ProgressTrack, stageLabel, stoppedAt, useElapsed } from './ProgressTrack';

const INVITATION: Record<Intent, { title: string; body: string }> = {
  create: {
    title: 'Describe the first frame.',
    body: 'Type what you want to see and press Enter. Drop an image anywhere to start from it instead.',
  },
  edit: {
    title: 'Choose an image to edit.',
    body: 'Select one from Assets, drop a file here, or paste from your clipboard. Then say what should change.',
  },
  animate: {
    title: 'Set a still in motion.',
    body: 'Attach an image to animate it, or describe a whole shot and KEYSTONE will create it as video.',
  },
  analyze: {
    title: 'Ask about an asset or an idea.',
    body: 'Select an asset to discuss it, or ask a question about your next shot.',
  },
};

function ratioValue(aspect: AspectRatio): number {
  const [w, h] = aspect.split(':').map(Number);
  return w && h ? w / h : 16 / 9;
}

/**
 * The stage slate — the one bold element (UI_SCHEMA §1.4.5).
 * A hairline frame at the chosen aspect ratio: an invitation when empty, the live stage name while a run is in flight,
 * the API's own error when it fails.
 */
export function StageSlate({
  intent,
  aspect,
  run,
  engineNotice,
  onRetry,
  onEditPrompt,
}: {
  intent: Intent;
  aspect: AspectRatio;
  run: Generation | null;
  engineNotice?: string | null;
  onRetry?: () => void;
  onEditPrompt?: () => void;
}) {
  const elapsed = useElapsed(run);
  const inFlight = run && (run.status === 'queued' || run.status === 'processing');
  const failed = run && run.status === 'failed';
  const r = ratioValue(aspect);

  return (
    <div className="flex size-full items-center justify-center p-6">
      <div
        className={cn(
          'relative flex max-h-full min-h-fit w-full flex-col justify-end overflow-hidden rounded-frame border',
          inFlight ? 'border-ks-indigo/30 bg-ks-indigo/[0.025]' : failed ? 'border-ks-deny/30' : 'border-ks-line-strong',
        )}
        style={{ aspectRatio: `${r}`, maxWidth: `min(100%, calc((100dvh - var(--ks-reserved, 300px)) * ${r}))` }}
        role={inFlight ? 'status' : failed ? 'alert' : undefined}
        aria-live="polite"
      >
        {/* Ratio tick — tells you the shape of what you're about to make */}
        <span className="absolute left-3 top-2.5 text-micro text-ks-ink-3">{aspect}</span>

        <div className="relative p-[clamp(20px,4vw,40px)]">
          {inFlight ? (
            <>
              <div className="mb-3 flex items-center gap-2 text-meta text-ks-ink-2">
                <span className="size-1.5 animate-cognition-pulse rounded-full bg-ks-violet" aria-hidden="true" />
                <span className="ks-num">{formatElapsed(elapsed)}</span>
              </div>
              <h2 className="text-[26px] font-semibold leading-[1.1] text-ks-ink sm:text-stage">{stageLabel(run!)}</h2>
              {run!.prompt && <p className="mt-2 line-clamp-2 max-w-[60ch] text-lead text-ks-ink-2">{run!.prompt}</p>}
              <ProgressTrack run={run!} className="mt-6 max-w-[520px]" />
              <p className="mt-2 min-h-[16px] max-w-[520px] text-meta text-ks-ink-3">
                {run!.progress === 'live' && run!.stepNote
                  ? run!.stepNote
                  : run!.progress === 'unavailable'
                    ? "This server doesn't report live progress, so the track shows only that the run is going."
                    : null}
              </p>
            </>
          ) : failed ? (
            <>
              <h2 className="text-[26px] font-semibold leading-[1.1] text-ks-ink sm:text-stage">That run didn't finish.</h2>
              {stoppedAt(run!) && (
                <div className="mt-4 max-w-[520px]">
                  <ProgressTrack run={run!} />
                  <p className="mt-2 text-meta text-ks-ink-3">Stopped at: {stoppedAt(run!)}</p>
                </div>
              )}
              <p className="mt-2 max-w-[64ch] whitespace-pre-wrap break-words text-lead text-ks-deny/90">{run!.error}</p>
              <div className="mt-5 flex gap-2">
                {onRetry && (
                  <Button variant="outline" onClick={onRetry}>
                    <RotateCcw /> Try again
                  </Button>
                )}
                {onEditPrompt && (
                  <Button variant="ghost" onClick={onEditPrompt}>
                    Edit the prompt
                  </Button>
                )}
              </div>
            </>
          ) : (
            <>
              <h2 className="text-[26px] font-semibold leading-[1.1] text-ks-ink sm:text-stage">{INVITATION[intent].title}</h2>
              <p className="mt-2 max-w-[56ch] text-lead text-ks-ink-2">{INVITATION[intent].body}</p>
              {engineNotice && <p className="mt-3 max-w-[56ch] text-body text-ks-hold">{engineNotice}</p>}
            </>
          )}
        </div>

        {inFlight && (
          <span className="pointer-events-none absolute inset-x-0 bottom-0 h-px overflow-hidden" aria-hidden="true">
            <span className="absolute inset-y-0 left-0 w-1/3 animate-exposure-sweep bg-gradient-to-r from-transparent via-ks-violet to-transparent" />
          </span>
        )}
      </div>
    </div>
  );
}
