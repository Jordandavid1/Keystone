'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Copy, Download, Maximize2, Play, ShieldCheck, X } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';
import { fetchAssetCredentials, replayRecipe } from '@/lib/api';
import { readableError } from '@/lib/errors';
import { INTENT_BY_ID, LOOK_LABELS, compilePrompt, estimateCredits, routeIntent } from '@/lib/intents';
import { selectActiveRun, selectAsset, selectSelected, useStudio } from '@/lib/studio/store';
import { useGeneration } from '@/lib/studio/useGeneration';
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

/** Region 4 — Result → Controls → Look → Recipes → Advanced → Developer, each deeper layer collapsed until asked for. */
export function RightInspector({ overlay = false }: { overlay?: boolean }) {
  const { state, dispatch } = useStudio();
  const { run: executeRun, upscale } = useGeneration();
  const selected = selectSelected(state);
  const activeRun = selectActiveRun(state);
  const { intent, prompt, references, personaId } = state.composer;
  const c = state.controls;
  const run = selected ? state.runs.find((r) => r.outputIds.includes(selected.id)) : null;
  const parent = selectAsset(state, selected?.parentId);
  const depictedPersona = selected?.personaId ? state.system.personas.find((p) => p.id === selected.personaId) : null;
  const routed = routeIntent({ intent, prompt, references, engine: state.system.engine });
  const [hash, setHash] = useState<string | null>(null);
  const [c2paInfo, setC2paInfo] = useState<Record<string, any> | null>(null);
  const [replayingId, setReplayingId] = useState<string | null>(null);
  const [replayNote, setReplayNote] = useState<string | null>(null);

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

  useEffect(() => {
    setC2paInfo(selected?.c2paManifest || null);
    if (!selected || !state.ui.showC2paBadge || selected.c2paManifest) return;
    let cancelled = false;
    fetchAssetCredentials(selected.id)
      .then((res) => {
        if (!cancelled && res) setC2paInfo(res);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [selected, state.ui.showC2paBadge]);

  if (!state.ui.inspectorOpen) return null;

  const set = (patch: Partial<typeof c>) => dispatch({ type: 'SET_CONTROLS', patch });
  const strengthId = STRENGTH.reduce((best, s) => (Math.abs(s.value - c.strength) < Math.abs(best.value - c.strength) ? s : best)).id;
  const hasRef = references.length > 0;
  const nonNeutralGrade =
    c.look.lut !== 'none' || c.look.exposure !== 0 || c.look.contrast !== 100 || c.look.saturation !== 100 || c.look.warmth !== 0;

  const handleReplayRecipe = async (recipeId: string) => {
    setReplayingId(recipeId);
    setReplayNote(null);
    try {
      const res = await replayRecipe(recipeId);
      setReplayNote(res?.status ? `Replay submitted (${res.status}).` : 'Recipe replay submitted through Gate.');
      dispatch({ type: 'REFRESH_ASSETS' });
    } catch (err) {
      setReplayNote(readableError(err));
    } finally {
      setReplayingId(null);
    }
  };

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
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="break-words text-body text-ks-ink">{selected.title}</p>
                {selected.mature && (
                  <span className="rounded-full border border-ks-hold/40 bg-ks-hold/10 px-2 py-0.5 text-micro font-medium text-ks-hold">
                    Mature 18+
                  </span>
                )}
              </div>
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
                {(depictedPersona || selected.personaId) && (
                  <>
                    <dt className="text-ks-ink-3">Depicts</dt>
                    <dd className="text-ks-ink-2">
                      {depictedPersona?.name || selected.personaId}
                      {selected.personaVersion ? ` (v${selected.personaVersion})` : ''}
                    </dd>
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

              <div className="flex items-center justify-between rounded-control border border-ks-line bg-ks-abyss/60 px-2.5 py-2 text-meta">
                <span className="flex items-center gap-1.5 text-ks-ink-2">
                  <ShieldCheck className={cn('size-3.5', c2paInfo ? 'text-ks-verified' : 'text-ks-ink-3')} />
                  <span>C2PA badge</span>
                </span>
                <button
                  type="button"
                  aria-pressed={state.ui.showC2paBadge}
                  onClick={() => dispatch({ type: 'UI', patch: { showC2paBadge: !state.ui.showC2paBadge } })}
                  className={cn(
                    'rounded-full px-2 py-0.5 text-micro font-medium transition-colors',
                    state.ui.showC2paBadge ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-3 hover:text-ks-ink',
                  )}
                >
                  {state.ui.showC2paBadge ? 'Visible' : 'Hidden'}
                </button>
              </div>
              {state.ui.showC2paBadge && c2paInfo && (
                <div className="rounded-control border border-ks-verified/30 bg-ks-verified/5 px-2.5 py-2 text-micro text-ks-ink-2">
                  Content Credentials attached ({c2paInfo.platform || 'KEYSTONE'}).
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
            <p className="text-meta text-ks-ink-3">Analyze inspects the selected asset and answers your question.</p>
          ) : (
            <>
              {intent === 'animate' && (
                <>
                  <Field label="Camera move">
                    <MotionPad
                      value={c.motion}
                      speed={c.motionSpeed}
                      canAnimate={!!(references[0] || selected || prompt.trim())}
                      busy={!!activeRun}
                      onChange={(motion) => set({ motion })}
                      onAnimate={({ camera_motion, motion_speed }) => {
                        const targetRef = references[0] || selected;
                        const animatePrompt = prompt.trim() || targetRef?.prompt || `Smooth ${camera_motion} camera move`;
                        void executeRun({
                          intent: 'animate',
                          references: targetRef ? [targetRef] : [],
                          prompt: animatePrompt,
                          label: `Animate (${camera_motion})`,
                          extra: { camera_motion, motion_speed },
                        });
                      }}
                    />
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

        {/* Look — previewed on stage and sent to backend deterministic grade lane before upscale */}
        <Section title="Look" hint={LOOK_LABELS[c.look.lut]} defaultOpen={false}>
          <p className="mb-3 text-meta text-ks-ink-3">
            {nonNeutralGrade
              ? 'Active grade is sent to the deterministic grade lane before upscale and included in runs.'
              : 'Previewed on the stage and sent to the backend grade lane before upscale.'}
          </p>
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
          {selected && selected.type !== 'audio' && (
            <div className="mt-3 flex items-center gap-1.5">
              <button
                type="button"
                disabled={!!activeRun}
                onClick={() => upscale(2)}
                className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-control bg-ks-lift text-meta font-medium text-ks-ink ring-1 ring-inset ring-ks-line-strong hover:bg-ks-indigo/25 disabled:opacity-40"
              >
                <Maximize2 className="size-3.5" /> Grade &amp; Upscale 2×
              </button>
              <button
                type="button"
                disabled={!!activeRun}
                onClick={() => upscale(4)}
                className="flex h-8 flex-1 items-center justify-center gap-1.5 rounded-control bg-ks-lift text-meta font-medium text-ks-ink ring-1 ring-inset ring-ks-line-strong hover:bg-ks-indigo/25 disabled:opacity-40"
              >
                <Maximize2 className="size-3.5" /> 4×
              </button>
            </div>
          )}
          <button
            onClick={() => dispatch({ type: 'SET_LOOK', patch: { lut: 'none', exposure: 0, contrast: 100, saturation: 100, warmth: 0 } })}
            className="mt-3 text-meta text-ks-ink-3 hover:text-ks-ink"
          >
            Reset look
          </button>
        </Section>

        {/* Proven Recipes (Row 12 UI hook ready for PR8) */}
        <Section title="Recipes" hint={state.system.recipes.length ? `${state.system.recipes.length}` : undefined} defaultOpen={false}>
          {state.system.recipes.length === 0 ? (
            <p className="text-meta text-ks-ink-3">
              No proven recipes for this project yet. Promoted runs appear here for one-click replay through the Gate.
            </p>
          ) : (
            <div className="space-y-2">
              {state.system.recipes.slice(0, 6).map((recipe) => (
                <div key={recipe.id} className="flex items-center justify-between gap-2 rounded-control border border-ks-line bg-ks-abyss/60 px-2.5 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-meta font-medium text-ks-ink">
                      Recipe {recipe.id.slice(0, 8)} {recipe.mode === 'unrestricted' ? '· 18+' : ''}
                    </div>
                    <div className="text-micro text-ks-ink-3">
                      {recipe.passing_runs ? `${recipe.passing_runs} passing runs` : 'Candidate'}
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={replayingId === recipe.id}
                    onClick={() => void handleReplayRecipe(recipe.id)}
                    className="inline-flex h-7 shrink-0 items-center gap-1 rounded-control bg-ks-lift px-2 text-micro font-medium text-ks-ink hover:bg-ks-indigo/25 disabled:opacity-40"
                  >
                    <Play className="size-3" /> {replayingId === recipe.id ? 'Running…' : 'Replay'}
                  </button>
                </div>
              ))}
            </div>
          )}
          {replayNote && <p className="mt-2 text-meta text-ks-ink-2">{replayNote}</p>}
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
              <dt className="text-ks-ink-3">Persona (as)</dt>
              <dd className="font-mono text-ks-ink-2">{personaId || 'none'}</dd>
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
            <p className="mt-3 text-meta text-ks-ink-3">Authority decisions and execution envelopes are made server-side at submit time.</p>
          </Section>
        )}
      </ScrollArea>
    </aside>
  );
}
