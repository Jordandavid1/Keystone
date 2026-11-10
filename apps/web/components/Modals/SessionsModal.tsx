'use client';

import React, { useEffect, useState } from 'react';
import { Clock, X } from 'lucide-react';
import { createSession, fetchSessionMessages, fetchSessions } from '../../lib/api';

interface SessionsModalProps {
  open: boolean;
  onClose: () => void;
  projectId?: string | null;
  onSelectSession?: (session: any) => void;
}

export const SessionsModal: React.FC<SessionsModalProps> = ({ open, onClose, projectId, onSelectSession }) => {
  const [sessions, setSessions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ title: string; messages: any[] } | null>(null);

  const reload = async () => {
    setError(null);
    try {
      setSessions(await fetchSessions(projectId));
    } catch (err: any) {
      setSessions([]);
      setError(err?.message || 'Could not load sessions.');
    }
  };

  useEffect(() => {
    if (open) {
      setPreview(null);
      reload();
    }
  }, [open, projectId]);

  const handleCreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createSession('Creative Session', projectId);
      await reload();
      if (created) onSelectSession?.(created);
    } catch (err: any) {
      setError(err?.message || 'Could not create session.');
    } finally {
      setBusy(false);
    }
  };

  const handleOpen = async (session: any) => {
    setError(null);
    onSelectSession?.(session);
    try {
      const messages = await fetchSessionMessages(session.id);
      setPreview({ title: session.title || session.id, messages });
    } catch (err: any) {
      setPreview({ title: session.title || session.id, messages: [] });
      setError(err?.message || 'Session opened, but messages could not be loaded.');
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Session History">
      <div className="command-modal" style={{ width: 'min(640px, 94vw)', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Clock size={16} color="#a855f7" />
            <strong>Multi-Turn Session History</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
        </div>
        <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
              Sessions preserve conversational context and generation lineage. No sample history is invented.
            </div>
            <button className="action-btn-mini" onClick={handleCreate} disabled={busy} style={{ background: 'linear-gradient(135deg, #a855f7, #ec4899)', color: '#fff', border: 'none', padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>
              + New Session
            </button>
          </div>
          {error && <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
            {sessions.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No sessions loaded.</div>
            ) : (
              sessions.map((session) => (
                <button key={session.id} onClick={() => handleOpen(session)} style={{ textAlign: 'left', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 10, color: 'inherit', cursor: 'pointer' }}>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{session.title || 'Untitled session'}</div>
                  <div style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{session.created_at || session.id}</div>
                </button>
              ))
            )}
          </div>
          {preview && (
            <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8 }}>{preview.title}</div>
              {preview.messages.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>This session has no stored messages.</div>
              ) : (
                preview.messages.map((message) => (
                  <div key={message.id} style={{ marginBottom: 8, fontSize: 12 }}>
                    <strong>{message.role}</strong>
                    <div style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{message.content}</div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
