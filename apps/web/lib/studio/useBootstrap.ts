'use client';
import { readableError } from '@/lib/errors';

import { useCallback, useEffect, useRef } from 'react';
import {
  ApiError,
  fetchAccount,
  fetchAssets,
  fetchAssetLineage,
  fetchAuthMode,
  fetchCreditLedger,
  fetchCurrentUser,
  fetchEngineStatus,
  fetchPersonas,
  fetchPlaybooks,
  fetchProjects,
  fetchRecipes,
  fetchSession,
  fetchSessionMessages,
} from '../api';
import { heldCredential, onAuthChange } from '../auth';
import type { LineageEdge } from '../lineage';
import {
  PROJECT_STORAGE_KEY,
  SESSION_STORAGE_KEY,
  loadStoredPreferences,
  readStoredString,
  useStudio,
  writeStoredString,
} from './store';

const STATUS_POLL_MS = 15000;

const message = readableError;

/** Initial data load + engine/ledger polling + project/session/lineage hydration. */
export function useBootstrap() {
  const { state, dispatch } = useStudio();
  const projectId = state.system.projectId;
  const sessionId = state.system.sessionId;
  const contentMode = state.system.contentMode;
  const assetsRefreshSeq = state.system.assetsRefreshSeq;
  const session = state.system.session;
  const signedIn = session.status === 'signed_in';
  const userId = session.user?.id || null;
  const lastUser = useRef<string | null | undefined>(undefined);
  const restoredRef = useRef(false);

  // Restore persisted project_id, session_id, and user preferences once on mount.
  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    const prefs = loadStoredPreferences();
    dispatch({ type: 'SET_PREFERENCES', patch: prefs });
    const storedProject = readStoredString(PROJECT_STORAGE_KEY);
    const storedSession = readStoredString(SESSION_STORAGE_KEY);
    if (storedProject) {
      dispatch({ type: 'SYSTEM', patch: { projectId: storedProject } });
    }
    if (storedSession) {
      dispatch({ type: 'SYSTEM', patch: { sessionId: storedSession } });
    }
  }, [dispatch]);

  // Work out who we are: saved token, then saved API key, then the server's dev bypass.
  const resolveSession = useCallback(async () => {
    let mode = null;
    try {
      mode = await fetchAuthMode();
    } catch {
      mode = null;
    }
    const held = heldCredential();
    if (!held && !mode?.dev_bypass) {
      dispatch({ type: 'SYSTEM', patch: { session: { status: 'signed_out', user: null, via: null, mode, error: null } } });
      return;
    }
    try {
      const user = await fetchCurrentUser();
      const via = user.auth_via && user.auth_via !== 'unknown' ? user.auth_via : held;
      dispatch({ type: 'SYSTEM', patch: { session: { status: 'signed_in', user, via, mode, error: null } } });
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 401) {
        const reason = held === 'api_key' ? 'The saved API key was refused by the server.' : held === 'token' ? 'Your session expired. Sign in again.' : null;
        dispatch({ type: 'SYSTEM', patch: { session: { status: 'signed_out', user: null, via: null, mode, error: reason } } });
      } else {
        dispatch({ type: 'SYSTEM', patch: { session: { status: 'error', user: null, via: null, mode, error: message(err) } } });
      }
    }
  }, [dispatch]);

  useEffect(() => {
    void resolveSession();
    return onAuthChange(() => void resolveSession());
  }, [resolveSession]);

  // Account switched or signed out: clear the previous account's library.
  useEffect(() => {
    if (session.status === 'checking') return;
    if (lastUser.current !== undefined && lastUser.current !== userId) dispatch({ type: 'IDENTITY_CHANGED' });
    lastUser.current = userId;
  }, [dispatch, session.status, userId]);

  useEffect(() => {
    let cancelled = false;
    const refreshStatus = () => {
      fetchEngineStatus()
        .then((engine) => !cancelled && dispatch({ type: 'SYSTEM', patch: { engine, engineError: null } }))
        .catch((err) => !cancelled && dispatch({ type: 'SYSTEM', patch: { engine: null, engineError: message(err) } }));
      fetchCreditLedger()
        .then((ledger) => !cancelled && dispatch({ type: 'SYSTEM', patch: { ledger } }))
        .catch(() => !cancelled && dispatch({ type: 'SYSTEM', patch: { ledger: null } }));
    };
    refreshStatus();
    fetchPlaybooks()
      .then((playbooks) => !cancelled && dispatch({ type: 'SYSTEM', patch: { playbooks, playbooksError: null, playbooksLoaded: true } }))
      .catch((err) => !cancelled && dispatch({ type: 'SYSTEM', patch: { playbooks: [], playbooksError: message(err), playbooksLoaded: true } }));
    const timer = window.setInterval(refreshStatus, STATUS_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [dispatch]);

  // Account-scoped data: account mode/age status, projects, and active session recovery.
  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;

    fetchAccount()
      .then((account) => {
        if (cancelled) return;
        const mode = account.age_verified && account.content_mode === 'unrestricted' ? 'unrestricted' : 'sfw';
        dispatch({
          type: 'SYSTEM',
          patch: {
            account,
            ageVerified: Boolean(account.age_verified),
            contentMode: mode,
          },
        });
      })
      .catch(() => undefined);

    fetchProjects()
      .then((projects) => {
        if (cancelled) return;
        const list = projects || [];
        dispatch({ type: 'SYSTEM', patch: { projects: list, projectsError: null } });
        const storedProject = readStoredString(PROJECT_STORAGE_KEY);
        if (storedProject && !list.some((p: any) => p.id === storedProject)) {
          writeStoredString(PROJECT_STORAGE_KEY, null);
          dispatch({ type: 'SYSTEM', patch: { projectId: null } });
        }
      })
      .catch((err) => !cancelled && dispatch({ type: 'SYSTEM', patch: { projects: [], projectsError: message(err) } }));

    return () => {
      cancelled = true;
    };
  }, [dispatch, signedIn, userId]);

  // Restore active session + persisted message history across refresh.
  useEffect(() => {
    if (!signedIn || !sessionId) return;
    let cancelled = false;
    Promise.all([fetchSession(sessionId), fetchSessionMessages(sessionId)])
      .then(([sess, msgs]) => {
        if (cancelled) return;
        dispatch({ type: 'SET_SESSION', session: sess, messages: msgs || [] });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
          writeStoredString(SESSION_STORAGE_KEY, null);
          dispatch({ type: 'SET_SESSION', session: null, messages: [] });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch, sessionId, signedIn, userId]);

  // Mode- and project-scoped personas & recipes.
  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    fetchPersonas({ projectId, contentMode })
      .then((personas) => !cancelled && dispatch({ type: 'SYSTEM', patch: { personas: personas || [], personasError: null } }))
      .catch((err) => !cancelled && dispatch({ type: 'SYSTEM', patch: { personas: [], personasError: message(err) } }));
    fetchRecipes(projectId, contentMode)
      .then((recipes) => !cancelled && dispatch({ type: 'SYSTEM', patch: { recipes: recipes || [] } }))
      .catch(() => !cancelled && dispatch({ type: 'SYSTEM', patch: { recipes: [] } }));
    return () => {
      cancelled = true;
    };
  }, [contentMode, dispatch, projectId, signedIn, userId]);

  // Mode- and project-scoped assets + persisted server lineage DAG hydration across refresh.
  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    fetchAssets(projectId, contentMode)
      .then(async (assets) => {
        if (cancelled) return;
        dispatch({ type: 'ASSETS_LOADED', assets, replace: true });
        if (!assets.length) return;
        const sample = assets.slice(0, 40);
        const parentMap: Record<string, string> = {};
        const depictsMap: Record<string, { personaId: string; personaVersion?: number | null }> = {};
        const edges: LineageEdge[] = [];
        await Promise.allSettled(
          sample.map(async (a) => {
            const lin = await fetchAssetLineage(a.id);
            if (lin.ancestors.length && !a.parentId) {
              parentMap[a.id] = lin.ancestors[0];
              edges.push({ from: lin.ancestors[0], to: a.id });
            }
            for (const desc of lin.descendants) {
              edges.push({ from: a.id, to: desc });
            }
            if (Array.isArray(lin.depicts) && lin.depicts.length) {
              const firstDep = lin.depicts[0];
              if (firstDep?.persona_id) {
                depictsMap[a.id] = {
                  personaId: firstDep.persona_id,
                  personaVersion: firstDep.persona_version ?? null,
                };
              }
            }
            if (Array.isArray(lin.edges)) {
              for (const e of lin.edges) {
                if (e.parent_asset_id && e.child_asset_id) {
                  edges.push({
                    from: e.parent_asset_id,
                    to: e.child_asset_id,
                    relationshipType: e.relationship_type,
                  });
                  if (!parentMap[e.child_asset_id]) parentMap[e.child_asset_id] = e.parent_asset_id;
                }
              }
            }
          }),
        );
        if (!cancelled && (edges.length || Object.keys(parentMap).length || Object.keys(depictsMap).length)) {
          dispatch({ type: 'HYDRATE_LINEAGE', edges, parentMap, depictsMap });
        }
      })
      .catch((err) => !cancelled && dispatch({ type: 'ASSETS_LOAD_FAILED', error: message(err) }));
    return () => {
      cancelled = true;
    };
  }, [assetsRefreshSeq, contentMode, dispatch, projectId, signedIn, userId]);
}
