'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ExternalLink, RefreshCw, Send, Square, X } from 'lucide-react';
import {
  ApiError,
  chatWithCognition,
  createSession,
  fetchCognitionStatus,
  fetchSessionMessages,
  mapPersistedAsset,
} from '../../lib/api';
import { readableError } from '../../lib/errors';
import { useStudio } from '@/lib/studio/store';
import { InternetFinding, StudioAsset } from '@/lib/types';
import { SignedOutNote } from '../auth/SignedOutNote';

interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
  createdAssets?: StudioAsset[];
  citations?: InternetFinding[];
  errors?: string[];
}

interface CognitionRuntimeStatus {
  online?: boolean;
  model?: string;
  served_model?: string;
  active_endpoint?: string;
  cognition_detail?: string;
  state?: string;
}

interface AgentChatModalProps {
  open: boolean;
  onClose: () => void;
}

export const AgentChatModal: React.FC<AgentChatModalProps> = ({ open, onClose }) => {
  const { state, dispatch } = useStudio();
  const { session, projectId, sessionId, activeSession, sessionMessages } = state.system;
  const personaId = state.composer.personaId;
  const isSignedIn = session.status === 'signed_in';

  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [busy, setBusy] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [allowGeneration, setAllowGeneration] = useState(false);
  const [runtime, setRuntime] = useState<CognitionRuntimeStatus | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);

  const refreshRuntime = useCallback(async () => {
    setRuntimeLoading(true);
    setRuntimeError(null);
    try {
      const status = await fetchCognitionStatus();
      setRuntime(status);
    } catch (err) {
      setRuntime(null);
      setRuntimeError(readableError(err));
    } finally {
      setRuntimeLoading(false);
    }
  }, []);

  // Hydrate persisted messages when opening or switching active session.
  useEffect(() => {
    if (!open) return;
    void refreshRuntime();
    if (sessionId) {
      fetchSessionMessages(sessionId)
        .then((persisted) => {
          const turns: ChatTurn[] = (persisted || [])
            .filter((m) => m.role === 'user' || m.role === 'assistant' || m.role === 'keystone')
            .map((m) => ({
              role: m.role === 'user' ? 'user' : 'assistant',
              content: m.content,
            }));
          setMessages(turns);
        })
        .catch(() => {
          if (sessionMessages.length) {
            setMessages(
              sessionMessages
                .filter((m) => m.role === 'user' || m.role === 'assistant' || m.role === 'keystone')
                .map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.content })),
            );
          }
        });
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose, refreshRuntime, sessionId, sessionMessages]);

  useEffect(() => {
    if (isSignedIn) setAuthRequired(false);
  }, [isSignedIn]);

  useEffect(() => {
    if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight;
  }, [messages, busy, error]);

  const handleNewChat = async () => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setAuthRequired(false);
    setBusy(false);
    setInput('');
    if (isSignedIn) {
      try {
        const created = await createSession('Cognition Chat', projectId);
        dispatch({ type: 'SET_SESSION', session: created, messages: [] });
      } catch {
        dispatch({ type: 'SET_SESSION', session: null, messages: [] });
      }
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setBusy(false);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || busy) return;
    if (session.status === 'signed_out') {
      setAuthRequired(true);
      setError('Sign in or add an API key first — POST /v1/cognition/chat requires an authenticated workspace session.');
      return;
    }

    const nextMessages: ChatTurn[] = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setInput('');
    setBusy(true);
    setError(null);
    setAuthRequired(false);

    // Ensure a persisted session_id is attached whenever signed in.
    let activeSessionId = sessionId;
    if (!activeSessionId && isSignedIn) {
      try {
        const created = await createSession(text.slice(0, 40) || 'Cognition Chat', projectId);
        if (created?.id) {
          activeSessionId = created.id;
          dispatch({ type: 'SET_SESSION', session: created, messages: [] });
        }
      } catch {
        // Proceed without blocking if session creation fails; server reports any error explicitly.
      }
    }

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await chatWithCognition(
        {
          messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
          web_search: webSearch,
          allow_generation: allowGeneration,
          session_id: activeSessionId,
          project_id: projectId,
          as: personaId,
          persona_id: personaId,
        },
        controller.signal,
      );
      if (controller.signal.aborted) return;

      const reply = result?.message?.content || result?.text;
      if (!reply) {
        throw new Error('Cognition returned an empty response body.');
      }

      const rawAssets = Array.isArray(result?.created_assets) ? result.created_assets : [];
      const createdAssets: StudioAsset[] = rawAssets
        .filter((a) => a && a.id && (a.download_url || a.url))
        .map((a) => mapPersistedAsset({ ...a, project_id: a.project_id ?? projectId }));

      if (createdAssets.length) {
        dispatch({ type: 'ASSETS_ADDED', assets: createdAssets, select: false });
      }

      const citations: InternetFinding[] = Array.isArray(result?.internet_findings) ? result.internet_findings : [];
      const inlineErrors: string[] = [];
      if (result?.generation_error) inlineErrors.push(`Generation: ${result.generation_error}`);
      if (result?.session_persist_error) inlineErrors.push(`Session save: ${result.session_persist_error}`);

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: String(reply),
          createdAssets,
          citations,
          errors: inlineErrors,
        },
      ]);
    } catch (err: any) {
      if (err?.name === 'AbortError') return;
      if (err instanceof ApiError && err.status === 401) {
        setAuthRequired(true);
      }
      setError(err?.message || readableError(err) || 'Cognition chat failed.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  const badgeLabel = runtimeLoading
    ? 'CHECKING'
    : runtime?.online
      ? 'ONLINE'
      : runtime
        ? 'OFFLINE'
        : 'UNREACHABLE';
  const badgeStyle = runtime?.online
    ? { background: 'rgba(16, 185, 129, 0.16)', color: '#34d399' }
    : { background: 'rgba(245, 158, 11, 0.16)', color: '#fbbf24' };

  const activeModel = runtime?.served_model || runtime?.model || 'OBLITERATUS/Qwen3.8-27B-OBLITERATED';
  const endpointLabel = runtime?.active_endpoint || 'Awaiting open-weight runtime selection (click Configure Engine)';

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Direct LLM Agent Chat">
      <div className="chat-modal-window" onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 700, fontSize: 14.5 }}>Direct Cognition Console</span>
              <span className="stage-chip" style={{ ...badgeStyle, fontSize: 10.5, fontWeight: 700 }}>
                {badgeLabel}
              </span>
              {sessionId && (
                <span className="stage-chip" style={{ fontSize: 10.5 }}>
                  Session: {activeSession?.title || sessionId.slice(0, 8)}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, wordBreak: 'break-word' }}>
              {runtimeError ? `Probe failed: ${runtimeError}` : `${activeModel} • ${endpointLabel} (/v1/cognition/chat)`}
            </div>
            {runtime && !runtime.online && runtime.cognition_detail && (
              <div style={{ fontSize: 11, color: '#fbbf24', marginTop: 2, wordBreak: 'break-word' }}>{runtime.cognition_detail}</div>
            )}
          </div>
          <div className="chat-header-actions">
            <button
              className="icon-btn"
              onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'worker' })}
              title="Configure Cognition & ComfyUI Endpoints"
              type="button"
            >
              Configure Engine
            </button>
            <button
              className="icon-btn"
              onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'sessions' })}
              title="Switch session"
              type="button"
            >
              Sessions
            </button>
            <button
              className="icon-btn"
              onClick={() => void refreshRuntime()}
              title="Refresh live cognition status"
              type="button"
              disabled={runtimeLoading}
            >
              <RefreshCw size={14} className={runtimeLoading ? 'animate-spin' : ''} />
            </button>
            <button id="btnNewAgentChat" className="btn-new-chat" onClick={() => void handleNewChat()} title="Start new session" type="button">
              <span>+</span>
              <span>New Chat</span>
            </button>
            <button className="icon-btn" onClick={onClose} title="Close" type="button">
              <X size={14} />
            </button>
          </div>
        </div>

        <div ref={streamRef} className="chat-stream-viewport">
          {(session.status === 'signed_out' || session.status === 'error' || authRequired) && (
            <div style={{ margin: 12, padding: 12, borderRadius: 8, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.03)' }}>
              <SignedOutNote what="the Direct Cognition Console" compact />
            </div>
          )}
          {messages.length === 0 && !error && session.status !== 'signed_out' && (
            <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>
              No messages yet. Type below to dispatch directly to the live configured cognition runtime.
            </div>
          )}
          {messages.map((message, idx) => (
            <div key={`${message.role}-${idx}`} className={`chat-msg-row ${message.role}`}>
              <div className="chat-avatar-icon qwen">{message.role === 'assistant' ? 'AI' : 'You'}</div>
              <div className="chat-bubble-content">
                <div className="chat-bubble-header">
                  <span style={{ fontWeight: 700, color: message.role === 'assistant' ? '#c084fc' : '#e2e8f0' }}>
                    {message.role === 'assistant' ? 'Cognition' : 'You'}
                  </span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>

                {message.createdAssets && message.createdAssets.length > 0 && (
                  <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {message.createdAssets.map((asset) => (
                      <button
                        key={asset.id}
                        type="button"
                        onClick={() => {
                          dispatch({ type: 'SELECT_ASSET', id: asset.id });
                          dispatch({ type: 'SET_VIEW', view: 'single' });
                          onClose();
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: 6,
                          borderRadius: 8,
                          border: '1px solid rgba(99,102,241,0.4)',
                          background: 'rgba(99,102,241,0.1)',
                          color: '#e2e8f0',
                          cursor: 'pointer',
                          textAlign: 'left',
                        }}
                      >
                        <img src={asset.previewUrl || asset.url} alt={asset.title} style={{ width: 48, height: 48, objectFit: 'cover', borderRadius: 6 }} />
                        <div>
                          <div style={{ fontSize: 11.5, fontWeight: 600 }}>{asset.title}</div>
                          <div style={{ fontSize: 10, color: '#a5b4fc' }}>Open on stage</div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {message.citations && message.citations.length > 0 && (
                  <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ fontSize: 10.5, fontWeight: 700, color: '#94a3b8' }}>Sources &amp; Citations</div>
                    {message.citations.map((c, cIdx) => (
                      <a
                        key={`${c.url}-${cIdx}`}
                        href={c.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: 11, color: '#a5b4fc', textDecoration: 'none', display: 'flex', alignItems: 'flex-start', gap: 6 }}
                      >
                        <ExternalLink size={12} style={{ marginTop: 2, flexShrink: 0 }} />
                        <span>
                          <strong>{c.title}</strong> — <span style={{ color: 'var(--text-secondary)' }}>{c.snippet}</span>
                        </span>
                      </a>
                    ))}
                  </div>
                )}

                {message.errors && message.errors.length > 0 && (
                  <div role="alert" style={{ marginTop: 8, padding: 8, borderRadius: 6, border: '1px solid rgba(244,63,94,0.4)', background: 'rgba(244,63,94,0.08)', color: '#fda4af', fontSize: 11.5 }}>
                    {message.errors.join(' · ')}
                  </div>
                )}
              </div>
            </div>
          ))}
          {busy && <div style={{ padding: 12, fontSize: 12, color: 'var(--text-secondary)' }}>Waiting for live cognition response...</div>}
          {error && (
            <div
              role="alert"
              style={{
                margin: 12,
                padding: 10,
                borderRadius: 8,
                border: '1px solid rgba(244,63,94,0.4)',
                background: 'rgba(244,63,94,0.08)',
                color: '#fda4af',
                fontSize: 12,
                wordBreak: 'break-word',
              }}
            >
              {error}
            </div>
          )}
        </div>

        <div className="chat-bottom-composer">
          <div className="chat-composer-toolbar">
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button className={`chat-tool-btn web ${webSearch ? 'active' : ''}`} onClick={() => setWebSearch((v) => !v)} type="button">
                <span>Web Search</span>
              </button>
              <button className={`chat-tool-btn gen ${allowGeneration ? 'active' : ''}`} onClick={() => setAllowGeneration((v) => !v)} type="button">
                <span>Asset Generation</span>
              </button>
            </div>
            <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10.5 }}>Shift+Enter for newline • Enter to send</span>
          </div>
          <div className="chat-composer-row">
            <textarea
              className="chat-input-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              placeholder="Message the live cognition model..."
            />
            {busy ? (
              <button className="btn-chat-send" style={{ background: '#ef4444' }} onClick={handleStop} type="button">
                <Square size={14} />
                <span>Stop</span>
              </button>
            ) : (
              <button className="btn-chat-send" onClick={() => void handleSend()} type="button" disabled={!input.trim()}>
                <Send size={14} />
                <span>Send</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
