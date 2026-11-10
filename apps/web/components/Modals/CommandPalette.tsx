'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import { CanvasViewMode, GenerativeToolId } from '../../lib/types';
import { TOOLS_CATALOG } from '../../lib/toolsCatalog';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelectTool: (tool: GenerativeToolId) => void;
  onChangeMode: (mode: CanvasViewMode) => void;
  onOpenPersonas: () => void;
  onOpenWebScrape: () => void;
  onOpenPipeline: () => void;
  onOpenSettings: () => void;
  onOpenProjects: () => void;
  onOpenSessions: () => void;
  onOpenCredits: () => void;
  onOpenWorker: () => void;
  onOpenAgentChat: () => void;
}

const CANVAS_MODES: { id: CanvasViewMode; label: string }[] = [
  { id: 'single', label: 'Primary Canvas' },
  { id: 'compare', label: 'Split Compare' },
  { id: 'video', label: 'MiniMax Video' },
  { id: 'variations', label: 'Variations Grid' },
  { id: 'lineage', label: 'Lineage DAG' },
  { id: 'pipeline', label: 'Pipeline Builder' },
];

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  open,
  onClose,
  onSelectTool,
  onChangeMode,
  onOpenPersonas,
  onOpenWebScrape,
  onOpenPipeline,
  onOpenSettings,
  onOpenProjects,
  onOpenSessions,
  onOpenCredits,
  onOpenWorker,
  onOpenAgentChat,
}) => {
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const items = useMemo(() => {
    const q = query.toLowerCase().trim();
    const toolItems = Object.values(TOOLS_CATALOG).map((tool) => ({
      id: `tool:${tool.id}`,
      label: tool.name,
      hint: `${tool.category} · ${tool.badge}`,
      run: () => onSelectTool(tool.id),
    }));
    const modeItems = CANVAS_MODES.map((mode) => ({
      id: `mode:${mode.id}`,
      label: mode.label,
      hint: 'Canvas mode',
      run: () => {
        if (mode.id === 'pipeline') onOpenPipeline();
        onChangeMode(mode.id);
      },
    }));
    const extras = [
      { id: 'cmd:personas', label: 'Personas & Voices', hint: 'Character cast', run: onOpenPersonas },
      { id: 'cmd:web', label: '@Web Style Extract', hint: 'Firecrawl URL ingest', run: onOpenWebScrape },
      { id: 'cmd:settings', label: 'Studio Settings', hint: 'Config / engine / identity', run: onOpenSettings },
      { id: 'cmd:projects', label: 'Projects Manager', hint: 'Workspace projects', run: onOpenProjects },
      { id: 'cmd:sessions', label: 'Session History', hint: 'Multi-turn sessions', run: onOpenSessions },
      { id: 'cmd:credits', label: 'Credit Ledger', hint: 'LOCAL ENGINE honesty', run: onOpenCredits },
      { id: 'cmd:worker', label: 'Colab Engine Telemetry', hint: 'Worker / cognition / ComfyUI', run: onOpenWorker },
      { id: 'cmd:chat', label: 'LLM Agent Chat', hint: 'Colab llama-server', run: onOpenAgentChat },
    ];
    return [...toolItems, ...modeItems, ...extras].filter((item) => {
      if (!q) return true;
      return `${item.label} ${item.hint} ${item.id}`.toLowerCase().includes(q);
    });
  }, [query, onSelectTool, onChangeMode, onOpenPersonas, onOpenWebScrape, onOpenPipeline, onOpenSettings, onOpenProjects, onOpenSessions, onOpenCredits, onOpenWorker, onOpenAgentChat]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="command-modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 8px' }}>
          <Search size={16} style={{ marginLeft: 10, color: 'var(--text-secondary)' }} />
          <input
            className="command-input"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search all 17 tools, canvas modes, or commands..."
            aria-label="Command search"
          />
          <button className="icon-btn" onClick={onClose} title="Close" style={{ marginRight: 8 }}>
            <X size={14} />
          </button>
        </div>
        <div className="command-list">
          {items.length === 0 ? (
            <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>No matching commands.</div>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                className="command-item"
                onClick={() => {
                  item.run();
                  onClose();
                }}
                style={{ width: '100%', background: 'transparent', border: 'none', textAlign: 'left' }}
              >
                <span>{item.label}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{item.hint}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
