'use client';

import React, { useState } from 'react';
import {
  Sparkles,
  Sliders,
  Palette,
  Video,
  Layers,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Zap,
  Info
} from 'lucide-react';
import { GenerativeToolId, StudioAsset, AspectRatio, QualityTier } from '../lib/types';
import { TOOLS_CATALOG } from '../lib/toolsCatalog';

interface RightInspectorProps {
  activeTool: GenerativeToolId;
  parameters: Record<string, any>;
  onChangeParameters: (params: Record<string, any>) => void;
  selectedAsset: StudioAsset | null;
  onSetAsReference: (asset: StudioAsset) => void;
  onQuickUpscale: (factor: 2 | 4) => void;
}

export const RightInspector: React.FC<RightInspectorProps> = ({
  activeTool,
  parameters,
  onChangeParameters,
  selectedAsset,
  onSetAsReference,
  onQuickUpscale,
}) => {
  const toolDef = TOOLS_CATALOG[activeTool];
  const [motionPreset, setMotionPreset] = useState<string>('orbit');
  const [activeLut, setActiveLut] = useState<string>('none');
  const [exposure, setExposure] = useState<number>(0);
  const [contrast, setContrast] = useState<number>(100);
  const [saturation, setSaturation] = useState<number>(100);
  const [warmth, setWarmth] = useState<number>(0);

  const updateParam = (key: string, val: any) => {
    onChangeParameters({ ...parameters, [key]: val });
  };

  return (
    <aside className="region-inspector" role="complementary" aria-label="Tool & Parameter Inspector">
      {/* Active Tool Parameters Header */}
      <div className="inspector-card" style={{ borderColor: 'rgba(99, 102, 241, 0.4)' }}>
        <div className="inspector-card-header">
          <span style={{ color: 'var(--accent-cyan)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sliders size={14} />
            {toolDef.name} Parameters
          </span>
          <span className="lut-active-label" style={{ background: 'rgba(99, 102, 241, 0.2)', color: '#c7d2fe' }}>
            {toolDef.credits} CR
          </span>
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.45, marginBottom: 12 }}>
          {toolDef.description}
        </p>

        {/* Model Selector (if supported) */}
        {toolDef.models && toolDef.models.length > 0 && (
          <div className="control-group" style={{ marginBottom: 10 }}>
            <span className="control-label">Generative Model</span>
            <select
              value={parameters.model || toolDef.defaultModel}
              onChange={(e) => updateParam('model', e.target.value)}
              className="command-input"
              style={{
                width: '100%',
                background: 'var(--bg-surface-3)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                padding: '6px 10px',
                borderRadius: 6,
                fontSize: 12,
              }}
            >
              {toolDef.models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Aspect Ratio Selector (if supported) */}
        {toolDef.supportsAspectRatios && (
          <div className="control-group" style={{ marginBottom: 10 }}>
            <span className="control-label">Aspect Ratio</span>
            <div className="segmented-pills" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4 }}>
              {['16:9', '1:1', '9:16', '21:9', '4:3', '3:4', '2:3', '3:2'].map((ratio) => (
                <button
                  key={ratio}
                  className={`seg-pill ${parameters.ratio === ratio ? 'active' : ''}`}
                  onClick={() => updateParam('ratio', ratio)}
                  style={{ fontSize: 10.5, padding: '5px 2px' }}
                >
                  {ratio}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Resolution Tier (if supported) */}
        {toolDef.supportsTiers && (
          <div className="control-group" style={{ marginBottom: 10 }}>
            <span className="control-label">Resolution Tier</span>
            <div className="segmented-pills" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
              {['1K', '2K', '4K'].map((tier) => (
                <button
                  key={tier}
                  className={`seg-pill ${parameters.tier === tier ? 'active' : ''}`}
                  onClick={() => updateParam('tier', tier)}
                >
                  {tier}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Tool-specific controls */}
        {activeTool === 'faceswap' && (
          <div className="control-group" style={{ marginBottom: 10 }}>
            <span className="control-label">Swap Coverage Type</span>
            <div className="segmented-pills" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
              {[
                { id: 'face', label: 'Face Only' },
                { id: 'head', label: 'Whole Head' },
                { id: 'person', label: 'Full Person' },
              ].map((item) => (
                <button
                  key={item.id}
                  className={`seg-pill ${parameters.swap_type === item.id ? 'active' : ''}`}
                  onClick={() => updateParam('swap_type', item.id)}
                  style={{ fontSize: 10.5 }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {activeTool === 'upscaler' && (
          <>
            <div className="control-group" style={{ marginBottom: 10 }}>
              <span className="control-label">Target Resolution</span>
              <div className="segmented-pills" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 4 }}>
                {['2k', '4k', '6k', '8k'].map((res) => (
                  <button
                    key={res}
                    className={`seg-pill ${parameters.target_resolution === res ? 'active' : ''}`}
                    onClick={() => updateParam('target_resolution', res)}
                  >
                    {res.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            <div className="control-group" style={{ marginBottom: 10 }}>
              <span className="control-label">Restoration Detail</span>
              <div className="segmented-pills" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
                {['low', 'medium', 'high'].map((det) => (
                  <button
                    key={det}
                    className={`seg-pill ${parameters.detail === det ? 'active' : ''}`}
                    onClick={() => updateParam('detail', det)}
                  >
                    {det.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}

        {(activeTool === 'videogen' || activeTool === 'text_to_video' || activeTool === 'video2video') && (
          <>
            <div className="control-group" style={{ marginBottom: 10 }}>
              <span className="control-label">Clip Duration: {parameters.duration || 5}s</span>
              <input
                type="range"
                min="5"
                max="30"
                step="5"
                value={parameters.duration || 5}
                onChange={(e) => updateParam('duration', Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-cyan)' }}
              />
            </div>
            <div className="control-group" style={{ marginBottom: 10 }}>
              <span className="control-label">Video Resolution</span>
              <div className="segmented-pills" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4 }}>
                {['480p', '720p', '1080p'].map((r) => (
                  <button
                    key={r}
                    className={`seg-pill ${parameters.resolution === r ? 'active' : ''}`}
                    onClick={() => updateParam('resolution', r)}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Native Audio Track</span>
              <input
                type="checkbox"
                checked={parameters.generate_audio ?? true}
                onChange={(e) => updateParam('generate_audio', e.target.checked)}
                style={{ accentColor: 'var(--accent-cyan)' }}
              />
            </div>
          </>
        )}

        {activeTool === 'facegen' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div>
              <span className="control-label">Gender</span>
              <select
                value={parameters.gender || 'Female'}
                onChange={(e) => updateParam('gender', e.target.value)}
                className="command-input"
                style={{ width: '100%', fontSize: 11, padding: 4 }}
              >
                <option value="Female">Female</option>
                <option value="Male">Male</option>
              </select>
            </div>
            <div>
              <span className="control-label">Age</span>
              <select
                value={parameters.age || '26-35'}
                onChange={(e) => updateParam('age', e.target.value)}
                className="command-input"
                style={{ width: '100%', fontSize: 11, padding: 4 }}
              >
                {['18-25', '26-35', '36-45', '46-55', '56-65'].map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Selected Asset Actions */}
      <div className="inspector-card">
        <div className="inspector-card-header">
          <span>Active Asset Operations</span>
          <span className="lut-active-label">
            {selectedAsset ? selectedAsset.type.toUpperCase() : 'NONE'}
          </span>
        </div>

        {selectedAsset ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
              <strong>ID:</strong> {selectedAsset.id.slice(0, 16)}...
            </div>
            <button
              className="action-btn"
              onClick={() => onSetAsReference(selectedAsset)}
              style={{
                background: 'linear-gradient(135deg, #4f46e5, #06b6d4)',
                color: '#fff',
                border: 'none',
                padding: '7px 10px',
                borderRadius: 6,
                fontSize: 11.5,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              📌 Anchor as Generation Reference
            </button>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                className="seg-pill"
                onClick={() => onQuickUpscale(2)}
                style={{ flex: 1, padding: '6px 4px', fontSize: 11 }}
              >
                ⚡ Upscale 2×
              </button>
              <button
                className="seg-pill"
                onClick={() => onQuickUpscale(4)}
                style={{ flex: 1, padding: '6px 4px', fontSize: 11 }}
              >
                ✨ Upscale 4K
              </button>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Select or generate an asset on the canvas to inspect and transform it.
          </div>
        )}
      </div>

      {/* Higgsfield Camera Motion Deck */}
      <div className="inspector-card">
        <div className="inspector-card-header">
          <span>Higgsfield Camera Motion</span>
          <span className="lut-active-label" style={{ color: 'var(--accent-cyan)' }}>
            {motionPreset.toUpperCase()}
          </span>
        </div>
        <div className="motion-grid-presets">
          {[
            { id: 'pan-left', label: '◄ Pan L' },
            { id: 'pan-right', label: 'Pan R ►' },
            { id: 'tilt-up', label: '▲ Tilt Up' },
            { id: 'tilt-down', label: '▼ Tilt Dn' },
            { id: 'zoom-in', label: '⊕ Zoom In' },
            { id: 'zoom-out', label: '⊖ Zoom Out' },
            { id: 'orbit', label: '⟳ Orbit 360' },
            { id: 'drone', label: '✈ FPV Drone' },
          ].map((m) => (
            <button
              key={m.id}
              className={`motion-preset-btn ${motionPreset === m.id ? 'active' : ''}`}
              onClick={() => setMotionPreset(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Hollywood Color Look & LUT Presets */}
      <div className="inspector-card">
        <div className="inspector-card-header">
          <span>Cinema Look & LUT Deck</span>
          <span className="lut-active-label">{activeLut.toUpperCase()}</span>
        </div>
        <div className="lut-pills-grid">
          {[
            { id: 'none', label: 'Raw Studio' },
            { id: 'kodak2383', label: 'Kodak 2383' },
            { id: 'arrilogc', label: 'Arri LogC' },
            { id: 'bleach', label: 'Bleach Bypass' },
            { id: 'bladerunner', label: 'Blade Runner' },
            { id: 'matrix', label: 'Matrix Green' },
            { id: 'tealorange', label: 'Teal & Orange' },
          ].map((l) => (
            <button
              key={l.id}
              className={`lut-pill ${activeLut === l.id ? 'active' : ''}`}
              onClick={() => setActiveLut(l.id)}
            >
              <span>{l.label}</span>
            </button>
          ))}
        </div>

        {/* Realtime Grade Sliders */}
        <div className="grade-sliders-cluster" style={{ marginTop: 10 }}>
          <div className="grade-slider-row">
            <label>Exposure</label>
            <input
              type="range"
              min="-2"
              max="2"
              step="0.1"
              value={exposure}
              onChange={(e) => setExposure(Number(e.target.value))}
            />
            <span className="grade-val">{exposure}</span>
          </div>
          <div className="grade-slider-row">
            <label>Contrast</label>
            <input
              type="range"
              min="70"
              max="150"
              step="1"
              value={contrast}
              onChange={(e) => setContrast(Number(e.target.value))}
            />
            <span className="grade-val">{contrast}%</span>
          </div>
          <div className="grade-slider-row">
            <label>Warmth</label>
            <input
              type="range"
              min="-30"
              max="30"
              step="1"
              value={warmth}
              onChange={(e) => setWarmth(Number(e.target.value))}
            />
            <span className="grade-val">{warmth}</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
