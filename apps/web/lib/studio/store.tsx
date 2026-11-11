'use client';

/**
 * Studio state — docs/UI_SCHEMA.md §5.1.
 * One typed reducer + context. Presentational state (zoom, split %, disclosure) stays in components.
 */
import React, { createContext, useContext, useMemo, useReducer } from 'react';
import type { WebContext } from '../intents';
import type { AuthMode, CurrentUser } from '../api';
import type { AuthVia } from '../auth';
import {
  CanonicalPlaybook,
  CanvasViewMode,
  EngineStatus,
  Generation,
  Intent,
  LedgerState,
  SidebarPanel,
  StudioAsset,
  StudioControls,
} from '../types';

export interface Persona {
  id: string;
  name: string;
  voice_name?: string;
  voice_id?: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string | null;
}

export type Modal =
  | null
  | 'command'
  | 'personas'
  | 'web'
  | 'settings'
  | 'projects'
  | 'sessions'
  | 'credits'
  | 'worker'
  | 'agent';

export interface StudioState {
  composer: {
    intent: Intent;
    prompt: string;
    references: StudioAsset[];
    playbook: CanonicalPlaybook | null;
    useCase: string | null;
    web: WebContext | null;
  };
  controls: StudioControls;
  library: {
    assets: StudioAsset[];
    selectedId: string | null;
    compareId: string | null;
    favorites: string[];
    loaded: boolean;
    loadError: string | null;
  };
  runs: Generation[];
  ui: {
    view: CanvasViewMode;
    panel: SidebarPanel;
    panelOpen: boolean;
    inspectorOpen: boolean;
    developer: boolean;
    modal: Modal;
    notice: { tone: 'error' | 'info'; text: string } | null;
    analysisRunId: string | null;
    /** Tab the settings modal opens on; 'account' jumps straight to sign-in and API key. */
    settingsTab: 'account' | null;
    fps: number;
    guides: boolean;
    matte: 'none' | 'scope' | 'flat' | 'tv' | 'reel';
  };
  system: {
    session: SessionState;
    personasError: string | null;
    projectsError: string | null;
    engine: EngineStatus | null;
    engineError: string | null;
    ledger: LedgerState | null;
    playbooks: CanonicalPlaybook[];
    playbooksError: string | null;
    playbooksLoaded: boolean;
    personas: Persona[];
    projects: Project[];
    projectId: string | null;
  };
}

export interface SessionState {
  /** checking → signed_in | signed_out. 'error' means the auth check itself failed (API down). */
  status: 'checking' | 'signed_in' | 'signed_out' | 'error';
  user: CurrentUser | null;
  via: AuthVia | null;
  mode: AuthMode | null;
  /** Why the last check didn't sign in (e.g. a saved key the server rejected). */
  error: string | null;
}

export const DEFAULT_CONTROLS: StudioControls = {
  aspect: '16:9',
  quality: 'high',
  results: 1,
  strength: 0.65,
  motion: 'orbit',
  motionSpeed: 1,
  duration: 5,
  look: { lut: 'none', exposure: 0, contrast: 100, saturation: 100, warmth: 0 },
};

export const initialState: StudioState = {
  composer: { intent: 'create', prompt: '', references: [], playbook: null, useCase: null, web: null },
  controls: DEFAULT_CONTROLS,
  library: { assets: [], selectedId: null, compareId: null, favorites: [], loaded: false, loadError: null },
  runs: [],
  ui: {
    view: 'single',
    panel: 'create',
    panelOpen: true,
    inspectorOpen: true,
    developer: false,
    modal: null,
    notice: null,
    analysisRunId: null,
    settingsTab: null,
    fps: 24,
    guides: false,
    matte: 'none',
  },
  system: {
    session: { status: 'checking', user: null, via: null, mode: null, error: null },
    personasError: null,
    projectsError: null,
    engine: null,
    engineError: null,
    ledger: null,
    playbooks: [],
    playbooksError: null,
    playbooksLoaded: false,
    personas: [],
    projects: [],
    projectId: null,
  },
};

export type Action =
  | { type: 'SET_INTENT'; intent: Intent }
  | { type: 'SET_PROMPT'; prompt: string }
  | { type: 'ADD_REFERENCE'; asset: StudioAsset }
  | { type: 'REMOVE_REFERENCE'; id: string }
  | { type: 'CLEAR_REFERENCES' }
  | { type: 'SET_PLAYBOOK'; playbook: CanonicalPlaybook | null }
  | { type: 'SET_USE_CASE'; useCase: string | null }
  | { type: 'SET_WEB'; web: WebContext | null }
  | { type: 'SET_CONTROLS'; patch: Partial<StudioControls> }
  | { type: 'SET_LOOK'; patch: Partial<StudioControls['look']> }
  | { type: 'ASSETS_LOADED'; assets: StudioAsset[] }
  | { type: 'IDENTITY_CHANGED' }
  | { type: 'ASSETS_LOAD_FAILED'; error: string }
  | { type: 'ASSETS_ADDED'; assets: StudioAsset[]; select?: boolean }
  | { type: 'SELECT_ASSET'; id: string | null }
  | { type: 'SET_COMPARE'; id: string | null }
  | { type: 'TOGGLE_FAVORITE'; id: string }
  | { type: 'RUN_STARTED'; run: Generation }
  | { type: 'RUN_UPDATED'; id: string; patch: Partial<Generation> }
  | { type: 'SET_VIEW'; view: CanvasViewMode }
  | { type: 'SET_PANEL'; panel: SidebarPanel }
  | { type: 'TOGGLE_PANEL'; open?: boolean }
  | { type: 'TOGGLE_INSPECTOR'; open?: boolean }
  | { type: 'TOGGLE_DEVELOPER' }
  | { type: 'OPEN_MODAL'; modal: Modal }
  | { type: 'NOTICE'; notice: StudioState['ui']['notice'] }
  | { type: 'SHOW_ANALYSIS'; runId: string | null }
  | { type: 'UI'; patch: Partial<StudioState['ui']> }
  | { type: 'SYSTEM'; patch: Partial<StudioState['system']> };

function uniqueById(list: StudioAsset[]): StudioAsset[] {
  const seen = new Set<string>();
  return list.filter((a) => (seen.has(a.id) ? false : (seen.add(a.id), true)));
}

export function reducer(state: StudioState, action: Action): StudioState {
  switch (action.type) {
    case 'SET_INTENT':
      return { ...state, composer: { ...state.composer, intent: action.intent } };
    case 'SET_PROMPT':
      return { ...state, composer: { ...state.composer, prompt: action.prompt } };
    case 'ADD_REFERENCE': {
      const refs = state.composer.references.filter((r) => r.id !== action.asset.id);
      return { ...state, composer: { ...state.composer, references: [action.asset, ...refs].slice(0, 4) } };
    }
    case 'REMOVE_REFERENCE':
      return {
        ...state,
        composer: { ...state.composer, references: state.composer.references.filter((r) => r.id !== action.id) },
      };
    case 'CLEAR_REFERENCES':
      return { ...state, composer: { ...state.composer, references: [] } };
    case 'SET_PLAYBOOK':
      return { ...state, composer: { ...state.composer, playbook: action.playbook, useCase: null } };
    case 'SET_USE_CASE':
      return { ...state, composer: { ...state.composer, useCase: action.useCase } };
    case 'SET_WEB':
      return { ...state, composer: { ...state.composer, web: action.web } };
    case 'SET_CONTROLS':
      return { ...state, controls: { ...state.controls, ...action.patch } };
    case 'SET_LOOK':
      return { ...state, controls: { ...state.controls, look: { ...state.controls.look, ...action.patch } } };
    case 'ASSETS_LOADED': {
      const merged = uniqueById([...state.library.assets, ...action.assets]).sort((a, b) => b.createdAt - a.createdAt);
      return { ...state, library: { ...state.library, assets: merged, loaded: true, loadError: null } };
    }
    case 'IDENTITY_CHANGED':
      // A different account (or none) is now in use: drop everything that belonged to the previous one.
      return {
        ...state,
        composer: { ...state.composer, references: [] },
        library: { ...initialState.library },
        system: { ...state.system, personas: [], projects: [], projectId: null, personasError: null, projectsError: null },
      };
    case 'ASSETS_LOAD_FAILED':
      return { ...state, library: { ...state.library, loaded: true, loadError: action.error } };
    case 'ASSETS_ADDED': {
      if (!action.assets.length) return state;
      const assets = uniqueById([...action.assets, ...state.library.assets]);
      return {
        ...state,
        library: {
          ...state.library,
          assets,
          selectedId: action.select === false ? state.library.selectedId : action.assets[0].id,
        },
      };
    }
    case 'SELECT_ASSET':
      return { ...state, library: { ...state.library, selectedId: action.id } };
    case 'SET_COMPARE':
      return { ...state, library: { ...state.library, compareId: action.id } };
    case 'TOGGLE_FAVORITE': {
      const fav = state.library.favorites;
      return {
        ...state,
        library: {
          ...state.library,
          favorites: fav.includes(action.id) ? fav.filter((f) => f !== action.id) : [action.id, ...fav],
        },
      };
    }
    case 'RUN_STARTED':
      return { ...state, runs: [action.run, ...state.runs] };
    case 'RUN_UPDATED':
      return { ...state, runs: state.runs.map((r) => (r.id === action.id ? { ...r, ...action.patch } : r)) };
    case 'SET_VIEW':
      return { ...state, ui: { ...state.ui, view: action.view } };
    case 'SET_PANEL':
      return { ...state, ui: { ...state.ui, panel: action.panel, panelOpen: true } };
    case 'TOGGLE_PANEL':
      return { ...state, ui: { ...state.ui, panelOpen: action.open ?? !state.ui.panelOpen } };
    case 'TOGGLE_INSPECTOR':
      return { ...state, ui: { ...state.ui, inspectorOpen: action.open ?? !state.ui.inspectorOpen } };
    case 'TOGGLE_DEVELOPER':
      return { ...state, ui: { ...state.ui, developer: !state.ui.developer } };
    case 'OPEN_MODAL':
      return { ...state, ui: { ...state.ui, modal: action.modal } };
    case 'NOTICE':
      return { ...state, ui: { ...state.ui, notice: action.notice } };
    case 'SHOW_ANALYSIS':
      return {
        ...state,
        ui: { ...state.ui, analysisRunId: action.runId, view: action.runId ? 'analysis' : 'single' },
      };
    case 'UI':
      return { ...state, ui: { ...state.ui, ...action.patch } };
    case 'SYSTEM':
      return { ...state, system: { ...state.system, ...action.patch } };
    default:
      return state;
  }
}

interface StudioContextValue {
  state: StudioState;
  dispatch: React.Dispatch<Action>;
}

const StudioContext = createContext<StudioContextValue | null>(null);

export function StudioProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return <StudioContext.Provider value={value}>{children}</StudioContext.Provider>;
}

export function useStudio(): StudioContextValue {
  const ctx = useContext(StudioContext);
  if (!ctx) throw new Error('useStudio must be used inside <StudioProvider>');
  return ctx;
}

/* Selectors */
export function selectSelected(state: StudioState): StudioAsset | null {
  return state.library.assets.find((a) => a.id === state.library.selectedId) || null;
}

export function selectCompare(state: StudioState): StudioAsset | null {
  return state.library.assets.find((a) => a.id === state.library.compareId) || null;
}

export function selectActiveRun(state: StudioState): Generation | null {
  return state.runs.find((r) => r.status === 'queued' || r.status === 'processing') || null;
}

export function selectAsset(state: StudioState, id: string | null | undefined): StudioAsset | null {
  if (!id) return null;
  return state.library.assets.find((a) => a.id === id) || null;
}
