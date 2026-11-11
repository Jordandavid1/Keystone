'use client';

import { useCallback, useRef } from 'react';
import { ApiError, GenerationJob, executeGenerativeTool, fetchCreditLedger, fetchGenerationJob, uploadMediaFile } from '../api';
import { INTENT_BY_ID, buildInput, compilePrompt, estimateCredits, routeIntent } from '../intents';
import { normalizeJobState } from '../progress';
import { TOOLS_CATALOG } from '../toolsCatalog';
import { Generation, GenerativeToolId, Intent, JobState, StudioAsset } from '../types';
import { selectSelected, useStudio } from './store';

const TERMINAL: JobState[] = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'];
const POLL_MS = 500;

function newJobId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // RFC 4122 v4 from getRandomValues for browsers without randomUUID (older Safari, http origins).
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** Last state the job reached before it failed, from the server's event list. */
function stateBeforeFailure(job: GenerationJob): JobState | null {
  for (let i = job.events.length - 1; i >= 0; i -= 1) {
    const st = normalizeJobState(job.events[i].state);
    if (st && !TERMINAL.includes(st)) return st;
  }
  return null;
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function titleFrom(prompt: string, fallback: string): string {
  const clean = prompt.replace(/\s+/g, ' ').trim();
  if (!clean) return fallback;
  return clean.length > 56 ? clean.slice(0, 55).trimEnd() + '…' : clean;
}

export interface RunOptions {
  intent?: Intent;
  /** Set by context-bar verbs (upscale, variation) that name the capability directly. */
  capability?: GenerativeToolId;
  references?: StudioAsset[];
  prompt?: string;
  label?: string;
  extra?: Record<string, any>;
}

export function useGeneration() {
  const { state, dispatch } = useStudio();
  const stateRef = useRef(state);
  stateRef.current = state;

  const execute = useCallback(
    async (run: Generation) => {
      const jobId = newJobId();
      dispatch({ type: 'RUN_STARTED', run: { ...run, jobId, progress: 'pending', status: 'queued', jobState: 'CREATED', stepNote: null, failedAt: null } });

      // Read real staged progress while the (synchronous) generate request is in flight.
      let settled = false;
      let lastSeen: GenerationJob | null = null;
      const apply = (job: GenerationJob) => {
        lastSeen = job;
        const st = normalizeJobState(job.current_state);
        if (!st || TERMINAL.includes(st)) return;
        dispatch({
          type: 'RUN_UPDATED',
          id: run.id,
          patch: {
            progress: 'live',
            jobState: st,
            status: st === 'CREATED' || st === 'VALIDATING' ? 'queued' : 'processing',
            stepNote: job.events[job.events.length - 1]?.reason || null,
          },
        });
      };
      const poll = (async () => {
        let misses = 0;
        while (!settled) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          if (settled) break;
          try {
            apply(await fetchGenerationJob(jobId));
            misses = 0;
          } catch (err) {
            // 404 before the server registers the id is normal for the first poll or two.
            // A server that never knows the id doesn't support live progress.
            misses += 1;
            if (misses >= 6 && !lastSeen) {
              dispatch({ type: 'RUN_UPDATED', id: run.id, patch: { progress: 'unavailable', status: 'processing', jobState: 'RUNNING' } });
              break;
            }
          }
        }
      })();

      try {
        const res = await executeGenerativeTool(run.request.tool, run.request.input, jobId);
        settled = true;
        await poll;
        const reported = normalizeJobState(res.job_state);
        const jobState: JobState = reported || 'COMPLETED';
        if (jobState !== 'COMPLETED') {
          throw new Error(`The job ended as ${jobState.toLowerCase()}.`);
        }
        dispatch({ type: 'RUN_UPDATED', id: run.id, patch: { progress: res.job_id ? 'live' : 'unavailable' } });

        const parentId = run.referenceIds[0] || null;
        const outputs = (res.outputs || [])
          .filter((o) => o.url)
          .map((o, idx, all) => ({
            ...o,
            title: titleFrom(run.prompt, run.label) + (all.length > 1 ? ` (${idx + 1})` : ''),
            parentId: o.parentId || parentId,
            prompt: run.prompt,
          }));

        if (outputs.length) dispatch({ type: 'ASSETS_ADDED', assets: outputs });
        dispatch({
          type: 'RUN_UPDATED',
          id: run.id,
          patch: {
            status: 'succeeded',
            jobState,
            finishedAt: Date.now(),
            outputIds: outputs.map((o) => o.id),
            text: res.text || null,
          },
        });

        if (res.text && !outputs.length) {
          dispatch({ type: 'SHOW_ANALYSIS', runId: run.id });
        } else if (outputs.length > 1) {
          dispatch({ type: 'SET_VIEW', view: 'variations' });
        } else if (outputs.length === 1) {
          const view = stateRef.current.ui.view;
          if (view !== 'compare' && view !== 'lineage') dispatch({ type: 'SET_VIEW', view: 'single' });
        } else if (!res.text) {
          dispatch({
            type: 'RUN_UPDATED',
            id: run.id,
            patch: { status: 'failed', jobState: 'FAILED', error: 'The engine finished without returning any media.' },
          });
        }
      } catch (err) {
        settled = true;
        await poll;
        // Ask the server where the job stopped, so the track shows the real stage.
        let failedAt: JobState | null = null;
        const failedJobId = (err instanceof ApiError && err.jobId) || jobId;
        try {
          failedAt = stateBeforeFailure(await fetchGenerationJob(failedJobId));
        } catch {
          failedAt = lastSeen ? stateBeforeFailure(lastSeen) : null;
        }
        dispatch({
          type: 'RUN_UPDATED',
          id: run.id,
          patch: { status: 'failed', jobState: 'FAILED', finishedAt: Date.now(), error: message(err), failedAt, stepNote: null },
        });
      } finally {
        fetchCreditLedger()
          .then((ledger) => dispatch({ type: 'SYSTEM', patch: { ledger } }))
          .catch(() => undefined);
      }
    },
    [dispatch],
  );

  /** Run the composer's current instruction (or a context-bar verb). Returns blocking problems, if any. */
  const run = useCallback(
    async (opts: RunOptions = {}): Promise<string[]> => {
      const s = stateRef.current;
      const intent = opts.intent || s.composer.intent;
      const prompt = opts.prompt ?? s.composer.prompt;
      const references = opts.references ?? s.composer.references;
      const routed = routeIntent({ intent, prompt, references, engine: s.system.engine });
      const capability = opts.capability || routed.capability;
      const problems = opts.capability ? [] : routed.problems;
      if (problems.length) return problems;

      const compiledPrompt = compilePrompt({
        text: prompt,
        playbook: s.composer.playbook,
        web: s.composer.web,
        lut: s.controls.look.lut,
        useCase: s.composer.useCase,
      });
      const input = buildInput({
        capability,
        compiledPrompt,
        controls: s.controls,
        references,
        playbook: s.composer.playbook,
        web: s.composer.web,
        extra: opts.extra,
      });
      const label = opts.label || INTENT_BY_ID[intent].verb;
      const gen: Generation = {
        id: `run_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
        intent,
        capability,
        label,
        prompt,
        compiledPrompt,
        referenceIds: references.map((r) => r.id),
        playbookId: s.composer.playbook?.id || null,
        status: 'queued',
        jobState: 'VALIDATING',
        startedAt: Date.now(),
        outputIds: [],
        estimatedCredits: estimateCredits(capability, s.controls),
        request: { tool: capability, input },
      };
      void execute(gen);
      return [];
    },
    [execute],
  );

  const retry = useCallback(
    (runId: string) => {
      const prev = stateRef.current.runs.find((r) => r.id === runId);
      if (!prev) return;
      void execute({
        ...prev,
        id: `run_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`,
        status: 'queued',
        jobState: 'VALIDATING',
        startedAt: Date.now(),
        finishedAt: undefined,
        outputIds: [],
        text: null,
        error: null,
      });
    },
    [execute],
  );

  const upscale = useCallback(
    (factor: 2 | 4) => {
      const asset = selectSelected(stateRef.current);
      if (!asset) return;
      const capability: GenerativeToolId = asset.type === 'video' ? 'video_upscaler' : 'upscaler';
      const extra = capability === 'upscaler' ? { target_resolution: factor === 4 ? '4k' : '2k' } : { scale: factor };
      void run({
        intent: 'edit',
        capability,
        references: [asset],
        prompt: asset.prompt || '',
        label: `Upscale ${factor}×`,
        extra,
      });
    },
    [run],
  );

  const variation = useCallback(() => {
    const asset = selectSelected(stateRef.current);
    if (!asset || asset.type !== 'image') return;
    void run({
      intent: 'create',
      capability: 'by_ref',
      references: [asset],
      prompt: stateRef.current.composer.prompt.trim() || asset.prompt || '',
      label: 'Variation',
    });
  }, [run]);

  const upload = useCallback(
    async (file: File, attach: boolean) => {
      try {
        const asset = await uploadMediaFile(file);
        dispatch({ type: 'ASSETS_ADDED', assets: [asset] });
        if (attach) dispatch({ type: 'ADD_REFERENCE', asset });
      } catch (err) {
        dispatch({ type: 'NOTICE', notice: { tone: 'error', text: `Upload failed: ${message(err)}` } });
      }
    },
    [dispatch],
  );

  return { run, retry, upscale, variation, upload, catalog: TOOLS_CATALOG };
}
