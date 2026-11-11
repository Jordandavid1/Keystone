'use client';

import React from 'react';
import { cn } from '@/lib/utils';
import { Generation, StudioAsset } from '@/lib/types';
import { AssetThumb } from '../studio/AssetThumb';

/** Which assets belong side by side with the selection: its run's outputs, else its siblings. */
export function variationSet(selected: StudioAsset | null, assets: StudioAsset[], runs: Generation[]): StudioAsset[] {
  if (!selected) return [];
  const run = runs.find((r) => r.outputIds.includes(selected.id));
  if (run && run.outputIds.length > 1) {
    return run.outputIds.map((id) => assets.find((a) => a.id === id)).filter(Boolean) as StudioAsset[];
  }
  if (selected.parentId) {
    const siblings = assets.filter((a) => a.parentId === selected.parentId);
    if (siblings.length > 1) return siblings;
  }
  return [selected];
}

/** Side-by-side gallery (Hugging Face pattern) — without the knobs. */
export function VariationsView({
  selected,
  assets,
  runs,
  onSelect,
  onOpen,
}: {
  selected: StudioAsset | null;
  assets: StudioAsset[];
  runs: Generation[];
  onSelect: (id: string) => void;
  onOpen: (id: string) => void;
}) {
  const set = variationSet(selected, assets, runs);

  if (set.length < 2) {
    return (
      <div className="flex size-full items-center justify-center p-6 text-center">
        <div className="max-w-[44ch]">
          <p className="text-title font-semibold text-ks-ink">Nothing to line up yet.</p>
          <p className="mt-1 text-body text-ks-ink-3">
            Variations appear here when a run returns more than one result, or when you make several versions from the same source.
            Set results per run in the inspector, or use Variation on the selected image.
          </p>
        </div>
      </div>
    );
  }

  const cols = set.length <= 2 ? 'grid-cols-2' : set.length <= 4 ? 'grid-cols-2 xl:grid-cols-4' : 'grid-cols-3 xl:grid-cols-4';
  return (
    <div className={cn('grid size-full content-center gap-3 overflow-auto p-4 sm:p-6 ks-scroll', cols)}>
      {set.map((a) => (
        <button
          key={a.id}
          onClick={() => onSelect(a.id)}
          onDoubleClick={() => onOpen(a.id)}
          aria-pressed={a.id === selected?.id}
          aria-label={`Select ${a.title}. Double-click to open.`}
          className={cn(
            'overflow-hidden rounded-frame bg-ks-abyss ring-1 ring-ks-line transition-shadow',
            a.id === selected?.id && 'ring-2 ring-ks-indigo',
          )}
        >
          <AssetThumb asset={a} fit="contain" className="aspect-square w-full" />
        </button>
      ))}
    </div>
  );
}
