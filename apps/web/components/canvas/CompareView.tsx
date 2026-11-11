'use client';

import React, { useMemo, useRef, useState } from 'react';
import { ArrowLeftRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ancestorsOf } from '@/lib/lineage';
import { StudioAsset } from '@/lib/types';
import { AssetThumb } from '../studio/AssetThumb';
import { VideoTransport } from './VideoTransport';

function Curtain({ before, after }: { before: StudioAsset; after: StudioAsset }) {
  const [split, setSplit] = useState(50);
  const box = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const fromPointer = (x: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    setSplit(Math.max(0, Math.min(100, ((x - r.left) / r.width) * 100)));
  };

  return (
    <div
      ref={box}
      className="relative max-h-full max-w-full cursor-ew-resize touch-none select-none overflow-hidden rounded-frame shadow-frame"
      onPointerDown={(e) => {
        dragging.current = true;
        (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
        fromPointer(e.clientX);
      }}
      onPointerMove={(e) => dragging.current && fromPointer(e.clientX)}
      onPointerUp={() => (dragging.current = false)}
    >
      {/* After defines the box; before is clipped over it. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={after.url} alt={`After: ${after.title}`} className="block max-h-[calc(100dvh-var(--ks-reserved,300px))] max-w-full object-contain" draggable={false} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={before.url}
        alt={`Before: ${before.title}`}
        draggable={false}
        className="absolute inset-0 size-full object-contain"
        style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
      />
      <div className="pointer-events-none absolute inset-y-0" style={{ left: `${split}%` }}>
        <div className="absolute inset-y-0 -ml-px w-0.5 bg-white/90 shadow-[0_0_12px_rgba(0,0,0,0.6)]" />
      </div>
      <div
        role="slider"
        tabIndex={0}
        aria-label="Compare position"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(split)}
        aria-valuetext={`${Math.round(split)}% before`}
        className="absolute top-1/2 flex size-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-black shadow-lg"
        style={{ left: `${split}%` }}
        onKeyDown={(e) => {
          const stepBy = e.shiftKey ? 10 : 2;
          if (e.key === 'ArrowLeft') setSplit((v) => Math.max(0, v - stepBy));
          else if (e.key === 'ArrowRight') setSplit((v) => Math.min(100, v + stepBy));
          else if (e.key === 'Home') setSplit(0);
          else if (e.key === 'End') setSplit(100);
          else return;
          e.preventDefault();
          e.stopPropagation();
        }}
      >
        <ArrowLeftRight className="size-4" />
      </div>
      <span className="pointer-events-none absolute left-3 top-3 rounded-md bg-black/60 px-2 py-0.5 text-meta text-white backdrop-blur">Before</span>
      <span className="pointer-events-none absolute right-3 top-3 rounded-md bg-black/60 px-2 py-0.5 text-meta text-white backdrop-blur">After</span>
    </div>
  );
}

function DualVideo({ before, after, fps }: { before: StudioAsset; after: StudioAsset; fps: number }) {
  const a = useRef<HTMLVideoElement>(null);
  const b = useRef<HTMLVideoElement>(null);
  const refs = useMemo(() => [a, b], []);
  return (
    <div className="flex size-full flex-col items-center gap-3">
      <div className="grid min-h-0 w-full flex-1 grid-cols-2 gap-3">
        {[
          { ref: a, asset: before, label: 'Before' },
          { ref: b, asset: after, label: 'After' },
        ].map(({ ref, asset, label }) => (
          <figure key={label} className="relative flex min-h-0 items-center justify-center">
            <video ref={ref} src={asset.url} muted={label === 'After'} playsInline preload="auto" className="max-h-full max-w-full rounded-frame bg-black shadow-frame" />
            <figcaption className="absolute left-2 top-2 rounded-md bg-black/60 px-2 py-0.5 text-meta text-white">{label}</figcaption>
          </figure>
        ))}
      </div>
      <VideoTransport key={`${before.id}-${after.id}`} videos={refs} fps={fps} />
    </div>
  );
}

/** Split-screen compare: curtain for images, synchronized playback for video (Bible §25). */
export function CompareView({
  after,
  before,
  assets,
  fps,
  onPickBefore,
}: {
  after: StudioAsset | null;
  before: StudioAsset | null;
  assets: StudioAsset[];
  fps: number;
  onPickBefore: (id: string) => void;
}) {
  const candidates = useMemo(() => {
    if (!after) return [];
    const anc = ancestorsOf(after.id, assets);
    const others = assets.filter((a) => a.id !== after.id && a.type === after.type);
    return [...others].sort((x, y) => {
      const ix = anc.indexOf(x.id);
      const iy = anc.indexOf(y.id);
      if (ix !== -1 || iy !== -1) return (ix === -1 ? 999 : ix) - (iy === -1 ? 999 : iy);
      return y.createdAt - x.createdAt;
    });
  }, [after, assets]);

  if (!after) {
    return (
      <div className="flex size-full items-center justify-center p-6 text-center">
        <div>
          <p className="text-title font-semibold text-ks-ink">Select an asset to compare.</p>
          <p className="mt-1 text-body text-ks-ink-3">Pick one from Assets; it becomes the after side.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex size-full flex-col gap-3 p-4 sm:p-6">
      <div className="flex min-h-0 flex-1 items-center justify-center">
        {!before ? (
          <div className="text-center">
            <p className="text-title font-semibold text-ks-ink">Choose what to compare against.</p>
            <p className="mt-1 text-body text-ks-ink-3">
              {candidates.length ? 'Pick the before side below. Its source is listed first.' : `Create or upload another ${after.type} to compare with this one.`}
            </p>
          </div>
        ) : before.type === 'video' && after.type === 'video' ? (
          <DualVideo before={before} after={after} fps={fps} />
        ) : before.type === 'image' && after.type === 'image' ? (
          <Curtain before={before} after={after} />
        ) : (
          <p className="text-body text-ks-ink-3">These two can't be compared side by side. Pick two images or two videos.</p>
        )}
      </div>
      {candidates.length > 0 && (
        <div className="flex shrink-0 items-center gap-2 overflow-x-auto pb-1 ks-scroll" aria-label="Compare against">
          <span className="shrink-0 text-meta text-ks-ink-3">Before</span>
          {candidates.slice(0, 24).map((c) => (
            <button
              key={c.id}
              onClick={() => onPickBefore(c.id)}
              aria-pressed={before?.id === c.id}
              aria-label={`Compare against ${c.title}`}
              className={cn('shrink-0 overflow-hidden rounded-control ring-1 ring-ks-line', before?.id === c.id && 'ring-2 ring-ks-indigo')}
            >
              <AssetThumb asset={c} className="size-12" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
