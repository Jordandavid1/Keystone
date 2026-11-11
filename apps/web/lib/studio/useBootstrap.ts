'use client';
import { readableError } from '@/lib/errors';

import { useCallback, useEffect, useRef } from 'react';
import {
  ApiError,
  fetchAuthMode,
  fetchCurrentUser,
  fetchAssets,
  fetchCreditLedger,
  fetchEngineStatus,
  fetchPersonas,
  fetchPlaybooks,
  fetchProjects,
} from '../api';
import { heldCredential, onAuthChange } from '../auth';
import { useStudio } from './store';

const STATUS_POLL_MS = 15000;

const message = readableError;

/** Initial data load + engine/ledger polling. Every failure is kept as a real error string. */
export function useBootstrap() {
  const { state, dispatch } = useStudio();
  const projectId = state.system.projectId;
  const session = state.system.session;
  const signedIn = session.status === 'signed_in';
  const userId = session.user?.id || null;
  const lastUser = useRef<string | null | undefined>(undefined);

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
        // A rejected token is dropped by apiRequest, which re-runs this check with whatever is left.
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

  // Account-scoped data: only asked for once someone is signed in.
  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    fetchPersonas()
      .then((personas) => !cancelled && dispatch({ type: 'SYSTEM', patch: { personas: personas || [], personasError: null } }))
      .catch((err) => !cancelled && dispatch({ type: 'SYSTEM', patch: { personas: [], personasError: message(err) } }));
    fetchProjects()
      .then((projects) => !cancelled && dispatch({ type: 'SYSTEM', patch: { projects: projects || [], projectsError: null } }))
      .catch((err) => !cancelled && dispatch({ type: 'SYSTEM', patch: { projects: [], projectsError: message(err) } }));
    return () => {
      cancelled = true;
    };
  }, [dispatch, signedIn, userId]);

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    fetchAssets(projectId)
      .then((assets) => !cancelled && dispatch({ type: 'ASSETS_LOADED', assets }))
      .catch((err) => !cancelled && dispatch({ type: 'ASSETS_LOAD_FAILED', error: message(err) }));
    return () => {
      cancelled = true;
    };
  }, [dispatch, projectId, signedIn, userId]);
}
