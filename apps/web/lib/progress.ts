import { JobState, RunStatus } from './types';

/** Bible §25 customer progress language, in order. */
export const CUSTOMER_STAGES = [
  'Understanding your request',
  'Planning the generation',
  'Preparing the workflow',
  'Creating',
  'Checking the result',
  'Refining when necessary',
  'Finishing',
] as const;

export type CustomerStage = (typeof CUSTOMER_STAGES)[number];

const STAGE_OF: Record<JobState, number> = {
  CREATED: 0,
  VALIDATING: 0,
  PLANNING: 1,
  AUTHORIZING: 2,
  QUEUED: 2,
  RUNNING: 3,
  VALIDATING_OUTPUT: 4,
  RETRY_PENDING: 5,
  REPLAN_REQUIRED: 5,
  COMPLETED: 6,
  FAILED: -1,
  CANCELLED: -1,
  REJECTED: -1,
};

/** Index into CUSTOMER_STAGES, or -1 for terminal failure states. */
export function stageIndexOf(state: JobState): number {
  return STAGE_OF[state] ?? 0;
}

export function isRefining(state: JobState): boolean {
  return state === 'RETRY_PENDING' || state === 'REPLAN_REQUIRED';
}

export function normalizeJobState(raw: unknown): JobState | null {
  if (typeof raw !== 'string') return null;
  const upper = raw.trim().toUpperCase();
  return upper in STAGE_OF ? (upper as JobState) : null;
}

export const STATUS_LABEL: Record<RunStatus, string> = {
  queued: 'Queued',
  processing: 'Processing',
  succeeded: 'Done',
  failed: 'Failed',
};

export function formatElapsed(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`;
}
