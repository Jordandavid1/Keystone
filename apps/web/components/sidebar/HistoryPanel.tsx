'use client';
import { readableError } from '@/lib/errors';
import { SignedOutNote } from '../auth/SignedOutNote';

import React, { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStudio } from '@/lib/studio/store';
import { useGeneration } from '@/lib/studio/useGeneration';
import { fetchJobs, JobSummary } from '@/lib/api';
import { STATUS_LABEL, formatElapsed } from '@/lib/progress';
import { TOOLS_CATALOG } from '@/lib/toolsCatalog';
import { Generation } from '@/lib/types';
import { PanelHeader, PanelNote } from './PanelHeader';

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [active]);
  return now;
}

const DOT: Record<Generation['status'], string> = {
  queued: 'bg-ks-ink-3',
  processing: 'bg-ks-indigo animate-cognition-pulse',
  succeeded: 'bg-ks-verified',
  failed: 'bg-ks-deny',
};

/** History — this session's runs (queued → processing → succeeded/failed) plus the server's job list. */
export function HistoryPanel() {
  const { state, dispatch } = useStudio();
  const { retry } = useGeneration();
  const anyActive = state.runs.some((r) => r.status === 'queued' || r.status === 'processing');
  const now = useNow(anyActive);
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);

  const signedIn = state.system.session.status === 'signed_in';
  const userId = state.system.session.user?.id;
  useEffect(() => {
    if (!signedIn) {
      setJobs(null);
      setJobsError(null);
      return;
    }
    let cancelled = false;
    fetchJobs()
      .then((j) => !cancelled && (setJobs(j), setJobsError(null)))
      .catch((err) => !cancelled && setJobsError(readableError(err)));
    return () => {
      cancelled = true;
    };
  }, [state.runs.length, signedIn, userId]);

  const open = (run: Generation) => {
    if (run.outputIds[0]) {
      dispatch({ type: 'SELECT_ASSET', id: run.outputIds[0] });
      dispatch({ type: 'SET_VIEW', view: run.outputIds.length > 1 ? 'variations' : 'single' });
    } else if (run.text) {
      dispatch({ type: 'SHOW_ANALYSIS', runId: run.id });
    }
  };

  return (
    <div className="flex flex-col pb-6">
      <PanelHeader title="History" />
      {state.runs.length === 0 ? (
        <PanelNote>Runs from this session appear here with their status, time and result.</PanelNote>
      ) : (
        <ol className="flex flex-col px-2" aria-label="Runs this session">
          {state.runs.map((run) => {
            const elapsed = (run.finishedAt || now) - run.startedAt;
            const clickable = run.outputIds.length > 0 || !!run.text;
            return (
              <li key={run.id}>
                <div
                  className={cn('rounded-control px-2 py-2', clickable && 'cursor-pointer hover:bg-ks-lift')}
                  onClick={clickable ? () => open(run) : undefined}
                  onKeyDown={clickable ? (e) => e.key === 'Enter' && open(run) : undefined}
                  role={clickable ? 'button' : undefined}
                  tabIndex={clickable ? 0 : undefined}
                >
                  <div className="flex items-center gap-2">
                    <span className={cn('size-2 shrink-0 rounded-full', DOT[run.status])} aria-hidden="true" />
                    <span className="text-body font-medium text-ks-ink">{run.label}</span>
                    <span className="ml-auto ks-num text-micro text-ks-ink-3">
                      {STATUS_LABEL[run.status]} in {formatElapsed(elapsed)}
                    </span>
                  </div>
                  {run.prompt && <p className="mt-0.5 line-clamp-2 pl-4 text-meta text-ks-ink-2">{run.prompt}</p>}
                  {state.ui.developer && (
                    <p className="mt-0.5 pl-4 font-mono text-micro text-ks-ink-3">{TOOLS_CATALOG[run.capability]?.name || run.capability}</p>
                  )}
                  {run.status === 'failed' && (
                    <div className="mt-1.5 pl-4">
                      <p className="line-clamp-3 text-meta text-ks-deny" title={run.error}>{run.error}</p>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          retry(run.id);
                        }}
                        className="mt-1 inline-flex items-center gap-1 rounded-control px-1.5 py-0.5 text-meta text-ks-ink-2 hover:bg-ks-raised hover:text-ks-ink"
                      >
                        <RotateCcw className="size-3" /> Try again
                      </button>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <div className="mx-4 my-3 h-px bg-ks-line" />
      <PanelHeader title="Jobs on the server" />
      {!signedIn ? (
        <SignedOutNote what="your account's jobs" compact />
      ) : jobsError ? (
        <PanelNote tone="error">Jobs didn't load: {jobsError}</PanelNote>
      ) : jobs == null ? (
        <PanelNote>Loading jobs…</PanelNote>
      ) : jobs.length === 0 ? (
        <PanelNote>No jobs recorded for this account yet.</PanelNote>
      ) : (
        <ul className="flex flex-col px-4 text-meta">
          {jobs.slice(0, 50).map((job) => (
            <li key={job.id} className="flex items-center justify-between gap-2 py-1">
              <span className="truncate text-ks-ink-2" title={job.id}>
                {job.created_at ? new Date(job.created_at).toLocaleString() : job.id.slice(0, 8)}
              </span>
              <span className="shrink-0 text-ks-ink-3">{job.state.toLowerCase().replace(/_/g, ' ')}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
