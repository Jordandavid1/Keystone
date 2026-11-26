'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Camera, Check, Dna, Mic, Plus, Sparkles, Trash2, Upload, UserCheck, Users } from 'lucide-react';
import {
  createPersona,
  deletePersona,
  fetchAudioVoices,
  fetchPersonas,
  uploadMediaFile,
} from '@/lib/api';
import { readableError } from '@/lib/errors';
import { useStudio } from '@/lib/studio/store';
import { Persona, StudioAsset } from '@/lib/types';
import { cn } from '@/lib/utils';
import { SignedOutNote } from '../auth/SignedOutNote';
import { PanelHeader, PanelNote } from './PanelHeader';

/**
 * First-Class Character & Identity Persona Panel (Bible v2 §25 & §41).
 * Enables customers to build multi-angle reference-locked personas (face, profile, body, wardrobe, voice)
 * and cast them directly (`as: persona_id`) into MiniMax-H3 video, photoshoot, and image runs.
 */
export function PersonasPanel() {
  const { state, dispatch } = useStudio();
  const { personas, personasError, projectId, contentMode, session } = state.system;
  const activePersonaId = state.composer.personaId;
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [creating, setCreating] = useState(personas.length === 0);
  const [name, setName] = useState('');
  const [identityAdapter, setIdentityAdapter] = useState<'reference_set' | 'ip'>('reference_set');
  const [physicalBuild, setPhysicalBuild] = useState('');
  const [hairEyesSkin, setHairEyesSkin] = useState('');
  const [wardrobeStyle, setWardrobeStyle] = useState('');
  const [bioNotes, setBioNotes] = useState('');
  const [voiceId, setVoiceId] = useState('');
  const [voices, setVoices] = useState<{ voice_id: string; name: string }[]>([]);
  const [uploadedRefs, setUploadedRefs] = useState<StudioAsset[]>([]);
  const [selectedLibraryRefIds, setSelectedLibraryRefIds] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    fetchAudioVoices()
      .then((list) => {
        setVoices(list || []);
        if (list?.[0]?.voice_id) setVoiceId((prev) => prev || list[0].voice_id);
      })
      .catch(() => undefined);
  }, []);

  const libraryImages = state.library.assets.filter((a) => a.type === 'image').slice(0, 12);
  const allRefIds = Array.from(new Set([...uploadedRefs.map((a) => a.id), ...selectedLibraryRefIds]));

  const handleUploadAnchorFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
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
        setUploadedRefs((prev) => [...prev, ...added]);
        setNotice(`Uploaded ${added.length} identity reference photo${added.length > 1 ? 's' : ''}.`);
      }
    } catch (err) {
      setError(readableError(err));
    } finally {
      setUploading(false);
    }
  };

  const handleCreatePersona = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Enter a character / persona name.');
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const visualParts = [
        physicalBuild.trim() ? `Build & facial structure: ${physicalBuild.trim()}` : '',
        hairEyesSkin.trim() ? `Hair, eyes & complexion: ${hairEyesSkin.trim()}` : '',
        wardrobeStyle.trim() ? `Signature wardrobe & aesthetic: ${wardrobeStyle.trim()}` : '',
        bioNotes.trim() ? `Character notes: ${bioNotes.trim()}` : '',
      ].filter(Boolean);

      const compiledSheet = visualParts.join(' | ') || `${name.trim()} consistent character identity`;
      const chosenVoice = voices.find((v) => v.voice_id === voiceId);

      const created = await createPersona({
        name: name.trim(),
        description: compiledSheet,
        project_id: projectId,
        avatar_asset_id: allRefIds[0] || null,
        reference_assets: allRefIds,
        identity_adapter: identityAdapter,
        voice_id: voiceId || null,
        voice_name: chosenVoice?.name || null,
        personality_traits: [physicalBuild, hairEyesSkin, wardrobeStyle]
          .map((s) => s.trim())
          .filter(Boolean),
        metadata: {
          physical_build: physicalBuild.trim() || null,
          hair_eyes_skin: hairEyesSkin.trim() || null,
          signature_wardrobe: wardrobeStyle.trim() || null,
          anchor_count: allRefIds.length,
        },
        mature: contentMode === 'unrestricted',
      });

      const refreshed = await fetchPersonas({ projectId, contentMode }).catch(() => [created, ...personas]);
      dispatch({ type: 'SYSTEM', patch: { personas: refreshed, personasError: null } });
      dispatch({ type: 'SET_PERSONA', personaId: created.id });

      setName('');
      setPhysicalBuild('');
      setHairEyesSkin('');
      setWardrobeStyle('');
      setBioNotes('');
      setUploadedRefs([]);
      setSelectedLibraryRefIds([]);
      setCreating(false);
      setNotice(`Created "${created.name}" (v${created.version ?? 1}) and cast into active composer.`);
    } catch (err) {
      setError(readableError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleCastPersona = (persona: Persona, attachRefs: boolean) => {
    const isSame = activePersonaId === persona.id && !attachRefs;
    dispatch({ type: 'SET_PERSONA', personaId: isSame ? null : persona.id });
    if (attachRefs && persona.reference_assets?.length) {
      const matchingAssets = state.library.assets.filter((a) => persona.reference_assets?.includes(a.id));
      matchingAssets.slice(0, 3).forEach((asset) => dispatch({ type: 'ADD_REFERENCE', asset }));
      setNotice(`Cast "${persona.name}" and attached ${matchingAssets.length || persona.reference_assets.length} reference anchor(s).`);
    }
  };

  const handleDeletePersona = async (persona: Persona) => {
    try {
      await deletePersona(persona.id);
      const next = personas.filter((p) => p.id !== persona.id);
      dispatch({ type: 'SYSTEM', patch: { personas: next } });
      if (activePersonaId === persona.id) {
        dispatch({ type: 'SET_PERSONA', personaId: null });
      }
    } catch (err) {
      setError(readableError(err));
    }
  };

  return (
    <div className="flex flex-col gap-3 pb-6">
      <PanelHeader title="Character Personas">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setCreating((v) => !v)}
            className="inline-flex items-center gap-1 rounded-control bg-ks-indigo/20 px-2 py-0.5 text-micro font-semibold text-ks-ink hover:bg-ks-indigo/30"
          >
            <Plus className="size-3" /> {creating ? 'Close' : 'New'}
          </button>
          <button
            type="button"
            onClick={() => dispatch({ type: 'OPEN_MODAL', modal: 'personas' })}
            className="text-micro text-ks-ink-3 hover:text-ks-ink"
          >
            Voice Studio
          </button>
        </div>
      </PanelHeader>

      <PanelNote>
        Build multi-angle identity-locked characters (front, profile, body, wardrobe &amp; voice) and reference them across every image and MiniMax-H3 video generation.
      </PanelNote>

      {session.status !== 'signed_in' ? (
        <SignedOutNote what="persona creation & identity lock" compact />
      ) : (
        <>
          {error && (
            <div className="mx-3 rounded-control border border-rose-500/40 bg-rose-500/10 px-2.5 py-2 text-micro text-rose-300">
              {error}
            </div>
          )}
          {notice && (
            <div className="mx-3 rounded-control border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-2 text-micro text-emerald-300">
              {notice}
            </div>
          )}

          {/* Shortcut to synthesize a brand-new face via Parametric Face Synthesizer */}
          <div className="mx-3 flex items-center justify-between gap-2 rounded-control border border-ks-line bg-ks-raised/50 px-2.5 py-2">
            <span className="text-micro text-ks-ink-2">Need a fresh anchor face first?</span>
            <button
              type="button"
              onClick={() => {
                dispatch({ type: 'SET_TOOL', tool: 'facegen' });
                dispatch({ type: 'SET_PANEL', panel: 'create' });
              }}
              className="inline-flex items-center gap-1 rounded border border-ks-line-strong bg-ks-lift px-2 py-0.5 text-micro font-medium text-ks-ink hover:border-ks-indigo"
            >
              <Dna className="size-3 text-ks-indigo" /> Synthesize Face
            </button>
          </div>

          {/* Inline High-Caliber Persona Builder */}
          {creating && (
            <form
              onSubmit={(e) => void handleCreatePersona(e)}
              className="mx-3 flex flex-col gap-2.5 rounded-panel border border-ks-indigo/40 bg-ks-abyss/80 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-meta font-semibold text-ks-ink">Create Identity-Locked Persona</span>
                <span className="text-micro text-ks-ink-3">{contentMode === 'unrestricted' ? '18+ Mode' : 'SFW Mode'}</span>
              </div>

              <input
                aria-label="Persona name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Character name (e.g. Aria Vance)"
                className="h-8 w-full rounded-control border border-ks-line-strong bg-ks-raised px-2.5 text-meta text-ks-ink"
              />

              <div>
                <label className="mb-1 block text-micro text-ks-ink-3">Identity Lock Conditioning</label>
                <select
                  aria-label="Identity lock mode"
                  value={identityAdapter}
                  onChange={(e) => setIdentityAdapter(e.target.value as 'reference_set' | 'ip')}
                  className="h-8 w-full rounded-control border border-ks-line-strong bg-ks-raised px-2 text-micro text-ks-ink"
                >
                  <option value="reference_set">Multi-Angle Reference Sheet Lock (H3 + Studio)</option>
                  <option value="ip">Deep Face / IP-Adapter Identity Lock</option>
                </select>
              </div>

              {/* Multi-Angle Reference Upload */}
              <div className="rounded-control border border-dashed border-ks-line-strong bg-ks-raised/40 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-micro font-medium text-ks-ink-2">
                    Reference Photos ({allRefIds.length} attached)
                  </span>
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center gap-1 rounded bg-ks-indigo/25 px-2 py-1 text-micro font-semibold text-ks-ink hover:bg-ks-indigo/40"
                  >
                    <Upload className="size-3" /> {uploading ? 'Uploading…' : 'Upload Photos'}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-ks-ink-3">
                  Upload 1–4 clear shots (front face, 45° angle, full body) for consistent likeness.
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  hidden
                  multiple
                  accept="image/*"
                  onChange={(e) => {
                    void handleUploadAnchorFiles(e.target.files);
                    e.target.value = '';
                  }}
                />

                {uploadedRefs.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {uploadedRefs.map((a) => (
                      <img
                        key={a.id}
                        src={a.previewUrl || a.url}
                        alt={a.title}
                        className="size-10 rounded border border-ks-indigo object-cover"
                      />
                    ))}
                  </div>
                )}

                {libraryImages.length > 0 && (
                  <div className="mt-2 border-t border-ks-line pt-2">
                    <span className="mb-1 block text-[10px] text-ks-ink-3">Or pick from project library:</span>
                    <div className="flex flex-wrap gap-1">
                      {libraryImages.map((img) => {
                        const on = selectedLibraryRefIds.includes(img.id);
                        return (
                          <button
                            key={img.id}
                            type="button"
                            onClick={() =>
                              setSelectedLibraryRefIds((prev) =>
                                on ? prev.filter((x) => x !== img.id) : [...prev, img.id],
                              )
                            }
                            className={cn(
                              'rounded p-0.5 transition-all',
                              on ? 'ring-2 ring-ks-indigo' : 'opacity-70 hover:opacity-100',
                            )}
                          >
                            <img src={img.previewUrl || img.url} alt={img.title} className="size-8 rounded object-cover" />
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              <input
                type="text"
                value={physicalBuild}
                onChange={(e) => setPhysicalBuild(e.target.value)}
                placeholder="Age, origin, build & jawline (e.g. 26yo Mediterranean, athletic)"
                className="h-7 w-full rounded-control border border-ks-line bg-ks-raised px-2 text-micro text-ks-ink"
              />
              <input
                type="text"
                value={hairEyesSkin}
                onChange={(e) => setHairEyesSkin(e.target.value)}
                placeholder="Hair, eyes & skin details (e.g. raven waves, emerald eyes)"
                className="h-7 w-full rounded-control border border-ks-line bg-ks-raised px-2 text-micro text-ks-ink"
              />
              <input
                type="text"
                value={wardrobeStyle}
                onChange={(e) => setWardrobeStyle(e.target.value)}
                placeholder="Signature wardrobe / style look"
                className="h-7 w-full rounded-control border border-ks-line bg-ks-raised px-2 text-micro text-ks-ink"
              />
              <textarea
                value={bioNotes}
                onChange={(e) => setBioNotes(e.target.value)}
                placeholder="Extra camera, lighting, or persona directives..."
                rows={2}
                className="w-full rounded-control border border-ks-line bg-ks-raised p-2 text-micro text-ks-ink"
              />

              {voices.length > 0 && (
                <div>
                  <label className="mb-1 block text-micro text-ks-ink-3">Bound Voice Profile</label>
                  <select
                    aria-label="Persona voice"
                    value={voiceId}
                    onChange={(e) => setVoiceId(e.target.value)}
                    className="h-7 w-full rounded-control border border-ks-line bg-ks-raised px-2 text-micro text-ks-ink"
                  >
                    {voices.map((v) => (
                      <option key={v.voice_id} value={v.voice_id}>
                        {v.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <button
                type="submit"
                disabled={saving || uploading}
                className="mt-1 flex h-8 w-full items-center justify-center gap-1.5 rounded-control bg-ks-indigo text-meta font-semibold text-white hover:bg-ks-indigo/90 disabled:opacity-50"
              >
                <Sparkles className="size-3.5" />
                {saving ? 'Creating Persona…' : 'Create & Cast Persona'}
              </button>
            </form>
          )}

          {/* Active Cast List */}
          <div className="flex flex-col gap-2 px-3">
            {personasError ? (
              <PanelNote tone="error">Personas error: {personasError}</PanelNote>
            ) : personas.length === 0 ? (
              <PanelNote>No personas created yet. Use the builder above to create your first character.</PanelNote>
            ) : (
              personas.map((p) => {
                const active = activePersonaId === p.id;
                const refCount = p.reference_assets?.length || 0;
                return (
                  <div
                    key={p.id}
                    className={cn(
                      'rounded-panel border p-2.5 transition-colors',
                      active
                        ? 'border-ks-indigo bg-ks-indigo/15'
                        : 'border-ks-line bg-ks-raised/40 hover:border-ks-line-strong',
                    )}
                  >
                    <div className="flex items-start gap-2.5">
                      {p.avatar_url ? (
                        <img src={p.avatar_url} alt={p.name} className="size-10 shrink-0 rounded-full object-cover ring-1 ring-ks-line-strong" />
                      ) : (
                        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-ks-lift text-body font-bold text-ks-ink">
                          {(p.name || '?').slice(0, 1).toUpperCase()}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate text-body font-semibold text-ks-ink">{p.name}</span>
                          <span className="rounded border border-ks-line-strong px-1 text-[10px] text-ks-ink-3">
                            v{p.version ?? 1}
                          </span>
                          {p.mature && (
                            <span className="rounded border border-amber-500/40 bg-amber-500/10 px-1 text-[10px] text-amber-300">
                              18+
                            </span>
                          )}
                        </div>
                        {p.description && (
                          <p className="mt-0.5 line-clamp-2 text-micro text-ks-ink-2">{p.description}</p>
                        )}
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-ks-ink-3">
                          <span className="inline-flex items-center gap-1">
                            <Camera className="size-2.5" /> {refCount} ref{refCount === 1 ? '' : 's'} ({p.identity_adapter || 'reference_set'})
                          </span>
                          <span className="inline-flex items-center gap-1">
                            <Mic className="size-2.5" /> {p.voice_name || 'No voice'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="mt-2.5 flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleCastPersona(p, false)}
                        className={cn(
                          'flex h-7 flex-1 items-center justify-center gap-1 rounded-control text-micro font-semibold transition-colors',
                          active
                            ? 'bg-ks-indigo text-white'
                            : 'border border-ks-line-strong bg-ks-lift text-ks-ink hover:border-ks-indigo',
                        )}
                      >
                        {active ? <Check className="size-3" /> : <UserCheck className="size-3" />}
                        {active ? 'Active in Composer' : 'Cast (`as`)'}
                      </button>
                      {refCount > 0 && (
                        <button
                          type="button"
                          onClick={() => handleCastPersona(p, true)}
                          title="Cast persona and attach anchor photos into composer"
                          className="h-7 rounded-control border border-ks-line-strong bg-ks-abyss px-2 text-micro text-ks-ink-2 hover:text-ks-ink"
                        >
                          + Load Refs
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => void handleDeletePersona(p)}
                        title="Archive persona"
                        className="flex size-7 items-center justify-center rounded-control text-ks-ink-3 hover:bg-rose-500/15 hover:text-rose-300"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}
