'use client';

import React from 'react';
import { Clock, FolderKanban, Heart, Images, MessageSquare, Settings, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStudio } from '@/lib/studio/store';
import { SidebarPanel } from '@/lib/types';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

const PANELS: { id: SidebarPanel; label: string; icon: React.ElementType }[] = [
  { id: 'create', label: 'Create', icon: Sparkles },
  { id: 'assets', label: 'Assets', icon: Images },
  { id: 'history', label: 'History', icon: Clock },
  { id: 'favorites', label: 'Favorites', icon: Heart },
];

function RailButton({
  label,
  active,
  onClick,
  icon: Icon,
  badge,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  icon: React.ElementType;
  badge?: number;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          onClick={onClick}
          aria-label={label}
          aria-current={active ? 'page' : undefined}
          className={cn(
            'relative flex size-10 items-center justify-center rounded-control text-ks-ink-3 transition-colors duration-quick hover:bg-ks-lift hover:text-ks-ink',
            active && 'bg-ks-lift text-ks-ink',
          )}
        >
          {active && <span className="absolute -left-[10px] h-5 w-[2px] rounded-full bg-ks-indigo" aria-hidden="true" />}
          <Icon className="size-[18px]" />
          {badge ? (
            <span className="ks-num absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-ks-indigo px-1 text-center text-[10px] font-semibold leading-4 text-white">
              {badge}
            </span>
          ) : null}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

/** The navigation rail (left edge). On mobile it becomes the bottom tab bar — see StudioShell. */
export function ActivityBar() {
  const { state, dispatch } = useStudio();
  const { panel, panelOpen } = state.ui;
  const running = state.runs.filter((r) => r.status === 'queued' || r.status === 'processing').length;

  const select = (id: SidebarPanel) => {
    if (panel === id && panelOpen) dispatch({ type: 'TOGGLE_PANEL', open: false });
    else dispatch({ type: 'SET_PANEL', panel: id });
  };

  return (
    <nav
      aria-label="Studio navigation"
      className="ks-region flex w-rail flex-col items-center gap-1 border-r border-ks-line py-3 [grid-area:rail] max-md:hidden"
    >
      {PANELS.map((p) => (
        <RailButton
          key={p.id}
          label={p.label}
          icon={p.icon}
          active={panelOpen && panel === p.id}
          onClick={() => select(p.id)}
          badge={p.id === 'history' ? running : undefined}
        />
      ))}
      <div className="my-2 h-px w-6 bg-ks-line" aria-hidden="true" />
      <RailButton label="Projects" icon={FolderKanban} onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'projects' })} />
      <RailButton label="Talk to KEYSTONE" icon={MessageSquare} onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'agent' })} />
      <div className="flex-1" />
      <RailButton label="Settings" icon={Settings} onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'settings' })} />
    </nav>
  );
}
