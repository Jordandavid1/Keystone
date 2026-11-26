'use client';

/**
 * Studio state — docs/UI_SCHEMA.md §5.1.
 * One typed reducer + context. Presentational state (zoom, split %, disclosure) stays in components.
 */
import React, { createContext, useContext, useMemo, useReducer } from 'react';
import type { WebContext } from '../intents';
import type { AuthMode, CurrentUser } from '../api';
import type { AuthVia } from '../auth';
import type { LineageEdge } from '../lineage';
import { TOOLS_CATALOG } from '../toolsCatalog';
import {
  AccountInfo,
  CanonicalPlaybook,
  CanvasViewMode,
  ContentMode,
  EngineStatus,
  Generation,
  GenerativeToolId,
  Intent,
  LedgerState,
  Persona,
  RecipeSummary,
  SessionMessage,
  SessionSummary,
  SidebarPanel,
  StudioAsset,
  StudioControls,
  StudioPreferences,
  VideoFramerate,
} from '../types';

export type { Persona };

export interface Project {
  id: string;
  name: string;
  description?: string | null;
  content_mode?: ContentMode | null;
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

export const PROJECT_STORAGE_KEY = 'keystone.studio.projectId';
export const SESSION_STORAGE_KEY = 'keystone.studio.sessionId';
export const PREFS_STORAGE_KEY = 'keystone.studio.preferences';

export const DEFAULT_PREFERENCES: StudioPreferences = {
  qualityTier: 'high',
  evalBudget: 'standard',
  defaultContentMode: 'sfw',
  defaultSeed: null,
  outputPrefs: {
    framerate: 30,
    format: 'auto',
    c2paBadge: true,
  },
};

export function readStoredString(key: string): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const val = window.localStorage.getItem(key);
    return val && val.trim() ? val.trim() : null;
  } catch {
    return null;
  }
}

export function writeStoredString(key: string, value: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (value && value.trim()) window.localStorage.setItem(key, value.trim());
    else window.localStorage.removeItem(key);
  } catch {
    /* ignore storage errors in restricted contexts */
  }
}

export function loadStoredPreferences(): StudioPreferences {
  if (typeof window === 'undefined') return { ...DEFAULT_PREFERENCES, outputPrefs: { ...DEFAULT_PREFERENCES.outputPrefs } };
  try {
    const raw = window.localStorage.getItem(PREFS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFERENCES, outputPrefs: { ...DEFAULT_PREFERENCES.outputPrefs } };
    const parsed = JSON.parse(raw);
    return {
      qualityTier: parsed?.qualityTier === 'draft' || parsed?.qualityTier === 'master' ? parsed.qualityTier : 'high',
      evalBudget: parsed?.evalBudget === 'minimal' || parsed?.evalBudget === 'thorough' ? parsed.evalBudget : 'standard',
      defaultContentMode: parsed?.defaultContentMode === 'unrestricted' ? 'unrestricted' : 'sfw',
      defaultSeed: typeof parsed?.defaultSeed === 'number' && Number.isFinite(parsed.defaultSeed) ? parsed.defaultSeed : null,
      outputPrefs: {
        framerate: [30, 60, 100, 120].includes(Number(parsed?.outputPrefs?.framerate))
          ? Number(parsed.outputPrefs.framerate)
          : 30,
        format: ['png', 'webp', 'mp4'].includes(parsed?.outputPrefs?.format) ? parsed.outputPrefs.format : 'auto',
        c2paBadge: parsed?.outputPrefs?.c2paBadge !== false,
      },
    };
  } catch {
    return { ...DEFAULT_PREFERENCES, outputPrefs: { ...DEFAULT_PREFERENCES.outputPrefs } };
  }
}

export function saveStoredPreferences(prefs: StudioPreferences): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(PREFS_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore storage errors */
  }
}

export interface StudioState {
  composer: {
    intent: Intent;
    explicitTool: GenerativeToolId | null;
    selectedModel: string | null;
    prompt: string;
    references: StudioAsset[];
    playbook: CanonicalPlaybook | null;
    useCase: string | null;
    web: WebContext | null;
    personaId: string | null;
  };
  controls: StudioControls;
  library: {
    assets: StudioAsset[];
    selectedId: string | null;
    compareId: string | null;
    favorites: string[];
    loaded: boolean;
    loadError: string | null;
    lineageEdges: LineageEdge[];
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
    /** Tab the settings modal opens on; 'account', 'content', or 'engine'. */
    settingsTab: 'account' | 'content' | 'engine' | null;
    fps: number;
    guides: boolean;
    matte: 'none' | 'scope' | 'flat' | 'tv' | 'reel';
    matureFilter: 'all' | 'sfw' | 'mature';
    showC2paBadge: boolean;
    ageGateOpen: boolean;
  };
  system: {
    session: SessionState;
    account: AccountInfo | null;
    contentMode: ContentMode;
    ageVerified: boolean;
    preferences: StudioPreferences;
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
    sessionId: string | null;
    activeSession: SessionSummary | null;
    sessionMessages: SessionMessage[];
    recipes: RecipeSummary[];
    assetsRefreshSeq: number;
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
  fps: 30,
  look: { lut: 'none', exposure: 0, contrast: 100, saturation: 100, warmth: 0 },
};

export const initialState: StudioState = {
  composer: {
    intent: 'create',
    explicitTool: null,
    selectedModel: null,
    prompt: '',
    references: [],
    playbook: null,
    useCase: null,
    web: null,
    personaId: null,
  },
  controls: DEFAULT_CONTROLS,
  library: { assets: [], selectedId: null, compareId: null, favorites: [], loaded: false, loadError: null, lineageEdges: [] },
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
    fps: 30,
    guides: false,
    matte: 'none',
    matureFilter: 'all',
    showC2paBadge: true,
    ageGateOpen: false,
  },
  system: {
    session: { status: 'checking', user: null, via: null, mode: null, error: null },
    account: null,
    contentMode: 'sfw',
    ageVerified: false,
    preferences: DEFAULT_PREFERENCES,
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
    sessionId: null,
    activeSession: null,
    sessionMessages: [],
    recipes: [],
    assetsRefreshSeq: 0,
  },
};

export type Action =
  | { type: 'SET_INTENT'; intent: Intent }
  | { type: 'SET_TOOL'; tool: GenerativeToolId | null }
  | { type: 'SET_MODEL'; model: string | null }
  | { type: 'SET_PROMPT'; prompt: string }
  | { type: 'SET_PERSONA'; personaId: string | null }
  | { type: 'ADD_REFERENCE'; asset: StudioAsset }
  | { type: 'REMOVE_REFERENCE'; id: string }
  | { type: 'CLEAR_REFERENCES' }
  | { type: 'SET_PLAYBOOK'; playbook: CanonicalPlaybook | null }
  | { type: 'SET_USE_CASE'; useCase: string | null }
  | { type: 'SET_WEB'; web: WebContext | null }
  | { type: 'SET_CONTROLS'; patch: Partial<StudioControls> }
  | { type: 'SET_LOOK'; patch: Partial<StudioControls['look']> }
  | { type: 'ASSETS_LOADED'; assets: StudioAsset[]; replace?: boolean }
  | { type: 'HYDRATE_LINEAGE'; edges: LineageEdge[]; parentMap?: Record<string, string>; depictsMap?: Record<string, { personaId: string; personaVersion?: number | null }> }
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
  | { type: 'SET_PROJECT'; projectId: string | null }
  | { type: 'SET_SESSION'; session: SessionSummary | null; messages?: SessionMessage[] }
  | { type: 'SET_PREFERENCES'; patch: Partial<StudioPreferences> }
  | { type: 'SET_CONTENT_MODE'; contentMode: ContentMode; ageVerified?: boolean }
  | { type: 'REFRESH_ASSETS' }
  | { type: 'UI'; patch: Partial<StudioState['ui']> }
  | { type: 'SYSTEM'; patch: Partial<StudioState['system']> };

function uniqueById(list: StudioAsset[]): StudioAsset[] {
  const seen = new Set<string>();
  return list.filter((a) => (seen.has(a.id) ? false : (seen.add(a.id), true)));
}

function uniqueEdges(edges: LineageEdge[]): LineageEdge[] {
  const map = new Map<string, LineageEdge>();
  for (const e of edges) {
    if (e.from && e.to && e.from !== e.to) {
      map.set(`${e.from}->${e.to}`, e);
    }
  }
  return Array.from(map.values());
}

function intentForTool(tool: GenerativeToolId): Intent {
  const cat = TOOLS_CATALOG[tool]?.category || 'Image Generation';
  if (cat.startsWith('Video')) return 'animate';
  if (cat === 'Image Modification') return 'edit';
  if (cat === 'Cognition & Audio') return 'analyze';
  return 'create';
}

export function reducer(state: StudioState, action: Action): StudioState {
  switch (action.type) {
    case 'SET_INTENT':
      return {
        ...state,
        composer: {
          ...state.composer,
          intent: action.intent,
          explicitTool: null,
          selectedModel: null,
        },
      };
    case 'SET_TOOL': {
      if (!action.tool) {
        return { ...state, composer: { ...state.composer, explicitTool: null, selectedModel: null } };
      }
      const def = TOOLS_CATALOG[action.tool];
      const nextIntent = intentForTool(action.tool);
      return {
        ...state,
        composer: {
          ...state.composer,
          intent: nextIntent,
          explicitTool: action.tool,
          selectedModel: def?.defaultModel || null,
        },
      };
    }
    case 'SET_MODEL':
      return { ...state, composer: { ...state.composer, selectedModel: action.model } };
    case 'SET_PROMPT':
      return { ...state, composer: { ...state.composer, prompt: action.prompt } };
    case 'SET_PERSONA':
      return { ...state, composer: { ...state.composer, personaId: action.personaId } };
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
      return {
        ...state,
        controls: { ...state.controls, ...action.patch },
        ui: action.patch.fps ? { ...state.ui, fps: action.patch.fps } : state.ui,
      };
    case 'SET_LOOK':
      return { ...state, controls: { ...state.controls, look: { ...state.controls.look, ...action.patch } } };
    case 'ASSETS_LOADED': {
      const incoming = action.assets;
      const merged = action.replace
        ? uniqueById(incoming).sort((a, b) => b.createdAt - a.createdAt)
        : uniqueById([...state.library.assets, ...incoming]).sort((a, b) => b.createdAt - a.createdAt);
      const selectedExists = merged.some((a) => a.id === state.library.selectedId);
      return {
        ...state,
        library: {
          ...state.library,
          assets: merged,
          selectedId: selectedExists ? state.library.selectedId : null,
          loaded: true,
          loadError: null,
        },
      };
    }
    case 'HYDRATE_LINEAGE': {
      const parentMap = action.parentMap || {};
      const depictsMap = action.depictsMap || {};
      const assets = state.library.assets.map((a) => {
        const dep = depictsMap[a.id];
        return {
          ...a,
          parentId: a.parentId || parentMap[a.id] || null,
          personaId: a.personaId || dep?.personaId || null,
          personaVersion: a.personaVersion ?? dep?.personaVersion ?? null,
        };
      });
      const lineageEdges = uniqueEdges([...state.library.lineageEdges, ...action.edges]);
      return { ...state, library: { ...state.library, assets, lineageEdges } };
    }
    case 'IDENTITY_CHANGED':
      writeStoredString(PROJECT_STORAGE_KEY, null);
      writeStoredString(SESSION_STORAGE_KEY, null);
      return {
        ...state,
        composer: { ...state.composer, references: [], personaId: null },
        library: { ...initialState.library },
        system: {
          ...state.system,
          account: null,
          contentMode: 'sfw',
          ageVerified: false,
          personas: [],
          projects: [],
          projectId: null,
          sessionId: null,
          activeSession: null,
          sessionMessages: [],
          recipes: [],
          personasError: null,
          projectsError: null,
        },
      };
    case 'ASSETS_LOAD_FAILED':
      return { ...state, library: { ...state.library, loaded: true, loadError: action.error } };
    case 'ASSETS_ADDED': {
      if (!action.assets.length) return state;
      const assets = uniqueById([...action.assets, ...state.library.assets]);
      const newEdges: LineageEdge[] = action.assets
        .filter((a) => a.parentId)
        .map((a) => ({ from: a.parentId as string, to: a.id }));
      return {
        ...state,
        library: {
          ...state.library,
          assets,
          selectedId: action.select === false ? state.library.selectedId : action.assets[0].id,
          lineageEdges: uniqueEdges([...state.library.lineageEdges, ...newEdges]),
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
    case 'SET_PROJECT': {
      writeStoredString(PROJECT_STORAGE_KEY, action.projectId);
      const changed = state.system.projectId !== action.projectId;
      return {
        ...state,
        library: changed ? { ...state.library, loaded: false, lineageEdges: [] } : state.library,
        system: {
          ...state.system,
          projectId: action.projectId,
          assetsRefreshSeq: state.system.assetsRefreshSeq + (changed ? 1 : 0),
        },
      };
    }
    case 'SET_SESSION': {
      const nextId = action.session?.id || null;
      writeStoredString(SESSION_STORAGE_KEY, nextId);
      return {
        ...state,
        system: {
          ...state.system,
          sessionId: nextId,
          activeSession: action.session,
          sessionMessages: action.messages ?? state.system.sessionMessages,
        },
      };
    }
    case 'SET_PREFERENCES': {
      const next: StudioPreferences = {
        ...state.system.preferences,
        ...action.patch,
        outputPrefs: {
          ...state.system.preferences.outputPrefs,
          ...(action.patch.outputPrefs || {}),
        },
      };
      saveStoredPreferences(next);
      const rawRate = Number(next.outputPrefs.framerate);
      const syncedControlFps: VideoFramerate = ([30, 60, 100, 120] as const).includes(rawRate as VideoFramerate)
        ? (rawRate as VideoFramerate)
        : state.controls.fps;
      return {
        ...state,
        controls: {
          ...state.controls,
          quality: next.qualityTier,
          fps: syncedControlFps,
        },
        ui: {
          ...state.ui,
          fps: next.outputPrefs.framerate || 30,
          showC2paBadge: next.outputPrefs.c2paBadge,
        },
        system: {
          ...state.system,
          preferences: next,
        },
      };
    }
    case 'SET_CONTENT_MODE': {
      const nextMode = action.contentMode;
      const nextAge = action.ageVerified ?? state.system.ageVerified;
      const assetsFiltered =
        nextMode === 'sfw' ? state.library.assets.filter((a) => !a.mature) : state.library.assets;
      const selectedKeep = assetsFiltered.some((a) => a.id === state.library.selectedId)
        ? state.library.selectedId
        : null;
      return {
        ...state,
        library: {
          ...state.library,
          assets: assetsFiltered,
          selectedId: selectedKeep,
          loaded: false,
        },
        ui: {
          ...state.ui,
          matureFilter: nextMode === 'sfw' ? 'all' : state.ui.matureFilter,
        },
        system: {
          ...state.system,
          contentMode: nextMode,
          ageVerified: nextAge,
          preferences: { ...state.system.preferences, defaultContentMode: nextMode },
          assetsRefreshSeq: state.system.assetsRefreshSeq + 1,
        },
      };
    }
    case 'REFRESH_ASSETS':
      return {
        ...state,
        system: { ...state.system, assetsRefreshSeq: state.system.assetsRefreshSeq + 1 },
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
