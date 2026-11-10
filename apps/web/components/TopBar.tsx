'use client';

import React from 'react';
import {
  Sparkles,
  Search,
  Grid,
  Maximize2,
  Smartphone,
  Shield,
  Layers,
  Globe,
  Users
} from 'lucide-react';

interface TopBarProps {
  creditBalance: number;
  workerOnline: boolean;
  onOpenCommandPalette: () => void;
  onOpenPersonasModal: () => void;
  onOpenWebScrapeModal: () => void;
  onToggleFramingGuides: () => void;
  onToggleFullscreen: () => void;
  onToggleMobilePreview: () => void;
  mobilePreview: boolean;
  guidesVisible: boolean;
}

export const TopBar: React.FC<TopBarProps> = ({
  creditBalance,
  workerOnline,
  onOpenCommandPalette,
  onOpenPersonasModal,
  onOpenWebScrapeModal,
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

      {/* Studio Master Telemetry & ZenCreator Credit Ledger */}
      <div className="studio-telemetry-hud" aria-label="Studio Master Telemetry">
        <div className="telemetry-pill credit-ledger-pill" title="ZenCreator 2-Phase Credit Ledger">
          <span className="credit-icon">⚡</span>
          <span className="telemetry-mono">{creditBalance.toLocaleString()} CREDITS</span>
          <span className="credit-hold-badge">ACTIVE</span>
        </div>

        <div className="telemetry-pill worker-telemetry-pill" title="Kaggle Worker Bridge (T4×2 Cognition & ComfyUI)">
          <span
            className="status-online-dot"
            style={{ background: workerOnline ? 'var(--accent-emerald)' : 'var(--accent-cyan)' }}
          />
          <span className="telemetry-mono">{workerOnline ? 'BRIDGE: ONLINE' : 'ENGINE: READY'}</span>
          <span className="worker-vram-badge">T4×2 / PROXY</span>
        </div>

        <div className="telemetry-pill">
          <span className="rec-pulse-indicator" />
          <span className="telemetry-mono">DCI-P3 ACEScc</span>
        </div>

        <div className="telemetry-pill">
          <span className="telemetry-dim">FPS</span>
          <span className="telemetry-mono">24.000</span>
        </div>

        {/* Master Audio Spectrum Meter */}
        <div className="studio-spectrum-meter" title="Master Audio & Luma Dynamic Spectrum">
          <span className="spectrum-bar" style={{ height: '65%' }} />
          <span className="spectrum-bar" style={{ height: '88%' }} />
          <span className="spectrum-bar" style={{ height: '42%' }} />
          <span className="spectrum-bar" style={{ height: '95%' }} />
          <span className="spectrum-bar" style={{ height: '75%' }} />
          <span className="spectrum-bar" style={{ height: '30%' }} />
          <span className="spectrum-bar" style={{ height: '85%' }} />
          <span className="spectrum-bar" style={{ height: '60%' }} />
        </div>
      </div>

      {/* Quick Command Trigger (⌘K) */}
      <button className="command-trigger" onClick={onOpenCommandPalette} aria-label="Open Command Palette">
        <Search size={14} />
        <span>Search all 17 tools, playbooks, or commands...</span>
        <kbd className="kbd-pill">⌘K</kbd>
      </button>

      <div className="topbar-actions">
        {/* Personas & Voices */}
        <button
          className="icon-btn"
          title="Digital Personas & Voices"
          onClick={onOpenPersonasModal}
        >
          <Users size={15} style={{ color: '#ec4899' }} />
          <span className="btn-label">Personas</span>
        </button>

        {/* Firecrawl Web Scrape */}
        <button
          className="icon-btn"
          title="Firecrawl Ingest Style from URL (@Web)"
          onClick={onOpenWebScrapeModal}
        >
          <Globe size={15} style={{ color: 'var(--accent-cyan)' }} />
          <span className="btn-label">@Web</span>
        </button>

        {/* Framing Guides */}
        <button
          className={`icon-btn ${guidesVisible ? 'active' : ''}`}
          title="Toggle Framing Guidelines & Rule of Thirds"
          onClick={onToggleFramingGuides}
        >
          <Grid size={15} />
          <span className="btn-label">Guides</span>
        </button>

        {/* Fullscreen / Theater */}
        <button
          className="icon-btn"
          title="Toggle Theater / Fullscreen Studio"
          onClick={onToggleFullscreen}
        >
          <Maximize2 size={15} />
          <span className="btn-label">Theater</span>
        </button>

        {/* Mobile Preview */}
        <button
          className={`icon-btn ${mobilePreview ? 'active' : ''}`}
          title="Toggle Mobile Preview Mode"
          onClick={onToggleMobilePreview}
        >
          <Smartphone size={15} />
          <span className="btn-label">Mobile</span>
        </button>

        {/* Operator Link */}
        <a href="/admin" className="icon-btn operator-link" title="Operator Admin Console">
          <Shield size={15} />
          <span className="btn-label">Operator</span>
        </a>
      </div>
    </header>
  );
};
