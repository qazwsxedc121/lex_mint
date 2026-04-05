export interface CodeExecutionSettings {
  enablePythonRunner: boolean;
  executionTimeoutMs: number;
  maxCodeChars: number;
}

const STORAGE_KEY = 'lex-mint.code-execution.settings.v1';

const DEFAULT_SETTINGS: CodeExecutionSettings = {
  enablePythonRunner: true,
  executionTimeoutMs: 45000,
  maxCodeChars: 20000,
};

let cachedSettings: CodeExecutionSettings | null = null;
const listeners = new Set<() => void>();

const toPositiveInt = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
    return Math.floor(value);
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return fallback;
};

const normalizeSettings = (value: unknown): CodeExecutionSettings => {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_SETTINGS };
  }

  const record = value as Record<string, unknown>;
  return {
    enablePythonRunner: record.enablePythonRunner !== false,
    executionTimeoutMs: toPositiveInt(record.executionTimeoutMs, DEFAULT_SETTINGS.executionTimeoutMs),
    maxCodeChars: toPositiveInt(record.maxCodeChars, DEFAULT_SETTINGS.maxCodeChars),
  };
};

const readFromStorage = (): CodeExecutionSettings => {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_SETTINGS };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { ...DEFAULT_SETTINGS };
    }
    return normalizeSettings(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
};

const writeToStorage = (settings: CodeExecutionSettings) => {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Ignore localStorage write failures.
  }
};

const emitChange = () => {
  listeners.forEach((listener) => listener());
};

export function getCodeExecutionSettings(): CodeExecutionSettings {
  if (!cachedSettings) {
    cachedSettings = readFromStorage();
  }
  return cachedSettings;
}

export function subscribeCodeExecutionSettings(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setCodeExecutionSettings(next: CodeExecutionSettings): CodeExecutionSettings {
  cachedSettings = normalizeSettings(next);
  writeToStorage(cachedSettings);
  emitChange();
  return cachedSettings;
}

export function resetCodeExecutionSettings(): CodeExecutionSettings {
  return setCodeExecutionSettings({ ...DEFAULT_SETTINGS });
}

export function getDefaultCodeExecutionSettings(): CodeExecutionSettings {
  return { ...DEFAULT_SETTINGS };
}
