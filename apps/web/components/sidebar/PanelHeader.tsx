import React from 'react';

export function PanelHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex h-12 shrink-0 items-center justify-between gap-2 pl-4 pr-12">
      <h2 className="text-lead font-semibold text-ks-ink">{title}</h2>
      <div className="flex items-center gap-1">{children}</div>
    </div>
  );
}

export function PanelNote({ children, tone = 'muted' }: { children: React.ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <p className={tone === 'error' ? 'px-4 text-meta text-ks-deny' : 'px-4 text-meta text-ks-ink-3'}>{children}</p>
  );
}
