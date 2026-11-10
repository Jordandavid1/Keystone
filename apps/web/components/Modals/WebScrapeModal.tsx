'use client';

import React, { useState } from 'react';
import { Globe, X } from 'lucide-react';
import { scrapeWebUrl } from '../../lib/api';

export interface WebScrapeResult {
  url: string;
  title: string;
  summary: string;
  styleHint: string;
}

interface WebScrapeModalProps {
  open: boolean;
  onClose: () => void;
  onAttach: (result: WebScrapeResult) => void;
}

export const WebScrapeModal: React.FC<WebScrapeModalProps> = ({ open, onClose, onAttach }) => {
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleScrape = async () => {
    const target = url.trim();
    if (!target) {
      setStatus('Enter a URL to extract style and prompt context.');
      return;
    }
    setBusy(true);
    setStatus('Extracting design tokens and page language from URL...');
    try {
      const extracted = await scrapeWebUrl(target);
      const title = extracted.app_name || extracted.title || target;
      const tokens = extracted.design_tokens ? JSON.stringify(extracted.design_tokens) : '';
      const summary = [
        extracted.inferred_domain ? `Domain: ${extracted.inferred_domain}` : '',
        tokens ? `Design tokens: ${tokens.slice(0, 400)}` : '',
        extracted.quarantined_content ? String(extracted.quarantined_content).slice(0, 500) : '',
      ].filter(Boolean).join('\n');
      const styleHint = `[Style Reference: ${title} | ${target}]`;
      onAttach({ url: target, title, summary, styleHint });
      setStatus(`Extracted style context from ${title}. Attached to your next job — it will not auto-run.`);
      setTimeout(() => {
        onClose();
        setStatus(null);
        setBusy(false);
      }, 700);
    } catch (err: any) {
      setStatus(err?.message || 'Web extract failed.');
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Web style extract">
      <div className="command-modal" style={{ width: 'min(640px, 94vw)' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Globe size={16} color="var(--accent-cyan)" />
            <strong>@Web Style & Prompt Extract</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close">
            <X size={14} />
          </button>
        </div>
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Paste a URL. Extracted style and language are attached as context for whatever job you run next. This does not fire a canned generation.
          </p>
          <input
            className="command-input"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/look-and-feel"
            aria-label="URL to extract"
          />
          {status && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{status}</div>}
          <button className="composer-submit-btn" onClick={handleScrape} disabled={busy}>
            {busy ? 'Extracting...' : 'Extract & Attach Context'}
          </button>
        </div>
      </div>
    </div>
  );
};
