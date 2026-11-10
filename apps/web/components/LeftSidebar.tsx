'use client';


import React, { useRef, useState } from 'react';
import {
  Sparkles,
  Image as ImageIcon,
  Scissors,
  UserCheck,
  Camera,
  Dna,
  RotateCw,
  Users,
  Heart,
  Maximize2,
  Film,
  Video,
  Repeat,
  Mic,
  Tv,
  Sliders,
  Brain,
  Upload,
  ChevronDown,
  ChevronRight,
  Infinity as InfinityIcon,
  Plus
} from 'lucide-react';
import { GenerativeToolId, StudioAsset, CanonicalPlaybook } from '../lib/types';
import { TOOLS_CATALOG } from '../lib/toolsCatalog';

interface LeftSidebarProps {
  activeTool: GenerativeToolId;
  onSelectTool: (tool: GenerativeToolId) => void;
  assets: StudioAsset[];
  selectedAssetId: string | null;
  onSelectAsset: (asset: StudioAsset) => void;
  onUploadFile: (file: File) => void;
  playbooks: CanonicalPlaybook[];
  attachedPlaybookId: string | null;
  onAttachPlaybook: (playbook: CanonicalPlaybook) => void;
  onDetachPlaybook: () => void;
}

export const LeftSidebar: React.FC<LeftSidebarProps> = ({
  activeTool,
  onSelectTool,
  assets,
  selectedAssetId,
  onSelectAsset,
  onUploadFile,
  playbooks,
  attachedPlaybookId,
  onAttachPlaybook,
  onDetachPlaybook,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [playbooksOpen, setPlaybooksOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>('All');

  const categories = [
    'All',
    'Image Generation',
    'Image Modification',
    'Video Generation',
    'Video Enhancement',
    'Cognition & Audio',
  ];

  const toolsList = Object.values(TOOLS_CATALOG).filter(
    (t) => activeCategory === 'All' || t.category === activeCategory
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUploadFile(e.target.files[0]);
    }
  };

  const getToolIcon = (toolId: GenerativeToolId) => {
    switch (toolId) {
      case 'by_prompt': return <Sparkles size={14} />;
      case 'by_ref': return <ImageIcon size={14} />;
      case 'image_editor': return <Scissors size={14} />;
      case 'faceswap': return <UserCheck size={14} />;
      case 'photoshoot': return <Camera size={14} />;
      case 'facegen': return <Dna size={14} />;
      case 'carousel': return <RotateCw size={14} />;
      case 'collaber': return <Users size={14} />;
      case 'couplegen': return <Heart size={14} />;
      case 'upscaler': return <Maximize2 size={14} />;
      case 'videogen': return <Film size={14} />;
      case 'text_to_video': return <Video size={14} />;
      case 'video2video': return <Repeat size={14} />;
      case 'lipsync': return <Mic size={14} />;
      case 'video_upscaler': return <Tv size={14} />;
      case 'video_merger': return <Sliders size={14} />;
      case 'run_any_llm': return <Brain size={14} />;
      default: return <Sparkles size={14} />;
    }
  };

  return (
    <aside className="region-sidebar" role="navigation" aria-label="Workspace Navigation">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span className="freedom-mode-badge">
          <InfinityIcon size={13} />
          TOTAL FREEDOM MODE
        </span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          17 Tools
        </span>
      </div>

      <div style={{ display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 6, marginBottom: 8 }}>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            style={{
              padding: '3px 8px',
              fontSize: '10.5px',
              borderRadius: '4px',
              border: '1px solid var(--border-subtle)',
              background: activeCategory === cat ? 'rgba(99, 102, 241, 0.25)' : 'transparent',
              color: activeCategory === cat ? '#a5b4fc' : 'var(--text-secondary)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="pipeline-tools-grid">
        {toolsList.map((tool) => {
          const isActive = activeTool === tool.id;
          return (
            <button
              key={tool.id}
              className={`pipeline-tool-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectTool(tool.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)' }}>
                  {getToolIcon(tool.id)}
                </span>
                <span>{tool.name}</span>
              </div>
              <span className="tool-badge-pill">{tool.badge}</span>
            </button>
          );
        })}
      </div>

      <div
        className="sidebar-section-row"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 14,
          marginBottom: 6,
        }}
      >
        <span className="sidebar-section-label" style={{ margin: 0 }}>
          Media & References
        </span>
        <button
          onClick={() => fileInputRef.current?.click()}
          className="action-btn-mini"
          style={{
            background: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
            color: '#fff',
            border: 'none',
            padding: '3px 8px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}
          title="Upload image, video or audio for references, faceswap, or inpainting"
        >
          <Plus size={12} />
          Upload
        </button>
      </div>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="image/*,video/*,audio/*"
        hidden
      />

      <div
        className="sidebar-dropzone"
        onClick={() => fileInputRef.current?.click()}
        title="Click or drop photos/videos/audio here"
        style={{
          border: '1px dashed var(--border-subtle)',
          borderRadius: 6,
          padding: '10px',
          textAlign: 'center',
          background: 'rgba(255,255,255,0.02)',
          cursor: 'pointer',
          marginBottom: 10,
        }}
      >
        <Upload size={16} style={{ margin: '0 auto 4px auto', color: 'var(--text-secondary)' }} />
        <span style={{ fontSize: 11, color: 'var(--text-secondary)', display: 'block' }}>
          Drop photos / videos / audio
        </span>
      </div>

      <div className="sidebar-section-label">Active Project Assets ({assets.length})</div>
      <div className="sidebar-asset-mini-list" style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
        {assets.length === 0 ? (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 4px' }}>
            No assets yet. Create or upload media to populate the canvas.
          </div>
        ) : (
          assets.map((asset) => {
            const isSelected = selectedAssetId === asset.id;
            return (
              <div
                key={asset.id}
                onClick={() => onSelectAsset(asset)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '5px 8px',
                  borderRadius: 6,
                  background: isSelected ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.02)',
                  border: isSelected ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                  cursor: 'pointer',
                }}
              >
                {asset.type === 'video' ? (
                  <div style={{ width: 28, height: 28, borderRadius: 4, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Film size={14} color="#38bdf8" />
                  </div>
                ) : asset.type === 'audio' ? (
                  <div style={{ width: 28, height: 28, borderRadius: 4, background: '#1e1b4b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Mic size={14} color="#ec4899" />
                  </div>
                ) : (
                  <img
                    src={asset.previewUrl || asset.url}
                    alt={asset.title}
                    style={{ width: 28, height: 28, borderRadius: 4, objectFit: 'cover' }}
                  />
                )}
                <div style={{ overflow: 'hidden', flex: 1 }}>
                  <div style={{ fontSize: 11.5, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {asset.title}
                  </div>
                  <div style={{ fontSize: 9.5, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {asset.toolUsed || asset.type}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div style={{ marginTop: 14 }}>
        <button
          onClick={() => setPlaybooksOpen(!playbooksOpen)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-secondary)',
            fontSize: 11,
            cursor: 'pointer',
            padding: '4px 0',
          }}
        >
          <span>Playbooks (attach context, do not auto-run)</span>
          {playbooksOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>

        {playbooksOpen && (
          <div style={{ marginTop: 6, display: 'flex', flexDirection: 'column', gap: 5 }}>
            {playbooks.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Playbooks will appear once the studio API is reachable.
              </div>
            ) : (
              playbooks.map((pb) => {
                const attached = attachedPlaybookId === pb.id;
                return (
                  <button
                    key={pb.id}
                    onClick={() => (attached ? onDetachPlaybook() : onAttachPlaybook(pb))}
                    style={{
                      textAlign: 'left',
                      padding: '6px 8px',
                      borderRadius: 6,
                      background: attached ? 'rgba(99, 102, 241, 0.18)' : 'rgba(15, 23, 42, 0.65)',
                      border: attached ? '1px solid var(--accent-primary)' : '1px solid rgba(56, 189, 248, 0.25)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontSize: 11, fontWeight: 600, color: attached ? '#c7d2fe' : '#38bdf8' }}>{pb.label}</div>
                    <div style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>{pb.outcome}</div>
                    {attached && (
                      <div style={{ fontSize: 9.5, color: '#a5b4fc', marginTop: 4 }}>
                        Attached — enriches your next job, does not fire a canned prompt
                      </div>
                    )}
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
