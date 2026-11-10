'use client';

import React, { useState } from 'react';
import {
  GitBranch,
  Plus,
  Play,
  Trash2,
  CheckCircle2,
  Clock,
  ArrowDown,
  Layers,
  Sparkles
} from 'lucide-react';
import { GenerativeToolId, PipelineStep, StudioAsset } from '../lib/types';
import { TOOLS_CATALOG } from '../lib/toolsCatalog';

interface PipelineBuilderProps {
  steps: PipelineStep[];
  onUpdateSteps: (steps: PipelineStep[]) => void;
  onExecutePipeline: () => void;
  isExecuting: boolean;
  onSelectAsset: (asset: StudioAsset) => void;
}

export const PipelineBuilder: React.FC<PipelineBuilderProps> = ({
  steps,
  onUpdateSteps,
  onExecutePipeline,
  isExecuting,
  onSelectAsset,
}) => {
  const [selectedToolToAdd, setSelectedToolToAdd] = useState<GenerativeToolId>('by_prompt');

  const addStep = () => {
    const toolDef = TOOLS_CATALOG[selectedToolToAdd];
    const newStep: PipelineStep = {
      id: `step_${Date.now()}`,
      tool: selectedToolToAdd,
      label: `Stage ${steps.length + 1}: ${toolDef.name}`,
      enabled: true,
      inputAssets: [],
      parameters: { ...toolDef.defaultParameters },
      status: 'idle',
    };
    onUpdateSteps([...steps, newStep]);
  };

  const removeStep = (id: string) => {
    onUpdateSteps(steps.filter((s) => s.id !== id));
  };

  const toggleStep = (id: string) => {
    onUpdateSteps(
      steps.map((s) => (s.id === id ? { ...s, enabled: !s.enabled } : s))
    );
  };

  return (
    <div className="pipeline-builder-container">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <GitBranch size={18} color="var(--accent-cyan)" />
            Custom Generative Pipeline Studio
          </h2>
          <p style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
            Total creative freedom. Chain any models, transformations, and synthesis stages together without restrictions.
          </p>
        </div>

        <button
          className="composer-submit-btn"
          onClick={onExecutePipeline}
          disabled={isExecuting || steps.length === 0}
          style={{ padding: '8px 16px', fontSize: 12 }}
        >
          <Play size={14} style={{ marginRight: 6 }} />
          <span>{isExecuting ? 'Executing Pipeline...' : 'Run Entire Pipeline'}</span>
        </button>
      </div>

      {/* Steps List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {steps.map((step, idx) => (
          <React.Fragment key={step.id}>
            <div className={`pipeline-step-card ${step.status === 'running' ? 'active-step' : ''}`}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <input
                    type="checkbox"
                    checked={step.enabled}
                    onChange={() => toggleStep(step.id)}
                    style={{ accentColor: 'var(--accent-cyan)' }}
                  />
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {step.label}
                  </span>
                  <span className="tool-badge-pill" style={{ background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc' }}>
                    {TOOLS_CATALOG[step.tool]?.category}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {step.status === 'completed' && <CheckCircle2 size={16} color="var(--accent-emerald)" />}
                  {step.status === 'running' && <Clock size={16} color="var(--accent-amber)" />}
                  <button
                    onClick={() => removeStep(step.id)}
                    style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer' }}
                    title="Remove Step"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Step Output Preview (if executed) */}
              {step.outputAsset && (
                <div
                  onClick={() => onSelectAsset(step.outputAsset!)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: 8,
                    borderRadius: 6,
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    marginTop: 8,
                    cursor: 'pointer',
                  }}
                >
                  <img
                    src={step.outputAsset.previewUrl || step.outputAsset.url}
                    alt={step.outputAsset.title}
                    style={{ width: 36, height: 36, borderRadius: 4, objectFit: 'cover' }}
                  />
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#34d399' }}>
                      Stage Output Ready (Click to View on Canvas)
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      {step.outputAsset.id.slice(0, 16)}...
                    </div>
                  </div>
                </div>
              )}
            </div>

            {idx < steps.length - 1 && (
              <div className="pipeline-arrow-separator">
                <ArrowDown size={18} />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Add Step Control */}
      <div
        style={{
          display: 'flex',
          gap: 10,
          alignItems: 'center',
          marginTop: 14,
          padding: 12,
          background: 'var(--bg-surface-2)',
          borderRadius: 8,
          border: '1px dashed var(--border-subtle)',
        }}
      >
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Add Pipeline Stage:</span>
        <select
          value={selectedToolToAdd}
          onChange={(e) => setSelectedToolToAdd(e.target.value as GenerativeToolId)}
          className="command-input"
          style={{ flex: 1, padding: '6px 10px', fontSize: 12 }}
        >
          {Object.values(TOOLS_CATALOG).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.category})
            </option>
          ))}
        </select>
        <button
          onClick={addStep}
          className="action-btn"
          style={{
            background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
            color: '#fff',
            border: 'none',
            padding: '6px 14px',
            borderRadius: 6,
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <Plus size={14} />
          Add Stage
        </button>
      </div>
    </div>
  );
};
