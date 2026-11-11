'use client';

import React, { useMemo, useRef, useState } from 'react';
import { Heart, Paperclip, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useStudio } from '@/lib/studio/store';
import { useGeneration } from '@/lib/studio/useGeneration';
import { AssetThumb } from '../studio/AssetThumb';
import { PanelHeader, PanelNote } from './PanelHeader';
import { SignedOutNote } from '../auth/SignedOutNote';

type Filter = 'all' | 'image' | 'video' | 'audio';
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'image', label: 'Images' },
  { id: 'video', label: 'Video' },
  { id: 'audio', label: 'Audio' },
];

/** Assets / Favorites panel — the real library, with upload by click or drop. */
export function AssetsPanel({ favoritesOnly = false }: { favoritesOnly?: boolean }) {
  const { state, dispatch } = useStudio();
  const { upload } = useGeneration();
  const { assets, favorites, selectedId, loaded, loadError } = state.library;
  const sessionStatus = state.system.session.status;
  const awaitingSession = sessionStatus === 'checking';
  const signedOut = sessionStatus === 'signed_out' || sessionStatus === 'error';
  const [filter, setFilter] = useState<Filter>('all');
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const visible = useMemo(
    () =>
      assets.filter(
        (a) => (!favoritesOnly || favorites.includes(a.id)) && (filter === 'all' || a.type === filter),
      ),
    [assets, favorites, favoritesOnly, filter],
  );

  const onFiles = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((f) => upload(f, false));
  };

  return (
    <div
      className={cn('flex min-h-full flex-col pb-6', dragOver && 'bg-ks-indigo/[0.05]')}
      onDragOver={(e) => {
        if (favoritesOnly) return;
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        if (favoritesOnly) return;
        e.preventDefault();
        setDragOver(false);
        onFiles(e.dataTransfer.files);
      }}
    >
      <PanelHeader title={favoritesOnly ? 'Favorites' : 'Assets'}>
        {!favoritesOnly && (
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1.5 rounded-control px-2 py-1 text-meta text-ks-ink-2 hover:bg-ks-lift hover:text-ks-ink"
          >
            <Upload className="size-3.5" /> Upload
          </button>
        )}
      </PanelHeader>
      <input
        ref={fileRef}
        type="file"
        multiple
        hidden
        accept="image/*,video/*,audio/*"
        onChange={(e) => {
          onFiles(e.target.files);
          e.target.value = '';
        }}
      />

      <div className="mb-3 flex gap-1 px-3" role="tablist" aria-label="Filter assets">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            role="tab"
            aria-selected={filter === f.id}
            onClick={() => setFilter(f.id)}
            className={cn(
              'rounded-full px-2.5 py-1 text-meta transition-colors',
              filter === f.id ? 'bg-ks-lift text-ks-ink' : 'text-ks-ink-3 hover:text-ks-ink',
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {signedOut && !favoritesOnly && (
        <div className="mb-3">
          <SignedOutNote what="your saved assets" />
        </div>
      )}

      {awaitingSession || (!loaded && !signedOut) ? (
        <PanelNote>Loading your assets…</PanelNote>
      ) : visible.length === 0 ? (
        favoritesOnly ? (
          <PanelNote>Mark an asset with the heart to keep it here.</PanelNote>
        ) : (
          <div className="px-3">
            <button
              onClick={() => fileRef.current?.click()}
              className="flex w-full flex-col items-center gap-2 rounded-panel border border-dashed border-ks-line-strong px-4 py-8 text-center text-meta text-ks-ink-3 transition-colors hover:border-ks-indigo/60 hover:text-ks-ink-2"
            >
              <Upload className="size-5" />
              <span className="text-body text-ks-ink-2">Drop images, video or audio</span>
              <span>or click to choose files. Everything you create lands here too.</span>
            </button>
            {loadError && <p className="mt-3 text-meta text-ks-deny">Saved assets didn't load: {loadError} New results from this session still appear here.</p>}
          </div>
        )
      ) : (
        <>
          {loadError && <PanelNote tone="error">Saved assets didn't load: {loadError} New results from this session still appear here.</PanelNote>}
          <ul className="grid grid-cols-2 gap-2 px-3" aria-label="Assets">
            {visible.map((asset) => {
              const selected = asset.id === selectedId;
              const fav = favorites.includes(asset.id);
              return (
                <li key={asset.id} className="group relative">
                  <button
                    onClick={() => {
                      dispatch({ type: 'SELECT_ASSET', id: asset.id });
                      if (state.ui.view === 'analysis') dispatch({ type: 'SHOW_ANALYSIS', runId: null });
                    }}
                    className={cn(
                      'block w-full overflow-hidden rounded-control ring-1 ring-ks-line transition-shadow',
                      selected && 'ring-2 ring-ks-indigo',
                    )}
                    aria-label={`Show ${asset.title}`}
                    aria-current={selected ? 'true' : undefined}
                  >
                    <AssetThumb asset={asset} className="aspect-square w-full" />
                  </button>
                  <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-end gap-1 p-1 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
                    <button
                      onClick={() => dispatch({ type: 'ADD_REFERENCE', asset })}
                      className="pointer-events-auto rounded-md bg-black/60 p-1 text-white backdrop-blur hover:bg-black/80"
                      aria-label={`Use ${asset.title} as reference`}
                      title="Use as reference"
                    >
                      <Paperclip className="size-3.5" />
                    </button>
                    <button
                      onClick={() => dispatch({ type: 'TOGGLE_FAVORITE', id: asset.id })}
                      className="pointer-events-auto rounded-md bg-black/60 p-1 text-white backdrop-blur hover:bg-black/80"
                      aria-label={fav ? `Remove ${asset.title} from favorites` : `Add ${asset.title} to favorites`}
                      aria-pressed={fav}
                    >
                      <Heart className={cn('size-3.5', fav && 'fill-ks-deny text-ks-deny')} />
                    </button>
                  </div>
                  {fav && (
                    <Heart className="absolute bottom-1.5 right-1.5 size-3 fill-ks-deny text-ks-deny group-hover:hidden" aria-hidden="true" />
                  )}
                  <div className="mt-1 truncate text-micro text-ks-ink-3" title={asset.title}>
                    {asset.title}
                  </div>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
