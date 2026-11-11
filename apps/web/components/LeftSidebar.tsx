'use client';

import React from 'react';
import { PanelLeftClose } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useStudio } from '@/lib/studio/store';
import { cn } from '@/lib/utils';
import { CreatePanel } from './sidebar/CreatePanel';
import { AssetsPanel } from './sidebar/AssetsPanel';
import { HistoryPanel } from './sidebar/HistoryPanel';
import { IconButton } from './studio/IconButton';

/** Region 2 — the panel the rail opens: Create (playbooks, personas), Assets, History, Favorites. */
export function LeftSidebar({ overlay = false }: { overlay?: boolean }) {
  const { state, dispatch } = useStudio();
  const { panel, panelOpen } = state.ui;
  if (!panelOpen) return null;

  return (
    <aside
      aria-label="Studio panel"
      className={cn(
        'ks-region relative flex w-panel flex-col border-r border-ks-line [grid-area:panel]',
        overlay && 'absolute inset-y-0 left-0 z-30 shadow-float max-md:w-full',
      )}
    >
      <IconButton
        label="Hide panel"
        shortcut="["
        side="right"
        className="absolute right-2 top-2 z-10"
        onClick={() => dispatch({ type: 'TOGGLE_PANEL', open: false })}
      >
        <PanelLeftClose />
      </IconButton>
      <ScrollArea className="h-full">
        {panel === 'create' && <CreatePanel />}
        {panel === 'assets' && <AssetsPanel />}
        {panel === 'favorites' && <AssetsPanel favoritesOnly />}
        {panel === 'history' && <HistoryPanel />}
      </ScrollArea>
    </aside>
  );
}
