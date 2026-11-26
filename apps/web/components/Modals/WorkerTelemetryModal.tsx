'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Play, Power, RefreshCw, Save, Server, X } from 'lucide-react';
import {
  configureStudioEngine,
  fetchCognitionStatus,
  fetchEngineStatus,
  fetchWorkers,
  launchLocalComfyEngine,
  stopLocalComfyEngine,
} from '../../lib/api';
import { readableError } from '../../lib/errors';
import { useStudio } from '../../lib/studio/store';

interface WorkerTelemetryModalProps {
  open: boolean;
  onClose: () => void;
}

const COGNITION_PRESETS = [
  { label: 'Together.ai (HF Partner)', url: 'https://api.together.xyz/v1', model: 'Qwen/Qwen2.5-72B-Instruct-Turbo' },
  { label: 'Fireworks.ai', url: 'https://api.fireworks.ai/inference/v1', model: 'accounts/fireworks/models/llama-v3p3-70b-instruct' },
  { label: 'Hugging Face Router', url: 'https://router.huggingface.co/v1', model: 'Qwen/Qwen2.5-72B-Instruct' },
  { label: 'Local / RunPod llama-server', url: 'http://127.0.0.1:8081/v1', model: 'OBLITERATUS/Qwen3.8-27B-OBLITERATED' },
];

export const WorkerTelemetryModal: React.FC<WorkerTelemetryModalProps> = ({ open, onClose }) => {
  const { dispatch } = useStudio();
  const [engine, setEngine] = useState<any>(null);
  const [cognition, setCognition] = useState<any>(null);
  const [workers, setWorkers] = useState<any>(null);
  const [comfyUrl, setComfyUrl] = useState('http://127.0.0.1:8188');
  const [comfyApiKey, setComfyApiKey] = useState('');
  const [openaiUrl, setOpenaiUrl] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [openaiModel, setOpenaiModel] = useState('OBLITERATUS/Qwen3.8-27B-OBLITERATED');
  const [error, setError] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [launching, setLaunching] = useState(false);

  const refresh = useCallback(async (populateInputs = false) => {
    setBusy(true);
    const notes: string[] = [];
    try {
      const eng = await fetchEngineStatus();
      setEngine(eng);
      dispatch({ type: 'SYSTEM', patch: { engine: eng, engineError: null } });
      if (populateInputs) {
        if (eng.comfy_base_url) setComfyUrl(eng.comfy_base_url);
        if (eng.cognition_endpoint || eng.llm?.endpoint) setOpenaiUrl(eng.cognition_endpoint || eng.llm?.endpoint || '');
        if (eng.llm?.model) setOpenaiModel(eng.llm.model);
      }
    } catch (err: any) {
      setEngine(null);
      notes.push(err?.message || 'Engine status unavailable.');
    }
    try {
      const cog = await fetchCognitionStatus();
      setCognition(cog);
    } catch (err: any) {
      setCognition(null);
      notes.push(err?.message || 'Cognition status unavailable.');
    }
    try {
      setWorkers(await fetchWorkers());
    } catch {
      setWorkers(null);
    }
    setError(notes.length ? notes.join(' ') : null);
    setBusy(false);
  }, [dispatch]);

  useEffect(() => {
    if (!open) return;
    setStatusNote(null);
    void refresh(true);
    const timer = window.setInterval(() => void refresh(false), 15000);
    return () => window.clearInterval(timer);
  }, [open, refresh]);

  if (!open) return null;

  const comfyOnline = Boolean(engine?.comfy_online || engine?.comfy?.reachable);
  const llmOnline = Boolean(cognition?.online || engine?.llm?.configured);
  const online = Boolean(comfyOnline || llmOnline);
  const workerList = workers?.workers || [];
  const devices = engine?.system_stats?.devices || [];
  const dev0 = devices[0] || null;
  const vramGb = dev0?.vram_total ? (Number(dev0.vram_total) / (1024 ** 3)).toFixed(1) : null;

  const handleLaunchLocalComfy = async () => {
    setLaunching(true);
    setError(null);
    setStatusNote('Starting local ComfyUI server on 127.0.0.1:8188 and binding MiniMax-H3 workflows...');
    try {
      const snap = await launchLocalComfyEngine({ host: '127.0.0.1', port: 8188, wait_seconds: 75 });
      setEngine(snap);
      if (snap.comfy_base_url) setComfyUrl(snap.comfy_base_url);
      dispatch({ type: 'SYSTEM', patch: { engine: snap, engineError: null } });
      setStatusNote(snap.launch_message || 'Local ComfyUI server is live and connected on http://127.0.0.1:8188.');
      await refresh(false);
    } catch (err) {
      setError(readableError(err));
      setStatusNote(null);
    } finally {
      setLaunching(false);
    }
  };

  const handleStopLocalComfy = async () => {
    setBusy(true);
    setError(null);
    try {
      const snap = await stopLocalComfyEngine();
      setEngine(snap);
      dispatch({ type: 'SYSTEM', patch: { engine: snap } });
      setStatusNote(snap.stop_message || 'Stopped managed local ComfyUI process.');
      await refresh(false);
    } catch (err) {
      setError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setStatusNote(null);
    try {
      const snap = await configureStudioEngine({
        comfy_base_url: comfyUrl.trim(),
        ...(comfyApiKey.trim() ? { comfy_api_key: comfyApiKey.trim() } : {}),
        openai_base_url: openaiUrl.trim(),
        ...(openaiApiKey.trim() ? { openai_api_key: openaiApiKey.trim() } : {}),
        openai_model: openaiModel.trim(),
      });
      setEngine(snap);
      dispatch({ type: 'SYSTEM', patch: { engine: snap, engineError: null } });
      setStatusNote('Engine endpoints saved to runtime, .env, and WorkerBridge.');
      await refresh(false);
    } catch (err) {
      setError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="ComfyUI & Engine Control Center">
      <div
        className="command-modal"
        style={{ width: 'min(780px, 95vw)', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Activity size={16} color={online ? '#34d399' : '#f59e0b'} />
            <strong>ComfyUI, MiniMax-H3 &amp; Open-Weight Engine Control Panel</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
        </div>

        <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {error && (
            <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>
              {error}
            </div>
          )}
          {statusNote && (
            <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(52,211,153,0.4)', background: 'rgba(52,211,153,0.08)', color: '#86efac', fontSize: 12 }}>
              {statusNote}
            </div>
          )}

          {/* Live Telemetry Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>ComfyUI + MiniMax H3</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: comfyOnline ? '#34d399' : '#fbbf24', marginTop: 4 }}>
                {comfyOnline ? 'ONLINE & WIRED' : 'OFFLINE'}
              </div>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginTop: 2 }}>
                {engine?.comfy?.latency_ms != null ? `${engine.comfy.latency_ms} ms` : (engine?.workflows?.minimax_h3_ref2va === 'ready' ? 'H3 Graph Ready' : 'Not connected')}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Hardware / Device</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#c7d2fe', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {dev0 ? `${String(dev0.name || dev0.type).toUpperCase()}${vramGb ? ` (${vramGb} GB)` : ''}` : (cognition?.gpus || 'Awaiting Connection')}
              </div>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginTop: 2 }}>
                {engine?.system_stats?.system?.comfyui_version ? `ComfyUI v${engine.system_stats.system.comfyui_version}` : (engine?.local_comfy_available ? 'Local ComfyUI Installed' : 'Remote Pod Mode')}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Pipeline Tools &amp; Cognition</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {engine?.wired_tools?.length || 19} Tools Wired · {llmOnline ? 'LLM Ready' : 'LLM Unset'}
              </div>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginTop: 2 }}>
                Video FPS: 30 / 60 / 100 / 120 Hz
              </div>
            </div>
          </div>

          {/* One-Click Local ComfyUI Server Launch Bar */}
          <div style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.35)', borderRadius: 8, padding: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Server size={14} /> Local ComfyUI Server Daemon
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', marginTop: 2 }}>
                {engine?.local_comfy_path
                  ? `Detected at ${engine.local_comfy_path}`
                  : 'Spawn or connect ComfyUI directly on http://127.0.0.1:8188'}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                disabled={launching || busy}
                onClick={() => void handleLaunchLocalComfy()}
                className="composer-submit-btn"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', fontSize: 12 }}
              >
                <Play size={13} />
                {launching ? 'Launching ComfyUI...' : comfyOnline ? 'Reconnect Local ComfyUI' : 'Launch Local ComfyUI (8188)'}
              </button>
              {comfyOnline && (
                <button
                  type="button"
                  disabled={busy || launching}
                  onClick={() => void handleStopLocalComfy()}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(244,63,94,0.14)', border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                >
                  <Power size={13} /> Stop
                </button>
              )}
              <button
                type="button"
                disabled={busy || launching}
                onClick={() => void refresh(false)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
              >
                <RefreshCw size={13} /> Probe
              </button>
            </div>
          </div>

          {/* Active Runtime Configuration Form */}
          <form onSubmit={(e) => void handleSaveConfig(e)} style={{ display: 'flex', flexDirection: 'column', gap: 12, background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>Configure ComfyUI &amp; Open-Weight Endpoints</div>

            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10 }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  ComfyUI Server URL (Local 8188, RunPod Pod, or Tunnel)
                </label>
                <input
                  type="text"
                  value={comfyUrl}
                  onChange={(e) => setComfyUrl(e.target.value)}
                  placeholder="http://127.0.0.1:8188"
                  className="command-input"
                  style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '7px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
                  ComfyUI API / Bearer Key (Optional)
                </label>
                <input
                  type="password"
                  value={comfyApiKey}
                  onChange={(e) => setComfyApiKey(e.target.value)}
                  placeholder="Optional token"
                  className="command-input"
                  style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '7px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
                <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                  Open-Weight Cognition Endpoint (Together.ai / Hugging Face / Fireworks.ai / llama.cpp)
                </label>
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  {COGNITION_PRESETS.map((p) => (
                    <button
                      key={p.label}
                      type="button"
                      onClick={() => {
                        setOpenaiUrl(p.url);
                        setOpenaiModel(p.model);
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
                  type="text"
                  value={openaiUrl}
                  onChange={(e) => setOpenaiUrl(e.target.value)}
                  placeholder="https://api.together.xyz/v1"
                  className="command-input"
                  style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '7px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
                <input
                  type="password"
                  value={openaiApiKey}
                  onChange={(e) => setOpenaiApiKey(e.target.value)}
                  placeholder="Provider API key"
                  className="command-input"
                  style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '7px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
                <input
                  type="text"
                  value={openaiModel}
                  onChange={(e) => setOpenaiModel(e.target.value)}
                  placeholder="OBLITERATUS/Qwen3.8-27B-OBLITERATED"
                  className="command-input"
                  style={{ width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '7px 10px', fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                Registered Workers: {workers?.count ?? workerList.length} · H3 Workflow: {engine?.workflows?.minimax_h3_ref2va || 'ready'}
              </span>
              <button
                type="submit"
                disabled={busy || launching}
                className="composer-submit-btn"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 16px', fontSize: 12 }}
              >
                <Save size={13} /> {busy ? 'Saving...' : 'Save & Connect Runtime'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
