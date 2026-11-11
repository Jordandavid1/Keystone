'use client';

import React from 'react';
import { Button, ButtonProps } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface IconButtonProps extends Omit<ButtonProps, 'children'> {
  label: string;
  shortcut?: string;
  active?: boolean;
  side?: 'top' | 'right' | 'bottom' | 'left';
  children: React.ReactNode;
}

/** Icon-only button with an accessible name and a tooltip that names the action (and its shortcut). */
export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ label, shortcut, active, side = 'bottom', className, variant = 'ghost', size = 'icon-sm', children, ...props }, ref) => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          ref={ref}
          variant={variant}
          size={size}
          aria-label={label}
          aria-pressed={active === undefined ? undefined : active}
          className={cn(active && 'bg-ks-lift text-ks-ink', className)}
          {...props}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent side={side}>
        <span>{label}</span>
        {shortcut ? <span className="ml-2 text-ks-ink-3">{shortcut}</span> : null}
      </TooltipContent>
    </Tooltip>
  ),
);
IconButton.displayName = 'IconButton';
