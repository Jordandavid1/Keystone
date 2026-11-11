'use client';

import React, { useEffect, useState } from 'react';
import { Settings, X } from 'lucide-react';
import {
  fetchAudioConfig,
  fetchCognitionStatus,
  fetchEngineStatus,
} from '../../lib/api';
import { AccountSettings } from '../auth/AccountSettings';

const FLAGS_KEY = 'keystone.studio.flags';

type SettingsTab = 'config' | 'engine' | 'security';

interface StudioFlags {
  nodes: boolean;
  composer: boolean;
  activityBar: boolean;
  motion: boolean;
  scrape: boolean;
  framerate: number;
}

const DEFAULT_FLAGS: StudioFlags = {
  nodes: true,
  composer: true,
  activityBar: true,
  motion: true,
  scrape: true,
  framerate: 24,
};

function loadFlags(): StudioFlags {
  try {
    const raw = localStorage.getItem(FLAGS_KEY);
    if (!raw) return { ...DEFAULT_FLAGS };
    return { ...DEFAULT_FLAGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_FLAGS };
  }
}

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  onFlagsSaved?: (flags: StudioFlags) => void;
  /** Open straight on the account tab (sign-in, API key, dev bypass). */
  initialTab?: 'account' | null;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose, onFlagsSaved, initialTab }) => {
  const [tab, setTab] = useState<SettingsTab>('config');
  const [flags, setFlags] = useState<StudioFlags>(DEFAULT_FLAGS);
  const [saveNote, setSaveNote] = useState<string | null>(null);
  const [engine, setEngine] = useState<any>(null);
  const [cognition, setCognition] = useState<any>(null);
  const [audio, setAudio] = useState<any>(null);
  const [engineError, setEngineError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (initialTab === 'account') setTab('security');
    setFlags(loadFlags());
    setSaveNote(null);
    setEngineError(null);
    fetchEngineStatus()
      .then(setEngine)
      .catch((err: any) => setEngineError(err?.message || 'Could not reach Colab engine status.'));
    fetchCognitionStatus()
      .then(setCognition)
      .catch((err: any) => setEngineError((prev) => prev || err?.message || 'Could not reach cognition status.'));
    fetchAudioConfig()
      .then(setAudio)
      .catch(() => setAudio(null));
  }, [open, initialTab]);

  if (!open) return null;

  const saveFlags = () => {
    localStorage.setItem(FLAGS_KEY, JSON.stringify(flags));
    onFlagsSaved?.(flags);
    setSaveNote('Workspace flags saved locally. They change studio chrome only — they do not invent engine state.');
  };

  const llmOnline = Boolean(cognition?.online || engine?.llm?.configured);
  const comfyOnline = Boolean(engine?.comfy?.configured || cognition?.comfy_configured);

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Studio Settings">
      <div className="command-modal" style={{ width: 'min(760px, 96vw)', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Settings size={16} color="var(--accent-cyan)" />
            <strong>KEYSTONE Studio Configuration & Authority</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
        </div>
        <div className="modal-nav-tabs">
          <button className={`modal-nav-tab ${tab === 'config' ? 'active' : ''}`} onClick={() => setTab('config')}>Remote Config & Flags</button>
          <button className={`modal-nav-tab ${tab === 'engine' ? 'active' : ''}`} onClick={() => setTab('engine')}>Engine & Infrastructure</button>
          <button className={`modal-nav-tab ${tab === 'security' ? 'active' : ''}`} onClick={() => setTab('security')}>Account & API keys</button>
        </div>

        {tab === 'config' && (
          <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1 }}>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginBottom: 14 }}>
              These flags are stored in this browser. They toggle workspace chrome; they do not fabricate engine, credit, or generation results.
            </div>
            {([
              ['nodes', 'ZenCreator Visual Node Graph', 'Enable pipeline/DAG visualization and execution graphs'],
              ['composer', 'Cursor Floating Composer & @Context', 'Interactive floating prompt composer with web ingestion pills'],
              ['activityBar', 'VS Code 48px Pro Activity Bar', 'Ultra-sleek navigation icon rail with hotkey switching'],
              ['motion', 'Higgsfield Cinema Camera Motion Splines', 'Motion HUD, orbit, pan, and tilt presets'],
              ['scrape', 'Firecrawl Single-Page Style Extraction (@Web)', 'Extract colors, typography, and layout prompts from live URLs'],
            ] as const).map(([key, title, desc]) => (
              <div className="settings-row" key={key}>
                <div className="settings-info">
                  <span className="settings-title">{title}</span>
                  <span className="settings-desc">{desc}</span>
                </div>
                <label className="switch-toggle">
                  <input type="checkbox" checked={Boolean(flags[key])} onChange={(e) => setFlags((prev) => ({ ...prev, [key]: e.target.checked }))} />
                  <span className="switch-slider" />
                </label>
              </div>
            ))}
            <div className="settings-row">
              <div className="settings-info">
                <span className="settings-title">Master Cinema Timeline Framerate</span>
                <span className="settings-desc">Base SMPTE timecode cadence</span>
              </div>
              <select
                className="command-input"
                style={{ width: 110, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
                value={flags.framerate}
                onChange={(e) => setFlags((prev) => ({ ...prev, framerate: Number(e.target.value) }))}
              >
                <option value={24}>24.000 fps</option>
                <option value={30}>30.000 fps</option>
                <option value={60}>60.000 fps</option>
              </select>
            </div>
            {saveNote && <div style={{ marginTop: 12, fontSize: 12, color: '#86efac' }}>{saveNote}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
              <button className="composer-submit-btn" onClick={saveFlags}>Apply & Save Configuration</button>
            </div>
          </div>
        )}

        {tab === 'engine' && (
          <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
            {engineError && (
              <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{engineError}</div>
            )}
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700 }}>Cognition Checkpoint & OpenAI-compatible Tunnel</span>
                <span className="telemetry-pill" style={{ borderColor: llmOnline ? 'rgba(52,211,153,0.4)' : 'rgba(148,163,184,0.4)', color: llmOnline ? '#34d399' : '#94a3b8' }}>
                  {llmOnline ? 'CONFIGURED' : 'OFFLINE'}
                </span>
              </div>
              <div style={{ fontSize: 11.5, fontFamily: 'var(--font-mono)', color: '#38bdf8', marginBottom: 4 }}>
                {cognition?.served_model || cognition?.model || engine?.llm?.model || 'No served model reported'}
              </div>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
                Endpoint present: {engine?.llm?.endpoint_present ? 'yes' : 'no'} · Latency: {cognition?.cognition_latency_ms != null ? `${cognition.cognition_latency_ms} ms` : 'n/a'}
              </div>
              {cognition?.cognition_detail && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>{String(cognition.cognition_detail)}</div>
              )}
            </div>
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700 }}>ComfyUI Creative Execution Engine</span>
                <span className="telemetry-pill" style={{ borderColor: comfyOnline ? 'rgba(56,189,248,0.4)' : 'rgba(148,163,184,0.4)', color: comfyOnline ? '#38bdf8' : '#94a3b8' }}>
                  {comfyOnline ? 'CONFIGURED' : 'OFFLINE'}
                </span>
              </div>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                {engine?.comfy ? JSON.stringify(engine.comfy) : (cognition?.comfy_endpoint || 'No ComfyUI status reported')}
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>ElevenLabs Voice Synthesis Engine</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                {audio
                  ? `Provider: ${audio.provider || 'unknown'} · Configured: ${audio.configured ? 'yes' : 'no'} · Voices listed: ${audio.voice_count ?? 0}`
                  : 'ElevenLabs status could not be loaded.'}
              </div>
            </div>
          </div>
        )}

        {tab === 'security' && (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            <AccountSettings />
          </div>
        )}
      </div>
    </div>
  );
};
