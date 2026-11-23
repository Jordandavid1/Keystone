'use client';

import React, { useState } from 'react';
import { CornerDownLeft, ScanSearch, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { analyzeWithCognition } from '@/lib/api';
import { readableError } from '@/lib/errors';
import { useStudio } from '@/lib/studio/store';
import { Generation, StudioAsset } from '@/lib/types';
import { AssetThumb } from '../studio/AssetThumb';

/** Split artifact view (Grok pattern): the asset stays on the left, the multimodal vision analysis reads on the right. */
export function AnalysisPane({
  run,
  asset,
  onClose,
  onUseAsPrompt,
}: {
  run: Generation;
  asset: StudioAsset | null;
  onClose: () => void;
  onUseAsPrompt: (text: string) => void;
}) {
  const { state, dispatch } = useStudio();
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleInspect = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const promptText = question.trim() || 'Inspect this asset in detail: describe composition, lighting, subjects, and technical quality.';
    setBusy(true);
    setError(null);
    try {
      const res = await analyzeWithCognition({
        asset_id: asset?.id || null,
        prompt: promptText,
        session_id: state.system.sessionId,
        project_id: state.system.projectId,
        playbook_id: state.composer.playbook?.id || null,
        as: state.composer.personaId,
        persona_id: state.composer.personaId,
      });
      const text = (res.analysis || res.text || '').trim();
      if (!text) {
        throw new Error(res.error || 'Vision analysis returned no text.');
      }
      dispatch({
        type: 'RUN_UPDATED',
        id: run.id,
        patch: {
          prompt: promptText,
          text,
          status: 'succeeded',
          jobState: 'COMPLETED',
          finishedAt: Date.now(),
        },
      });
      setQuestion('');
    } catch (err) {
      setError(readableError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid size-full min-h-0 grid-cols-1 gap-4 p-4 sm:p-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
      <div className="flex min-h-0 flex-col items-center justify-center gap-3 max-lg:hidden">
        {asset ? (
          <>
            <AssetThumb asset={asset} fit="contain" className="max-h-full w-full rounded-frame bg-transparent shadow-frame" />
            <div className="text-meta text-ks-ink-3">
              Analyzing: <span className="text-ks-ink-2">{asset.title}</span>
            </div>
          </>
        ) : (
          <p className="max-w-[36ch] text-center text-body text-ks-ink-3">
            This question wasn&apos;t about a specific asset. Select one from Assets to inspect its pixels with KEYSTONE vision.
          </p>
        )}
      </div>
      <article className="flex min-h-0 flex-col overflow-hidden rounded-panel border border-ks-line bg-ks-chrome">
        <header className="flex items-start justify-between gap-3 border-b border-ks-line px-4 py-3">
          <div className="min-w-0">
            <div className="text-meta text-ks-ink-3">You asked</div>
            <p className="line-clamp-3 text-body text-ks-ink">{run.prompt}</p>
          </div>
          <Button variant="ghost" size="icon-sm" aria-label="Close answer" onClick={onClose}>
            <X />
          </Button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto px-4 py-4 ks-scroll">
          {error && (
            <div role="alert" className="mb-3 rounded-control border border-ks-deny/40 bg-ks-deny/10 px-3 py-2 text-meta text-ks-deny">
              {error}
            </div>
          )}
          <p className="max-w-[72ch] whitespace-pre-wrap text-body leading-6 text-ks-ink">
            {busy ? 'Inspecting asset via KEYSTONE cognition…' : run.text || 'Ask a question below to inspect this asset.'}
          </p>
        </div>
        <form onSubmit={handleInspect} className="flex items-center gap-2 border-t border-ks-line px-4 py-2.5">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={asset ? `Ask about ${asset.title}…` : 'Ask a follow-up question…'}
            aria-label="Follow-up asset inspection question"
            className="h-8 min-w-0 flex-1 rounded-control border border-ks-line-strong bg-ks-abyss px-2.5 text-meta text-ks-ink placeholder:text-ks-ink-3 focus:outline-none focus:ring-1 focus:ring-ks-indigo"
          />
          <Button type="submit" variant="outline" size="sm" disabled={busy}>
            <ScanSearch className="size-3.5" />
            {busy ? 'Analyzing…' : asset ? 'Inspect asset' : 'Ask'}
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={!run.text} onClick={() => onUseAsPrompt(run.text || '')}>
            <CornerDownLeft className="size-3.5" /> Use as prompt
          </Button>
        </form>
      </article>
    </div>
  );
}
