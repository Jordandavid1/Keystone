'use client';

import React from 'react';
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Plane, RotateCw, ZoomIn, ZoomOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MotionPreset } from '@/lib/types';

// A d-pad: lateral moves sit where they point; corners stay empty so the cross reads at a glance.
const PAD: ({ id: MotionPreset; label: string; icon: React.ElementType } | null)[] = [
  null,
  { id: 'tilt-up', label: 'Tilt up', icon: ArrowUp },
  null,
  { id: 'pan-left', label: 'Pan left', icon: ArrowLeft },
  { id: 'orbit', label: 'Orbit', icon: RotateCw },
  { id: 'pan-right', label: 'Pan right', icon: ArrowRight },
  null,
  { id: 'tilt-down', label: 'Tilt down', icon: ArrowDown },
  null,
];

// Depth moves travel along the lens axis, so they live on their own row.
const DEPTH: { id: MotionPreset; label: string; icon: React.ElementType }[] = [
  { id: 'zoom-in', label: 'Push in', icon: ZoomIn },
  { id: 'zoom-out', label: 'Pull out', icon: ZoomOut },
  { id: 'drone', label: 'Drone flyover', icon: Plane },
];

/**
 * Tactile camera-motion pad (Higgsfield pattern): directions sit where they point,
 * so choosing a move is spatial rather than reading a list. Arrow keys move between cells.
 */
export function MotionPad({ value, onChange }: { value: MotionPreset; onChange: (v: MotionPreset) => void }) {
  const cells = PAD;
  const move = (from: number, dx: number, dy: number) => {
    let i = from;
    for (let n = 0; n < 9; n += 1) {
      const x = (i % 3) + dx;
      const y = Math.floor(i / 3) + dy;
      if (x < 0 || x > 2 || y < 0 || y > 2) return;
      i = y * 3 + x;
      if (cells[i]) {
        onChange(cells[i]!.id);
        (document.getElementById(`ks-motion-${cells[i]!.id}`) as HTMLButtonElement | null)?.focus();
        return;
      }
    }
  };
  const selected = [...cells, ...DEPTH].find((c) => c?.id === value);

  return (
    <div>
      <div role="radiogroup" aria-label="Camera move" className="grid grid-cols-3 gap-1.5">
        {cells.map((c, idx) =>
          c ? (
            <button
              key={c.id}
              id={`ks-motion-${c.id}`}
              role="radio"
              aria-checked={value === c.id}
              aria-label={c.label}
              tabIndex={value === c.id || (!cells.some((x) => x?.id === value) && c.id === 'orbit') ? 0 : -1}
              onClick={() => onChange(c.id)}
              onKeyDown={(e) => {
                const d: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
                if (d[e.key]) {
                  e.preventDefault();
                  move(idx, d[e.key][0], d[e.key][1]);
                }
              }}
              className={cn(
                'flex aspect-[4/3] items-center justify-center rounded-control bg-ks-abyss/70 text-ks-ink-3 ring-1 ring-inset ring-ks-line transition-all duration-quick hover:text-ks-ink active:scale-95',
                value === c.id && 'bg-ks-lift text-ks-ink ring-ks-line-strong',
              )}
            >
              <c.icon className="size-4" />
            </button>
          ) : (
            <span key={`empty-${idx}`} aria-hidden="true" />
          ),
        )}
      </div>
      <div role="radiogroup" aria-label="Depth move" className="mt-1.5 grid grid-cols-3 gap-1.5">
        {DEPTH.map((c) => (
          <button
            key={c.id}
            role="radio"
            aria-checked={value === c.id}
            onClick={() => onChange(c.id)}
            className={cn(
              'flex h-8 items-center justify-center gap-1.5 rounded-control bg-ks-abyss/70 text-meta text-ks-ink-3 ring-1 ring-inset ring-ks-line transition-all duration-quick hover:text-ks-ink active:scale-95',
              value === c.id && 'bg-ks-lift text-ks-ink ring-ks-line-strong',
            )}
          >
            <c.icon className="size-3.5" />
            <span className="max-[380px]:hidden">{c.label.split(' ')[0] === 'Drone' ? 'Drone' : c.label}</span>
          </button>
        ))}
      </div>
      <p className="mt-2 text-meta text-ks-ink-2">{selected ? selected.label : 'Choose a move'}</p>
    </div>
  );
}
