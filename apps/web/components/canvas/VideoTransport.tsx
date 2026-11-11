'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pause, Play, Repeat, SkipBack, SkipForward } from 'lucide-react';
import { cn } from '@/lib/utils';
import { IconButton } from '../studio/IconButton';

function timecode(t: number, fps: number): string {
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const f = Math.floor((t % 1) * fps);
  return [h, m, s, f].map((n) => String(n).padStart(2, '0')).join(':');
}

/**
 * Cinema transport for one or more synchronized <video> elements (the first is the master).
 * Keys (when focus isn't in a field): Space/K play, J/L shuttle ±1s, ←/→ step one frame, R loop.
 */
export function VideoTransport({ videos, fps }: { videos: React.RefObject<HTMLVideoElement>[]; fps: number }) {
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [loop, setLoop] = useState(true);
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const all = useCallback(() => videos.map((v) => v.current).filter(Boolean) as HTMLVideoElement[], [videos]);
  const master = useCallback(() => videos[0]?.current || null, [videos]);

  useEffect(() => {
    const m = master();
    if (!m) return;
    const onTime = () => {
      setTime(m.currentTime);
      // Keep followers within 50ms of the master (synchronized compare, Bible §25).
      all()
        .slice(1)
        .forEach((v) => {
          if (Math.abs(v.currentTime - m.currentTime) > 0.05) v.currentTime = m.currentTime;
        });
    };
    const onMeta = () => setDuration(m.duration || 0);
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    m.addEventListener('timeupdate', onTime);
    m.addEventListener('loadedmetadata', onMeta);
    m.addEventListener('play', onPlay);
    m.addEventListener('pause', onPause);
    if (m.readyState >= 1) onMeta();
    return () => {
      m.removeEventListener('timeupdate', onTime);
      m.removeEventListener('loadedmetadata', onMeta);
      m.removeEventListener('play', onPlay);
      m.removeEventListener('pause', onPause);
    };
  }, [all, master]);

  useEffect(() => {
    all().forEach((v) => (v.loop = loop));
  }, [all, loop]);

  const toggle = useCallback(() => {
    const m = master();
    if (!m) return;
    if (m.paused) all().forEach((v) => void v.play().catch(() => undefined));
    else all().forEach((v) => v.pause());
  }, [all, master]);

  const seek = useCallback(
    (t: number) => {
      const m = master();
      if (!m) return;
      const clamped = Math.max(0, Math.min(m.duration || 0, t));
      all().forEach((v) => (v.currentTime = clamped));
      setTime(clamped);
    },
    [all, master],
  );

  const step = useCallback((frames: number) => seek((master()?.currentTime || 0) + frames / fps), [fps, master, seek]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'].includes(el.tagName))) return;
      const k = e.key.toLowerCase();
      if (k === ' ' || k === 'k') {
        e.preventDefault();
        toggle();
      } else if (k === 'j') seek((master()?.currentTime || 0) - 1);
      else if (k === 'l') seek((master()?.currentTime || 0) + 1);
      else if (e.key === 'ArrowLeft') step(-1);
      else if (e.key === 'ArrowRight') step(1);
      else if (k === 'r') setLoop((v) => !v);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [master, seek, step, toggle]);

  const seekFromPointer = (clientX: number) => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || !duration) return;
    seek(((clientX - rect.left) / rect.width) * duration);
  };

  const pct = duration ? (time / duration) * 100 : 0;

  return (
    <div className="ks-glass flex w-full max-w-[760px] items-center gap-3 rounded-panel px-3 py-2 shadow-float" role="group" aria-label="Playback">
      <span className="ks-num shrink-0 font-mono text-meta text-ks-ink">{timecode(time, fps)}</span>
      <div className="flex items-center">
        <IconButton label="Previous frame" shortcut="←" onClick={() => step(-1)} side="top">
          <SkipBack />
        </IconButton>
        <IconButton label={playing ? 'Pause' : 'Play'} shortcut="Space" onClick={toggle} side="top" className="text-ks-ink">
          {playing ? <Pause /> : <Play />}
        </IconButton>
        <IconButton label="Next frame" shortcut="→" onClick={() => step(1)} side="top">
          <SkipForward />
        </IconButton>
        <IconButton label={loop ? 'Loop on' : 'Loop off'} shortcut="R" active={loop} onClick={() => setLoop((v) => !v)} side="top">
          <Repeat />
        </IconButton>
      </div>
      <div
        ref={trackRef}
        role="slider"
        aria-label="Playhead"
        aria-valuemin={0}
        aria-valuemax={Math.round(duration * 100) / 100}
        aria-valuenow={Math.round(time * 100) / 100}
        aria-valuetext={timecode(time, fps)}
        tabIndex={0}
        className="relative h-7 flex-1 cursor-pointer touch-none"
        onPointerDown={(e) => {
          dragging.current = true;
          (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
          seekFromPointer(e.clientX);
        }}
        onPointerMove={(e) => dragging.current && seekFromPointer(e.clientX)}
        onPointerUp={() => (dragging.current = false)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') {
            e.preventDefault();
            e.stopPropagation();
            step(e.shiftKey ? -fps : -1);
          } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            e.stopPropagation();
            step(e.shiftKey ? fps : 1);
          }
        }}
      >
        <div className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-white/10" />
        <div className="absolute left-0 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-ks-ink-2" style={{ width: `${pct}%` }} />
        <div
          className={cn('absolute top-1/2 h-4 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-ks-ink shadow')}
          style={{ left: `${pct}%` }}
        />
      </div>
      <span className="ks-num shrink-0 font-mono text-meta text-ks-ink-3">{timecode(duration, fps)}</span>
    </div>
  );
}
