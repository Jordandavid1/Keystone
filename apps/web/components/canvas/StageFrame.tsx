'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AudioLines, ImageOff, RefreshCw, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchAsset } from '@/lib/api';
import { LookState, StudioAsset } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { VideoTransport } from './VideoTransport';

export function lookFilter(look: LookState): string | undefined {
  const neutral = look.exposure === 0 && look.contrast === 100 && look.saturation === 100 && look.warmth === 0;
  if (neutral) return undefined;
  return `brightness(${1 + look.exposure / 4}) contrast(${look.contrast}%) saturate(${look.saturation}%) sepia(${
    Math.max(0, look.warmth) / 80
  }) hue-rotate(${look.warmth * 1.2}deg)`;
}

const MATTE_RATIO: Record<string, number | null> = { none: null, scope: 2.39, flat: 1.85, tv: 16 / 9, reel: 9 / 16 };

function Guides() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      {[33.333, 66.666].map((p) => (
        <React.Fragment key={p}>
          <span className="absolute inset-y-0 w-px bg-white/20" style={{ left: `${p}%` }} />
          <span className="absolute inset-x-0 h-px bg-white/20" style={{ top: `${p}%` }} />
        </React.Fragment>
      ))}
      <span className="absolute inset-[5%] border border-white/15" />
      <span className="absolute inset-[10%] border border-dashed border-white/10" />
    </div>
  );
}

function Matte({ ratio }: { ratio: number }) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden rounded-frame" aria-hidden="true">
      <div
        className="max-h-full max-w-full shadow-[0_0_0_100vmax_rgba(0,0,0,0.72)] outline outline-1 outline-white/20"
        style={{ aspectRatio: `${ratio}`, width: ratio >= 1 ? '100%' : 'auto', height: ratio >= 1 ? 'auto' : '100%' }}
      />
    </div>
  );
}

/** Single-asset stage: the creative asset at maximum size on the abyss. */
export function StageFrame({
  asset,
  look,
  zoom,
  guides,
  matte,
  fps,
  showC2paBadge = false,
}: {
  asset: StudioAsset;
  look: LookState;
  zoom: 'fit' | 1 | 2;
  guides: boolean;
  matte: string;
  fps: number;
  showC2paBadge?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [broken, setBroken] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [freshUrl, setFreshUrl] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);

  // Reset broken/retry state cleanly whenever the selected asset or source URL changes.
  useEffect(() => {
    setBroken(false);
    setRetrying(false);
    setRetryError(null);
    setFreshUrl(null);
    setRetryNonce(0);
  }, [asset.id, asset.url]);

  const activeUrl = freshUrl || asset.url;
  const filter = lookFilter(look);
  const matteRatio = MATTE_RATIO[matte] || null;

  const handleRetry = async () => {
    setRetrying(true);
    setRetryError(null);
    try {
      const latest = await fetchAsset(asset.id);
      if (latest?.url) {
        setFreshUrl(latest.url);
      }
      setBroken(false);
      setRetryNonce((n) => n + 1);
    } catch (err: any) {
      // Allow retrying local/blob URLs even if server refresh failed.
      if (activeUrl.startsWith('blob:') || activeUrl.startsWith('data:')) {
        setBroken(false);
        setRetryNonce((n) => n + 1);
      } else {
        setRetryError(err?.message || 'Could not refresh asset URL.');
      }
    } finally {
      setRetrying(false);
    }
  };

  if (broken) {
    return (
      <div className="flex size-full flex-col items-center justify-center gap-3 p-6 text-center" role="alert">
        <ImageOff className="size-6 text-ks-ink-3" />
        <p className="text-lead text-ks-ink">This asset couldn&apos;t be loaded.</p>
        <p className="max-w-[48ch] text-meta text-ks-ink-3">
          Its signed link may have expired or the asset is still finalizing. Retry to request a fresh signed URL.
        </p>
        {retryError && <p className="max-w-[48ch] text-meta text-ks-deny">{retryError}</p>}
        <div className="mt-1 flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void handleRetry()} disabled={retrying}>
            <RefreshCw className={cn('size-3.5', retrying && 'animate-spin')} />
            {retrying ? 'Retrying…' : 'Retry'}
          </Button>
        </div>
      </div>
    );
  }

  if (asset.type === 'audio') {
    return (
      <div className="flex size-full items-center justify-center p-6">
        <div className="flex w-full max-w-[560px] flex-col items-center gap-4 rounded-panel border border-ks-line bg-ks-raised/60 p-8">
          <AudioLines className="size-8 text-ks-ink-2" />
          <p className="text-lead text-ks-ink">{asset.title}</p>
          <audio key={`${asset.id}-${retryNonce}`} src={activeUrl} controls className="w-full" onError={() => setBroken(true)} />
        </div>
      </div>
    );
  }

  const scaled = zoom === 'fit' ? undefined : { transform: `scale(${zoom})` };

  return (
    <div className="flex size-full flex-col items-center justify-center gap-3 p-4 sm:p-6">
      <div className={cn('relative flex min-h-0 w-full flex-1 items-center justify-center', zoom !== 'fit' && 'overflow-auto ks-scroll')}>
        <div className="relative max-h-full max-w-full animate-in fade-in-0 zoom-in-[0.985] duration-settle">
          {asset.type === 'video' ? (
            <video
              key={`${asset.id}-${retryNonce}`}
              ref={videoRef}
              src={activeUrl}
              playsInline
              preload="auto"
              onError={() => setBroken(true)}
              className="block max-h-[calc(100dvh-var(--ks-reserved,300px)-56px)] max-w-full rounded-frame bg-black shadow-frame"
              style={{ filter, ...scaled }}
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={`${asset.id}-${retryNonce}`}
              src={activeUrl}
              alt={asset.title}
              onError={() => setBroken(true)}
              className="block max-h-[calc(100dvh-var(--ks-reserved,300px))] max-w-full origin-center rounded-frame object-contain shadow-frame transition-transform duration-base ease-shutter"
              style={{ filter, ...scaled }}
            />
          )}
          {guides && <Guides />}
          {matteRatio && <Matte ratio={matteRatio} />}
          {(asset.mature || (showC2paBadge && asset.c2paManifest)) && (
            <div className="pointer-events-none absolute left-2.5 top-2.5 flex items-center gap-1.5">
              {asset.mature && (
                <span className="rounded-full border border-ks-hold/50 bg-black/70 px-2 py-0.5 text-micro font-medium text-ks-hold backdrop-blur">
                  Mature 18+
                </span>
              )}
              {showC2paBadge && asset.c2paManifest && (
                <span className="inline-flex items-center gap-1 rounded-full border border-ks-verified/40 bg-black/70 px-2 py-0.5 text-micro font-medium text-ks-verified backdrop-blur">
                  <ShieldCheck className="size-3" /> C2PA
                </span>
              )}
            </div>
          )}
        </div>
      </div>
      {asset.type === 'video' && <VideoTransport key={asset.id} videos={[videoRef]} fps={fps} />}
    </div>
  );
}
