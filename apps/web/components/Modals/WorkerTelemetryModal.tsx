'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Activity, X } from 'lucide-react';
import { fetchCognitionStatus, fetchEngineStatus, fetchWorkers } from '../../lib/api';

interface WorkerTelemetryModalProps {
  open: boolean;
  onClose: () => void;
}

export const WorkerTelemetryModal: React.FC<WorkerTelemetryModalProps> = ({ open, onClose }) => {
  const [engine, setEngine] = useState<any>(null);
  const [cognition, setCognition] = useState<any>(null);
  const [workers, setWorkers] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    const notes: string[] = [];
    try {
      setEngine(await fetchEngineStatus());
    } catch (err: any) {
      setEngine(null);
      notes.push(err?.message || 'Engine status unavailable.');
    }
    try {
      setCognition(await fetchCognitionStatus());
    } catch (err: any) {
      setCognition(null);
      notes.push(err?.message || 'Cognition status unavailable.');
    }
    try {
      setWorkers(await fetchWorkers());
    } catch (err: any) {
      setWorkers(null);
      notes.push(err?.message || 'Worker bridge list unavailable.');
    }
    setError(notes.length ? notes.join(' ') : null);
    setBusy(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, [open, refresh]);

  if (!open) return null;

  const online = Boolean(engine?.online || cognition?.online);
  const workerList = workers?.workers || [];
  const primary = workerList[0] || null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Worker Telemetry">
      <div className="command-modal" style={{ width: 'min(700px, 94vw)', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Activity size={16} color={online ? '#34d399' : '#94a3b8'} />
            <strong>Colab Engine Telemetry</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
        </div>
        <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {error && <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Worker State</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: online ? '#34d399' : '#94a3b8', marginTop: 4 }}>
                {cognition?.state || (online ? 'CONFIGURED' : 'OFFLINE')}
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>VRAM / Engine Status</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#c7d2fe', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {cognition?.vram_total_gb ? `${cognition.vram_allocated_gb || 0} / ${cognition.vram_total_gb} GB` : (cognition?.gpus || 'No GPU telemetry reported')}
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Heartbeat Latency</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
                {cognition?.cognition_latency_ms != null ? `${cognition.cognition_latency_ms} ms` : '-- ms'}
              </div>
            </div>
          </div>
          <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14, fontFamily: 'var(--font-mono)', fontSize: 11, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div><strong style={{ color: 'var(--text-secondary)' }}>Worker ID:</strong> {primary?.worker_id || cognition?.worker_cluster || 'No registered worker'}</div>
            <div><strong style={{ color: 'var(--text-secondary)' }}>Pinned / served model:</strong> {cognition?.served_model || cognition?.model || engine?.llm?.model || 'None reported'}</div>
            <div><strong style={{ color: 'var(--text-secondary)' }}>Cognition:</strong> {engine?.llm?.configured ? 'OpenAI-compatible endpoint configured' : 'Not configured'}</div>
            <div><strong style={{ color: 'var(--text-secondary)' }}>ComfyUI:</strong> {engine?.comfy?.configured || cognition?.comfy_configured ? (cognition?.comfy_endpoint || 'Configured') : 'Not configured'}</div>
            <div><strong style={{ color: 'var(--text-secondary)' }}>Registered workers:</strong> {workers?.count ?? workerList.length}</div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button className="action-btn-mini" onClick={refresh} disabled={busy} style={{ background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)', padding: '6px 12px', borderRadius: 6, cursor: 'pointer' }}>
              {busy ? 'Refreshing...' : 'Ping & Refresh Engine'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
