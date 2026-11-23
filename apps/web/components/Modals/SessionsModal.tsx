'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Check, Clock, MessageSquare, X } from 'lucide-react';
import { createSession, fetchSessionMessages, fetchSessions } from '../../lib/api';
import { SessionMessage, SessionSummary } from '../../lib/types';

interface SessionsModalProps {
  open: boolean;
  onClose: () => void;
  projectId?: string | null;
  activeSessionId?: string | null;
  onSelectSession?: (session: SessionSummary, messages: SessionMessage[]) => void;
  onOpenChat?: () => void;
}

export const SessionsModal: React.FC<SessionsModalProps> = ({
  open,
  onClose,
  projectId,
  activeSessionId,
  onSelectSession,
  onOpenChat,
}) => {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<{ session: SessionSummary; messages: SessionMessage[] } | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      setSessions(await fetchSessions(projectId));
    } catch (err: any) {
      setSessions([]);
      setError(err?.message || 'Could not load sessions.');
    }
  }, [projectId]);

  useEffect(() => {
    if (open) {
      setPreview(null);
      void reload();
    }
  }, [open, reload]);

  const handleCreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createSession('Creative Session', projectId);
      await reload();
      if (created) {
        setPreview({ session: created, messages: [] });
        onSelectSession?.(created, []);
      }
    } catch (err: any) {
      setError(err?.message || 'Could not create session.');
    } finally {
      setBusy(false);
    }
  };

  const handleOpen = async (session: SessionSummary) => {
    setError(null);
    try {
      const messages = await fetchSessionMessages(session.id);
      setPreview({ session, messages });
      onSelectSession?.(session, messages);
    } catch (err: any) {
      setPreview({ session, messages: [] });
      onSelectSession?.(session, []);
      setError(err?.message || 'Session selected, but messages could not be loaded.');
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Session History">
      <div className="command-modal" style={{ width: 'min(660px, 94vw)', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Clock size={16} color="#a855f7" />
            <strong>Multi-Turn Session History</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close">
            <X size={14} />
          </button>
        </div>
        <div style={{ padding: '18px 22px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
              Selecting a session sets the active workspace context and loads its persisted messages.
            </div>
            <button
              className="action-btn-mini"
              onClick={handleCreate}
              disabled={busy}
              style={{ background: 'linear-gradient(135deg, #a855f7, #ec4899)', color: '#fff', border: 'none', padding: '5px 12px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}
            >
              + New Session
            </button>
          </div>
          {error && <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{error}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 280, overflowY: 'auto' }}>
            {sessions.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No sessions loaded.</div>
            ) : (
              sessions.map((session) => {
                const isActive = activeSessionId === session.id;
                return (
                  <button
                    key={session.id}
                    onClick={() => void handleOpen(session)}
                    style={{
                      textAlign: 'left',
                      background: isActive ? 'rgba(99, 102, 241, 0.14)' : 'rgba(255,255,255,0.02)',
                      border: isActive ? '1px solid rgba(99, 102, 241, 0.5)' : '1px solid var(--border-subtle)',
                      borderRadius: 8,
                      padding: 10,
                      color: 'inherit',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700 }}>{session.title || 'Untitled session'}</div>
                      <div style={{ fontSize: 10.5, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                        {session.created_at || session.id}
                        {session.content_mode ? ` · ${session.content_mode}` : ''}
                      </div>
                    </div>
                    {isActive && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#a5b4fc', flexShrink: 0 }}>
                        <Check size={13} /> Active
                      </span>
                    )}
                  </button>
                );
              })
            )}
          </div>
          {preview && (
            <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 700 }}>
                  {preview.session.title || preview.session.id} ({preview.messages.length} messages)
                </div>
                {onOpenChat && (
                  <button type="button" className="icon-btn" onClick={onOpenChat}>
                    <MessageSquare size={12} /> Open in Chat
                  </button>
                )}
              </div>
              {preview.messages.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>This session has no stored messages yet.</div>
              ) : (
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {preview.messages.map((message) => (
                    <div key={message.id} style={{ marginBottom: 8, fontSize: 12 }}>
                      <strong>{message.role}</strong>
                      <div style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>{message.content}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
