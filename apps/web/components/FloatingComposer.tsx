'use client';

import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, CornerDownLeft, Film, Globe, Lock, Paperclip, Palette, Pencil, ScanSearch, Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { INTENTS, INTENT_BY_ID, LOOK_LABELS, estimateCredits, routeIntent } from '@/lib/intents';
import { useStudio } from '@/lib/studio/store';
import { useGeneration } from '@/lib/studio/useGeneration';
import { Intent } from '@/lib/types';
import { AssetThumb } from './studio/AssetThumb';
import { IconButton } from './studio/IconButton';

const INTENT_ICON: Record<Intent, React.ElementType> = {
  create: Sparkles,
  edit: Pencil,
  animate: Film,
  analyze: ScanSearch,
};

function Chip({ icon: Icon, label, onRemove, tone = 'default' }: { icon: React.ElementType; label: string; onRemove: () => void; tone?: 'default' | 'accent' }) {
  return (
    <span
      className={cn(
        'inline-flex max-w-[220px] items-center gap-1.5 rounded-full border py-0.5 pl-2 pr-1 text-meta',
        tone === 'accent' ? 'border-ks-indigo/40 bg-ks-indigo/10 text-ks-ink' : 'border-ks-line-strong text-ks-ink-2',
      )}
    >
      <Icon className="size-3 shrink-0" />
      <span className="truncate">{label}</span>
      <button onClick={onRemove} className="rounded-full p-0.5 text-ks-ink-3 hover:bg-white/10 hover:text-ks-ink" aria-label={`Remove ${label}`}>
        <X className="size-3" />
      </button>
    </span>
  );
}

/**
 * Region 5 — the floating composer (Venice-clean): intent, words, attachments, cost and trust, one run button.
 * It never chooses the capability; lib/intents.ts does.
 */
export function FloatingComposer({ onHeight, inputRef }: { onHeight?: (h: number) => void; inputRef?: React.RefObject<HTMLTextAreaElement> }) {
  const { state, dispatch } = useStudio();
  const { run, upload } = useGeneration();
  const { intent, prompt, references, playbook, useCase, web } = state.composer;
  const { engine, ledger } = state.system;
  const ownRef = useRef<HTMLTextAreaElement>(null);
  const textRef = inputRef || ownRef;
  const rootRef = useRef<HTMLElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [problems, setProblems] = useState<string[]>([]);

  const routed = useMemo(() => routeIntent({ intent, prompt, references, engine }), [intent, prompt, references, engine]);
  const credits = estimateCredits(routed.capability, state.controls);
  const def = INTENT_BY_ID[intent];

  useEffect(() => setProblems([]), [intent, prompt, references]);

  // Auto-grow the prompt field (1–6 lines).
  useLayoutEffect(() => {
    const el = textRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 6 * 22 + 16)}px`;
  }, [prompt, textRef]);

  // Width changes (breakpoints, sheets opening) change wrapping, so re-measure then too.
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 6 * 22 + 16)}px`;
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [textRef]);

  useLayoutEffect(() => {
    if (!rootRef.current || !onHeight) return;
    const ro = new ResizeObserver(([entry]) => onHeight(entry.contentRect.height));
    ro.observe(rootRef.current);
    return () => ro.disconnect();
  }, [onHeight]);

  const submit = async () => {
    const found = await run();
    setProblems(found);
  };

  const onPaste = (e: React.ClipboardEvent) => {
    const files = Array.from(e.clipboardData.files || []).filter((f) => /^(image|video|audio)\//.test(f.type));
    if (files.length) {
      e.preventDefault();
      files.forEach((f) => upload(f, true));
    }
  };

  const billingOff = ledger && ledger.balance == null;
  const engineReady = !!engine?.online;

  return (
    <section
      ref={rootRef}
      aria-label="Composer"
      className="ks-glass pointer-events-auto w-full max-w-[760px] rounded-composer border border-ks-line-strong shadow-float transition-colors duration-base focus-within:border-ks-indigo/50"
    >
      {/* Intent switch */}
      <div className="flex items-center gap-1 px-2.5 pt-2.5" role="radiogroup" aria-label="What do you want to do?">
        {INTENTS.map((i) => {
          const Icon = INTENT_ICON[i.id];
          const on = intent === i.id;
          return (
            <button
              key={i.id}
              role="radio"
              aria-checked={on}
              title={`${i.label} (${i.shortcut})`}
              onClick={() => dispatch({ type: 'SET_INTENT', intent: i.id })}
              className={cn(
                'flex h-7 items-center gap-1.5 rounded-full px-3 text-meta font-medium transition-colors duration-quick',
                on ? 'bg-ks-indigo/20 text-ks-ink ring-1 ring-inset ring-ks-indigo/60' : 'text-ks-ink-3 hover:text-ks-ink',
              )}
            >
              <Icon className="size-3.5" />
              {i.label}
            </button>
          );
        })}
      </div>

      {/* Attachments and context */}
      {(references.length > 0 || playbook || useCase || web || state.controls.look.lut !== 'none') && (
        <div className="flex flex-wrap items-center gap-1.5 px-3 pt-2.5">
          {references.map((r) => (
            <span key={r.id} className="group relative">
              <AssetThumb asset={r} className="size-10 rounded-control ring-1 ring-ks-line-strong" />
              <button
                onClick={() => dispatch({ type: 'REMOVE_REFERENCE', id: r.id })}
                className="absolute -right-1.5 -top-1.5 rounded-full bg-ks-lift p-0.5 text-ks-ink-2 ring-1 ring-ks-line-strong hover:text-ks-ink"
                aria-label={`Remove reference ${r.title}`}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
          {playbook && <Chip icon={BookOpen} label={playbook.label} tone="accent" onRemove={() => dispatch({ type: 'SET_PLAYBOOK', playbook: null })} />}
          {useCase && <Chip icon={BookOpen} label={useCase.length > 40 ? useCase.slice(0, 39) + '…' : useCase} onRemove={() => dispatch({ type: 'SET_USE_CASE', useCase: null })} />}
          {web && <Chip icon={Globe} label={web.title || web.url} onRemove={() => dispatch({ type: 'SET_WEB', web: null })} />}
          {state.controls.look.lut !== 'none' && (
            <Chip icon={Palette} label={LOOK_LABELS[state.controls.look.lut] || state.controls.look.lut} onRemove={() => dispatch({ type: 'SET_LOOK', patch: { lut: 'none' } })} />
          )}
        </div>
      )}

      <div className="px-3 pt-2">
        <label htmlFor="ks-prompt" className="sr-only">
          {def.prompt}
        </label>
        <textarea
          id="ks-prompt"
          ref={textRef}
          value={prompt}
          rows={1}
          onChange={(e) => dispatch({ type: 'SET_PROMPT', prompt: e.target.value })}
          onPaste={onPaste}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={`${def.prompt}…`}
          className="block max-h-[148px] min-h-[38px] w-full resize-none bg-transparent py-1.5 text-lead text-ks-ink placeholder:text-ks-ink-3 focus:outline-none focus-visible:outline-none focus-visible:!shadow-none"
        />
      </div>

      {(problems.length > 0 || routed.notices.length > 0) && (
        <div className="space-y-0.5 px-3 pb-1 text-meta" aria-live="polite">
          {problems.map((p) => (
            <p key={p} className="text-ks-hold">
              {p}
            </p>
          ))}
          {routed.notices.map((n) => (
            <p key={n} className="text-ks-ink-3">
              {n}
            </p>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1 px-2 pb-2 pt-1">
        <IconButton label="Attach media" side="top" onClick={() => fileRef.current?.click()}>
          <Paperclip />
        </IconButton>
        <IconButton label="Add a web reference" side="top" onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'web' })}>
          <Globe />
        </IconButton>
        <input
          ref={fileRef}
          type="file"
          hidden
          multiple
          accept="image/*,video/*,audio/*"
          onChange={(e) => {
            Array.from(e.target.files || []).forEach((f) => upload(f, true));
            e.target.value = '';
          }}
        />

        {/* Trust + cost line (Venice + ZenCreator patterns) — only facts the client can verify */}
        <div className="ml-1 flex min-w-0 flex-1 items-center gap-3 text-micro text-ks-ink-3">
          <span className="flex min-w-0 items-center gap-1.5" title={engineReady ? 'Requests go to the KEYSTONE engine configured for this studio.' : 'The studio reports no connected engine.'}>
            <span className={cn('size-1.5 shrink-0 rounded-full', engineReady ? 'bg-ks-verified' : 'bg-ks-hold')} aria-hidden="true" />
            <span className="truncate">{engineReady ? 'Your KEYSTONE engine' : 'Engine offline'}</span>
          </span>
          {web && (
            <span className="hidden items-center gap-1 sm:flex" title="Web references are requested with personal-data redaction turned on.">
              <Lock className="size-3" /> Web text redacted
            </span>
          )}
          <span className="ks-num hidden truncate sm:inline">
            {billingOff ? 'Not billed while billing is off' : `About ${credits} credit${credits === 1 ? '' : 's'}`}
          </span>
        </div>

        <Button variant="run" size="sm" onClick={() => void submit()} className="h-8 rounded-[10px] px-3.5">
          {def.verb}
          <CornerDownLeft className="!size-3.5 opacity-80" aria-hidden="true" />
        </Button>
      </div>
    </section>
  );
}
