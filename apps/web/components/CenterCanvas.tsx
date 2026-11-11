'use client';

import React, { useCallback, useState } from 'react';
import { Code2, Grid3x3, PanelLeftOpen, PanelRightClose, PanelRightOpen, RectangleHorizontal } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { selectActiveRun, selectAsset, selectCompare, selectSelected, useStudio } from '@/lib/studio/store';
import { useGeneration } from '@/lib/studio/useGeneration';
import { CanvasViewMode } from '@/lib/types';
import { FloatingComposer } from './FloatingComposer';
import { PipelineBuilder } from './PipelineBuilder';
import { IconButton } from './studio/IconButton';
import { AnalysisPane } from './canvas/AnalysisPane';
import { CompareView } from './canvas/CompareView';
import { ContextBar } from './canvas/ContextBar';
import { LineageView } from './canvas/LineageView';
import { ProgressStrip } from './canvas/ProgressStrip';
import { StageFrame } from './canvas/StageFrame';
import { StageSlate } from './canvas/StageSlate';
import { VariationsView } from './canvas/VariationsView';
import { usePipeline } from '@/lib/studio/usePipeline';

const VIEWS: { id: CanvasViewMode; label: string }[] = [
  { id: 'single', label: 'Stage' },
  { id: 'compare', label: 'Compare' },
  { id: 'variations', label: 'Variations' },
  { id: 'lineage', label: 'Lineage' },
];

const MATTES = [
  { id: 'none', label: 'No matte' },
  { id: 'scope', label: '2.39:1 scope' },
  { id: 'flat', label: '1.85:1 flat' },
  { id: 'tv', label: '16:9' },
  { id: 'reel', label: '9:16 vertical' },
] as const;

/** Region 3 — the stage. The creative asset is visually primary (Bible §25). */
export function CenterCanvas({ composerRef }: { composerRef: React.RefObject<HTMLTextAreaElement> }) {
  const { state, dispatch } = useStudio();
  const { retry, upscale, variation } = useGeneration();
  const pipeline = usePipeline();
  const [composerH, setComposerH] = useState(150);
  const [zoom, setZoom] = useState<'fit' | 1 | 2>('fit');

  const selected = selectSelected(state);
  const compare = selectCompare(state);
  const activeRun = selectActiveRun(state);
  const lastRun = state.runs[0] || null;
  const { view, developer, guides, matte, fps } = state.ui;
  const analysisRun = state.runs.find((r) => r.id === state.ui.analysisRunId) || null;
  const before = compare || selectAsset(state, selected?.parentId);

  // Routing notices live in the composer, next to the action they affect.
  // The slate only repeats the one fact that blocks everything: no API.
  const engineNotice = state.system.engineError ? `The studio API isn't reachable: ${state.system.engineError}` : null;

  const setView = (v: CanvasViewMode) => dispatch({ type: 'SET_VIEW', view: v });
  const focusComposer = useCallback(() => composerRef.current?.focus(), [composerRef]);

  const startWith = (intent: 'edit' | 'animate') => {
    if (!selected) return;
    dispatch({ type: 'CLEAR_REFERENCES' });
    dispatch({ type: 'ADD_REFERENCE', asset: selected });
    dispatch({ type: 'SET_INTENT', intent });
    focusComposer();
  };

  // Space reserved below/around the frame so media never sits under the composer.
  const hasBar = !!selected && (view === 'single' || view === 'compare' || view === 'variations');
  const padBottom = composerH + (hasBar ? 76 : 32);
  const reserved = 52 + 44 + padBottom + 48;

  const showSlate = view === 'single' && !selected;
  const slateRun = activeRun || (lastRun && lastRun.status === 'failed' && !selected ? lastRun : null);

  return (
    <main
      className="ks-stage relative flex min-w-0 flex-col overflow-hidden [grid-area:stage]"
      style={{ ['--ks-reserved' as any]: `${reserved}px` }}
      aria-label="Stage"
    >
      {/* Canvas header */}
      <div className="flex h-11 shrink-0 items-center gap-2 px-3">
        {!state.ui.panelOpen && (
          <IconButton label="Show panel" shortcut="[" onClick={() => dispatch({ type: 'TOGGLE_PANEL', open: true })} className="max-md:hidden">
            <PanelLeftOpen />
          </IconButton>
        )}
        <div className="flex items-center gap-0.5 rounded-control p-0.5" role="tablist" aria-label="Canvas view">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              role="tab"
              aria-selected={view === v.id}
              onClick={() => setView(v.id)}
              className={cn(
                'h-7 rounded-[7px] px-2.5 text-meta font-medium transition-colors duration-quick',
                view === v.id ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-3 hover:text-ks-ink',
              )}
            >
              {v.label}
            </button>
          ))}
          {developer && (
            <button
              role="tab"
              aria-selected={view === 'pipeline'}
              onClick={() => setView('pipeline')}
              className={cn(
                'flex h-7 items-center gap-1 rounded-[7px] px-2.5 text-meta font-medium',
                view === 'pipeline' ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-3 hover:text-ks-ink',
              )}
            >
              <Code2 className="size-3.5" /> Pipeline
            </button>
          )}
        </div>

        <div className="ml-auto flex items-center gap-1">
          {view === 'single' && selected && selected.type === 'image' && (
            <div className="mr-1 flex items-center rounded-control text-meta" role="group" aria-label="Zoom">
              {(['fit', 1, 2] as const).map((z) => (
                <button
                  key={String(z)}
                  onClick={() => setZoom(z)}
                  aria-pressed={zoom === z}
                  className={cn('h-7 rounded-[7px] px-2 ks-num', zoom === z ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-3 hover:text-ks-ink')}
                >
                  {z === 'fit' ? 'Fit' : `${z * 100}%`}
                </button>
              ))}
            </div>
          )}
          {view === 'single' && selected && selected.type !== 'audio' && (
            <>
              <IconButton label={guides ? 'Hide framing guides' : 'Show framing guides'} active={guides} onClick={() => dispatch({ type: 'UI', patch: { guides: !guides } })}>
                <Grid3x3 />
              </IconButton>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    aria-label="Cinema matte"
                    className={cn(
                      'flex h-8 items-center gap-1.5 rounded-control px-2 text-meta text-ks-ink-2 hover:bg-ks-lift hover:text-ks-ink',
                      matte !== 'none' && 'bg-ks-lift text-ks-ink',
                    )}
                  >
                    <RectangleHorizontal className="size-4" />
                    <span className="max-lg:hidden">{MATTES.find((m) => m.id === matte)?.label}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {MATTES.map((m) => (
                    <DropdownMenuItem key={m.id} onSelect={() => dispatch({ type: 'UI', patch: { matte: m.id } })}>
                      {m.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
          <IconButton
            label={state.ui.inspectorOpen ? 'Hide inspector' : 'Show inspector'}
            shortcut="]"
            onClick={() => dispatch({ type: 'TOGGLE_INSPECTOR' })}
          >
            {state.ui.inspectorOpen ? <PanelRightClose /> : <PanelRightOpen />}
          </IconButton>
        </div>
      </div>

      {/* Stage body — bottom padding keeps media clear of the floating composer */}
      <div className="relative min-h-0 flex-1" style={{ paddingBottom: padBottom }}>
        {view === 'single' &&
          (showSlate ? (
            <StageSlate
              intent={state.composer.intent}
              aspect={state.controls.aspect}
              run={slateRun}
              engineNotice={engineNotice}
              onRetry={slateRun && slateRun.status === 'failed' ? () => retry(slateRun.id) : undefined}
              onEditPrompt={focusComposer}
            />
          ) : (
            selected && (
              <StageFrame asset={selected} look={state.controls.look} zoom={zoom} guides={guides} matte={matte} fps={fps} />
            )
          ))}

        {view === 'compare' && (
          <CompareView
            after={selected}
            before={before && before.id !== selected?.id ? before : null}
            assets={state.library.assets}
            fps={fps}
            onPickBefore={(id) => dispatch({ type: 'SET_COMPARE', id })}
          />
        )}

        {view === 'variations' && (
          <VariationsView
            selected={selected}
            assets={state.library.assets}
            runs={state.runs}
            onSelect={(id) => dispatch({ type: 'SELECT_ASSET', id })}
            onOpen={(id) => {
              dispatch({ type: 'SELECT_ASSET', id });
              setView('single');
            }}
          />
        )}

        {view === 'lineage' && (
          <LineageView
            assets={state.library.assets}
            selectedId={selected?.id || null}
            onSelect={(id) => dispatch({ type: 'SELECT_ASSET', id })}
            onCompareWithParent={(id) => {
              const a = selectAsset(state, id);
              dispatch({ type: 'SELECT_ASSET', id });
              dispatch({ type: 'SET_COMPARE', id: a?.parentId || null });
              setView('compare');
            }}
          />
        )}

        {view === 'analysis' &&
          (analysisRun ? (
            <AnalysisPane
              run={analysisRun}
              asset={selectAsset(state, analysisRun.referenceIds[0]) || selected}
              onClose={() => dispatch({ type: 'SHOW_ANALYSIS', runId: null })}
              onUseAsPrompt={(text) => {
                dispatch({ type: 'SET_PROMPT', prompt: text });
                dispatch({ type: 'SET_INTENT', intent: 'create' });
                dispatch({ type: 'SHOW_ANALYSIS', runId: null });
                focusComposer();
              }}
            />
          ) : (
            <div className="flex size-full items-center justify-center text-body text-ks-ink-3">Ask something with Analyze to see the answer here.</div>
          ))}

        {view === 'pipeline' && developer && (
          <div className="size-full overflow-auto p-4 ks-scroll">
            <PipelineBuilder
              steps={pipeline.steps}
              onUpdateSteps={pipeline.setSteps}
              onExecutePipeline={pipeline.execute}
              isExecuting={pipeline.running}
              onSelectAsset={(a) => dispatch({ type: 'SELECT_ASSET', id: a.id })}
            />
          </div>
        )}
      </div>

      {/* Floating layer: progress, context bar, composer */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col items-center gap-2.5 px-3 pb-4 sm:px-5 sm:pb-5">
        {activeRun && !showSlate && <ProgressStrip run={activeRun} />}
        {selected && (view === 'single' || view === 'compare' || view === 'variations') && (
          <ContextBar
            asset={selected}
            favorite={state.library.favorites.includes(selected.id)}
            busy={!!activeRun}
            onEdit={() => startWith('edit')}
            onAnimate={() => startWith('animate')}
            onVariation={variation}
            onUpscale={upscale}
            onCompare={() => setView('compare')}
            onReference={() => {
              dispatch({ type: 'ADD_REFERENCE', asset: selected });
              focusComposer();
            }}
            onFavorite={() => dispatch({ type: 'TOGGLE_FAVORITE', id: selected.id })}
          />
        )}
        <FloatingComposer onHeight={setComposerH} inputRef={composerRef} />
      </div>
    </main>
  );
}
