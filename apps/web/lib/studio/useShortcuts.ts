'use client';

import { useEffect } from 'react';
import { INTENTS } from '../intents';
import { useStudio } from './store';

function typing(el: EventTarget | null): boolean {
  const t = el as HTMLElement | null;
  return !!t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
}

/** ⌘K palette · Alt+1–4 intents · [ / ] panels · / focuses the composer · Esc closes overlays. */
export function useShortcuts(focusComposer: () => void) {
  const { state, dispatch } = useStudio();
  const modal = state.ui.modal;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        dispatch({ type: 'OPEN_MODAL', modal: modal === 'command' ? null : 'command' });
        return;
      }
      if (e.altKey && /^Digit[1-4]$/.test(e.code)) {
        e.preventDefault();
        dispatch({ type: 'SET_INTENT', intent: INTENTS[Number(e.code.slice(5)) - 1].id });
        return;
      }
      if (modal || typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === '[') dispatch({ type: 'TOGGLE_PANEL' });
      else if (e.key === ']') dispatch({ type: 'TOGGLE_INSPECTOR' });
      else if (e.key === '/') {
        e.preventDefault();
        focusComposer();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dispatch, focusComposer, modal]);
}
