'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Code2, Image as ImageIcon, LayoutGrid, Search, Settings2, Wand2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { INTENTS } from '@/lib/intents';
import { Modal, useStudio } from '@/lib/studio/store';
import { CanvasViewMode, SidebarPanel } from '@/lib/types';

interface Item {
  id: string;
  group: 'Do' | 'Go to' | 'Playbooks' | 'Assets' | 'Studio' | 'Developer';
  label: string;
  hint?: string;
  icon: React.ElementType;
  run: () => void;
}

/** ⌘K — intents, views, playbooks, assets and studio commands. Raw capabilities only appear in Developer mode. */
export function CommandPalette() {
  const { state, dispatch } = useStudio();
  const open = state.ui.modal === 'command';
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const close = () => dispatch({ type: 'OPEN_MODAL', modal: null });

  useEffect(() => {
    if (open) {
      setQuery('');
      setActive(0);
    }
  }, [open]);

  const items = useMemo<Item[]>(() => {
    const modal = (m: Modal) => () => dispatch({ type: 'OPEN_MODAL', modal: m });
    const view = (v: CanvasViewMode) => () => dispatch({ type: 'SET_VIEW', view: v });
    const panel = (p: SidebarPanel) => () => dispatch({ type: 'SET_PANEL', panel: p });
    const list: Item[] = [
      ...INTENTS.map((i) => ({ id: `intent:${i.id}`, group: 'Do' as const, label: i.label, hint: i.prompt, icon: Wand2, run: () => dispatch({ type: 'SET_INTENT', intent: i.id }) })),
      { id: 'view:single', group: 'Go to', label: 'Stage', icon: LayoutGrid, run: view('single') },
      { id: 'view:compare', group: 'Go to', label: 'Compare', icon: LayoutGrid, run: view('compare') },
      { id: 'view:variations', group: 'Go to', label: 'Variations', icon: LayoutGrid, run: view('variations') },
      { id: 'view:lineage', group: 'Go to', label: 'Lineage', icon: LayoutGrid, run: view('lineage') },
      { id: 'panel:assets', group: 'Go to', label: 'Assets', icon: LayoutGrid, run: panel('assets') },
      { id: 'panel:history', group: 'Go to', label: 'History', icon: LayoutGrid, run: panel('history') },
      { id: 'panel:favorites', group: 'Go to', label: 'Favorites', icon: LayoutGrid, run: panel('favorites') },
      ...state.system.playbooks.map((pb) => ({
        id: `playbook:${pb.id}`,
        group: 'Playbooks' as const,
        label: pb.label,
        hint: state.composer.playbook?.id === pb.id ? 'Attached' : 'Attach',
        icon: BookOpen,
        run: () => dispatch({ type: 'SET_PLAYBOOK', playbook: state.composer.playbook?.id === pb.id ? null : pb }),
      })),
      ...state.library.assets.slice(0, 200).map((a) => ({
        id: `asset:${a.id}`,
        group: 'Assets' as const,
        label: a.title,
        hint: a.type,
        icon: ImageIcon,
        run: () => {
          dispatch({ type: 'SELECT_ASSET', id: a.id });
          dispatch({ type: 'SET_VIEW', view: 'single' });
        },
      })),
      { id: 'cmd:projects', group: 'Studio', label: 'Projects', icon: Settings2, run: modal('projects') },
      { id: 'cmd:sessions', group: 'Studio', label: 'Sessions', icon: Settings2, run: modal('sessions') },
      { id: 'cmd:agent', group: 'Studio', label: 'Talk to KEYSTONE', icon: Settings2, run: modal('agent') },
      { id: 'cmd:personas', group: 'Studio', label: 'Personas and voices', icon: Settings2, run: modal('personas') },
      { id: 'cmd:web', group: 'Studio', label: 'Add web reference', icon: Settings2, run: modal('web') },
      { id: 'cmd:credits', group: 'Studio', label: 'Credits', icon: Settings2, run: modal('credits') },
      { id: 'cmd:engine', group: 'Studio', label: 'Engine status', icon: Settings2, run: modal('worker') },
      { id: 'cmd:settings', group: 'Studio', label: 'Settings', icon: Settings2, run: modal('settings') },
      { id: 'cmd:dev', group: 'Studio', label: state.ui.developer ? 'Turn off developer mode' : 'Turn on developer mode', icon: Code2, run: () => dispatch({ type: 'TOGGLE_DEVELOPER' }) },
    ];
    if (state.ui.developer) {
      list.push({ id: 'dev:pipeline', group: 'Developer', label: 'Pipeline', icon: Code2, run: view('pipeline') });
    }
    return list;
  }, [dispatch, state.composer.playbook, state.library.assets, state.system.playbooks, state.ui.developer]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = q ? items.filter((i) => `${i.label} ${i.hint || ''} ${i.group}`.toLowerCase().includes(q)) : items.filter((i) => i.group !== 'Assets');
    return base;
  }, [items, query]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  if (!open) return null;

  const choose = (item: Item | undefined) => {
    if (!item) return;
    close();
    item.run();
  };

  let lastGroup = '';
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 px-4 pt-[12vh] backdrop-blur-sm" onClick={close} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="ks-glass w-full max-w-[600px] overflow-hidden rounded-panel border border-ks-line-strong shadow-float" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-ks-line px-4">
          <Search className="size-4 text-ks-ink-3" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') close();
              else if (e.key === 'ArrowDown') {
                e.preventDefault();
                setActive((a) => Math.min(filtered.length - 1, a + 1));
              } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setActive((a) => Math.max(0, a - 1));
              } else if (e.key === 'Enter') {
                e.preventDefault();
                choose(filtered[active]);
              }
            }}
            placeholder="Search assets, playbooks and commands"
            aria-label="Search commands"
            className="h-12 flex-1 bg-transparent text-lead text-ks-ink placeholder:text-ks-ink-3 focus:outline-none focus-visible:outline-none focus-visible:!shadow-none"
          />
          <kbd className="rounded border border-ks-line-strong px-1.5 text-micro text-ks-ink-3">Esc</kbd>
        </div>
        <div ref={listRef} className="max-h-[52vh] overflow-auto p-1.5 ks-scroll" role="listbox">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-center text-body text-ks-ink-3">Nothing matches “{query}”.</p>
          ) : (
            filtered.map((item, idx) => {
              const header = item.group !== lastGroup ? item.group : null;
              lastGroup = item.group;
              return (
                <React.Fragment key={item.id}>
                  {header && <div className="px-3 pb-1 pt-2.5 text-micro font-medium text-ks-ink-3">{header}</div>}
                  <button
                    data-index={idx}
                    role="option"
                    aria-selected={idx === active}
                    onMouseEnter={() => setActive(idx)}
                    onClick={() => choose(item)}
                    className={cn('flex w-full items-center gap-3 rounded-control px-3 py-2 text-left', idx === active ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-2')}
                  >
                    <item.icon className="size-4 shrink-0 text-ks-ink-3" />
                    <span className="flex-1 truncate text-body">{item.label}</span>
                    {item.hint && <span className="truncate text-meta text-ks-ink-3">{item.hint}</span>}
                  </button>
                </React.Fragment>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
