'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Download,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Maximize2,
  Film,
  Layers,
  GitBranch,
  Grid,
  Sparkles
} from 'lucide-react';
import { StudioAsset, CanvasViewMode } from '../lib/types';

interface CenterCanvasProps {
  activeMode: CanvasViewMode;
  onChangeMode: (mode: CanvasViewMode) => void;
  selectedAsset: StudioAsset | null;
  referenceAsset: StudioAsset | null;
  assets: StudioAsset[];
  onSelectAsset: (asset: StudioAsset) => void;
  isGenerating: boolean;
  stageText: string;
  stageIndex: number;
  framingGuidesVisible: boolean;
  activeAspectMask: string;
  onChangeAspectMask: (mask: string) => void;
}

export const CenterCanvas: React.FC<CenterCanvasProps> = ({
  activeMode,
  onChangeMode,
  selectedAsset,
  referenceAsset,
  assets,
  onSelectAsset,
  isGenerating,
  stageText,
  stageIndex,
  framingGuidesVisible,
  activeAspectMask,
  onChangeAspectMask,
}) => {
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [compareSplit, setCompareSplit] = useState<number>(50);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTimecode, setCurrentTimecode] = useState<string>('00:00:00:00');
  const [timelinePercent, setTimelinePercent] = useState<number>(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const scrubberRef = useRef<HTMLDivElement>(null);

  const PROGRESS_STAGES = [
    'Understanding your request',
    'Planning the generation',
    'Preparing the workflow',
    'Creating & Synthesizing',
    'Checking the result with KHF',
    'Refining when necessary',
    'Finishing & Delivery'
  ];

  // Video Timecode sync
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const cur = video.currentTime;
      const dur = video.duration || 1;
      setTimelinePercent((cur / dur) * 100);

      const hours = Math.floor(cur / 3600).toString().padStart(2, '0');
      const mins = Math.floor((cur % 3600) / 60).toString().padStart(2, '0');
      const secs = Math.floor(cur % 60).toString().padStart(2, '0');
      const frames = Math.floor((cur % 1) * 24).toString().padStart(2, '0');
      setCurrentTimecode(`${hours}:${mins}:${secs}:${frames}`);
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => video.removeEventListener('timeupdate', handleTimeUpdate);
  }, [selectedAsset]);

  const togglePlayPause = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const stepFrame = (forward: boolean) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime += forward ? 1 / 24 : -1 / 24;
  };

  const handleScrub = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!scrubberRef.current || !videoRef.current) return;
    const rect = scrubberRef.current.getBoundingClientRect();
    const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    videoRef.current.currentTime = pos * (videoRef.current.duration || 1);
  };

  const handleDownload = () => {
    if (!selectedAsset) return;
    const a = document.createElement('a');
    a.href = selectedAsset.downloadUrl || selectedAsset.url;
    a.download = `${selectedAsset.id}_keystone.${selectedAsset.type === 'video' ? 'mp4' : 'png'}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <main className="region-canvas" role="main">
      {/* Top Canvas View Tabs */}
      <div className="canvas-toolbar">
        <div className="canvas-mode-tabs" role="tablist">
          <button
            className={`mode-tab ${activeMode === 'single' ? 'active' : ''}`}
            onClick={() => onChangeMode('single')}
          >
            <span>Primary Canvas</span>
          </button>
          <button
            className={`mode-tab ${activeMode === 'compare' ? 'active' : ''}`}
            onClick={() => onChangeMode('compare')}
          >
            <span>Split Compare</span>
          </button>
          <button
            className={`mode-tab ${activeMode === 'video' ? 'active' : ''}`}
            onClick={() => onChangeMode('video')}
          >
            <Film size={13} style={{ marginRight: 4 }} />
            <span>MiniMax Video</span>
          </button>
          <button
            className={`mode-tab ${activeMode === 'variations' ? 'active' : ''}`}
            onClick={() => onChangeMode('variations')}
          >
            <Grid size={13} style={{ marginRight: 4 }} />
            <span>Variations</span>
          </button>
          <button
            className={`mode-tab ${activeMode === 'lineage' ? 'active' : ''}`}
            onClick={() => onChangeMode('lineage')}
          >
            <GitBranch size={13} style={{ marginRight: 4 }} />
            <span>Lineage DAG</span>
          </button>
        </div>

        <div className="canvas-actions">
          {/* Zoom loupe */}
          <div className="zoom-segment-control">
            <button
              className={`zoom-btn ${zoomLevel === 1 ? 'active' : ''}`}
              onClick={() => setZoomLevel(1)}
            >
              1X
            </button>
            <button
              className={`zoom-btn ${zoomLevel === 2 ? 'active' : ''}`}
              onClick={() => setZoomLevel(2)}
            >
              2X
            </button>
            <button
              className={`zoom-btn ${zoomLevel === 4 ? 'active' : ''}`}
              onClick={() => setZoomLevel(4)}
            >
              4X
            </button>
          </div>

          {/* Download button */}
          <button
            className="icon-btn"
            onClick={handleDownload}
            disabled={!selectedAsset}
            title="Download Persisted Asset"
          >
            <Download size={14} />
            <span>Download</span>
          </button>
        </div>
      </div>

      {/* 7-Stage Customer Progress Banner */}
      {isGenerating && (
        <div className="progress-overlay-card" role="status" aria-live="polite">
          <div className="progress-header">
            <div className="progress-stage-label">
              <span className="pulse-ring" />
              <span>{stageText || 'Generating creative asset...'}</span>
            </div>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', color: 'var(--text-secondary)' }}>
              Stage {stageIndex + 1} / 7
            </span>
          </div>
          <div className="progress-steps-track">
            {PROGRESS_STAGES.map((label, idx) => (
              <div
                key={label}
                className={`progress-step-pill ${idx < stageIndex ? 'done' : idx === stageIndex ? 'active' : ''}`}
                title={`${idx + 1}. ${label}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Center Stage Viewport */}
      <div className="stage-viewport-wrapper">
        <div className="canvas-stage">
          {activeMode === 'single' && (
            <div className="media-viewport-container">
              {selectedAsset ? (
                selectedAsset.type === 'video' ? (
                  <video
                    ref={videoRef}
                    src={selectedAsset.url}
                    controls
                    loop
                    className="stage-primary-media"
                    style={{ transform: `scale(${zoomLevel})` }}
                  />
                ) : (
                  <img
                    src={selectedAsset.url}
                    alt={selectedAsset.title}
                    className="stage-primary-media"
                    style={{ transform: `scale(${zoomLevel})`, transition: 'transform 0.2s ease' }}
                  />
                )
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Sparkles size={36} style={{ margin: '0 auto 12px auto', color: 'var(--accent-cyan)' }} />
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                    Creative Canvas Stage
                  </div>
                  <p style={{ fontSize: 12, marginTop: 4 }}>
                    Select any tool on the left and enter your creative intent below.
                  </p>
                </div>
              )}
            </div>
          )}

          {activeMode === 'compare' && (
            <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
              {selectedAsset ? (
                <>
                  <img
                    src={referenceAsset ? referenceAsset.url : selectedAsset.url}
                    alt="Reference / Before"
                    style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: `${compareSplit}%`,
                      height: '100%',
                      overflow: 'hidden',
                      borderRight: '2px solid var(--accent-cyan)',
                    }}
                  >
                    <img
                      src={selectedAsset.url}
                      alt="Generated / After"
                      style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }}
                    />
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={compareSplit}
                    onChange={(e) => setCompareSplit(Number(e.target.value))}
                    style={{
                      position: 'absolute',
                      bottom: 20,
                      left: '50%',
                      transform: 'translateX(-50%)',
                      width: '60%',
                      accentColor: 'var(--accent-cyan)',
                      zIndex: 10,
                    }}
                  />
                </>
              ) : (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', paddingTop: '20%' }}>
                  Compare mode requires at least one active asset.
                </div>
              )}
            </div>
          )}

          {activeMode === 'video' && (
            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <video
                ref={videoRef}
                src={
                  selectedAsset && selectedAsset.type === 'video'
                    ? selectedAsset.url
                    : 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
                }
                loop
                className="stage-primary-media"
              />
            </div>
          )}

          {activeMode === 'variations' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 14, padding: 20, overflowY: 'auto', height: '100%' }}>
              {assets.map((ast) => (
                <div
                  key={ast.id}
                  onClick={() => onSelectAsset(ast)}
                  style={{
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: 'var(--bg-surface-2)',
                    border: selectedAsset?.id === ast.id ? '2px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                  }}
                >
                  <img src={ast.previewUrl || ast.url} alt={ast.title} style={{ width: '100%', height: 160, objectFit: 'cover' }} />
                  <div style={{ padding: 8, fontSize: 11, color: 'var(--text-primary)' }}>{ast.title}</div>
                </div>
              ))}
            </div>
          )}

          {activeMode === 'lineage' && (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-secondary)' }}>
              <GitBranch size={36} style={{ margin: '0 auto 10px auto', color: '#a5b4fc' }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                ZenCreator Asset Lineage DAG Graph
              </div>
              <div style={{ marginTop: 14, display: 'inline-flex', alignItems: 'center', gap: 12 }}>
                <div style={{ padding: '8px 14px', borderRadius: 6, background: 'rgba(99, 102, 241, 0.2)', border: '1px solid var(--accent-primary)' }}>
                  Source Prompt / Upload
                </div>
                <span>→</span>
                <div style={{ padding: '8px 14px', borderRadius: 6, background: 'rgba(6, 182, 212, 0.2)', border: '1px solid var(--accent-cyan)' }}>
                  Generative Inference
                </div>
                <span>→</span>
                <div style={{ padding: '8px 14px', borderRadius: 6, background: 'rgba(16, 185, 129, 0.2)', border: '1px solid var(--accent-emerald)' }}>
                  Persisted Asset Lineage
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Framing Overlays */}
        {framingGuidesVisible && (
          <div className="framing-grid-overlay" aria-hidden="true">
            <div className="grid-rule horizontal top" />
            <div className="grid-rule horizontal bottom" />
            <div className="grid-rule vertical left" />
            <div className="grid-rule vertical right" />
            <div className="grid-safe-box title-safe" />
            <div className="grid-safe-box action-safe" />
            <div className="grid-crosshair" />
          </div>
        )}

        {/* Aspect Ratio Mask */}
        <div className="aspect-overlay-mask" data-mask={activeAspectMask} aria-hidden="true" />
      </div>

      {/* Hollywood Cinema Transport Bar */}
      <div className="cinema-transport-bar" role="region" aria-label="Playback Transport Controls">
        <div className="transport-timecode-cluster">
          <span className="timecode-label">TC</span>
          <div className="smpte-digital-display">{currentTimecode}</div>
          <span className="timecode-fps-badge">24 FPS</span>
        </div>

        <div className="transport-shuttle-cluster">
          <button className="transport-btn" onClick={() => stepFrame(false)} title="Step Back 1 Frame">
            <SkipBack size={14} />
          </button>
          <button className="transport-btn transport-btn-play" onClick={togglePlayPause} title="Play / Pause">
            {isPlaying ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button className="transport-btn" onClick={() => stepFrame(true)} title="Step Forward 1 Frame">
            <SkipForward size={14} />
          </button>
        </div>

        <div className="transport-scrub-container" ref={scrubberRef} onClick={handleScrub} title="Drag / Click Timeline Scrubber">
          <div className="scrub-ticks-track">
            <span className="scrub-tick major" />
            <span className="scrub-tick" />
            <span className="scrub-tick" />
            <span className="scrub-tick" />
            <span className="scrub-tick major" />
            <span className="scrub-tick" />
            <span className="scrub-tick" />
            <span className="scrub-tick" />
            <span className="scrub-tick major" />
          </div>
          <div className="scrub-cached-range" style={{ width: '100%' }} />
          <div className="scrub-playhead" style={{ left: `${timelinePercent}%` }}>
            <div className="playhead-needle" />
            <div className="playhead-badge">{currentTimecode.slice(3, 8)}</div>
          </div>
        </div>

        {/* Aspect Ratio Framing Guide Pills */}
        <div className="transport-matte-selector" title="Cinema Matte Aspect Mask">
          <span className="matte-label">MASK</span>
          {['none', 'scope', 'flat', 'tv', 'reel'].map((mask) => (
            <button
              key={mask}
              className={`matte-pill ${activeAspectMask === mask ? 'active' : ''}`}
              onClick={() => onChangeAspectMask(mask)}
            >
              {mask === 'none' ? 'Full' : mask === 'scope' ? '2.39:1' : mask === 'flat' ? '1.85:1' : mask === 'tv' ? '16:9' : '9:16'}
            </button>
          ))}
        </div>
      </div>
    </main>
  );
};
