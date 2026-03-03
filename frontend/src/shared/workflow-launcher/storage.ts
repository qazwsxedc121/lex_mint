import { useCallback, useMemo, useState } from 'react';
import type { LauncherRecentItem } from './types';

export const WORKFLOW_LAUNCHER_FAVORITES_KEY = 'lex-mint.workflow-launcher.favorites.v1';
export const WORKFLOW_LAUNCHER_RECENTS_KEY = 'lex-mint.workflow-launcher.recents.v1';
const MAX_RECENTS = 20;

const isBrowser = () => typeof window !== 'undefined' && !!window.localStorage;

const normalizeFavorites = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of value) {
    if (typeof item !== 'string') {
      continue;
    }
    const trimmed = item.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    result.push(trimmed);
  }
  return result;
};

const normalizeRecents = (value: unknown): LauncherRecentItem[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const latestById = new Map<string, number>();
  for (const item of value) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const rawId = (item as { id?: unknown }).id;
    const rawTs = (item as { ts?: unknown }).ts;
    if (typeof rawId !== 'string') {
      continue;
    }
    const id = rawId.trim();
    const ts = typeof rawTs === 'number' && Number.isFinite(rawTs) ? rawTs : 0;
    if (!id) {
      continue;
    }
    const previous = latestById.get(id) ?? -1;
    if (ts > previous) {
      latestById.set(id, ts);
    }
  }
  return Array.from(latestById.entries())
    .map(([id, ts]) => ({ id, ts }))
    .sort((a, b) => b.ts - a.ts)
    .slice(0, MAX_RECENTS);
};

const readJson = (key: string): unknown => {
  if (!isBrowser()) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

const writeJson = (key: string, value: unknown) => {
  if (!isBrowser()) {
    return;
  }
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore localStorage write failures.
  }
};

export const readWorkflowLauncherFavorites = (): string[] =>
  normalizeFavorites(readJson(WORKFLOW_LAUNCHER_FAVORITES_KEY));

export const readWorkflowLauncherRecents = (): LauncherRecentItem[] =>
  normalizeRecents(readJson(WORKFLOW_LAUNCHER_RECENTS_KEY));

export const writeWorkflowLauncherFavorites = (favorites: string[]) => {
  writeJson(WORKFLOW_LAUNCHER_FAVORITES_KEY, normalizeFavorites(favorites));
};

export const writeWorkflowLauncherRecents = (recents: LauncherRecentItem[]) => {
  writeJson(WORKFLOW_LAUNCHER_RECENTS_KEY, normalizeRecents(recents));
};

export const markWorkflowRecent = (
  recents: LauncherRecentItem[],
  workflowId: string,
  ts: number = Date.now()
): LauncherRecentItem[] => {
  const id = workflowId.trim();
  if (!id) {
    return recents;
  }
  const filtered = recents.filter((item) => item.id !== id);
  return [{ id, ts }, ...filtered].slice(0, MAX_RECENTS);
};

export const toggleWorkflowFavoriteIds = (favorites: string[], workflowId: string): string[] => {
  const id = workflowId.trim();
  if (!id) {
    return favorites;
  }
  if (favorites.includes(id)) {
    return favorites.filter((item) => item !== id);
  }
  return [id, ...favorites];
};

export function useWorkflowLauncherStorage() {
  const [favorites, setFavorites] = useState<string[]>(() => readWorkflowLauncherFavorites());
  const [recents, setRecents] = useState<LauncherRecentItem[]>(() => readWorkflowLauncherRecents());

  const toggleFavorite = useCallback((workflowId: string) => {
    setFavorites((previous) => {
      const next = toggleWorkflowFavoriteIds(previous, workflowId);
      writeWorkflowLauncherFavorites(next);
      return next;
    });
  }, []);

  const addRecent = useCallback((workflowId: string, ts?: number) => {
    setRecents((previous) => {
      const next = markWorkflowRecent(previous, workflowId, ts);
      writeWorkflowLauncherRecents(next);
      return next;
    });
  }, []);

  const favoritesSet = useMemo(() => new Set(favorites), [favorites]);

  return {
    favorites,
    favoritesSet,
    recents,
    toggleFavorite,
    addRecent,
  };
}
