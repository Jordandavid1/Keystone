'use client';


import React, { useEffect, useState } from 'react';
import { X, Users, Mic } from 'lucide-react';
import { apiRequest } from '../../lib/api';

interface VoiceInfo {
  voice_id: string;
  name: string;
  gender?: string;
  accent?: string;
  description?: string;
}

interface PersonaInfo {
  id: string;
  name: string;
  description?: string;
  voice_id?: string;
  voice_name?: string;
  personality_traits?: string[];
  avatar_url?: string;
}

interface PersonasModalProps {
  open: boolean;
  onClose: () => void;
}

export const PersonasModal: React.FC<PersonasModalProps> = ({ open, onClose }) => {
  const [tab, setTab] = useState<'cast' | 'tts'>('cast');
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [traits, setTraits] = useState('');
  const [voiceId, setVoiceId] = useState('21m00Tcm4TlvDq8ikWAM');

  useEffect(() => {
    if (!open) return;
    setError(null);
    (async () => {
      try {
        const voiceRes = await apiRequest<{ voices: VoiceInfo[] }>('/v1/audio/voices');
        setVoices(voiceRes.voices || []);
      } catch (err: any) {
        setError(err?.message || 'Could not load ElevenLabs voice catalog.');
      }
      try {
        const personaRes = await apiRequest<{ personas: PersonaInfo[] }>('/v1/personas');
        setPersonas(personaRes.personas || []);
      } catch (err: any) {
        setPersonas([]);
        setError((prev) => prev || err?.message || 'Personas API requires a signed-in account.');
      }
    })();
  }, [open]);

  const selectedVoice = voices.find((v) => v.voice_id === voiceId);

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('A persona name is required.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await apiRequest<PersonaInfo>('/v1/personas', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || null,
          voice_id: voiceId,
          voice_name: selectedVoice?.name,
          personality_traits: traits.split(',').map((t) => t.trim()).filter(Boolean),
        }),
      });
      setPersonas((prev) => [created, ...prev]);
      setName('');
      setDescription('');
      setTraits('');
    } catch (err: any) {
      setError(err?.message || 'Could not create persona.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Personas and voices">
      <div className="command-modal" style={{ width: 'min(760px, 94vw)' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Users size={16} color="#ec4899" />
            <strong>Digital Personas & Voices</strong>
          </div>
          <button className="icon-btn" onClick={onClose} title="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-nav-tabs">
          <button className={`modal-nav-tab ${tab === 'cast' ? 'active' : ''}`} onClick={() => setTab('cast')}>
            Character Cast
          </button>
          <button className={`modal-nav-tab ${tab === 'tts' ? 'active' : ''}`} onClick={() => setTab('tts')}>
            ElevenLabs Voices
          </button>
        </div>
        <div style={{ padding: 16, maxHeight: '70vh', overflowY: 'auto' }}>
          {error && (
            <div style={{ marginBottom: 12, padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>
              {error}
            </div>
          )}

          {tab === 'cast' && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
                <input className="command-input" style={{ borderBottom: '1px solid var(--border-subtle)' }} placeholder="Persona name" value={name} onChange={(e) => setName(e.target.value)} />
                <input className="command-input" placeholder="Traits (comma separated)" value={traits} onChange={(e) => setTraits(e.target.value)} />
              </div>
              <textarea className="command-input" style={{ minHeight: 64, resize: 'vertical' }} placeholder="Bio, visual cues, backstory" value={description} onChange={(e) => setDescription(e.target.value)} />
              <div style={{ margin: '10px 0' }}>
                <div className="control-label" style={{ marginBottom: 6 }}>Assigned ElevenLabs voice</div>
                <div className="voice-select-grid">
                  {voices.map((voice) => (
                    <button
                      key={voice.voice_id}
                      className={`voice-card-pill ${voiceId === voice.voice_id ? 'active' : ''}`}
                      onClick={() => setVoiceId(voice.voice_id)}
                      type="button"
                    >
                      <strong>{voice.name}</strong>
                      <span style={{ color: 'var(--text-muted)' }}>{[voice.gender, voice.accent].filter(Boolean).join(' · ')}</span>
                    </button>
                  ))}
                </div>
              </div>
              <button className="composer-submit-btn" onClick={handleCreate} disabled={busy} style={{ marginBottom: 16 }}>
                {busy ? 'Saving...' : 'Save Persona'}
              </button>
              <div className="sidebar-personas-mini-list">
                {personas.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No personas loaded. Create one above, or sign in if the personas API requires an account.</div>
                ) : (
                  personas.map((persona) => (
                    <div key={persona.id} className="persona-mini-card">
                      <div className="persona-avatar-fallback">{persona.name.slice(0, 1).toUpperCase()}</div>
                      <div className="persona-mini-info">
                        <div className="persona-mini-name">{persona.name}</div>
                        <div className="persona-mini-voice">
                          <Mic size={10} />
                          {persona.voice_name || persona.voice_id || 'No voice assigned'}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}

          {tab === 'tts' && (
            <div className="voice-select-grid" style={{ maxHeight: 'none' }}>
              {voices.map((voice) => (
                <div key={voice.voice_id} className="voice-card-pill">
                  <strong>{voice.name}</strong>
                  <span>{voice.description || [voice.gender, voice.accent].filter(Boolean).join(' · ')}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
