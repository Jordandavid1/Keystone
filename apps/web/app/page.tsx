'use client';


import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { TopBar } from '../components/TopBar';
import { ActivityBar } from '../components/ActivityBar';
import { LeftSidebar } from '../components/LeftSidebar';
import { CenterCanvas } from '../components/CenterCanvas';
import { RightInspector } from '../components/RightInspector';
import { FloatingComposer } from '../components/FloatingComposer';
import { PipelineBuilder } from '../components/PipelineBuilder';
import { CommandPalette } from '../components/Modals/CommandPalette';
import { PersonasModal } from '../components/Modals/PersonasModal';
import { WebScrapeModal, WebScrapeResult } from '../components/Modals/WebScrapeModal';
import {
  executeGenerativeTool,
  fetchCreditBalance,
  fetchEngineStatus,
  fetchPlaybooks,
  uploadMediaFile,
} from '../lib/api';
import { TOOLS_CATALOG } from '../lib/toolsCatalog';
import {
  CanonicalPlaybook,
  CanvasViewMode,
  GenerativeToolId,
  PipelineStep,
  StudioAsset,
} from '../lib/types';

const PROGRESS_STAGES = [
  'Understanding your request',
  'Planning the generation',
  'Preparing the workflow',
  'Creating & Synthesizing',
  'Checking the result with KHF',
  'Refining when necessary',
  'Finishing & Delivery',
];

function formatPlaybookContext(playbook: CanonicalPlaybook): string {
  const ctx = playbook.domain_context || {};
  const skills = (playbook.skills || [])
    .map((skill) => `- ${skill.name || skill.id}: ${skill.description || skill.capability || ''}`)
    .filter((line) => line.trim() !== '- :')
    .join('\n');
  return [
    `Playbook: ${playbook.label} (${playbook.id})`,
    `Intended outcome: ${playbook.outcome}`,
    ctx.system_framing ? `System framing: ${ctx.system_framing}` : '',
    ctx.domain_brief ? `Domain brief: ${ctx.domain_brief}` : '',
    ctx.default_visual_style ? `Default visual style: ${ctx.default_visual_style}` : '',
    ctx.default_environment ? `Default environment: ${ctx.default_environment}` : '',
    ctx.quality_standard ? `Quality standard: ${ctx.quality_standard}` : '',
    skills ? `Bound skills and workflows:\n${skills}` : '',
  ].filter(Boolean).join('\n');
}

function compilePrompt(userText: string, playbook: CanonicalPlaybook | null, web: WebScrapeResult | null): string {
  const sections: string[] = [];
  if (playbook) sections.push(formatPlaybookContext(playbook));
  if (web) {
    sections.push(`${web.styleHint}\n${web.summary}`.trim());
  }
  sections.push(userText.trim());
  return sections.filter(Boolean).join('\n\n');
}

export default function StudioPage() {
  const [activeTool, setActiveTool] = useState<GenerativeToolId>('by_prompt');
  const [promptText, setPromptText] = useState('');
  const [parameters, setParameters] = useState<Record<string, any>>({ ...TOOLS_CATALOG.by_prompt.defaultParameters });
  const [assets, setAssets] = useState<StudioAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<StudioAsset | null>(null);
  const [referenceAsset, setReferenceAsset] = useState<StudioAsset | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [stageText, setStageText] = useState('');
  const [stageIndex, setStageIndex] = useState(0);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [activeMode, setActiveMode] = useState<CanvasViewMode>('single');
  const [canvasAspectMask, setCanvasAspectMask] = useState('none');
  const [commandOpen, setCommandOpen] = useState(false);
  const [personasOpen, setPersonasOpen] = useState(false);
  const [webScrapeOpen, setWebScrapeOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('explorer');
  const [mobilePreview, setMobilePreview] = useState(false);
  const [guidesVisible, setGuidesVisible] = useState(false);
  const [creditBalance, setCreditBalance] = useState<number | null>(null);
  const [workerOnline, setWorkerOnline] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [llmResult, setLlmResult] = useState<string | null>(null);
  const [playbooks, setPlaybooks] = useState<CanonicalPlaybook[]>([]);
  const [attachedPlaybook, setAttachedPlaybook] = useState<CanonicalPlaybook | null>(null);
  const [webContext, setWebContext] = useState<WebScrapeResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchCreditBalance()
      .then(setCreditBalance)
      .catch(() => setCreditBalance(null));
    fetchEngineStatus()
      .then((status) => setWorkerOnline(Boolean(status.online)))
      .catch(() => setWorkerOnline(false));
    fetchPlaybooks()
      .then(setPlaybooks)
      .catch(() => setPlaybooks([]));
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const handleSelectTool = useCallback((tool: GenerativeToolId) => {
    setActiveTool(tool);
    setParameters({ ...TOOLS_CATALOG[tool].defaultParameters });
    if (tool === 'run_any_llm') setActiveTab('cognition');
  }, []);

  const prependAssets = useCallback((incoming: StudioAsset[]) => {
    if (!incoming.length) return;
    setAssets((prev) => [...incoming, ...prev]);
    setSelectedAsset(incoming[0]);
  }, []);

  const buildToolInput = useCallback((
    tool: GenerativeToolId,
    rawPrompt: string,
    params: Record<string, any>,
    refAsset: StudioAsset | null,
    priorAsset?: StudioAsset | null,
  ) => {
    const compiled = compilePrompt(rawPrompt, attachedPlaybook, webContext);
    const input: Record<string, any> = {
      ...params,
      prompt: compiled,
      positive_prompt: compiled,
    };
    if (attachedPlaybook) {
      input.playbook_id = attachedPlaybook.id;
      input.playbook_context = formatPlaybookContext(attachedPlaybook);
    }
    if (webContext) {
      input.web_context_url = webContext.url;
    }
    const ref = refAsset || priorAsset || null;
    if (ref) {
      input.ref_asset_id = ref.id;
      input.reference_asset_id = ref.id;
      if (tool === 'couplegen' || tool === 'collaber') {
        input.character_assets = [ref.id];
      }
    }
    return input;
  }, [attachedPlaybook, webContext]);

  const handleRunKeystone = useCallback(async () => {
    if (isGenerating) return;
    setGenerationError(null);
    setLlmResult(null);
    setIsGenerating(true);
    setStageIndex(2);
    setStageText(PROGRESS_STAGES[2]);
    try {
      setStageIndex(3);
      setStageText(PROGRESS_STAGES[3]);
      const result = await executeGenerativeTool(
        activeTool,
        buildToolInput(activeTool, promptText, parameters, referenceAsset),
      );
      setStageIndex(6);
      setStageText(PROGRESS_STAGES[6]);
      if (result.text) setLlmResult(result.text);
      prependAssets(result.outputs || []);
    } catch (err: any) {
      setGenerationError(err?.message || String(err));
    } finally {
      setIsGenerating(false);
    }
  }, [activeTool, buildToolInput, isGenerating, parameters, prependAssets, promptText, referenceAsset]);

  const handleExecutePipeline = useCallback(async () => {
    if (isPipelineRunning) return;
    setIsPipelineRunning(true);
    setGenerationError(null);
    setLlmResult(null);
    let prior: StudioAsset | null = referenceAsset || selectedAsset;
    const nextSteps = [...pipelineSteps];
    try {
      for (let i = 0; i < nextSteps.length; i += 1) {
        const step = nextSteps[i];
        if (!step.enabled) continue;
        nextSteps[i] = { ...step, status: 'running', error: undefined };
        setPipelineSteps([...nextSteps]);
        setIsGenerating(true);
        setStageIndex(3);
        setStageText(`Pipeline: ${step.label}`);
        try {
          const result = await executeGenerativeTool(
            step.tool,
            buildToolInput(step.tool, promptText, step.parameters || {}, referenceAsset, prior),
          );
          const output = (result.outputs && result.outputs[0]) || null;
          if (result.text) setLlmResult(result.text);
          if (output) {
            prependAssets([output]);
            prior = output;
          }
          nextSteps[i] = { ...nextSteps[i], status: 'completed', outputAsset: output };
          setPipelineSteps([...nextSteps]);
        } catch (err: any) {
          const message = err?.message || String(err);
          nextSteps[i] = { ...nextSteps[i], status: 'failed', error: message };
          setPipelineSteps([...nextSteps]);
          setGenerationError(message);
          break;
        }
      }
    } finally {
      setIsGenerating(false);
      setIsPipelineRunning(false);
    }
  }, [buildToolInput, isPipelineRunning, pipelineSteps, prependAssets, promptText, referenceAsset, selectedAsset]);

  const handleUploadFile = useCallback(async (file: File) => {
    setGenerationError(null);
    try {
      const asset = await uploadMediaFile(file);
      setAssets((prev) => [asset, ...prev]);
      setSelectedAsset(asset);
    } catch (err: any) {
      setGenerationError(err?.message || String(err));
    }
  }, []);

  const handleQuickUpscale = useCallback((factor: 2 | 4) => {
    setActiveTool('upscaler');
    setParameters({
      ...TOOLS_CATALOG.upscaler.defaultParameters,
      target_resolution: factor === 4 ? '4k' : '2k',
    });
    if (selectedAsset) setReferenceAsset(selectedAsset);
  }, [selectedAsset]);

  const handleSelectTab = useCallback((tab: string) => {
    setActiveTab(tab);
    if (tab === 'pipeline') setActiveMode('pipeline');
    if (tab === 'cognition') setActiveTool('run_any_llm');
    if (tab === 'audio') setPersonasOpen(true);
    if (tab === 'explorer' && activeMode === 'pipeline') setActiveMode('single');
  }, [activeMode]);

  const shellClass = useMemo(
    () => `workspace-shell${mobilePreview ? ' mobile-preview-mode' : ''}`,
    [mobilePreview],
  );

  return (
    <div className={shellClass}>
      <TopBar
        creditBalance={creditBalance}
        workerOnline={workerOnline}
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenPersonasModal={() => setPersonasOpen(true)}
        onOpenWebScrapeModal={() => setWebScrapeOpen(true)}
        onToggleFramingGuides={() => setGuidesVisible((value) => !value)}
        onToggleFullscreen={() => {
          if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
          else document.exitFullscreen?.();
        }}
        onToggleMobilePreview={() => setMobilePreview((value) => !value)}
        mobilePreview={mobilePreview}
        guidesVisible={guidesVisible}
      />

      <ActivityBar
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        onOpenSettings={() => setGenerationError('Studio settings from v1 are not ported into this Next.js shell yet.')}
      />

      <LeftSidebar
        activeTool={activeTool}
        onSelectTool={handleSelectTool}
        assets={assets}
        selectedAssetId={selectedAsset?.id || null}
        onSelectAsset={setSelectedAsset}
        onUploadFile={handleUploadFile}
        playbooks={playbooks}
        attachedPlaybookId={attachedPlaybook?.id || null}
        onAttachPlaybook={setAttachedPlaybook}
        onDetachPlaybook={() => setAttachedPlaybook(null)}
      />

      {activeTab === 'pipeline' || activeMode === 'pipeline' ? (
        <main className="region-canvas">
          <PipelineBuilder
            steps={pipelineSteps}
            onUpdateSteps={setPipelineSteps}
            onExecutePipeline={handleExecutePipeline}
            isExecuting={isPipelineRunning}
            onSelectAsset={setSelectedAsset}
          />
        </main>
      ) : (
        <CenterCanvas
          activeMode={activeMode}
          onChangeMode={setActiveMode}
          selectedAsset={selectedAsset}
          referenceAsset={referenceAsset}
          assets={assets}
          onSelectAsset={setSelectedAsset}
          isGenerating={isGenerating}
          stageText={stageText}
          stageIndex={stageIndex}
          framingGuidesVisible={guidesVisible}
          activeAspectMask={canvasAspectMask}
          onChangeAspectMask={setCanvasAspectMask}
        />
      )}

      <RightInspector
        activeTool={activeTool}
        parameters={parameters}
        onChangeParameters={setParameters}
        selectedAsset={selectedAsset}
        onSetAsReference={setReferenceAsset}
        onQuickUpscale={handleQuickUpscale}
      />

      <FloatingComposer
        promptText={promptText}
        onChangePrompt={setPromptText}
        activeTool={activeTool}
        onSelectTool={handleSelectTool}
        referenceAsset={referenceAsset}
        onRemoveReference={() => setReferenceAsset(null)}
        onAttachFileClick={() => fileInputRef.current?.click()}
        onOpenWebModal={() => setWebScrapeOpen(true)}
        onSubmit={handleRunKeystone}
        isGenerating={isGenerating}
      />

      <footer className="vscode-status-bar">
        <div className="status-left">
          <span className="status-item">
            <span className="status-online-dot" style={{ background: workerOnline ? '#10b981' : '#64748b' }} />
            {workerOnline ? 'Colab engine configured' : 'Colab engine offline'}
          </span>
          <span className="status-item">Tool: {TOOLS_CATALOG[activeTool].name}</span>
        </div>
        <div className="status-center">
          {attachedPlaybook && <span className="status-item">Playbook context: {attachedPlaybook.label}</span>}
          {webContext && <span className="status-item">@Web: {webContext.title}</span>}
        </div>
        <div className="status-right">
          <span className="status-item">{assets.length} assets</span>
        </div>
      </footer>

      {generationError && (
        <div className="progress-overlay-card" style={{ borderColor: 'rgba(244,63,94,0.55)' }} role="alert">
          <div className="progress-header">
            <div className="progress-stage-label">Generation error</div>
            <button className="icon-btn" onClick={() => setGenerationError(null)}>Dismiss</button>
          </div>
          <div style={{ fontSize: 12, color: '#fda4af', whiteSpace: 'pre-wrap' }}>{generationError}</div>
        </div>
      )}

      {llmResult && (
        <div className="progress-overlay-card" style={{ top: generationError ? 180 : 68 }} role="status">
          <div className="progress-header">
            <div className="progress-stage-label">LLM result</div>
            <button className="icon-btn" onClick={() => setLlmResult(null)}>Dismiss</button>
          </div>
          <div className="code-block-mono">{llmResult}</div>
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,video/*,audio/*"
        hidden
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) handleUploadFile(e.target.files[0]);
          e.target.value = '';
        }}
      />

      <CommandPalette
        open={commandOpen}
        onClose={() => setCommandOpen(false)}
        onSelectTool={handleSelectTool}
        onChangeMode={(mode) => {
          setActiveMode(mode);
          if (mode === 'pipeline') setActiveTab('pipeline');
          else setActiveTab('explorer');
        }}
        onOpenPersonas={() => setPersonasOpen(true)}
        onOpenWebScrape={() => setWebScrapeOpen(true)}
        onOpenPipeline={() => {
          setActiveTab('pipeline');
          setActiveMode('pipeline');
        }}
      />
      <PersonasModal open={personasOpen} onClose={() => setPersonasOpen(false)} />
      <WebScrapeModal
        open={webScrapeOpen}
        onClose={() => setWebScrapeOpen(false)}
        onAttach={(result) => {
          setWebContext(result);
          if (result.styleHint && !promptText.includes(result.styleHint)) {
            setPromptText((current) => `${result.styleHint} ${current}`.trim());
          }
        }}
      />
    </div>
  );
}
