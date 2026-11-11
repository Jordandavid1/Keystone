'use client';

import React from 'react';
import {
  Check,
  ChevronDown,
  Code2,
  FolderPlus,
  Globe,
  MessageSquare,
  MoreHorizontal,
  Search,
  Settings,
  Shield,
  Users,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { Modal, useStudio } from '@/lib/studio/store';
import { KeystoneMark } from './studio/KeystoneMark';
import { IconButton } from './studio/IconButton';
import { AccountMenu } from './auth/AccountMenu';

/** Region 1 — product + project identity, command palette, engine and credit truth (Bible §25). */
export function TopBar() {
  const { state, dispatch } = useStudio();
  const { engine, engineError, ledger, projects, projectId, projectsError, session } = state.system;
  const project = projects.find((p) => p.id === projectId) || null;

  const engineTone = engineError ? 'deny' : engine?.online ? 'verified' : 'hold';
  const engineLabel = engineError ? 'Studio API unreachable' : engine?.online ? 'Engine ready' : engine ? 'Engine offline' : 'Checking engine';

  const billingOff = ledger && ledger.balance == null;
  const open = (modal: Modal) => dispatch({ type: 'OPEN_MODAL', modal });

  return (
    <header
      role="banner"
      className="ks-region flex h-topbar items-center gap-3 border-b border-ks-line px-3 [grid-area:topbar]"
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <KeystoneMark />
        <span className="text-[15px] font-semibold tracking-[0.04em] text-ks-ink">KEYSTONE</span>
        <span className="hidden text-ks-ink-3 md:inline" aria-hidden="true">/</span>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="hidden min-w-0 items-center gap-1.5 rounded-control px-2 py-1 text-body text-ks-ink-2 transition-colors hover:bg-ks-lift hover:text-ks-ink md:flex"
              aria-label="Switch project"
            >
              <span className="max-w-[180px] truncate">{project ? project.name : 'All assets'}</span>
              <ChevronDown className="size-3.5 opacity-70" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel className="text-meta font-medium text-ks-ink-3">Projects</DropdownMenuLabel>
            <DropdownMenuItem onSelect={() => dispatch({ type: 'SYSTEM', patch: { projectId: null } })}>
              <span className="flex-1">All assets</span>
              {!projectId && <Check className="size-3.5" />}
            </DropdownMenuItem>
            {session.status !== 'signed_in' && (
              <DropdownMenuLabel className="text-meta font-normal text-ks-ink-3">Sign in to see your projects.</DropdownMenuLabel>
            )}
            {projectsError && (
              <DropdownMenuLabel className="text-meta font-normal text-ks-deny">Projects didn't load: {projectsError}</DropdownMenuLabel>
            )}
            {projects.map((p) => (
              <DropdownMenuItem key={p.id} onSelect={() => dispatch({ type: 'SYSTEM', patch: { projectId: p.id } })}>
                <span className="flex-1 truncate">{p.name}</span>
                {projectId === p.id && <Check className="size-3.5" />}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => open('projects')}>
              <FolderPlus className="size-3.5" /> Manage projects
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex flex-1 justify-center">
        <button
          onClick={() => open('command')}
          className="group flex h-9 w-full max-w-[440px] items-center gap-2.5 rounded-control border border-ks-line bg-ks-raised/60 px-3 text-left text-body text-ks-ink-3 transition-colors hover:border-ks-line-strong hover:text-ks-ink-2 max-md:w-9 max-md:justify-center max-md:px-0"
          aria-label="Search assets, playbooks and commands"
        >
          <Search className="size-4 shrink-0" />
          <span className="flex-1 truncate max-md:hidden">Search assets, playbooks and commands</span>
          <kbd className="rounded border border-ks-line-strong px-1.5 py-px text-micro text-ks-ink-3 max-md:hidden">⌘K</kbd>
        </button>
      </div>

      <div className="flex items-center gap-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => open('worker')}
              className="flex h-8 items-center gap-2 rounded-control px-2.5 text-meta text-ks-ink-2 transition-colors hover:bg-ks-lift hover:text-ks-ink"
            >
              <span
                className={cn(
                  'size-2 rounded-full',
                  engineTone === 'verified' && 'bg-ks-verified',
                  engineTone === 'hold' && 'bg-ks-hold',
                  engineTone === 'deny' && 'bg-ks-deny',
                )}
                aria-hidden="true"
              />
              <span className="max-sm:hidden">{engineLabel}</span>
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-[280px]">
            {engineError ? (
              <span>{engineError}</span>
            ) : engine ? (
              <div className="space-y-1">
                <div>Cognition: {engine.llm?.configured ? engine.llm?.model || 'connected' : 'not connected'}</div>
                <div>Media engine: {engine.comfy?.configured ? 'connected' : 'not connected'}</div>
              </div>
            ) : (
              <span>Asking the studio API for engine status.</span>
            )}
          </TooltipContent>
        </Tooltip>

        <button
          onClick={() => open('credits')}
          className="flex h-8 items-center gap-2 rounded-control px-2.5 text-meta text-ks-ink-2 transition-colors hover:bg-ks-lift hover:text-ks-ink"
          aria-label="Credits"
        >
          {ledger == null ? (
            <span>Credits unavailable</span>
          ) : billingOff ? (
            <span>Billing off</span>
          ) : (
            <>
              <span className="ks-num text-ks-ink">{(ledger.balance as number).toLocaleString()}</span>
              <span className="max-sm:hidden">credits</span>
              {ledger.hold ? <span className="ks-num text-ks-hold">{ledger.hold} held</span> : null}
            </>
          )}
        </button>

        <IconButton label="Talk to KEYSTONE" onClick={() => open('agent')} className="max-sm:hidden">
          <MessageSquare />
        </IconButton>

        <AccountMenu />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="More">
              <MoreHorizontal />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuItem onSelect={() => open('personas')}>
              <Users className="size-3.5" /> Personas and voices
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => open('web')}>
              <Globe className="size-3.5" /> Add web reference
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => open('settings')}>
              <Settings className="size-3.5" /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => dispatch({ type: 'TOGGLE_DEVELOPER' })}>
              <Code2 className="size-3.5" />
              <span className="flex-1">Developer mode</span>
              {state.ui.developer && <Check className="size-3.5" />}
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <a href="/admin">
                <Shield className="size-3.5" /> Operator console
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
