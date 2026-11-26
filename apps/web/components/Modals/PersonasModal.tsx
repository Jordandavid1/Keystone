'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Edit3, Mic, Trash2, Upload, Users, Volume2, X } from 'lucide-react';
import {
  apiRequest,
  createPersona,
  deletePersona,
  fetchAudioConfig,
  fetchPersonas,
  speakAsPersona,
  synthesizeSpeech,
  updatePersona,
  uploadMediaFile,
} from '../../lib/api';
import { useStudio } from '../../lib/studio/store';
import { Persona, StudioAsset } from '../../lib/types';

interface VoiceInfo {
  voice_id: string;
  name: string;
  gender?: string;
  accent?: string;
  description?: string;
}

interface PersonasModalProps {
  open: boolean;
  onClose: () => void;
  onPersonasLoaded?: (personas: Persona[]) => void;
}

export const PersonasModal: React.FC<PersonasModalProps> = ({ open, onClose, onPersonasLoaded }) => {
  const { state, dispatch } = useStudio();
  const { projectId, contentMode } = state.system;
  const activePersonaId = state.composer.personaId;

  const [tab, setTab] = useState<'cast' | 'tts'>('cast');
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Create / Edit form state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [traits, setTraits] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [voiceId, setVoiceId] = useState('');
  const voiceIdRef = useRef('');
  voiceIdRef.current = voiceId;
  const [identityAdapter, setIdentityAdapter] = useState<'reference_set' | 'ip'>('reference_set');
  const [referenceAssetIds, setReferenceAssetIds] = useState<string[]>([]);
  const [uploadingRefs, setUploadingRefs] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  // TTS / Speak state
  const [ttsText, setTtsText] = useState('');
  const [ttsUrl, setTtsUrl] = useState<string | null>(null);
  const [ttsMeta, setTtsMeta] = useState('');
  const [ttsWarning, setTtsWarning] = useState<string | null>(null);
  const [ttsStatus, setTtsStatus] = useState('Voices load live from /v1/audio/voices.');
  const [stability, setStability] = useState(0.5);
  const [clarity, setClarity] = useState(0.75);
  const [ttsPersonaId, setTtsPersonaId] = useState('');

  const resetForm = useCallback(() => {
    setEditingId(null);
    setName('');
    setDescription('');
    setTraits('');
    setSystemPrompt('');
    setReferenceAssetIds([]);
  }, []);

  const reloadPersonas = useCallback(async () => {
    try {
      const list = await fetchPersonas({ projectId, contentMode });
      setPersonas(list);
      dispatch({ type: 'SYSTEM', patch: { personas: list, personasError: null } });
      onPersonasLoaded?.(list);
    } catch (err: any) {
      setPersonas([]);
      onPersonasLoaded?.([]);
      setError((prev) => prev || err?.message || 'Personas API requires a signed-in account.');
    }
  }, [contentMode, dispatch, onPersonasLoaded, projectId]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setNotice(null);
    (async () => {
      try {
        const voiceRes = await apiRequest<{ voices: VoiceInfo[] }>('/v1/audio/voices');
        const list = voiceRes.voices || [];
        setVoices(list);
        if (!voiceIdRef.current && list[0]?.voice_id) {
          setVoiceId(list[0].voice_id);
        }
        try {
          const cfg = await fetchAudioConfig();
          setTtsStatus(
            cfg?.configured
              ? `Provider: ${cfg.provider || 'elevenlabs'} · configured`
              : `Provider: ${cfg?.provider || 'unconfigured'} · configure ElevenLabs key or local SAPI`,
          );
        } catch (cfgErr: any) {
          setTtsStatus(cfgErr?.message || 'Could not load audio config.');
        }
      } catch (err: any) {
        setError(err?.message || 'Could not load voice catalog.');
      }
      await reloadPersonas();
    })();
  }, [open, reloadPersonas]);

  const selectedVoice = voices.find((v) => v.voice_id === voiceId);

  const handleDirectRefUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadingRefs(true);
    setError(null);
    try {
      const added: StudioAsset[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith('image/')) continue;
        const asset = await uploadMediaFile(file, projectId);
        added.push(asset);
      }
      if (added.length > 0) {
        dispatch({ type: 'ASSETS_ADDED', assets: added, select: false });
        setReferenceAssetIds((prev) => Array.from(new Set([...prev, ...added.map((a) => a.id)])));
        setNotice(`Uploaded and attached ${added.length} reference anchor photo${added.length > 1 ? 's' : ''}.`);
      }
    } catch (err: any) {
      setError(err?.message || 'Could not upload reference image.');
    } finally {
      setUploadingRefs(false);
    }
  };

  const handleSavePersona = async () => {
    if (!name.trim()) {
      setError('A persona name is required.');
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim() || null,
        project_id: projectId,
        avatar_asset_id: referenceAssetIds[0] || null,
        identity_adapter: identityAdapter,
        voice_id: voiceId || null,
        voice_name: selectedVoice?.name || null,
        voice_settings: { stability, similarity_boost: clarity },
        personality_traits: traits.split(',').map((t) => t.trim()).filter(Boolean),
        system_prompt: systemPrompt.trim() || null,
        reference_assets: referenceAssetIds,
      };
      if (editingId) {
        const updated = await updatePersona(editingId, payload);
        const next = personas.map((p) => (p.id === editingId ? updated : p));
        setPersonas(next);
        dispatch({ type: 'SYSTEM', patch: { personas: next } });
        onPersonasLoaded?.(next);
        setNotice(`Saved ${updated.name} (v${updated.version ?? 1}).`);
      } else {
        const created = await createPersona(payload);
        const next = [created, ...personas];
        setPersonas(next);
        dispatch({ type: 'SYSTEM', patch: { personas: next } });
        dispatch({ type: 'SET_PERSONA', personaId: created.id });
        onPersonasLoaded?.(next);
        setNotice(`Created ${created.name} (v${created.version ?? 1}) and cast into active composer.`);
      }
      resetForm();
    } catch (err: any) {
      setError(err?.message || 'Could not save persona.');
    } finally {
      setBusy(false);
    }
  };

  const handleStartEdit = async (persona: Persona) => {
    setError(null);
    setNotice(null);
    try {
      const qs = contentMode ? `?content_mode=${encodeURIComponent(contentMode)}` : '';
      const res = await apiRequest<any>(`/v1/personas/${encodeURIComponent(persona.id)}${qs}`);
      const detail: Persona = res.persona ?? res;
      setEditingId(detail.id);
      setName(detail.name || '');
      setDescription(detail.description || '');
      setTraits((detail.personality_traits || []).join(', '));
      setSystemPrompt(detail.system_prompt || '');
      setVoiceId(detail.voice_id || voiceId || '');
      setReferenceAssetIds(detail.reference_assets || []);
    } catch {
      setEditingId(persona.id);
      setName(persona.name || '');
      setDescription(persona.description || '');
      setTraits((persona.personality_traits || []).join(', '));
      setSystemPrompt(persona.system_prompt || '');
      if (persona.voice_id) setVoiceId(persona.voice_id);
      setReferenceAssetIds(persona.reference_assets || []);
    }
  };

  const handleDelete = async (persona: Persona) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await deletePersona(persona.id);
      const next = personas.filter((p) => p.id !== persona.id);
      setPersonas(next);
      onPersonasLoaded?.(next);
      if (activePersonaId === persona.id) {
        dispatch({ type: 'SET_PERSONA', personaId: null });
      }
      if (editingId === persona.id) resetForm();
      setNotice(`Archived persona "${persona.name}". Historical depicts lineage remains intact.`);
    } catch (err: any) {
      setError(err?.message || 'Could not delete persona.');
    } finally {
      setBusy(false);
    }
  };

  const handleBindVoiceOnly = async (persona: Persona) => {
    if (!voiceId) {
      setError('Select a voice first to bind it.');
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updatePersona(persona.id, {
        voice_id: voiceId,
        voice_name: selectedVoice?.name || voiceId,
        voice_settings: { stability, similarity_boost: clarity },
      });
      const next = personas.map((p) => (p.id === persona.id ? updated : p));
      setPersonas(next);
      onPersonasLoaded?.(next);
      setNotice(`Bound voice "${updated.voice_name || voiceId}" to ${updated.name} (v${updated.version ?? 1}).`);
    } catch (err: any) {
      setError(err?.message || 'Could not bind voice.');
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
    setTtsWarning(null);
    setTtsUrl(null);
    try {
      if (ttsPersonaId) {
        const result = await speakAsPersona(ttsPersonaId, {
          text: ttsText.trim(),
          voice_id: voiceId || undefined,
          voice_settings: { stability, similarity_boost: clarity },
          project_id: projectId,
        });
        const audioUrl = result.audio_url || result.download_url;
        if (!audioUrl) throw new Error('Persona speak returned no audio URL.');
        if (result.warning) setTtsWarning(result.warning);
        setTtsUrl(audioUrl);
        setTtsMeta(`Asset ${result.asset_id?.slice(0, 8) || ''} · Voice: ${result.voice_used || 'default'}`);
        const newAsset: StudioAsset = {
          id: result.asset_id,
          title: `Speak: ${ttsText.trim().slice(0, 28)}`,
          type: 'audio',
          url: audioUrl,
          downloadUrl: audioUrl,
          projectId,
          personaId: result.persona_id || ttsPersonaId,
          personaVersion: result.persona_version ?? null,
          mature: Boolean(result.mature),
          createdAt: Date.now(),
        };
        dispatch({ type: 'ASSETS_ADDED', assets: [newAsset], select: false });
      } else {
        const result = await synthesizeSpeech({
          text: ttsText.trim(),
          voice_id: voiceId || undefined,
          voice_settings: { stability, similarity_boost: clarity },
          project_id: projectId,
          save_asset: true,
        });
        if (!result?.download_url) {
          throw new Error('Audio API returned no download URL.');
        }
        setTtsUrl(result.download_url);
        setTtsMeta(`${result.mime_type || 'audio'} · ${result.byte_size ? `${result.byte_size} bytes` : 'saved asset'} · ${result.provider || 'elevenlabs'}`);
        if (result.asset_id) {
          dispatch({
            type: 'ASSETS_ADDED',
            assets: [
              {
                id: result.asset_id,
                title: `Speech: ${ttsText.trim().slice(0, 28)}`,
                type: 'audio',
                url: result.download_url,
                downloadUrl: result.download_url,
                mimeType: result.mime_type,
                byteSize: result.byte_size,
                projectId,
                createdAt: Date.now(),
              },
            ],
            select: false,
          });
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Speech synthesis failed.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  const imageAssets = state.library.assets.filter((a) => a.type === 'image').slice(0, 12);

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Personas and voices">
      <div className="command-modal" style={{ width: 'min(780px, 95vw)' }} onClick={(e) => e.stopPropagation()}>
        <div className="chat-top-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Users size={16} color="#ec4899" />
            <strong>Digital Personas &amp; Voices</strong>
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
            Speak &amp; Voice Synthesis
          </button>
        </div>
        <div style={{ padding: 16, maxHeight: '72vh', overflowY: 'auto' }}>
          {error && (
            <div role="alert" style={{ marginBottom: 12, padding: 10, borderRadius: 8, border: '1px solid rgba(244,63,94,0.4)', color: '#fda4af', fontSize: 12 }}>
              {error}
            </div>
          )}
          {notice && (
            <div style={{ marginBottom: 12, padding: 10, borderRadius: 8, border: '1px solid rgba(16,185,129,0.4)', color: '#86efac', fontSize: 12 }}>
              {notice}
            </div>
          )}

          {tab === 'cast' && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700 }}>
                  {editingId ? 'Edit Persona (creates new immutable version)' : 'Create New Persona'}
                </span>
                {editingId && (
                  <button type="button" className="icon-btn" onClick={resetForm}>
                    Cancel edit
                  </button>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <input
                  className="command-input"
                  style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  placeholder="Persona name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <input
                  className="command-input"
                  placeholder="Traits (comma separated)"
                  value={traits}
                  onChange={(e) => setTraits(e.target.value)}
                />
              </div>
              <textarea
                className="command-input"
                style={{ minHeight: 56, resize: 'vertical', marginBottom: 8 }}
                placeholder="Visual sheet, appearance cues, backstory"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <input
                  className="command-input"
                  placeholder="Dedicated system / style prompt instructions (optional)"
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                />
                <select
                  aria-label="Identity conditioning adapter"
                  className="command-input"
                  value={identityAdapter}
                  onChange={(e) => setIdentityAdapter(e.target.value as 'reference_set' | 'ip')}
                  style={{ background: 'var(--bg-surface-3)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px' }}
                >
                  <option value="reference_set">Multi-Angle Reference Sheet Lock (H3 + Studio)</option>
                  <option value="ip">Deep Face / IP-Adapter Identity Lock</option>
                </select>
              </div>

              <div style={{ marginBottom: 12, padding: 12, borderRadius: 8, border: '1px dashed var(--border-subtle)', background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <span className="control-label">
                    Multi-Angle Identity Reference Photos ({referenceAssetIds.length} selected — front face, profile, body)
                  </span>
                  <button
                    type="button"
                    disabled={uploadingRefs}
                    onClick={() => uploadInputRef.current?.click()}
                    className="icon-btn"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, borderColor: '#6366f1', color: '#c7d2fe' }}
                  >
                    <Upload size={12} /> {uploadingRefs ? 'Uploading...' : 'Upload Reference Photos'}
                  </button>
                </div>
                <input
                  ref={uploadInputRef}
                  type="file"
                  hidden
                  multiple
                  accept="image/*"
                  onChange={(e) => {
                    void handleDirectRefUpload(e.target.files);
                    e.target.value = '';
                  }}
                />
                {imageAssets.length > 0 ? (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {imageAssets.map((a) => {
                      const picked = referenceAssetIds.includes(a.id);
                      return (
                        <button
                          key={a.id}
                          type="button"
                          onClick={() =>
                            setReferenceAssetIds((prev) => (picked ? prev.filter((x) => x !== a.id) : [...prev, a.id]))
                          }
                          style={{
                            border: picked ? '2px solid #6366f1' : '1px solid var(--border-subtle)',
                            borderRadius: 6,
                            padding: 2,
                            background: 'transparent',
                            cursor: 'pointer',
                          }}
                          title={a.title}
                        >
                          <img src={a.previewUrl || a.url} alt={a.title} style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4 }} />
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                    Upload 1–4 character reference photos directly using the button above to lock facial likeness and physique across generations.
                  </div>
                )}
              </div>

              <div style={{ margin: '10px 0' }}>
                <div className="control-label" style={{ marginBottom: 6 }}>Bind Voice</div>
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

              <button className="composer-submit-btn" onClick={handleSavePersona} disabled={busy} style={{ marginBottom: 16 }}>
                {busy ? 'Saving...' : editingId ? 'Save New Version' : 'Create Persona'}
              </button>

              <div className="sidebar-personas-mini-list">
                {personas.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    No personas visible in {contentMode.toUpperCase()} mode. Create one above.
                  </div>
                ) : (
                  personas.map((persona) => {
                    const isActive = activePersonaId === persona.id;
                    return (
                      <div key={persona.id} className="persona-mini-card" style={{ justifyContent: 'space-between', gap: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                          {persona.avatar_url ? (
                            <img
                              src={persona.avatar_url}
                              alt={persona.name}
                              style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover', flexShrink: 0 }}
                            />
                          ) : (
                            <div className="persona-avatar-fallback">{(persona.name || '?').slice(0, 1).toUpperCase()}</div>
                          )}
                          <div className="persona-mini-info" style={{ minWidth: 0 }}>
                            <div className="persona-mini-name" style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                              <span>{persona.name}</span>
                              <span className="stage-chip" style={{ fontSize: 10, padding: '1px 6px' }}>
                                v{persona.version ?? 1}
                              </span>
                              {persona.mature && (
                                <span className="stage-chip" style={{ fontSize: 10, padding: '1px 6px', color: '#fbbf24' }}>
                                  18+
                                </span>
                              )}
                            </div>
                            <div className="persona-mini-voice">
                              <Mic size={10} />
                              {persona.voice_name || persona.voice_id || 'No voice bound'}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                          <button
                            type="button"
                            className="icon-btn"
                            onClick={() => dispatch({ type: 'SET_PERSONA', personaId: isActive ? null : persona.id })}
                            title="Cast this persona (`as: persona_id`) in the composer"
                            style={isActive ? { borderColor: '#6366f1', color: '#a5b4fc' } : undefined}
                          >
                            <Check size={12} />
                            <span>{isActive ? 'Active (`as`)' : 'Use `as`'}</span>
                          </button>
                          <button
                            type="button"
                            className="icon-btn"
                            onClick={() => void handleBindVoiceOnly(persona)}
                            title="Bind currently selected voice to this persona"
                          >
                            <Volume2 size={12} />
                          </button>
                          <button
                            type="button"
                            className="icon-btn"
                            onClick={() => {
                              setTtsPersonaId(persona.id);
                              if (persona.voice_id) setVoiceId(persona.voice_id);
                              setTab('tts');
                            }}
                            title="Speak with this persona"
                          >
                            Speak
                          </button>
                          <button type="button" className="icon-btn" onClick={() => void handleStartEdit(persona)} title="Edit / Create new version">
                            <Edit3 size={12} />
                          </button>
                          <button type="button" className="icon-btn" onClick={() => void handleDelete(persona)} title="Soft-delete persona">
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          )}

          {tab === 'tts' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{ttsStatus}</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                    Character Persona (routes via `/v1/personas/{'{id}'}/speak`)
                  </label>
                  <select
                    className="command-input"
                    value={ttsPersonaId}
                    onChange={(e) => {
                      setTtsPersonaId(e.target.value);
                      const persona = personas.find((item) => item.id === e.target.value);
                      if (persona?.voice_id) setVoiceId(persona.voice_id);
                    }}
                    style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)' }}
                  >
                    <option value="">Standalone Voice (No Persona)</option>
                    {personas.map((persona) => (
                      <option key={persona.id} value={persona.id}>
                        {persona.name} (v{persona.version ?? 1})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                    Voice Profile
                  </label>
                  <select
                    className="command-input"
                    value={voiceId}
                    onChange={(e) => setVoiceId(e.target.value)}
                    style={{ border: '1px solid var(--border-subtle)', borderRadius: 6, padding: '6px 10px', width: '100%', background: 'var(--bg-surface-3)', color: 'var(--text-primary)' }}
                  >
                    {voices.map((voice) => (
                      <option key={voice.voice_id} value={voice.voice_id}>
                        {voice.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <textarea
                className="composer-textarea"
                value={ttsText}
                onChange={(e) => setTtsText(e.target.value)}
                placeholder="Type narration, character dialogue, or monologue to synthesize..."
                style={{ minHeight: 85, border: '1px solid var(--border-subtle)', borderRadius: 8, fontSize: 13 }}
              />
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
              {ttsWarning && (
                <div style={{ padding: 10, borderRadius: 8, border: '1px solid rgba(245,158,11,0.4)', color: '#fbbf24', fontSize: 12 }}>
                  {ttsWarning}
                </div>
              )}
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
