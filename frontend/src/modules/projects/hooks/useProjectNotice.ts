import { useCallback, useEffect, useState } from 'react';

export type ProjectNoticeLevel = 'error' | 'success' | 'info';

export interface ProjectNoticeState {
  level: ProjectNoticeLevel;
  message: string;
  durationMs: number;
}

const DEFAULT_NOTICE_DURATION_MS = 3200;
const ERROR_NOTICE_DURATION_MS = 4800;

export function useProjectNotice() {
  const [notice, setNotice] = useState<ProjectNoticeState | null>(null);

  useEffect(() => {
    if (!notice) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setNotice(null);
    }, notice.durationMs);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const showNotice = useCallback((level: ProjectNoticeLevel, message: string, durationMs?: number) => {
    const resolvedDuration = typeof durationMs === 'number'
      ? durationMs
      : level === 'error'
      ? ERROR_NOTICE_DURATION_MS
      : DEFAULT_NOTICE_DURATION_MS;
    setNotice({ level, message, durationMs: resolvedDuration });
  }, []);

  const showError = useCallback((message: string, durationMs?: number) => {
    showNotice('error', message, durationMs);
  }, [showNotice]);

  const showSuccess = useCallback((message: string, durationMs?: number) => {
    showNotice('success', message, durationMs);
  }, [showNotice]);

  const clearNotice = useCallback(() => {
    setNotice(null);
  }, []);

  return {
    notice,
    showNotice,
    showError,
    showSuccess,
    clearNotice,
  };
}
