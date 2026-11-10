'use client';

import React, { useEffect, useState } from 'react';
import { X, Users, Mic } from 'lucide-react';
import { apiRequest, fetchAudioConfig, synthesizeSpeech } from '../../lib/api';

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
  onPersonasLoaded?: (personas: PersonaInfo[]) => void;
}

export const PersonasModal: React.FC<PersonasModalProps> = ({ open, onClose, onPersonasLoaded }) => {
  const [tab, setTab] = useState<'cast' | 'tts'>('cast');
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [traits, setTraits] = useState('');
  const [voiceId, setVoiceId] = useState('21m00Tcm4TlvDq8ikWAM');
  const [ttsText, setTtsText] = useState('');
  const [ttsUrl, setTtsUrl] = useState<string | null>(null);
  const [ttsMeta, setTtsMeta] = useState('');
  const [ttsStatus, setTtsStatus] = useState('ElevenLabs voices load from /v1/audio/voices.');
  const [stability, setStability] = useState(0.5);
  const [clarity, setClarity] = useState(0.75);
  const [ttsPersonaId, setTtsPersonaId] = useState('');

  useEffect(() => {
    if (!open) return;
    setError(null);
    (async () => {
      try {
        const voiceRes = await apiRequest<{ voices: VoiceInfo[] }>('/v1/audio/voices');
        setVoices(voiceRes.voices || []);
        try {
          const cfg = await fetchAudioConfig();
          setTtsStatus(
            cfg?.configured
              ? `Provider: ${cfg.provider || 'elevenlabs'} · configured`
              : `Provider: ${cfg?.provider || 'unconfigured'} · synthesis needs a configured ElevenLabs key and a reachable audio API`
          );
        } catch (cfgErr: any) {
          setTtsStatus(cfgErr?.message || 'Could not load audio config.');
        }
      } catch (err: any) {
        setError(err?.message || 'Could not load ElevenLabs voice catalog.');
      }
      try {
        const personaRes = await apiRequest<{ personas: PersonaInfo[] }>('/v1/personas');
        const list = personaRes.personas || [];
        setPersonas(list);
        onPersonasLoaded?.(list);
      } catch (err: any) {
        setPersonas([]);
        onPersonasLoaded?.([]);
        setError((prev) => prev || err?.message || 'Personas API requires a signed-in account.');
      }
    })();
  }, [open, onPersonasLoaded]);

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
      const next = [created, ...personas];
      setPersonas(next);
      onPersonasLoaded?.(next);
      setName('');
      setDescription('');
      setTraits('');
    } catch (err: any) {
      setError(err?.message || 'Could not create persona.');
    } finally {
      setBusy(false);
    }
  };

  const handleSynthesize = async () => {
    if (!ttsText.trim()) {
      setError('Dialogue text is required to synthesize speech.');
      return;
    }
    setBusy(true);
    setError(null);
    setTtsUrl(null);
    try {
      const chosenPersona = personas.find((persona) => persona.id === ttsPersonaId);
      const result = await synthesizeSpeech({
        text: ttsText.trim(),
        voice_id: chosenPersona?.voice_id || voiceId,
        voice_settings: { stability, similarity_boost: clarity },
        save_asset: true,
      });
      if (!result?.download_url) {
        throw new Error('Audio API returned no download URL.');
      }
      setTtsUrl(result.download_url);
      setTtsMeta(`${result.mime_type || 'audio'} · ${result.byte_size ? `${result.byte_size} bytes` : 'saved asset'} · ${result.provider || 'elevenlabs'}`);
    } catch (err: any) {
      setError(err?.message || 'Speech synthesis failed. A signed-in account and configured ElevenLabs key are required.');
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
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ttsStatus}</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Select Character Persona (Optional)</label>
                  <select className="command-input" value={ttsPersonaId} onChange={(e) => {
                    setTtsPersonaId(e.target.value);
                    const persona = personas.find((item) => item.id === e.target.value);
                    if (persona?.voice_id) setVoiceId(persona.voice_id);
                  }} style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)' }}>
                    <option value="">Standalone Voice (No Persona)</option>
                    {personas.map((persona) => (
                      <option key={persona.id} value={persona.id}>{persona.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>ElevenLabs Voice Profile</label>
                  <select className="command-input" value={voiceId} onChange={(e) => setVoiceId(e.target.value)} style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)' }}>
                    {voices.map((voice) => (
                      <option key={voice.voice_id} value={voice.voice_id}>{voice.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <textarea className="composer-textarea" value={ttsText} onChange={(e) => setTtsText(e.target.value)} placeholder="Type narration, character dialogue, or cinematic monologue to synthesize with ElevenLabs..." style={{ minHeight: 85, border: '1px solid var(--border-subtle)', borderRadius: 8, fontSize: 13 }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                  <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    Stability: {stability.toFixed(2)}
                    <input type="range" min={0} max={1} step={0.05} value={stability} onChange={(e) => setStability(Number(e.target.value))} />
                  </label>
                  <label style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                    Clarity: {clarity.toFixed(2)}
                    <input type="range" min={0} max={1} step={0.05} value={clarity} onChange={(e) => setClarity(Number(e.target.value))} />
                  </label>
                </div>
                <button className="composer-submit-btn" onClick={handleSynthesize} disabled={busy}>
                  {busy ? 'Synthesizing...' : 'Synthesize Speech Audio'}
                </button>
              </div>
              {ttsUrl && (
                <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: 8, padding: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: '#ec4899', marginBottom: 8 }}>{ttsMeta || 'Generated Speech Track'}</div>
                  <audio controls src={ttsUrl} style={{ width: '100%', height: 36 }} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
