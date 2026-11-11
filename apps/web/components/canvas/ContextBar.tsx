'use client';

import React, { useEffect, useState } from 'react';
import { ArrowUpRight, Columns2, Copy, Download, Film, Heart, Maximize2, Paperclip, Pencil, Share2 } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { StudioAsset } from '@/lib/types';

function Action({
  label,
  icon: Icon,
  onClick,
  active,
  disabled,
}: {
  label: string;
  icon: React.ElementType;
  onClick?: () => void;
  active?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        'flex h-8 shrink-0 items-center gap-1.5 rounded-control px-2.5 text-meta font-medium text-ks-ink-2 transition-colors duration-quick hover:bg-white/[0.06] hover:text-ks-ink disabled:pointer-events-none disabled:opacity-40',
        active && 'text-ks-ink',
      )}
    >
      <Icon className={cn('size-3.5', active && label === 'Favorite' && 'fill-ks-deny text-ks-deny')} />
      <span>{label}</span>
    </button>
  );
}

/** Contextual floating action bar (Adobe pattern): the verbs for whatever is on stage. */
export function ContextBar({
  asset,
  favorite,
  busy,
  onEdit,
  onAnimate,
  onVariation,
  onUpscale,
  onCompare,
  onReference,
  onFavorite,
}: {
  asset: StudioAsset;
  favorite: boolean;
  busy: boolean;
  onEdit: () => void;
  onAnimate: () => void;
  onVariation: () => void;
  onUpscale: (f: 2 | 4) => void;
  onCompare: () => void;
  onReference: () => void;
  onFavorite: () => void;
}) {
  const [canShare, setCanShare] = useState(false);
  useEffect(() => setCanShare(typeof navigator !== 'undefined' && typeof navigator.share === 'function'), []);
  const isImage = asset.type === 'image';
  const href = asset.downloadUrl || asset.url;

  return (
    <div
      role="toolbar"
      aria-label={`Actions for ${asset.title}`}
      className="ks-glass pointer-events-auto flex max-w-full items-center gap-0.5 overflow-x-auto rounded-panel p-1 shadow-float ks-scroll"
    >
      {isImage && <Action label="Edit" icon={Pencil} onClick={onEdit} />}
      {asset.type !== 'audio' && <Action label="Animate" icon={Film} onClick={onAnimate} />}
      {isImage && <Action label="Variation" icon={Copy} onClick={onVariation} disabled={busy} />}
      {asset.type !== 'audio' && (
        <Popover>
          <PopoverTrigger asChild>
            <button className="flex h-8 shrink-0 items-center gap-1.5 rounded-control px-2.5 text-meta font-medium text-ks-ink-2 hover:bg-white/[0.06] hover:text-ks-ink">
              <Maximize2 className="size-3.5" />
              <span>Upscale</span>
            </button>
          </PopoverTrigger>
          <PopoverContent side="top" className="w-44 p-1">
            {[2, 4].map((f) => (
              <button
                key={f}
                onClick={() => onUpscale(f as 2 | 4)}
                className="flex w-full items-center justify-between rounded-control px-2.5 py-2 text-body text-ks-ink hover:bg-ks-lift"
              >
                <span>Upscale {f}×</span>
                <span className="text-meta text-ks-ink-3">{f === 2 ? 'Sharper' : 'Print size'}</span>
              </button>
            ))}
          </PopoverContent>
        </Popover>
      )}
      <span className="mx-1 h-5 w-px shrink-0 bg-ks-line-strong" aria-hidden="true" />
      {asset.type !== 'audio' && <Action label="Compare" icon={Columns2} onClick={onCompare} />}
      <Action label="Use as reference" icon={Paperclip} onClick={onReference} />
      <Action label="Favorite" icon={Heart} onClick={onFavorite} active={favorite} />
      <a
        href={href}
        download
        target="_blank"
        rel="noreferrer"
        className="flex h-8 shrink-0 items-center gap-1.5 rounded-control px-2.5 text-meta font-medium text-ks-ink-2 hover:bg-white/[0.06] hover:text-ks-ink"
      >
        <Download className="size-3.5" />
        <span>Download</span>
      </a>
      {canShare && (
        <Action
          label="Share"
          icon={Share2}
          onClick={() => void navigator.share({ title: asset.title, url: new URL(href, window.location.href).toString() }).catch(() => undefined)}
        />
      )}
      {!canShare && (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="flex h-8 shrink-0 items-center gap-1.5 rounded-control px-2.5 text-meta font-medium text-ks-ink-2 hover:bg-white/[0.06] hover:text-ks-ink"
          aria-label="Open original in a new tab"
        >
          <ArrowUpRight className="size-3.5" />
        </a>
      )}
    </div>
  );
}
