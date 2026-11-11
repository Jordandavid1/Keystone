import React from 'react';

/** The keystone: the wedge at the crown of an arch that locks the other stones in place. */
export function KeystoneMark({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <defs>
        <linearGradient id="ks-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366F1" />
          <stop offset="1" stopColor="#8B5CF6" />
        </linearGradient>
      </defs>
      <path d="M3.5 4h17l-4.2 16H7.7L3.5 4z" fill="url(#ks-mark)" />
      <path d="M7.7 20l1.1-4.4h6.4l1.1 4.4" fill="rgba(6,7,11,0.35)" />
    </svg>
  );
}
