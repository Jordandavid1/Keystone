'use client';

import React from 'react';
import {
  Sparkles,
  Search,
  Grid,
  Maximize2,
  Smartphone,
  Shield,
  Globe,
  Users
} from 'lucide-react';

interface TopBarProps {
  creditBalance: number | null;
  workerOnline: boolean;
  fps: string;
  onOpenCommandPalette: () => void;
  onOpenPersonasModal: () => void;
  onOpenWebScrapeModal: () => void;
  onOpenCredits: () => void;
  onOpenWorkerTelemetry: () => void;
  onOpenAgentChat: () => void;
  onToggleFramingGuides: () => void;
  onToggleFullscreen: () => void;
  onToggleMobilePreview: () => void;
  mobilePreview: boolean;
  guidesVisible: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  creditBalance,
  workerOnline,
  fps,
  onOpenCommandPalette,
  onOpenPersonasModal,
  onOpenWebScrapeModal,
  onOpenCredits,
  onOpenWorkerTelemetry,
  onOpenAgentChat,
  onToggleFramingGuides,
  onToggleFullscreen,
  onToggleMobilePreview,
  mobilePreview,
  guidesVisible,
}) => {
  return (
    <header className="region-topbar" role="banner">
      <div className="brand-cluster">
        <div className="brand-mark" aria-hidden="true">
          <Sparkles size={18} />
        </div>
        <div className="brand-info">
          <span className="brand-title">KEYSTONE</span>
          <span className="brand-edition">STUDIO PRO • NEXT.JS SOVEREIGN UX</span>
        </div>
        <span className="brand-badge">Creative Workspace</span>
      </div>

      <div className="studio-telemetry-hud" aria-label="Studio Master Telemetry">
        <button className="telemetry-pill credit-ledger-pill" title="Studio credit ledger" onClick={onOpenCredits} type="button">
          <span className="credit-icon">⚡</span>
          <span className="telemetry-mono">{creditBalance == null ? 'LOCAL ENGINE' : `${creditBalance.toLocaleString()} CREDITS`}</span>
          <span className="credit-hold-badge">{creditBalance == null ? 'UNBILLED' : 'ACTIVE'}</span>
        </button>

        <button className="telemetry-pill worker-telemetry-pill" title="Colab engine telemetry" onClick={onOpenWorkerTelemetry} type="button">
          <span className="status-online-dot" style={{ background: workerOnline ? 'var(--accent-emerald)' : 'var(--accent-cyan)' }} />
          <span className="telemetry-mono">{workerOnline ? 'ENGINE: CONFIGURED' : 'ENGINE: OFFLINE'}</span>
          <span className="worker-vram-badge">COLAB PRO</span>
        </button>

        <button className="telemetry-pill agent-chat-pill" title="Speak with the Colab llama-server" onClick={onOpenAgentChat} type="button" style={{ borderColor: 'rgba(168, 85, 247, 0.4)', background: 'rgba(168, 85, 247, 0.12)', color: '#c084fc', cursor: 'pointer' }}>
          <span className="status-online-dot" style={{ background: '#c084fc', boxShadow: '0 0 6px #c084fc' }} />
          <span className="telemetry-mono" style={{ fontWeight: 700 }}>LLM AGENT</span>
          <span className="worker-vram-badge" style={{ background: 'rgba(168, 85, 247, 0.3)', color: '#e9d5ff' }}>QWEN</span>
        </button>

        <div className="telemetry-pill">
          <span className="rec-pulse-indicator" />
          <span className="telemetry-mono">DCI-P3 ACEScc</span>
        </div>

        <div className="telemetry-pill">
          <span className="telemetry-dim">FPS</span>
          <span className="telemetry-mono">{fps}</span>
        </div>

        <div className="telemetry-pill">
          <span className="telemetry-dim">COLOR</span>
          <span className="telemetry-mono">10-BIT HDR</span>
        </div>

        <div className="studio-spectrum-meter" title="Playback activity meter">
          <span className="spectrum-bar" style={{ height: workerOnline ? '65%' : '18%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '88%' : '22%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '42%' : '14%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '95%' : '20%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '75%' : '16%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '30%' : '12%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '85%' : '19%' }} />
          <span className="spectrum-bar" style={{ height: workerOnline ? '60%' : '15%' }} />
        </div>
      </div>

      <button className="command-trigger" onClick={onOpenCommandPalette} aria-label="Open Command Palette">
        <Search size={14} />
        <span>Search assets, playbooks, lineage, or commands...</span>
        <kbd className="kbd-pill">⌘K</kbd>
      </button>

      <div className="topbar-actions">
        <button className="icon-btn" title="Character Personas & ElevenLabs Audio Studio" onClick={onOpenPersonasModal}>
          <Users size={15} style={{ color: '#ec4899' }} />
          <span className="btn-label">Personas & Audio</span>
        </button>
        <button className="icon-btn" title="Firecrawl ingest style from URL (@Web)" onClick={onOpenWebScrapeModal}>
          <Globe size={15} style={{ color: 'var(--accent-cyan)' }} />
          <span className="btn-label">@Web Scrape</span>
        </button>
        <button className={`icon-btn ${guidesVisible ? 'active' : ''}`} title="Toggle Framing Guidelines" onClick={onToggleFramingGuides}>
          <Grid size={15} />
          <span className="btn-label">Guides</span>
        </button>
        <button className="icon-btn" title="Toggle Theater / Fullscreen Studio" onClick={onToggleFullscreen}>
          <Maximize2 size={15} />
          <span className="btn-label">Theater</span>
        </button>
        <button className={`icon-btn ${mobilePreview ? 'active' : ''}`} title="Toggle Mobile Preview Mode" onClick={onToggleMobilePreview}>
          <Smartphone size={15} />
          <span className="btn-label">Mobile</span>
        </button>
        <a href="/admin" className="icon-btn operator-link" title="Operator Admin Console">
          <Shield size={15} />
          <span className="btn-label">Operator</span>
        </a>
      </div>
    </header>
  );
};
