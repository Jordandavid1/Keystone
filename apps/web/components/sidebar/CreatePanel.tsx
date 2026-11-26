'use client';

import React, { useState } from 'react';
import { BookOpen, Check, Cpu, Flame, Layers, Plus, Sparkles, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStudio } from '@/lib/studio/store';
import { TOOLS_CATALOG } from '@/lib/toolsCatalog';
import { GenerativeToolId } from '@/lib/types';
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

const CATEGORY_ORDER: Array<
  'Video Generation' | 'Image Generation' | 'Image Modification' | 'Video Enhancement' | 'Cognition & Audio'
> = [
  'Video Generation',
  'Image Generation',
  'Image Modification',
  'Video Enhancement',
  'Cognition & Audio',
];

/** Create panel — Creative Jobs & MiniMax-H3 Tools, Domain Playbooks, and Persona Cast (`as`). */
export function CreatePanel() {
  const { state, dispatch } = useStudio();
  const { playbooks, playbooksError, playbooksLoaded, personas, personasError, session, engine } = state.system;
  const attached = state.composer.playbook;
  const activePersonaId = state.composer.personaId;
  const explicitTool = state.composer.explicitTool;
  const selectedModel = state.composer.selectedModel;
  const [activeCategory, setActiveCategory] = useState<string>('ALL');

  const allTools = Object.values(TOOLS_CATALOG);
  const visibleTools =
    activeCategory === 'ALL' ? allTools : allTools.filter((t) => t.category === activeCategory);
  const comfyOnline = Boolean(engine?.comfy_online || engine?.comfy?.reachable || engine?.comfy?.configured);

  return (
    <div className="flex flex-col gap-4 pb-6">
      {/* 1. Live Engine Banner + Creative Jobs & MiniMax-H3 Tools */}
      <PanelHeader title="Creative Jobs & MiniMax H3" />
      <div className="mx-3 flex items-center justify-between gap-2 rounded-panel border border-ks-line-strong bg-ks-raised/70 px-3 py-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-meta font-semibold text-ks-ink">
            <span className={cn('size-2 rounded-full', comfyOnline ? 'bg-ks-verified' : 'bg-ks-hold')} />
            <span>{comfyOnline ? 'ComfyUI + MiniMax H3 Online' : 'ComfyUI Runtime Offline'}</span>
          </div>
          <div className="truncate font-mono text-micro text-ks-ink-3">
            {engine?.comfy_base_url || 'Click Configure to launch or connect'}
          </div>
        </div>
        <button
          type="button"
          onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'worker' })}
          className="inline-flex h-7 shrink-0 items-center gap-1 rounded-control border border-ks-indigo/50 bg-ks-indigo/15 px-2.5 text-micro font-semibold text-ks-ink hover:bg-ks-indigo/25"
        >
          <Cpu className="size-3" /> {comfyOnline ? 'Engine' : 'Connect'}
        </button>
      </div>

      {/* Category Filter Pills */}
      <div className="flex flex-wrap gap-1 px-3">
        {(['ALL', ...CATEGORY_ORDER] as const).map((cat) => {
          const shortLabel =
            cat === 'ALL'
              ? 'All (19)'
              : cat === 'Video Generation'
                ? 'Video & H3'
                : cat === 'Image Generation'
                  ? 'Image'
                  : cat === 'Image Modification'
                    ? 'Edit/Swap'
                    : cat === 'Video Enhancement'
                      ? 'Enhance'
                      : 'Cognition';
          const active = activeCategory === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={cn(
                'rounded-full border px-2 py-0.5 text-micro font-medium transition-colors',
                active
                  ? 'border-ks-indigo bg-ks-indigo/20 text-ks-ink'
                  : 'border-ks-line text-ks-ink-3 hover:border-ks-line-strong hover:text-ks-ink',
              )}
            >
              {shortLabel}
            </button>
          );
        })}
      </div>

      {/* All Creative Jobs List */}
      <div className="flex flex-col gap-1 px-2">
        {visibleTools.map((tool) => {
          const isSelected = explicitTool === tool.id;
          const isH3 = tool.id === 'minimax_h3';
          return (
            <div
              key={tool.id}
              className={cn(
                'rounded-control border px-2.5 py-2 transition-colors',
                isSelected
                  ? 'border-ks-indigo/60 bg-ks-indigo/15'
                  : 'border-transparent hover:border-ks-line hover:bg-ks-lift/70',
              )}
            >
              <button
                type="button"
                onClick={() =>
                  dispatch({
                    type: 'SET_TOOL',
                    tool: isSelected ? null : (tool.id as GenerativeToolId),
                  })
                }
                aria-pressed={isSelected}
                className="flex w-full items-start gap-2 text-left"
              >
                {isH3 ? (
                  <Flame className={cn('mt-0.5 size-4 shrink-0', isSelected ? 'text-ks-indigo' : 'text-amber-400')} />
                ) : (
                  <Sparkles className={cn('mt-0.5 size-3.5 shrink-0', isSelected ? 'text-ks-indigo' : 'text-ks-ink-3')} />
                )}
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-1.5">
                    <span className="truncate text-body font-medium text-ks-ink">{tool.name}</span>
                    <span className="shrink-0 rounded border border-ks-line-strong px-1.5 py-px text-micro text-ks-ink-3">
                      {tool.badge}
                    </span>
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-meta text-ks-ink-3">{tool.description}</span>
                </span>
              </button>

              {isSelected && tool.models && tool.models.length > 0 && (
                <div className="mt-2 border-t border-ks-line/60 pt-2">
                  <label className="mb-1 block text-micro font-medium text-ks-ink-2">
                    Active Model / Checkpoint
                  </label>
                  <select
                    aria-label={`Model for ${tool.name}`}
                    value={selectedModel || tool.defaultModel || tool.models[0]}
                    onChange={(e) => dispatch({ type: 'SET_MODEL', model: e.target.value })}
                    className="w-full rounded-control border border-ks-line-strong bg-ks-abyss px-2 py-1 font-mono text-micro text-ks-ink"
                  >
                    {tool.models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mx-4 h-px bg-ks-line" />

      {/* 2. Domain Playbooks */}
      <PanelHeader title="Playbooks" />
      <PanelNote>Attach a playbook to shape every run with its domain brief.</PanelNote>

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
              <ol className="mt-2 list-decimal space-y-1.5 pl-4">
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
          <PanelNote tone="error">Playbooks didn&apos;t load: {playbooksError}</PanelNote>
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

      {/* 3. Personas */}
      <PanelHeader title="Personas">
        <button
          onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'personas' })}
          className="inline-flex items-center gap-1 text-meta text-ks-ink-3 hover:text-ks-ink"
        >
          <Plus className="size-3" /> Manage
        </button>
      </PanelHeader>
      {session.status !== 'signed_in' ? (
        <SignedOutNote what="your personas" compact />
      ) : personasError ? (
        <PanelNote tone="error">Personas didn&apos;t load: {personasError}</PanelNote>
      ) : personas.length === 0 ? (
        <PanelNote>No personas yet. Create one to keep a character and voice consistent across runs.</PanelNote>
      ) : (
        <div className="flex flex-col px-2">
          {personas.map((p) => {
            const active = activePersonaId === p.id;
            return (
              <button
                key={p.id}
                onClick={() => dispatch({ type: 'SET_PERSONA', personaId: active ? null : p.id })}
                aria-pressed={active}
                className={cn(
                  'flex items-center gap-2.5 rounded-control px-2 py-1.5 text-left transition-colors hover:bg-ks-lift',
                  active && 'bg-ks-lift',
                )}
              >
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-ks-raised text-meta font-semibold text-ks-ink">
                  {(p.name || '?').slice(0, 1).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 text-body text-ks-ink">
                    <span className="truncate">{p.name}</span>
                    {p.version ? <span className="text-micro text-ks-ink-3">v{p.version}</span> : null}
                    {p.mature ? <span className="text-micro text-ks-hold">18+</span> : null}
                  </span>
                  <span className="block truncate text-meta text-ks-ink-3">{p.voice_name || 'No voice bound'}</span>
                </span>
                {active && <Check className="size-3.5 shrink-0 text-ks-indigo" aria-hidden="true" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
