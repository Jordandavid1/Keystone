'use client';

import React, { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

/** Progressive-disclosure section: flush, hairline-divided, no card chrome. */
export function Section({
  title,
  hint,
  defaultOpen = true,
  children,
}: {
  title: string;
  hint?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="border-b border-ks-line">
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-white/[0.02]">
        <ChevronRight className={cn('size-3.5 text-ks-ink-3 transition-transform duration-base', open && 'rotate-90')} />
        <span className="text-body font-semibold text-ks-ink">{title}</span>
        {hint && <span className="ml-auto truncate text-meta text-ks-ink-3">{hint}</span>}
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4">{children}</CollapsibleContent>
    </Collapsible>
  );
}

export function Field({ label, value, children }: { label: string; value?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mt-3 first:mt-0">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-meta font-medium text-ks-ink-2">{label}</span>
        {value != null && <span className="ks-num text-meta text-ks-ink-3">{value}</span>}
      </div>
      {children}
    </div>
  );
}

export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
  columns,
}: {
  options: { id: T; label: string; hint?: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  columns?: number;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="grid gap-1 rounded-control bg-ks-abyss/60 p-0.5 ring-1 ring-inset ring-ks-line"
      style={{ gridTemplateColumns: `repeat(${columns || options.length}, minmax(0, 1fr))` }}
    >
      {options.map((o) => (
        <button
          key={String(o.id)}
          role="radio"
          aria-checked={value === o.id}
          title={o.hint}
          onClick={() => onChange(o.id)}
          className={cn(
            'h-7 rounded-[6px] px-1.5 text-meta font-medium transition-colors duration-quick',
            value === o.id ? 'bg-ks-lift text-ks-ink shadow-sm' : 'text-ks-ink-3 hover:text-ks-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
