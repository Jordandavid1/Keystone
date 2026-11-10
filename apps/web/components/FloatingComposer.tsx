'use client';

import React from 'react';
import {
  Sparkles,
  Paperclip,
  Globe,
  X,
  Pencil,
  Play,
  Search
} from 'lucide-react';
import { GenerativeToolId, StudioAsset } from '../lib/types';
import { TOOLS_CATALOG } from '../lib/toolsCatalog';

export type CreativeIntent = 'create' | 'edit' | 'animate' | 'analyze';
export type GenerationMode = 'text2image' | 'img2img';

interface FloatingComposerProps {
  promptText: string;
  onChangePrompt: (val: string) => void;
  activeTool: GenerativeToolId;
  onSelectTool?: (tool: GenerativeToolId) => void;
  referenceAsset: StudioAsset | null;
  onRemoveReference: () => void;
  onAttachFileClick: () => void;
  onOpenWebModal: () => void;
  onSubmit: () => void;
  isGenerating: boolean;
  intent: CreativeIntent;
  onChangeIntent: (intent: CreativeIntent) => void;
  webContextLabel: string | null;
  onRemoveWebContext: () => void;
  lutLabel: string | null;
  onRemoveLut: () => void;
  playbookLabel: string | null;
  generationMode: GenerationMode;
  onChangeGenerationMode: (mode: GenerationMode) => void;
  denoise: number;
  onChangeDenoise: (value: number) => void;
}

export const FloatingComposer: React.FC<FloatingComposerProps> = ({
  promptText,
  onChangePrompt,
  activeTool,
  referenceAsset,
  onRemoveReference,
  onAttachFileClick,
  onOpenWebModal,
  onSubmit,
  isGenerating,
  intent,
  onChangeIntent,
  webContextLabel,
  onRemoveWebContext,
  lutLabel,
  onRemoveLut,
  playbookLabel,
  generationMode,
  onChangeGenerationMode,
  denoise,
  onChangeDenoise,
}) => {
  const toolDef = TOOLS_CATALOG[activeTool];

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating && promptText.trim()) onSubmit();
    }
  };

  return (
    <section className="region-composer" aria-label="KEYSTONE Creative Composer">
      <div className="composer-top-row">
        <div className="intent-pills-group" role="radiogroup">
          <button className={`intent-pill ${intent === 'create' ? 'active' : ''}`} onClick={() => onChangeIntent('create')}>
            <Sparkles size={13} />
            <span>Create</span>
          </button>
          <button className={`intent-pill ${intent === 'edit' ? 'active' : ''}`} onClick={() => onChangeIntent('edit')}>
            <Pencil size={13} />
            <span>Edit</span>
          </button>
          <button className={`intent-pill ${intent === 'animate' ? 'active' : ''}`} onClick={() => onChangeIntent('animate')}>
            <Play size={13} />
            <span>Animate</span>
          </button>
          <button className={`intent-pill ${intent === 'analyze' ? 'active' : ''}`} onClick={() => onChangeIntent('analyze')}>
            <Search size={13} />
            <span>Analyze</span>
          </button>
        </div>

        <div className="cursor-context-tray">
          {webContextLabel && (
            <span className="context-pill">
              <span className="ctx-type">@Web:</span>
              <span className="ctx-val">{webContextLabel}</span>
              <button className="ctx-remove-btn" onClick={onRemoveWebContext} type="button">x</button>
            </span>
          )}
          {lutLabel && (
            <span className="context-pill">
              <span className="ctx-type">@LUT:</span>
              <span className="ctx-val">{lutLabel}</span>
              <button className="ctx-remove-btn" onClick={onRemoveLut} type="button">x</button>
            </span>
          )}
        </div>

        <div className="composer-shield-indicators">
          <span className="shield-tag" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#c7d2fe' }}>
            {playbookLabel ? `Playbook: ${playbookLabel}` : 'No playbook attached'}
          </span>
          <span className="shield-tag" style={{ background: 'rgba(6, 182, 212, 0.12)', color: '#67e8f9' }}>
            Tool: {toolDef.name}
          </span>
        </div>
      </div>

      <div className="gen-mode-bar" style={{ marginBottom: 8, padding: '5px 12px', background: 'rgba(15, 23, 42, 0.7)', border: '1px solid var(--border-subtle)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>Generation Mode:</span>
          <button type="button" className={`gen-mode-btn ${generationMode === 'text2image' ? 'active' : ''}`} onClick={() => onChangeGenerationMode('text2image')} style={{ padding: '4px 12px', fontSize: 11, fontWeight: 600, borderRadius: 6, border: generationMode === 'text2image' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)', background: generationMode === 'text2image' ? 'rgba(6, 182, 212, 0.18)' : 'transparent', color: generationMode === 'text2image' ? '#fff' : 'var(--text-secondary)', cursor: 'pointer' }}>
            Text-to-Image (Prompt Only)
          </button>
          <button type="button" className={`gen-mode-btn ${generationMode === 'img2img' ? 'active' : ''}`} onClick={() => onChangeGenerationMode('img2img')} style={{ padding: '4px 12px', fontSize: 11, fontWeight: 600, borderRadius: 6, border: generationMode === 'img2img' ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)', background: generationMode === 'img2img' ? 'rgba(6, 182, 212, 0.18)' : 'transparent', color: generationMode === 'img2img' ? '#fff' : 'var(--text-secondary)', cursor: 'pointer' }}>
            Reference-Guided (Img2Img)
          </button>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {generationMode === 'img2img' ? (referenceAsset ? `Reference: ${referenceAsset.title}` : 'Img2Img needs a reference asset') : 'Pure prompt generation — no reference conditioning'}
        </div>
      </div>

      {referenceAsset && (
        <div className="reference-anchor-box">
          <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: 'rgba(99, 102, 241, 0.3)', color: '#818cf8', letterSpacing: 0.5 }}>
            REFERENCE ANCHOR
          </span>
          <img src={referenceAsset.previewUrl || referenceAsset.url} alt="Reference thumbnail" style={{ width: 28, height: 28, borderRadius: 4, objectFit: 'cover' }} />
          <span style={{ fontSize: 12, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {referenceAsset.title}
          </span>
          <label style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
            Denoise: {denoise.toFixed(2)}
            <input type="range" min={0.1} max={0.95} step={0.05} value={denoise} onChange={(e) => onChangeDenoise(Number(e.target.value))} style={{ width: 80, accentColor: 'var(--accent-cyan)' }} />
          </label>
          <button onClick={onRemoveReference} style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#fca5a5', fontSize: 11, fontWeight: 600, cursor: 'pointer', padding: '3px 8px', borderRadius: 5 }}>
            <X size={12} /> Detach
          </button>
        </div>
      )}

      <div className="composer-input-row">
        <div className="composer-action-btn-group">
          <button className="icon-btn" title="Attach or upload media reference" onClick={onAttachFileClick} style={{ padding: '8px 10px' }}>
            <Paperclip size={16} />
          </button>
          <button className="icon-btn" title="Firecrawl Ingest Style from URL (@Web)" onClick={onOpenWebModal} style={{ padding: '8px 10px', color: 'var(--accent-cyan)' }}>
            <Globe size={16} />
          </button>
        </div>
        <textarea
          className="composer-textarea"
          value={promptText}
          onChange={(e) => onChangePrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Describe your vision for ${toolDef.name} (type @ for Web/Asset context, Enter to run)...`}
          aria-label="Creative prompt input"
          rows={2}
        />
        <button className="composer-submit-btn" onClick={onSubmit} disabled={isGenerating || !promptText.trim()}>
          {isGenerating ? <span>Running...</span> : (<><span>Run KEYSTONE</span><kbd className="submit-kbd">↵</kbd></>)}
        </button>
      </div>
    </section>
  );
};
