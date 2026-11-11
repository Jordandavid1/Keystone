'use client';

import React from 'react';
import { BookOpen, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStudio } from '@/lib/studio/store';
import { SignedOutNote } from '../auth/SignedOutNote';
import { PanelHeader, PanelNote } from './PanelHeader';

function useCaseLabel(useCase: any, idx: number): string {
  if (typeof useCase === 'string') return useCase;
  return useCase?.title || useCase?.name || useCase?.summary || `Use case ${idx + 1}`;
}
function useCaseText(useCase: any): string {
  if (typeof useCase === 'string') return useCase;
  return useCase?.prompt || useCase?.description || useCase?.title || useCase?.name || JSON.stringify(useCase);
}

/** Create panel — Domain Playbooks (attach context, never auto-run) and the persona cast. */
export function CreatePanel() {
  const { state, dispatch } = useStudio();
  const { playbooks, playbooksError, playbooksLoaded, personas, personasError, session } = state.system;
  const attached = state.composer.playbook;

  return (
    <div className="flex flex-col gap-4 pb-6">
      <PanelHeader title="Playbooks" />
      <PanelNote>Attach a playbook to shape every run with its domain brief. Nothing runs until you do.</PanelNote>

      {attached && (
        <section aria-label="Attached playbook" className="mx-3 rounded-panel border border-ks-indigo/40 bg-ks-indigo/[0.07] p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-body font-semibold text-ks-ink">{attached.label}</div>
              <p className="mt-0.5 text-meta text-ks-ink-2">{attached.domain_context?.domain_brief || attached.outcome}</p>
            </div>
            <button
              onClick={() => dispatch({ type: 'SET_PLAYBOOK', playbook: null })}
              className="rounded p-1 text-ks-ink-3 hover:bg-ks-lift hover:text-ks-ink"
              aria-label={`Detach ${attached.label}`}
            >
              <X className="size-3.5" />
            </button>
          </div>

          {(attached.use_cases || []).length > 0 && (
            <div className="mt-3">
              <div className="mb-1.5 text-meta font-medium text-ks-ink-2">Start from a use case</div>
              <div className="flex flex-wrap gap-1.5">
                {(attached.use_cases || []).map((uc: any, idx: number) => {
                  const text = useCaseText(uc);
                  const on = state.composer.useCase === text;
                  return (
                    <button
                      key={uc?.id || idx}
                      onClick={() => dispatch({ type: 'SET_USE_CASE', useCase: on ? null : text })}
                      aria-pressed={on}
                      className={cn(
                        'rounded-control border px-2.5 py-1.5 text-left text-meta transition-colors',
                        on ? 'border-ks-indigo bg-ks-indigo/20 text-ks-ink' : 'border-ks-line-strong text-ks-ink-2 hover:text-ks-ink',
                      )}
                    >
                      {useCaseLabel(uc, idx)}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {(attached.path || []).length > 0 && (
            <details className="mt-3 text-meta text-ks-ink-2">
              <summary className="cursor-pointer text-ks-ink-2 hover:text-ks-ink">How this playbook works</summary>
              <ol className="mt-2 space-y-1.5 pl-4 list-decimal">
                {(attached.path || []).map((step, idx) => (
                  <li key={step.title || idx}>
                    <span className="text-ks-ink">{step.title}</span> — {step.objective}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </section>
      )}

      <div className="flex flex-col px-2">
        {!playbooksLoaded ? (
          <PanelNote>Loading playbooks…</PanelNote>
        ) : playbooksError ? (
          <PanelNote tone="error">Playbooks didn't load: {playbooksError}</PanelNote>
        ) : playbooks.length === 0 ? (
          <PanelNote>The studio API returned no playbooks.</PanelNote>
        ) : (
          playbooks.map((pb) => {
            const on = attached?.id === pb.id;
            return (
              <button
                key={pb.id}
                onClick={() => dispatch({ type: 'SET_PLAYBOOK', playbook: on ? null : pb })}
                aria-pressed={on}
                className={cn(
                  'group flex items-start gap-2.5 rounded-control px-2 py-2 text-left transition-colors hover:bg-ks-lift',
                  on && 'bg-ks-lift',
                )}
              >
                <BookOpen className={cn('mt-0.5 size-4 shrink-0', on ? 'text-ks-indigo' : 'text-ks-ink-3')} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body text-ks-ink">{pb.label}</span>
                  <span className="line-clamp-2 text-meta text-ks-ink-3">{pb.outcome}</span>
                </span>
                {on && <Check className="mt-0.5 size-3.5 text-ks-indigo" aria-hidden="true" />}
              </button>
            );
          })
        )}
      </div>

      <div className="mx-4 h-px bg-ks-line" />

      <PanelHeader title="Personas">
        <button
          onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'personas' })}
          className="rounded-control px-2 py-1 text-meta text-ks-ink-2 hover:bg-ks-lift hover:text-ks-ink"
        >
          Manage
        </button>
      </PanelHeader>
      {session.status !== 'signed_in' ? (
        <SignedOutNote what="your personas" compact />
      ) : personasError ? (
        <PanelNote tone="error">Personas didn't load: {personasError}</PanelNote>
      ) : personas.length === 0 ? (
        <PanelNote>No personas yet. Create one to keep a character and voice consistent across runs.</PanelNote>
      ) : (
        <div className="flex flex-col px-2">
          {personas.map((p) => (
            <button
              key={p.id}
              onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'personas' })}
              className="flex items-center gap-2.5 rounded-control px-2 py-1.5 text-left hover:bg-ks-lift"
            >
              <span className="flex size-7 items-center justify-center rounded-full bg-ks-lift text-meta font-semibold text-ks-ink">
                {p.name.slice(0, 1).toUpperCase()}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-body text-ks-ink">{p.name}</span>
                <span className="block truncate text-meta text-ks-ink-3">{p.voice_name || 'No voice assigned'}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
