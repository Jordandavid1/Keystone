'use client';

import { useCallback, useRef, useState } from 'react';
import { executeGenerativeTool } from '../api';
import { buildInput, compilePrompt } from '../intents';
import { PipelineStep, StudioAsset } from '../types';
import { selectSelected, useStudio } from './store';

/** Developer-mode pipeline: chains capabilities explicitly, each step's output feeding the next. */
export function usePipeline() {
  const { state, dispatch } = useStudio();
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [running, setRunning] = useState(false);
  const stateRef = useRef(state);
  stateRef.current = state;

  const execute = useCallback(async () => {
    if (running) return;
    setRunning(true);
    const s = stateRef.current;
    let prior: StudioAsset | null = s.composer.references[0] || selectSelected(s);
    const next = [...steps];
    try {
      for (let i = 0; i < next.length; i += 1) {
        const step = next[i];
        if (!step.enabled) continue;
        next[i] = { ...step, status: 'running', error: undefined };
        setSteps([...next]);
        try {
          const compiled = compilePrompt({
            text: s.composer.prompt,
            playbook: s.composer.playbook,
            web: s.composer.web,
            lut: s.controls.look.lut,
            useCase: s.composer.useCase,
          });
          const input = buildInput({
            capability: step.tool,
            compiledPrompt: compiled,
            controls: s.controls,
            references: prior ? [prior] : [],
            playbook: s.composer.playbook,
            web: s.composer.web,
            extra: step.parameters || {},
          });
          const res = await executeGenerativeTool(step.tool, input);
          const out = (res.outputs || []).find((o) => o.url) || null;
          if (out) {
            const withParent = { ...out, parentId: out.parentId || prior?.id || null, title: step.label };
            dispatch({ type: 'ASSETS_ADDED', assets: [withParent] });
            prior = withParent;
          }
          next[i] = { ...next[i], status: 'completed', outputAsset: out };
          setSteps([...next]);
        } catch (err) {
          next[i] = { ...next[i], status: 'failed', error: err instanceof Error ? err.message : String(err) };
          setSteps([...next]);
          break;
        }
      }
    } finally {
      setRunning(false);
    }
  }, [dispatch, running, steps]);

  return { steps, setSteps, execute, running };
}
