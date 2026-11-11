'use client';

import React from 'react';
import { CornerDownLeft, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Generation, StudioAsset } from '@/lib/types';
import { AssetThumb } from '../studio/AssetThumb';

/** Split artifact view (Grok pattern): the asset stays on the left, the answer reads on the right. */
export function AnalysisPane({
  run,
  asset,
  onClose,
  onUseAsPrompt,
}: {
  run: Generation;
  asset: StudioAsset | null;
  onClose: () => void;
  onUseAsPrompt: (text: string) => void;
}) {
  return (
    <div className="grid size-full min-h-0 grid-cols-1 gap-4 p-4 sm:p-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
      <div className="flex min-h-0 items-center justify-center max-lg:hidden">
        {asset ? (
          <AssetThumb asset={asset} fit="contain" className="max-h-full w-full rounded-frame bg-transparent shadow-frame" />
        ) : (
          <p className="max-w-[36ch] text-center text-body text-ks-ink-3">This question wasn't about a specific asset. Select one before asking to discuss it here.</p>
        )}
      </div>
      <article className="flex min-h-0 flex-col overflow-hidden rounded-panel border border-ks-line bg-ks-chrome">
        <header className="flex items-start justify-between gap-3 border-b border-ks-line px-4 py-3">
          <div className="min-w-0">
            <div className="text-meta text-ks-ink-3">You asked</div>
            <p className="line-clamp-3 text-body text-ks-ink">{run.prompt}</p>
          </div>
          <Button variant="ghost" size="icon-sm" aria-label="Close answer" onClick={onClose}>
            <X />
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-4 ks-scroll">
          <p className="max-w-[72ch] whitespace-pre-wrap text-body leading-6 text-ks-ink">{run.text}</p>
        </div>
        <footer className="flex justify-end gap-2 border-t border-ks-line px-4 py-2.5">
          <Button variant="outline" size="sm" onClick={() => onUseAsPrompt(run.text || '')}>
            <CornerDownLeft /> Use as prompt
          </Button>
        </footer>
      </article>
    </div>
  );
}
