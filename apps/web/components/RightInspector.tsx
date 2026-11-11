'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Copy, Download, X } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';
import { INTENT_BY_ID, LOOK_LABELS, compilePrompt, estimateCredits, routeIntent } from '@/lib/intents';
import { selectAsset, selectSelected, useStudio } from '@/lib/studio/store';
import { TOOLS_CATALOG } from '@/lib/toolsCatalog';
import { AspectRatio, QualityTier } from '@/lib/types';
import { Field, Section, Segmented } from './inspector/Section';
import { MotionPad } from './inspector/MotionPad';

const ASPECTS: AspectRatio[] = ['21:9', '16:9', '3:2', '4:3', '1:1', '4:5', '3:4', '2:3', '9:16'];
const QUALITY: { id: QualityTier; label: string; hint: string }[] = [
  { id: 'draft', label: 'Draft', hint: 'Fastest, for exploring' },
  { id: 'high', label: 'High', hint: 'Balanced detail and speed' },
  { id: 'master', label: 'Master', hint: 'Highest detail, slowest' },
];
const STRENGTH = [
  { id: 'subtle', label: 'Subtle', value: 0.35 },
  { id: 'balanced', label: 'Balanced', value: 0.65 },
  { id: 'bold', label: 'Bold', value: 0.85 },
] as const;

function AspectGlyph({ ratio }: { ratio: AspectRatio }) {
  const [w, h] = ratio.split(':').map(Number);
  const scale = 14 / Math.max(w, h);
  return <span className="inline-block rounded-[2px] border border-current" style={{ width: w * scale, height: h * scale }} aria-hidden="true" />;
}

function bytes(n?: number): string | null {
  if (!n) return null;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

async function sha256(text: string): Promise<string | null> {
  if (typeof crypto === 'undefined' || !crypto.subtle) return null;
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/** Region 4 — Result → Controls → Look → Advanced → Developer, each deeper layer collapsed until asked for. */
export function RightInspector({ overlay = false }: { overlay?: boolean }) {
  const { state, dispatch } = useStudio();
  const selected = selectSelected(state);
  const { intent, prompt, references } = state.composer;
  const c = state.controls;
  const run = selected ? state.runs.find((r) => r.outputIds.includes(selected.id)) : null;
  const parent = selectAsset(state, selected?.parentId);
  const routed = routeIntent({ intent, prompt, references, engine: state.system.engine });
  const [hash, setHash] = useState<string | null>(null);

  const compiled = useMemo(
    () =>
      compilePrompt({
        text: prompt,
        playbook: state.composer.playbook,
        web: state.composer.web,
        lut: c.look.lut,
        useCase: state.composer.useCase,
      }),
    [prompt, state.composer.playbook, state.composer.web, state.composer.useCase, c.look.lut],
  );

  useEffect(() => {
    if (!state.ui.developer) return;
    let cancelled = false;
    sha256(compiled).then((h) => !cancelled && setHash(h));
    return () => {
      cancelled = true;
    };
  }, [compiled, state.ui.developer]);

  if (!state.ui.inspectorOpen) return null;

  const set = (patch: Partial<typeof c>) => dispatch({ type: 'SET_CONTROLS', patch });
  const strengthId = STRENGTH.reduce((best, s) => (Math.abs(s.value - c.strength) < Math.abs(best.value - c.strength) ? s : best)).id;
  const hasRef = references.length > 0;

  return (
    <aside
      aria-label="Inspector"
      className={cn(
        'ks-region flex w-inspector flex-col border-l border-ks-line [grid-area:inspector]',
        overlay && 'absolute inset-y-0 right-0 z-30 shadow-float max-md:w-full',
      )}
    >
      {overlay && (
        <button
          onClick={() => dispatch({ type: 'TOGGLE_INSPECTOR', open: false })}
          className="absolute right-2 top-2 z-10 rounded-control p-1.5 text-ks-ink-3 hover:bg-ks-lift hover:text-ks-ink"
          aria-label="Close inspector"
        >
          <X className="size-4" />
        </button>
      )}
      <ScrollArea className="h-full">
        {/* Result */}
        <Section title="Result" hint={selected ? selected.type : undefined}>
          {!selected ? (
            <p className="text-meta text-ks-ink-3">Select an asset to see where it came from and what you can do with it.</p>
          ) : (
            <div className="space-y-3">
              <p className="break-words text-body text-ks-ink">{selected.title}</p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-meta">
                {selected.width && selected.height ? (
                  <>
                    <dt className="text-ks-ink-3">Size</dt>
                    <dd className="ks-num text-ks-ink-2">
                      {selected.width} × {selected.height}
                    </dd>
                  </>
                ) : null}
                {bytes(selected.byteSize) && (
                  <>
                    <dt className="text-ks-ink-3">File</dt>
                    <dd className="ks-num text-ks-ink-2">
                      {bytes(selected.byteSize)}
                      {selected.mimeType ? `, ${selected.mimeType.split('/')[1]}` : ''}
                    </dd>
                  </>
                )}
                <dt className="text-ks-ink-3">Added</dt>
                <dd className="text-ks-ink-2">{new Date(selected.createdAt).toLocaleString()}</dd>
                {run && (
                  <>
                    <dt className="text-ks-ink-3">Made with</dt>
                    <dd className="text-ks-ink-2">{run.label}</dd>
                  </>
                )}
                {parent && (
                  <>
                    <dt className="text-ks-ink-3">Made from</dt>
                    <dd>
                      <button className="max-w-full truncate text-left text-ks-ink-2 underline-offset-2 hover:text-ks-ink hover:underline" onClick={() => dispatch({ type: 'SELECT_ASSET', id: parent.id })}>
                        {parent.title}
                      </button>
                    </dd>
                  </>
                )}
              </dl>
              {selected.prompt && (
                <div>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-meta font-medium text-ks-ink-2">Prompt</span>
                    <button
                      onClick={() => dispatch({ type: 'SET_PROMPT', prompt: selected.prompt || '' })}
                      className="flex items-center gap-1 text-meta text-ks-ink-3 hover:text-ks-ink"
                    >
                      <Copy className="size-3" /> Reuse
                    </button>
                  </div>
                  <p className="line-clamp-6 whitespace-pre-wrap text-meta text-ks-ink-2">{selected.prompt}</p>
                </div>
              )}
              <a
                href={selected.downloadUrl || selected.url}
                download
                target="_blank"
                rel="noreferrer"
                className="flex h-8 w-full items-center justify-center gap-2 rounded-control bg-ks-lift text-meta font-medium text-ks-ink hover:bg-[#212740]"
              >
                <Download className="size-3.5" /> Download original
              </a>
            </div>
          )}
        </Section>

        {/* Controls — customer-level only, per intent */}
        <Section title="Controls" hint={INTENT_BY_ID[intent].label}>
          {intent === 'analyze' ? (
            <p className="text-meta text-ks-ink-3">Analyze uses your question and the selected asset. There's nothing to set.</p>
          ) : (
            <>
              {intent === 'animate' && (
                <>
                  <Field label="Camera move">
                    <MotionPad value={c.motion} onChange={(motion) => set({ motion })} />
                  </Field>
                  <Field label="Speed" value={`${c.motionSpeed.toFixed(1)}×`}>
                    <Slider min={0.2} max={2} step={0.1} value={[c.motionSpeed]} onValueChange={([v]) => set({ motionSpeed: v })} aria-label="Camera speed" />
                  </Field>
                  <Field label="Length" value={`${c.duration} s`}>
                    <Segmented
                      label="Clip length"
                      value={c.duration}
                      onChange={(duration) => set({ duration })}
                      options={[5, 10, 15, 20, 30].map((d) => ({ id: d, label: `${d}s` }))}
                    />
                  </Field>
                </>
              )}

              {(intent === 'edit' || (intent !== 'animate' && hasRef)) && (
                <Field label={intent === 'edit' ? 'How much to change' : 'How closely to follow the reference'}>
                  <Segmented
                    label="Change amount"
                    value={strengthId}
                    onChange={(id) => set({ strength: STRENGTH.find((s) => s.id === id)!.value })}
                    options={
                      intent === 'edit'
                        ? STRENGTH.map((s) => ({ id: s.id, label: s.label }))
                        : [
                            { id: 'subtle', label: 'Closely' },
                            { id: 'balanced', label: 'Balanced' },
                            { id: 'bold', label: 'Loosely' },
                          ]
                    }
                  />
                </Field>
              )}

              {intent !== 'edit' && (
                <Field label="Frame" value={c.aspect}>
                  <div role="radiogroup" aria-label="Aspect ratio" className="grid grid-cols-3 gap-1">
                    {ASPECTS.map((a) => (
                      <button
                        key={a}
                        role="radio"
                        aria-checked={c.aspect === a}
                        onClick={() => set({ aspect: a })}
                        className={cn(
                          'flex h-9 items-center justify-center gap-2 rounded-control text-meta text-ks-ink-3 ring-1 ring-inset ring-ks-line transition-colors hover:text-ks-ink',
                          c.aspect === a && 'bg-ks-lift text-ks-ink ring-ks-line-strong',
                        )}
                      >
                        <AspectGlyph ratio={a} />
                        <span className="ks-num">{a}</span>
                      </button>
                    ))}
                  </div>
                </Field>
              )}

              <Field label="Quality" value={QUALITY.find((q) => q.id === c.quality)?.hint}>
                <Segmented label="Quality" value={c.quality} onChange={(quality) => set({ quality })} options={QUALITY} />
              </Field>

              {intent === 'create' && 'batch_size' in (TOOLS_CATALOG[routed.capability].defaultParameters || {}) && (
                <Field label="Results per run">
                  <Segmented
                    label="Results per run"
                    value={c.results}
                    onChange={(results) => set({ results })}
                    options={[
                      { id: 1 as const, label: '1' },
                      { id: 2 as const, label: '2' },
                      { id: 4 as const, label: '4' },
                    ]}
                  />
                </Field>
              )}
            </>
          )}
        </Section>

        {/* Look */}
        <Section title="Look" hint={LOOK_LABELS[c.look.lut]} defaultOpen={false}>
          <p className="mb-3 text-meta text-ks-ink-3">Previewed on the stage and sent with your next run.</p>
          <div className="grid grid-cols-2 gap-1" role="radiogroup" aria-label="Film look">
            {Object.entries(LOOK_LABELS).map(([id, label]) => (
              <button
                key={id}
                role="radio"
                aria-checked={c.look.lut === id}
                onClick={() => dispatch({ type: 'SET_LOOK', patch: { lut: id } })}
                className={cn(
                  'h-8 truncate rounded-control px-2 text-left text-meta text-ks-ink-3 ring-1 ring-inset ring-ks-line hover:text-ks-ink',
                  c.look.lut === id && 'bg-ks-lift text-ks-ink ring-ks-line-strong',
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {(
            [
              { key: 'exposure', label: 'Exposure', min: -2, max: 2, step: 0.1, fmt: (v: number) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)) },
              { key: 'contrast', label: 'Contrast', min: 70, max: 150, step: 1, fmt: (v: number) => `${v}%` },
              { key: 'saturation', label: 'Saturation', min: 0, max: 200, step: 2, fmt: (v: number) => `${v}%` },
              { key: 'warmth', label: 'Warmth', min: -30, max: 30, step: 1, fmt: (v: number) => (v > 0 ? `+${v}` : `${v}`) },
            ] as const
          ).map((g) => (
            <Field key={g.key} label={g.label} value={g.fmt(c.look[g.key])}>
              <Slider
                min={g.min}
                max={g.max}
                step={g.step}
                value={[c.look[g.key]]}
                onValueChange={([v]) => dispatch({ type: 'SET_LOOK', patch: { [g.key]: v } as any })}
                aria-label={g.label}
              />
            </Field>
          ))}
          <button
            onClick={() => dispatch({ type: 'SET_LOOK', patch: { lut: 'none', exposure: 0, contrast: 100, saturation: 100, warmth: 0 } })}
            className="mt-3 text-meta text-ks-ink-3 hover:text-ks-ink"
          >
            Reset look
          </button>
        </Section>

        {/* Advanced */}
        <Section title="Advanced" defaultOpen={false}>
          <Field label="Exact strength" value={c.strength.toFixed(2)}>
            <Slider min={0.1} max={0.95} step={0.05} value={[c.strength]} onValueChange={([v]) => set({ strength: v })} aria-label="Exact strength" />
          </Field>
          <p className="mt-2 text-meta text-ks-ink-3">Used when a reference or source image is attached. Higher values move further from it.</p>
        </Section>

        {/* Developer — provider details, separate from the customer UI (Bible §25) */}
        {state.ui.developer && (
          <Section title="Developer" hint="Not shown to customers" defaultOpen>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-meta">
              <dt className="text-ks-ink-3">Routed to</dt>
              <dd className="text-ks-ink-2">
                {TOOLS_CATALOG[routed.capability].name} <span className="font-mono text-ks-ink-3">{routed.capability}</span>
              </dd>
              <dt className="text-ks-ink-3">Estimate</dt>
              <dd className="ks-num text-ks-ink-2">{estimateCredits(routed.capability, c)} credits (catalog)</dd>
              <dt className="text-ks-ink-3">Engine</dt>
              <dd className="text-ks-ink-2">
                {state.system.engine?.unwired_tools?.includes(routed.capability) ? 'Not wired for this capability' : state.system.engine ? 'Wired' : 'Unknown'}
              </dd>
            </dl>
            <div className="mt-3 text-meta font-medium text-ks-ink-2">Compiled prompt</div>
            <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-control bg-ks-abyss p-2.5 font-mono text-[11px] leading-4 text-ks-ink-2 ks-scroll">{compiled || '—'}</pre>
            <div className="mt-2 text-meta text-ks-ink-3">
              SHA-256 <span className="break-all font-mono text-[11px] text-ks-ink-2">{hash || '—'}</span>
            </div>
            {state.runs[0] && (
              <>
                <div className="mt-3 text-meta font-medium text-ks-ink-2">Last request</div>
                <pre className="mt-1 max-h-48 overflow-auto rounded-control bg-ks-abyss p-2.5 font-mono text-[11px] leading-4 text-ks-ink-2 ks-scroll">
                  {JSON.stringify({ tool: state.runs[0].request.tool, input: { ...state.runs[0].request.input, positive_prompt: undefined, playbook_context: undefined } }, null, 2)}
                </pre>
              </>
            )}
            <p className="mt-3 text-meta text-ks-ink-3">Authority decisions and execution envelopes are made server-side at submit time and aren't returned to this client yet.</p>
          </Section>
        )}
      </ScrollArea>
    </aside>
  );
}
