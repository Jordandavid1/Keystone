'use client';

import React, { useEffect, useState } from 'react';
import { Play, Power, RefreshCw, Save, Server, Settings, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import {
  configureStudioEngine,
  fetchAccount,
  fetchAudioConfig,
  fetchCognitionStatus,
  fetchEngineStatus,
  launchLocalComfyEngine,
  stopLocalComfyEngine,
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
  /** Open straight on the account, content, or engine tab. */
  initialTab?: 'account' | 'content' | 'engine' | null;
}

const PROVIDER_PRESETS = [
  { label: 'Together.ai (HF Partner)', url: 'https://api.together.xyz/v1', model: 'Qwen/Qwen2.5-72B-Instruct-Turbo' },
  { label: 'Fireworks.ai', url: 'https://api.fireworks.ai/inference/v1', model: 'accounts/fireworks/models/llama-v3p3-70b-instruct' },
  { label: 'Hugging Face Router', url: 'https://router.huggingface.co/v1', model: 'Qwen/Qwen2.5-72B-Instruct' },
  { label: 'Local / RunPod llama-server', url: 'http://127.0.0.1:8081/v1', model: 'OBLITERATUS/Qwen3.8-27B-OBLITERATED' },
];

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
  const [launchingComfy, setLaunchingComfy] = useState(false);
  const [saveNote, setSaveNote] = useState<string | null>(null);
  const [errorNote, setErrorNote] = useState<string | null>(null);
  const [engine, setEngine] = useState<any>(null);
  const [cognition, setCognition] = useState<any>(null);
  const [audio, setAudio] = useState<any>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [engineNote, setEngineNote] = useState<string | null>(null);
  const [comfyUrlInput, setComfyUrlInput] = useState('http://127.0.0.1:8188');
  const [comfyKeyInput, setComfyKeyInput] = useState('');
  const [openaiUrlInput, setOpenaiUrlInput] = useState('');
  const [openaiKeyInput, setOpenaiKeyInput] = useState('');
  const [openaiModelInput, setOpenaiModelInput] = useState('OBLITERATUS/Qwen3.8-27B-OBLITERATED');

  useEffect(() => {
    if (!open) return;
    if (initialTab === 'account') setTab('security');
    else if (initialTab === 'content') setTab('config');
    else if (initialTab === 'engine') setTab('engine');

    setDraftPrefs(preferences);
    setSeedInput(preferences.defaultSeed != null ? String(preferences.defaultSeed) : '');
    setSelectedMode(contentMode);
    setSaveNote(null);
    setErrorNote(null);
    setEngineNote(null);
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
      .then((eng) => {
        setEngine(eng);
        if (eng.comfy_base_url) setComfyUrlInput(eng.comfy_base_url);
        if (eng.cognition_endpoint || eng.llm?.endpoint) setOpenaiUrlInput(eng.cognition_endpoint || eng.llm?.endpoint || '');
        if (eng.llm?.model) setOpenaiModelInput(eng.llm.model);
      })
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
  const comfyOnline = Boolean(engine?.comfy_online || engine?.comfy?.reachable || engine?.comfy?.configured);

  const handleRefreshEngine = async () => {
    setBusy(true);
    setEngineError(null);
    try {
      const eng = await fetchEngineStatus();
      setEngine(eng);
      dispatch({ type: 'SYSTEM', patch: { engine: eng, engineError: null } });
      const cog = await fetchCognitionStatus().catch(() => null);
      if (cog) setCognition(cog);
    } catch (err) {
      setEngineError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleLaunchComfy = async () => {
    setLaunchingComfy(true);
    setEngineError(null);
    setEngineNote('Starting local ComfyUI server on 127.0.0.1:8188 and wiring MiniMax-H3...');
    try {
      const snap = await launchLocalComfyEngine({ host: '127.0.0.1', port: 8188, wait_seconds: 75 });
      setEngine(snap);
      if (snap.comfy_base_url) setComfyUrlInput(snap.comfy_base_url);
      dispatch({ type: 'SYSTEM', patch: { engine: snap, engineError: null } });
      setEngineNote(snap.launch_message || 'ComfyUI server launched and wired on http://127.0.0.1:8188.');
    } catch (err) {
      setEngineError(readableError(err));
      setEngineNote(null);
    } finally {
      setLaunchingComfy(false);
    }
  };

  const handleStopComfy = async () => {
    setBusy(true);
    setEngineError(null);
    try {
      const snap = await stopLocalComfyEngine();
      setEngine(snap);
      dispatch({ type: 'SYSTEM', patch: { engine: snap } });
      setEngineNote(snap.stop_message || 'Stopped managed local ComfyUI process.');
    } catch (err) {
      setEngineError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveEngineRuntime = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setEngineError(null);
    setEngineNote(null);
    try {
      const snap = await configureStudioEngine({
        comfy_base_url: comfyUrlInput.trim(),
        ...(comfyKeyInput.trim() ? { comfy_api_key: comfyKeyInput.trim() } : {}),
        openai_base_url: openaiUrlInput.trim(),
        ...(openaiKeyInput.trim() ? { openai_api_key: openaiKeyInput.trim() } : {}),
        openai_model: openaiModelInput.trim(),
      });
      setEngine(snap);
      dispatch({ type: 'SYSTEM', patch: { engine: snap, engineError: null } });
      setEngineNote('ComfyUI & Cognition endpoints saved and live-wired across WorkerBridge and .env.');
    } catch (err) {
      setEngineError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

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
                  <option value={30}>30 Hz</option>
                  <option value={60}>60 Hz</option>
                  <option value={100}>100 Hz</option>
                  <option value={120}>120 Hz</option>
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
            {engineNote && (
              <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(52,211,153,0.4)', background: 'rgba(52,211,153,0.08)', color: '#86efac', fontSize: 12 }}>
                {engineNote}
              </div>
            )}

            {/* Active Local ComfyUI Server Control */}
            <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.35)', borderRadius: 8, padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Server size={14} /> ComfyUI &amp; MiniMax-H3 Creative Execution Server
                    <span className="telemetry-pill" style={{ borderColor: comfyOnline ? 'rgba(52,211,153,0.4)' : 'rgba(245,158,11,0.4)', color: comfyOnline ? '#34d399' : '#fbbf24' }}>
                      {comfyOnline ? 'ONLINE' : 'OFFLINE'}
                    </span>
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 4 }}>
                    {engine?.local_comfy_path
                      ? `Local install: ${engine.local_comfy_path} · H3 workflow: ${engine?.workflows?.minimax_h3_ref2va || 'ready'}`
                      : `Active URL: ${engine?.comfy_base_url || 'Not connected'}`}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    disabled={launchingComfy || busy}
                    onClick={() => void handleLaunchComfy()}
                    className="composer-submit-btn"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: 12 }}
                  >
                    <Play size={13} /> {launchingComfy ? 'Launching...' : comfyOnline ? 'Reconnect 8188' : 'Launch Local ComfyUI'}
                  </button>
                  {comfyOnline && (
                    <button
                      type="button"
                      disabled={busy || launchingComfy}
                      onClick={() => void handleStopComfy()}
                      className="icon-btn"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 5, borderColor: 'rgba(244,63,94,0.4)', color: '#fda4af', padding: '6px 10px', fontSize: 12 }}
                    >
                      <Power size={13} /> Stop
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={busy || launchingComfy}
                    onClick={() => void handleRefreshEngine()}
                    className="icon-btn"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 10px', fontSize: 12 }}
                  >
                    <RefreshCw size={13} /> Probe
                  </button>
                </div>
              </div>
            </div>

            {/* Live Endpoint & Model Form */}
            <form onSubmit={(e) => void handleSaveEngineRuntime(e)} style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 700 }}>ComfyUI &amp; Open-Weight Cognition Endpoints</span>
                <span className="telemetry-pill" style={{ borderColor: llmOnline ? 'rgba(52,211,153,0.4)' : 'rgba(148,163,184,0.4)', color: llmOnline ? '#34d399' : '#94a3b8' }}>
                  Cognition: {llmOnline ? 'CONNECTED' : 'NOT SET'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                    ComfyUI Server URL (Local 8188, RunPod Pod, or Tunnel)
                  </label>
                  <input
                    aria-label="ComfyUI server URL"
                    type="text"
                    value={comfyUrlInput}
                    onChange={(e) => setComfyUrlInput(e.target.value)}
                    placeholder="http://127.0.0.1:8188"
                    className="command-input"
                    style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                    ComfyUI API Key (Optional)
                  </label>
                  <input
                    aria-label="ComfyUI API key"
                    type="password"
                    value={comfyKeyInput}
                    onChange={(e) => setComfyKeyInput(e.target.value)}
                    placeholder="Bearer token"
                    className="command-input"
                    style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  />
                </div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
                  <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    Open-Weight Cognition Provider (1-Click Presets)
                  </label>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {PROVIDER_PRESETS.map((p) => (
                      <button
                        key={p.label}
                        type="button"
                        onClick={() => {
                          setOpenaiUrlInput(p.url);
                          setOpenaiModelInput(p.model);
                        }}
                        style={{ fontSize: 10.5, padding: '2px 7px', borderRadius: 999, border: '1px solid var(--border-subtle)', background: 'rgba(255,255,255,0.04)', color: '#c7d2fe', cursor: 'pointer' }}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.2fr', gap: 10 }}>
                  <input
                    aria-label="OpenAI-compatible endpoint URL"
                    type="text"
                    value={openaiUrlInput}
                    onChange={(e) => setOpenaiUrlInput(e.target.value)}
                    placeholder="https://api.together.xyz/v1"
                    className="command-input"
                    style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  />
                  <input
                    aria-label="OpenAI-compatible API key"
                    type="password"
                    value={openaiKeyInput}
                    onChange={(e) => setOpenaiKeyInput(e.target.value)}
                    placeholder="Provider API Key"
                    className="command-input"
                    style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  />
                  <input
                    aria-label="Served open-weight model"
                    type="text"
                    value={openaiModelInput}
                    onChange={(e) => setOpenaiModelInput(e.target.value)}
                    placeholder="OBLITERATUS/Qwen3.8-27B-OBLITERATED"
                    className="command-input"
                    style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
                  Wired tools: {engine?.wired_tools?.length || 19} · Latency: {cognition?.cognition_latency_ms != null ? `${cognition.cognition_latency_ms} ms` : (engine?.comfy?.latency_ms != null ? `${engine.comfy.latency_ms} ms` : 'n/a')}
                </span>
                <button
                  type="submit"
                  disabled={busy || launchingComfy}
                  className="composer-submit-btn"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', fontSize: 12 }}
                >
                  <Save size={13} /> {busy ? 'Saving...' : 'Save & Connect Runtime'}
                </button>
              </div>
            </form>

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
