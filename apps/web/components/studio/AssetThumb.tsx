'use client';

import React, { useState } from 'react';
import { AudioLines, Film, ImageOff } from 'lucide-react';
import { cn } from '@/lib/utils';
import { StudioAsset } from '@/lib/types';

/** Renders the real asset at thumbnail size. Broken media shows an explicit "can't load" state, never a stand-in image. */
export function AssetThumb({ asset, className, fit = 'cover' }: { asset: StudioAsset; className?: string; fit?: 'cover' | 'contain' }) {
  const [broken, setBroken] = useState(false);
  const src = asset.previewUrl || asset.url;

  if (broken || !src) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-1 bg-ks-raised text-micro text-ks-ink-3', className)}>
        <ImageOff className="size-4" />
        <span>Can't load</span>
      </div>
    );
  }
  if (asset.type === 'audio') {
    return (
      <div className={cn('flex items-center justify-center bg-ks-raised text-ks-ink-2', className)}>
        <AudioLines className="size-5" />
      </div>
    );
  }
  if (asset.type === 'video') {
    return (
      <div className={cn('relative overflow-hidden bg-black', className)}>
        <video
          src={asset.url}
          preload="metadata"
          muted
          playsInline
          onError={() => setBroken(true)}
          className={cn('size-full', fit === 'cover' ? 'object-cover' : 'object-contain')}
        />
        <Film className="absolute bottom-1.5 left-1.5 size-3.5 text-white/80 drop-shadow" aria-hidden="true" />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={asset.title}
      loading="lazy"
      onError={() => setBroken(true)}
      className={cn('bg-ks-raised', fit === 'cover' ? 'object-cover' : 'object-contain', className)}
    />
  );
}
