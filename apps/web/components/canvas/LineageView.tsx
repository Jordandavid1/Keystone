'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { GitBranch } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchAssetLineage } from '@/lib/api';
import { ancestorsOf, buildLineage, descendantsOf } from '@/lib/lineage';
import { StudioAsset } from '@/lib/types';
import { AssetThumb } from '../studio/AssetThumb';

const NODE = 112;
const GAP_X = 72;
const GAP_Y = 28;
const PAD = 32;

/** Interactive lineage DAG: every upload, edit, variation and animation linked parent → child. */
export function LineageView({
  assets,
  selectedId,
  onSelect,
  onCompareWithParent,
}: {
  assets: StudioAsset[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCompareWithParent: (id: string) => void;
}) {
  const graph = useMemo(() => buildLineage(assets), [assets]);
  const [server, setServer] = useState<{ ancestors: string[]; descendants: string[] } | null>(null);

  useEffect(() => {
    setServer(null);
    if (!selectedId) return;
    let cancelled = false;
    fetchAssetLineage(selectedId)
      .then((l) => !cancelled && setServer(l))
      .catch(() => undefined); // local-only assets have no server lineage; the local graph still draws
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const related = useMemo(() => {
    if (!selectedId) return new Set<string>();
    return new Set([
      ...ancestorsOf(selectedId, assets),
      ...descendantsOf(selectedId, assets),
      ...(server?.ancestors || []),
      ...(server?.descendants || []),
    ]);
  }, [assets, selectedId, server]);

  if (!assets.length) {
    return (
      <div className="flex size-full items-center justify-center p-6 text-center">
        <div className="max-w-[44ch]">
          <GitBranch className="mx-auto mb-3 size-6 text-ks-ink-3" />
          <p className="text-title font-semibold text-ks-ink">Lineage starts with your first asset.</p>
          <p className="mt-1 text-body text-ks-ink-3">Every edit, variation, animation and upscale links back to its source here, so you can return to any step.</p>
        </div>
      </div>
    );
  }

  const pos = new Map(graph.nodes.map((n) => [n.asset.id, { x: PAD + n.depth * (NODE + GAP_X), y: PAD + n.row * (NODE + GAP_Y + 18) }]));
  const width = PAD * 2 + graph.columns * NODE + Math.max(0, graph.columns - 1) * GAP_X;
  const height = PAD * 2 + graph.rows * (NODE + GAP_Y + 18);

  return (
    <div className="size-full overflow-auto ks-scroll">
      <div className="relative" style={{ width, height, minWidth: '100%' }}>
        <svg className="pointer-events-none absolute inset-0" width={width} height={height} aria-hidden="true">
          {graph.edges.map((e) => {
            const a = pos.get(e.from)!;
            const b = pos.get(e.to)!;
            const x1 = a.x + NODE;
            const y1 = a.y + NODE / 2;
            const x2 = b.x;
            const y2 = b.y + NODE / 2;
            const mid = (x1 + x2) / 2;
            const lit = selectedId && (e.to === selectedId || e.from === selectedId || (related.has(e.from) && related.has(e.to)) || (related.has(e.from) && e.to === selectedId));
            return (
              <path
                key={`${e.from}-${e.to}`}
                d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke={lit ? '#8B5CF6' : 'rgba(255,255,255,0.14)'}
                strokeWidth={lit ? 2 : 1.25}
              />
            );
          })}
        </svg>
        {graph.nodes.map((n) => {
          const p = pos.get(n.asset.id)!;
          const selected = n.asset.id === selectedId;
          const dim = !!selectedId && !selected && !related.has(n.asset.id);
          return (
            <div key={n.asset.id} className="absolute" style={{ left: p.x, top: p.y, width: NODE }}>
              <button
                onClick={() => onSelect(n.asset.id)}
                aria-label={`Open ${n.asset.title}`}
                aria-current={selected ? 'true' : undefined}
                className={cn(
                  'block overflow-hidden rounded-control ring-1 ring-ks-line transition-opacity duration-base',
                  selected && 'ring-2 ring-ks-indigo',
                  dim && 'opacity-40 hover:opacity-100',
                )}
                style={{ width: NODE, height: NODE }}
              >
                <AssetThumb asset={n.asset} className="size-full" />
              </button>
              <div className="mt-1 flex items-center justify-between gap-1">
                <span className="truncate text-micro text-ks-ink-3" title={n.asset.title}>
                  {n.asset.title}
                </span>
                {selected && n.asset.parentId && (
                  <button onClick={() => onCompareWithParent(n.asset.id)} className="shrink-0 text-micro text-ks-ink-2 hover:text-ks-ink">
                    Compare
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
