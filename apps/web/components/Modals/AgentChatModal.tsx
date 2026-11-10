'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Send, Square, X } from 'lucide-react';
import { chatWithCognition } from '../../lib/api';

interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

interface AgentChatModalProps {
  open: boolean;
  onClose: () => void;
}

export const AgentChatModal: React.FC<AgentChatModalProps> = ({ open, onClose }) => {
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [allowGeneration, setAllowGeneration] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight;
  }, [messages, busy]);

  const handleNewChat = () => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setBusy(false);
    setInput('');
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setBusy(false);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const nextMessages: ChatTurn[] = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setInput('');
    setBusy(true);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await chatWithCognition({
        messages: nextMessages,
        web_search: webSearch,
        allow_generation: allowGeneration,
      });
      if (controller.signal.aborted) return;
      const reply = result?.message?.content || result?.text;
      if (!reply) {
        throw new Error('Cognition returned no text. The Colab llama-server may be offline.');
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: String(reply) }]);
    } catch (err: any) {
      if (err?.name === 'AbortError') return;
      setError(err?.message || 'Cognition chat failed.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Direct LLM Agent Chat">
      <div className="chat-modal-window" onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 14.5 }}>Direct Cognition Console</span>
              <span className="stage-chip" style={{ background: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', fontSize: 10.5, fontWeight: 700 }}>COLAB LLM</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
              Messages go to the OpenAI-compatible Colab llama-server via /v1/cognition/chat. No canned replies.
            </div>
          </div>
          <div className="chat-header-actions">
            <button id="btnNewAgentChat" className="btn-new-chat" onClick={handleNewChat} title="Clear conversation">
              <span>+</span>
              <span>New Chat</span>
            </button>
            <button className="icon-btn" onClick={onClose} title="Close"><X size={14} /></button>
          </div>
        </div>

        <div ref={streamRef} className="chat-stream-viewport">
          {messages.length === 0 && !error && (
            <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>
              No messages yet. Type below to talk to the configured cognition model.
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
              </div>
            </div>
          ))}
          {busy && <div style={{ padding: 12, fontSize: 12, color: 'var(--text-secondary)' }}>Waiting for the Colab llama-server...</div>}
          {error && <div style={{ margin: 12, padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>{error}</div>}
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
                  handleSend();
                }
              }}
              placeholder="Message the Colab cognition model..."
            />
            {busy ? (
              <button className="btn-chat-send" style={{ background: '#ef4444' }} onClick={handleStop} type="button">
                <Square size={14} />
                <span>Stop</span>
              </button>
            ) : (
              <button className="btn-chat-send" onClick={handleSend} type="button" disabled={!input.trim()}>
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
