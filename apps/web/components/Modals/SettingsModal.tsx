'use client';

import React, { useEffect, useState } from 'react';
import { Settings, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import {
  fetchAccount,
  fetchAudioConfig,
  fetchCognitionStatus,
  fetchEngineStatus,
  updateContentMode,
  verifyAccountAge,
} from '../../lib/api';
import { readableError } from '../../lib/errors';
import { useStudio } from '../../lib/studio/store';
import { ContentMode, EvalBudget, OutputFormatPref, QualityTier, StudioPreferences } from '../../lib/types';
import { AccountSettings } from '../auth/AccountSettings';

type SettingsTab = 'config' | 'engine' | 'security';

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  /** Open straight on the account or content tab. */
  initialTab?: 'account' | 'content' | null;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose, initialTab }) => {
  const { state, dispatch } = useStudio();
  const { projectId, sessionId, ageVerified, contentMode, preferences } = state.system;

  const [tab, setTab] = useState<SettingsTab>('config');
  const [draftPrefs, setDraftPrefs] = useState<StudioPreferences>(preferences);
  const [seedInput, setSeedInput] = useState<string>(preferences.defaultSeed != null ? String(preferences.defaultSeed) : '');
  const [modeScope, setModeScope] = useState<'user' | 'project' | 'session'>('user');
  const [selectedMode, setSelectedMode] = useState<ContentMode>(contentMode);
  const [ageModalOpen, setAgeModalOpen] = useState(false);
  const [adultConfirmed, setAdultConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saveNote, setSaveNote] = useState<string | null>(null);
  const [errorNote, setErrorNote] = useState<string | null>(null);
  const [engine, setEngine] = useState<any>(null);
  const [cognition, setCognition] = useState<any>(null);
  const [audio, setAudio] = useState<any>(null);
  const [engineError, setEngineError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (initialTab === 'account') setTab('security');
    else if (initialTab === 'content') setTab('config');

    setDraftPrefs(preferences);
    setSeedInput(preferences.defaultSeed != null ? String(preferences.defaultSeed) : '');
    setSelectedMode(contentMode);
    setSaveNote(null);
    setErrorNote(null);
    setAgeModalOpen(false);
    setAdultConfirmed(false);
    setEngineError(null);

    fetchAccount()
      .then((acct) => {
        dispatch({
          type: 'SYSTEM',
          patch: {
            account: acct,
            ageVerified: Boolean(acct.age_verified),
            contentMode: acct.age_verified && acct.content_mode === 'unrestricted' ? 'unrestricted' : 'sfw',
          },
        });
        setSelectedMode(acct.age_verified && acct.content_mode === 'unrestricted' ? 'unrestricted' : 'sfw');
      })
      .catch(() => undefined);

    fetchEngineStatus()
      .then(setEngine)
      .catch((err: any) => setEngineError(err?.message || 'Could not reach engine status.'));
    fetchCognitionStatus()
      .then(setCognition)
      .catch((err: any) => setEngineError((prev) => prev || err?.message || 'Could not reach cognition status.'));
    fetchAudioConfig()
      .then(setAudio)
      .catch(() => setAudio(null));
  }, [open, initialTab, contentMode, dispatch, preferences]);

  if (!open) return null;

  const applyContentModeChange = async (nextMode: ContentMode) => {
    if (nextMode === 'unrestricted' && !ageVerified) {
      setAgeModalOpen(true);
      return;
    }
    setBusy(true);
    setErrorNote(null);
    setSaveNote(null);
    try {
      await updateContentMode({
        content_mode: nextMode,
        project_id: modeScope === 'project' ? projectId : null,
        session_id: modeScope === 'session' ? sessionId : null,
      });
      setSelectedMode(nextMode);
      dispatch({ type: 'SET_CONTENT_MODE', contentMode: nextMode });
      setSaveNote(`Content mode updated to ${nextMode.toUpperCase()} (${modeScope} scope).`);
    } catch (err) {
      setErrorNote(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmAgeAndUnlock = async () => {
    if (!adultConfirmed) {
      setErrorNote('Please confirm that you are 18+ to unlock Unrestricted mode.');
      return;
    }
    setBusy(true);
    setErrorNote(null);
    setSaveNote(null);
    try {
      await verifyAccountAge(true, 'attestation');
      await updateContentMode({
        content_mode: 'unrestricted',
        project_id: modeScope === 'project' ? projectId : null,
        session_id: modeScope === 'session' ? sessionId : null,
      });
      setAgeModalOpen(false);
      setSelectedMode('unrestricted');
      dispatch({ type: 'SET_CONTENT_MODE', contentMode: 'unrestricted', ageVerified: true });
      setSaveNote('Stage-1 18+ age verification recorded and Unrestricted content mode enabled.');
    } catch (err) {
      setErrorNote(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSavePreferences = async () => {
    setBusy(true);
    setErrorNote(null);
    setSaveNote(null);
    const parsedSeed = seedInput.trim() === '' ? null : Number(seedInput.trim());
    if (parsedSeed != null && (!Number.isInteger(parsedSeed) || parsedSeed < 0)) {
      setErrorNote('Default seed must be a non-negative integer or blank for random.');
      setBusy(false);
      return;
    }
    try {
      if (selectedMode !== contentMode) {
        if (selectedMode === 'unrestricted' && !ageVerified) {
          setAgeModalOpen(true);
          setBusy(false);
          return;
        }
        await updateContentMode({
          content_mode: selectedMode,
          project_id: modeScope === 'project' ? projectId : null,
          session_id: modeScope === 'session' ? sessionId : null,
        });
        dispatch({ type: 'SET_CONTENT_MODE', contentMode: selectedMode });
      }
      const nextPrefs: StudioPreferences = {
        ...draftPrefs,
        defaultContentMode: selectedMode,
        defaultSeed: parsedSeed,
      };
      dispatch({ type: 'SET_PREFERENCES', patch: nextPrefs });
      setSaveNote('Studio preferences applied and attached to generation requests.');
    } catch (err) {
      setErrorNote(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  const llmOnline = Boolean(cognition?.online || engine?.llm?.configured);
  const comfyOnline = Boolean(engine?.comfy?.configured || cognition?.comfy_configured);

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Studio Settings">
      <div className="command-modal" style={{ width: 'min(760px, 96vw)', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Settings size={16} color="var(--accent-cyan)" />
            <strong>KEYSTONE Studio Preferences &amp; Content Mode</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-nav-tabs">
          <button className={`modal-nav-tab ${tab === 'config' ? 'active' : ''}`} onClick={() => setTab('config')}>
            Workspace &amp; Content Mode
          </button>
          <button className={`modal-nav-tab ${tab === 'engine' ? 'active' : ''}`} onClick={() => setTab('engine')}>
            Engine &amp; Infrastructure
          </button>
          <button className={`modal-nav-tab ${tab === 'security' ? 'active' : ''}`} onClick={() => setTab('security')}>
            Account &amp; API keys
          </button>
        </div>

        {tab === 'config' && (
          <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
            {/* 1. Content Mode Toggle & Stage-1 18+ Age Gate */}
            <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, background: 'rgba(255,255,255,0.02)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <div>
                  <div className="settings-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {selectedMode === 'unrestricted' ? <ShieldAlert size={14} color="#f59e0b" /> : <ShieldCheck size={14} color="#10b981" />}
                    <span>Default Content Mode (SFW | Unrestricted)</span>
                  </div>
                  <div className="settings-desc">
                    Enforced at the backend Gate. Age status: {ageVerified ? 'Verified 18+' : 'Unverified (SFW locked)'}.
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <select
                    aria-label="Content mode scope"
                    className="command-input"
                    value={modeScope}
                    onChange={(e) => setModeScope(e.target.value as 'user' | 'project' | 'session')}
                    style={{ width: 110, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
                  >
                    <option value="user">Account</option>
                    {projectId && <option value="project">Project</option>}
                    {sessionId && <option value="session">Session</option>}
                  </select>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void applyContentModeChange('sfw')}
                    className="icon-btn"
                    style={selectedMode === 'sfw' ? { borderColor: '#10b981', color: '#34d399' } : undefined}
                  >
                    SFW
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void applyContentModeChange('unrestricted')}
                    className="icon-btn"
                    style={selectedMode === 'unrestricted' ? { borderColor: '#f59e0b', color: '#fbbf24' } : undefined}
                  >
                    Unrestricted (18+)
                  </button>
                </div>
              </div>

              {ageModalOpen && (
                <div role="dialog" aria-label="18+ Age Verification" style={{ marginTop: 12, padding: 12, borderRadius: 8, border: '1px solid rgba(245,158,11,0.45)', background: 'rgba(245,158,11,0.08)' }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, color: '#fbbf24', marginBottom: 6 }}>
                    Stage-1 18+ Age Verification Required
                  </div>
                  <p style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Unrestricted mode permits adult creative work subject to the non-configurable lawful-content floor. Attestation is audited on your account.
                  </p>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, marginBottom: 10, cursor: 'pointer' }}>
                    <input type="checkbox" checked={adultConfirmed} onChange={(e) => setAdultConfirmed(e.target.checked)} />
                    <span>I confirm that I am at least 18 years of age (legal adult).</span>
                  </label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" className="composer-submit-btn" disabled={busy || !adultConfirmed} onClick={() => void handleConfirmAgeAndUnlock()}>
                      {busy ? 'Verifying...' : 'Confirm 18+ & Enable Unrestricted'}
                    </button>
                    <button type="button" className="icon-btn" onClick={() => setAgeModalOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* 2. Default Quality Tier */}
            <div className="settings-row">
              <div className="settings-info">
                <span className="settings-title">Default Quality Tier</span>
                <span className="settings-desc">Controls resolution tier (Draft 1K, High 2K, Master 4K) sent to generation endpoints</span>
              </div>
              <select
                aria-label="Default quality tier"
                className="command-input"
                style={{ width: 140, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
                value={draftPrefs.qualityTier}
                onChange={(e) => setDraftPrefs((prev) => ({ ...prev, qualityTier: e.target.value as QualityTier }))}
              >
                <option value="draft">Draft (1K)</option>
                <option value="high">High (2K)</option>
                <option value="master">Master (4K)</option>
              </select>
            </div>

            {/* 3. Evaluator Budget */}
            <div className="settings-row">
              <div className="settings-info">
                <span className="settings-title">Quality Evaluator Budget</span>
                <span className="settings-desc">Tier-A / Tier-B quality verification rigor sent with each run</span>
              </div>
              <select
                aria-label="Evaluator budget"
                className="command-input"
                style={{ width: 140, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
                value={draftPrefs.evalBudget}
                onChange={(e) => setDraftPrefs((prev) => ({ ...prev, evalBudget: e.target.value as EvalBudget }))}
              >
                <option value="minimal">Minimal (Tier A)</option>
                <option value="standard">Standard</option>
                <option value="thorough">Thorough (Full)</option>
              </select>
            </div>

            {/* 4. Replay-Default Seed */}
            <div className="settings-row">
              <div className="settings-info">
                <span className="settings-title">Replay-Default Seed</span>
                <span className="settings-desc">Leave blank for random seed, or set an integer for deterministic replay</span>
              </div>
              <input
                aria-label="Replay-default seed"
                type="number"
                min={0}
                placeholder="Random"
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value)}
                className="command-input"
                style={{ width: 140, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
              />
            </div>

            {/* 5. Output Preferences */}
            <div className="settings-row">
              <div className="settings-info">
                <span className="settings-title">Output Preferences (FPS / Format / C2PA)</span>
                <span className="settings-desc">Cinema transport cadence, preferred output format, and Content Credentials badge</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <select
                  aria-label="Cinema timeline framerate"
                  className="command-input"
                  style={{ width: 100, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
                  value={draftPrefs.outputPrefs.framerate}
                  onChange={(e) =>
                    setDraftPrefs((prev) => ({
                      ...prev,
                      outputPrefs: { ...prev.outputPrefs, framerate: Number(e.target.value) },
                    }))
                  }
                >
                  <option value={24}>24 fps</option>
                  <option value={30}>30 fps</option>
                  <option value={60}>60 fps</option>
                </select>
                <select
                  aria-label="Preferred output format"
                  className="command-input"
                  style={{ width: 92, background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '4px 8px' }}
                  value={draftPrefs.outputPrefs.format}
                  onChange={(e) =>
                    setDraftPrefs((prev) => ({
                      ...prev,
                      outputPrefs: { ...prev.outputPrefs, format: e.target.value as OutputFormatPref },
                    }))
                  }
                >
                  <option value="auto">Auto</option>
                  <option value="png">PNG</option>
                  <option value="webp">WEBP</option>
                  <option value="mp4">MP4</option>
                </select>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5 }}>
                  <input
                    type="checkbox"
                    checked={draftPrefs.outputPrefs.c2paBadge}
                    onChange={(e) =>
                      setDraftPrefs((prev) => ({
                        ...prev,
                        outputPrefs: { ...prev.outputPrefs, c2paBadge: e.target.checked },
                      }))
                    }
                  />
                  <span>C2PA</span>
                </label>
              </div>
            </div>

            {errorNote && (
              <div role="alert" style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>
                {errorNote}
              </div>
            )}
            {saveNote && <div style={{ fontSize: 12, color: '#86efac' }}>{saveNote}</div>}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 6 }}>
              <button className="composer-submit-btn" disabled={busy} onClick={() => void handleSavePreferences()}>
                {busy ? 'Applying...' : 'Apply & Save Preferences'}
              </button>
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
                <span style={{ fontSize: 13, fontWeight: 700 }}>Cognition Checkpoint &amp; OpenAI-compatible Tunnel</span>
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
                {engine?.comfy ? JSON.stringify(engine.comfy) : cognition?.comfy_endpoint || 'No ComfyUI status reported'}
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>Voice Synthesis Engine</div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                {audio
                  ? `Provider: ${audio.provider || 'unknown'} · Configured: ${audio.configured ? 'yes' : 'no'} · Voices listed: ${audio.voice_count ?? 0}`
                  : 'Voice synthesis status could not be loaded.'}
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
