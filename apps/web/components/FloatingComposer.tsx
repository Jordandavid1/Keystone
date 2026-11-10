'use client';

import React, { useRef } from 'react';
import {
  Sparkles,
  Paperclip,
  Globe,
  X,
  CornerDownLeft,
  Infinity as InfinityIcon
} from 'lucide-react';
import { GenerativeToolId, StudioAsset } from '../lib/types';
import { TOOLS_CATALOG } from '../lib/toolsCatalog';

interface FloatingComposerProps {
  promptText: string;
  onChangePrompt: (val: string) => void;
  activeTool: GenerativeToolId;
  onSelectTool: (tool: GenerativeToolId) => void;
  referenceAsset: StudioAsset | null;
  onRemoveReference: () => void;
  onAttachFileClick: () => void;
  onOpenWebModal: () => void;
  onSubmit: () => void;
  isGenerating: boolean;
}

export const FloatingComposer: React.FC<FloatingComposerProps> = ({
  promptText,
  onChangePrompt,
  activeTool,
  onSelectTool,
  referenceAsset,
  onRemoveReference,
  onAttachFileClick,
  onOpenWebModal,
  onSubmit,
  isGenerating,
}) => {
  const toolDef = TOOLS_CATALOG[activeTool];

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating && promptText.trim()) {
        onSubmit();
      }
    }
  };

  return (
    <section className="region-composer" aria-label="KEYSTONE Creative Composer">
      {/* Composer Top Row */}
      <div className="composer-top-row">
        {/* Quick Tool Switcher Pills */}
        <div className="intent-pills-group" role="radiogroup">
          <button
            className={`intent-pill ${activeTool === 'by_prompt' ? 'active' : ''}`}
            onClick={() => onSelectTool('by_prompt')}
          >
            <Sparkles size={13} />
            <span>Text-to-Image</span>
          </button>
          <button
            className={`intent-pill ${activeTool === 'by_ref' ? 'active' : ''}`}
            onClick={() => onSelectTool('by_ref')}
          >
            <span>Ref-to-Image</span>
          </button>
          <button
            className={`intent-pill ${activeTool === 'image_editor' ? 'active' : ''}`}
            onClick={() => onSelectTool('image_editor')}
          >
            <span>Inpaint / Edit</span>
          </button>
          <button
            className={`intent-pill ${activeTool === 'faceswap' ? 'active' : ''}`}
            onClick={() => onSelectTool('faceswap')}
          >
            <span>Face Swap</span>
          </button>
          <button
            className={`intent-pill ${activeTool === 'videogen' ? 'active' : ''}`}
            onClick={() => onSelectTool('videogen')}
          >
            <span>Image-to-Video</span>
          </button>
          <button
            className={`intent-pill ${activeTool === 'text_to_video' ? 'active' : ''}`}
            onClick={() => onSelectTool('text_to_video')}
          >
            <span>Text-to-Video</span>
          </button>
        </div>

        <div className="composer-shield-indicators">
          <span className="shield-tag" style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#c7d2fe' }}>
            Active Tool: {toolDef.name}
          </span>
        </div>
      </div>

      {/* Active Reference Asset Anchor Tray */}
      {referenceAsset && (
        <div className="reference-anchor-box">
          <span
            style={{
              fontSize: '10px',
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: 4,
              background: 'rgba(99, 102, 241, 0.3)',
              color: '#818cf8',
              letterSpacing: 0.5,
            }}
          >
            REFERENCE ANCHOR
          </span>
          <img
            src={referenceAsset.previewUrl || referenceAsset.url}
            alt="Reference thumbnail"
            style={{ width: 28, height: 28, borderRadius: 4, objectFit: 'cover' }}
          />
          <span
            style={{
              fontSize: 12,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)',
              maxWidth: 220,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {referenceAsset.title}
          </span>
          <button
            onClick={onRemoveReference}
            style={{
              marginLeft: 'auto',
              background: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fca5a5',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: 5,
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <X size={12} />
            Detach
          </button>
        </div>
      )}

      {/* Main Composer Input Box */}
      <div className="composer-input-row">
        <div className="composer-action-btn-group">
          <button
            className="icon-btn"
            title="Attach or upload media reference"
            onClick={onAttachFileClick}
            style={{ padding: '8px 10px' }}
          >
            <Paperclip size={16} />
          </button>
          <button
            className="icon-btn"
            title="Firecrawl Ingest Style from URL (@Web)"
            onClick={onOpenWebModal}
            style={{ padding: '8px 10px', color: 'var(--accent-cyan)' }}
          >
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

        <button
          className="composer-submit-btn"
          onClick={onSubmit}
          disabled={isGenerating || !promptText.trim()}
        >
          {isGenerating ? (
            <span>Running...</span>
          ) : (
            <>
              <span>Run KEYSTONE</span>
              <kbd className="submit-kbd">↵</kbd>
            </>
          )}
        </button>
      </div>
    </section>
  );
};
