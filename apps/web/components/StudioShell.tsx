'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Clock, Images, PanelRight, Sparkles, X } from 'lucide-react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useStudio } from '@/lib/studio/store';
import { useBootstrap } from '@/lib/studio/useBootstrap';
import { useGeneration } from '@/lib/studio/useGeneration';
import { useShortcuts } from '@/lib/studio/useShortcuts';
import { TopBar } from './TopBar';
import { ActivityBar } from './ActivityBar';
import { LeftSidebar } from './LeftSidebar';
import { CenterCanvas } from './CenterCanvas';
import { RightInspector } from './RightInspector';
import { CommandPalette } from './Modals/CommandPalette';
import { PersonasModal } from './Modals/PersonasModal';
import { WebScrapeModal } from './Modals/WebScrapeModal';
import { SettingsModal } from './Modals/SettingsModal';
import { ProjectsModal } from './Modals/ProjectsModal';
import { SessionsModal } from './Modals/SessionsModal';
import { CreditsModal } from './Modals/CreditsModal';
import { WorkerTelemetryModal } from './Modals/WorkerTelemetryModal';
import { AgentChatModal } from './Modals/AgentChatModal';

type Mode = 'desktop' | 'compact' | 'tablet' | 'mobile';

/** ≥1280 desktop · 1024–1279 compact (inspector overlays) · 768–1023 tablet (both overlay) · <768 mobile. */
function useMode(): Mode {
  const [mode, setMode] = useState<Mode>('desktop');
  useEffect(() => {
    const calc = () => {
      const w = window.innerWidth;
      setMode(w >= 1280 ? 'desktop' : w >= 1024 ? 'compact' : w >= 768 ? 'tablet' : 'mobile');
    };
    calc();
    window.addEventListener('resize', calc);
    return () => window.removeEventListener('resize', calc);
  }, []);
  return mode;
}

/** The five-region studio (Bible §25, UI_SCHEMA §6). */
export function StudioShell() {
  useBootstrap();
  const { state, dispatch } = useStudio();
  const { upload } = useGeneration();
  const mode = useMode();
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const focusComposer = useCallback(() => composerRef.current?.focus(), []);
  useShortcuts(focusComposer);
  const [dropping, setDropping] = useState(false);
  const dragDepth = useRef(0);

  // Overlay regions start closed on smaller screens.
  const lastMode = useRef<Mode | null>(null);
  useEffect(() => {
    if (lastMode.current === mode) return;
    lastMode.current = mode;
    if (mode === 'mobile' || mode === 'tablet') {
      dispatch({ type: 'TOGGLE_PANEL', open: false });
      dispatch({ type: 'TOGGLE_INSPECTOR', open: false });
    } else if (mode === 'compact') {
      dispatch({ type: 'TOGGLE_PANEL', open: true });
      dispatch({ type: 'TOGGLE_INSPECTOR', open: false });
    } else {
      dispatch({ type: 'TOGGLE_PANEL', open: true });
      dispatch({ type: 'TOGGLE_INSPECTOR', open: true });
    }
  }, [dispatch, mode]);

  const panelOverlay = mode === 'tablet' || mode === 'mobile';
  const inspectorOverlay = mode !== 'desktop';
  const close = () => dispatch({ type: 'OPEN_MODAL', modal: null });
  const m = state.ui.modal;

  return (
    <TooltipProvider delayDuration={350} skipDelayDuration={150}>
      <div
        className="relative grid h-dvh w-screen overflow-hidden bg-ks-abyss text-ks-ink"
        style={{
          gridTemplateAreas: mode === 'mobile' ? '"topbar" "stage" "tabs"' : '"topbar topbar topbar topbar" "rail panel stage inspector"',
          gridTemplateColumns: mode === 'mobile' ? 'minmax(0,1fr)' : 'auto auto minmax(0,1fr) auto',
          gridTemplateRows: mode === 'mobile' ? '52px minmax(0,1fr) 56px' : '52px minmax(0,1fr)',
        }}
        onDragEnter={(e) => {
          if (!Array.from(e.dataTransfer.types).includes('Files')) return;
          dragDepth.current += 1;
          setDropping(true);
        }}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1);
          if (dragDepth.current === 0) setDropping(false);
        }}
        onDragOver={(e) => {
          if (Array.from(e.dataTransfer.types).includes('Files')) e.preventDefault();
        }}
        onDrop={(e) => {
          if (!e.dataTransfer.files.length) return;
          e.preventDefault();
          dragDepth.current = 0;
          setDropping(false);
          Array.from(e.dataTransfer.files)
            .filter((f) => /^(image|video|audio)\//.test(f.type))
            .forEach((f) => upload(f, true));
        }}
      >
        <TopBar />
        {mode !== 'mobile' && <ActivityBar />}
        {!panelOverlay && <LeftSidebar />}
        <CenterCanvas composerRef={composerRef} />
        {!inspectorOverlay && <RightInspector />}

        {/* Overlay sheets for smaller screens */}
        {panelOverlay && state.ui.panelOpen && (
          <div className="absolute inset-x-0 bottom-[56px] top-[52px] z-30 md:bottom-0 md:left-[60px]">
            <button className="absolute inset-0 bg-black/50" aria-label="Close panel" onClick={() => dispatch({ type: 'TOGGLE_PANEL', open: false })} />
            <LeftSidebar overlay />
          </div>
        )}
        {inspectorOverlay && state.ui.inspectorOpen && (
          <div className={cn('absolute inset-x-0 top-[52px] z-30', mode === 'mobile' ? 'bottom-[56px]' : 'bottom-0')}>
            <button className="absolute inset-0 bg-black/50" aria-label="Close inspector" onClick={() => dispatch({ type: 'TOGGLE_INSPECTOR', open: false })} />
            <RightInspector overlay />
          </div>
        )}

        {/* Mobile tab bar: create, review, assets, history (Bible §25 mobile emphasis) */}
        {mode === 'mobile' && (
          <nav aria-label="Studio" className="ks-region z-40 grid grid-cols-4 border-t border-ks-line [grid-area:tabs]">
            {[
              { id: 'create', label: 'Create', icon: Sparkles, on: () => { dispatch({ type: 'TOGGLE_PANEL', open: false }); dispatch({ type: 'TOGGLE_INSPECTOR', open: false }); focusComposer(); } },
              { id: 'assets', label: 'Assets', icon: Images, on: () => { dispatch({ type: 'TOGGLE_INSPECTOR', open: false }); dispatch({ type: 'SET_PANEL', panel: 'assets' }); } },
              { id: 'history', label: 'History', icon: Clock, on: () => { dispatch({ type: 'TOGGLE_INSPECTOR', open: false }); dispatch({ type: 'SET_PANEL', panel: 'history' }); } },
              { id: 'review', label: 'Review', icon: PanelRight, on: () => { dispatch({ type: 'TOGGLE_PANEL', open: false }); dispatch({ type: 'TOGGLE_INSPECTOR', open: true }); } },
            ].map((t) => (
              <button key={t.id} onClick={t.on} className="flex flex-col items-center justify-center gap-0.5 text-micro text-ks-ink-3 hover:text-ks-ink">
                <t.icon className="size-[18px]" />
                {t.label}
              </button>
            ))}
          </nav>
        )}

        {dropping && (
          <div className="pointer-events-none absolute inset-0 z-50 flex items-center justify-center bg-ks-abyss/70 backdrop-blur-sm">
            <div className="rounded-panel border border-dashed border-ks-indigo/70 px-10 py-8 text-center">
              <p className="text-title font-semibold text-ks-ink">Drop to attach</p>
              <p className="mt-1 text-body text-ks-ink-2">Images, video and audio upload to your library and attach to the composer.</p>
            </div>
          </div>
        )}

        {state.ui.notice && (
          <div
            role={state.ui.notice.tone === 'error' ? 'alert' : 'status'}
            className={cn(
              'ks-glass absolute right-4 top-[64px] z-50 flex max-w-[420px] items-start gap-3 rounded-panel border px-4 py-3 shadow-float',
              state.ui.notice.tone === 'error' ? 'border-ks-deny/40' : 'border-ks-line-strong',
            )}
          >
            <p className={cn('text-body', state.ui.notice.tone === 'error' ? 'text-ks-ink' : 'text-ks-ink-2')}>{state.ui.notice.text}</p>
            <button onClick={() => dispatch({ type: 'NOTICE', notice: null })} aria-label="Dismiss" className="text-ks-ink-3 hover:text-ks-ink">
              <X className="size-4" />
            </button>
          </div>
        )}
      </div>

      <CommandPalette />
      <PersonasModal open={m === 'personas'} onClose={close} onPersonasLoaded={(personas) => dispatch({ type: 'SYSTEM', patch: { personas } })} />
      <SettingsModal
        open={m === 'settings'}
        initialTab={state.ui.settingsTab}
        onClose={() => {
          dispatch({ type: 'UI', patch: { settingsTab: null } });
          close();
        }}
        onFlagsSaved={(flags) => dispatch({ type: 'UI', patch: { fps: flags.framerate || 24 } })} />
      <ProjectsModal
        open={m === 'projects'}
        onClose={close}
        onSelectProject={(project) => dispatch({ type: 'SYSTEM', patch: { projectId: project.id, projects: state.system.projects.some((p) => p.id === project.id) ? state.system.projects : [...state.system.projects, project] } })}
      />
      <SessionsModal open={m === 'sessions'} onClose={close} projectId={state.system.projectId} />
      <CreditsModal open={m === 'credits'} onClose={close} />
      <WorkerTelemetryModal open={m === 'worker'} onClose={close} />
      <AgentChatModal open={m === 'agent'} onClose={close} />
      <WebScrapeModal open={m === 'web'} onClose={close} onAttach={(web) => dispatch({ type: 'SET_WEB', web })} />
    </TooltipProvider>
  );
}
