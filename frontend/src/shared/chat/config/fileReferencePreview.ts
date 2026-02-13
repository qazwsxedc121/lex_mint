export interface FileReferencePreviewConfig {
  maxChars: number;
  maxLines: number;
}

export interface FileReferenceRuntimeConfig {
  ui_preview_max_chars: number;
  ui_preview_max_lines: number;
  injection_preview_max_chars: number;
  injection_preview_max_lines: number;
  chunk_size: number;
  max_chunks: number;
  total_budget_chars: number;
}

export interface FileReferencePreviewResult {
  text: string;
  totalChars: number;
  shownChars: number;
  hiddenChars: number;
  totalLines: number;
  shownLines: number;
  hiddenLines: number;
  truncated: boolean;
}

const DEFAULT_RUNTIME_CONFIG: FileReferenceRuntimeConfig = {
  ui_preview_max_chars: 1200,
  ui_preview_max_lines: 28,
  injection_preview_max_chars: 600,
  injection_preview_max_lines: 40,
  chunk_size: 2500,
  max_chunks: 6,
  total_budget_chars: 18000,
};

let runtimeConfig: FileReferenceRuntimeConfig = { ...DEFAULT_RUNTIME_CONFIG };
let previewConfigSnapshot: FileReferencePreviewConfig = {
  maxChars: runtimeConfig.ui_preview_max_chars,
  maxLines: runtimeConfig.ui_preview_max_lines,
};
let loadPromise: Promise<FileReferenceRuntimeConfig> | null = null;
let lastLoadedAt = 0;
const MIN_RELOAD_INTERVAL_MS = 30000;
const listeners = new Set<() => void>();

const toPositiveInt = (value: unknown, fallback: number): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 0 ? Math.floor(value) : fallback;
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return fallback;
};

const normalizeRuntimeConfig = (payload: Record<string, unknown>): FileReferenceRuntimeConfig => ({
  ui_preview_max_chars: toPositiveInt(payload.ui_preview_max_chars, DEFAULT_RUNTIME_CONFIG.ui_preview_max_chars),
  ui_preview_max_lines: toPositiveInt(payload.ui_preview_max_lines, DEFAULT_RUNTIME_CONFIG.ui_preview_max_lines),
  injection_preview_max_chars: toPositiveInt(payload.injection_preview_max_chars, DEFAULT_RUNTIME_CONFIG.injection_preview_max_chars),
  injection_preview_max_lines: toPositiveInt(payload.injection_preview_max_lines, DEFAULT_RUNTIME_CONFIG.injection_preview_max_lines),
  chunk_size: toPositiveInt(payload.chunk_size, DEFAULT_RUNTIME_CONFIG.chunk_size),
  max_chunks: toPositiveInt(payload.max_chunks, DEFAULT_RUNTIME_CONFIG.max_chunks),
  total_budget_chars: toPositiveInt(payload.total_budget_chars, DEFAULT_RUNTIME_CONFIG.total_budget_chars),
});

const emitConfigChange = () => {
  listeners.forEach((listener) => listener());
};

const buildPreviewConfigSnapshot = (config: FileReferenceRuntimeConfig): FileReferencePreviewConfig => ({
  maxChars: config.ui_preview_max_chars,
  maxLines: config.ui_preview_max_lines,
});

const applyRuntimeConfig = (nextConfig: FileReferenceRuntimeConfig): FileReferenceRuntimeConfig => {
  const changed = Object.keys(DEFAULT_RUNTIME_CONFIG).some((key) => {
    const typedKey = key as keyof FileReferenceRuntimeConfig;
    return runtimeConfig[typedKey] !== nextConfig[typedKey];
  });
  const previewChanged = (
    previewConfigSnapshot.maxChars !== nextConfig.ui_preview_max_chars ||
    previewConfigSnapshot.maxLines !== nextConfig.ui_preview_max_lines
  );
  runtimeConfig = nextConfig;
  if (previewChanged) {
    previewConfigSnapshot = buildPreviewConfigSnapshot(nextConfig);
  }
  if (changed) {
    emitConfigChange();
  }
  return runtimeConfig;
};

export function getFileReferenceRuntimeConfig(): FileReferenceRuntimeConfig {
  return runtimeConfig;
}

export function getFileReferencePreviewConfig(): FileReferencePreviewConfig {
  return previewConfigSnapshot;
}

export function subscribeFileReferencePreviewConfig(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

async function fetchFileReferenceRuntimeConfig(): Promise<FileReferenceRuntimeConfig> {
  const apiBase = import.meta.env.VITE_API_URL as string | undefined;
  if (!apiBase) {
    return runtimeConfig;
  }

  const response = await fetch(`${apiBase}/api/file-reference/config`);
  if (!response.ok) {
    throw new Error(`Failed to load file reference config: HTTP ${response.status}`);
  }

  const payload = await response.json();
  if (!payload || typeof payload !== 'object') {
    return runtimeConfig;
  }

  return normalizeRuntimeConfig(payload as Record<string, unknown>);
}

export function ensureFileReferencePreviewConfigLoaded(forceReload: boolean = false): Promise<FileReferenceRuntimeConfig> {
  if (!forceReload && Date.now() - lastLoadedAt < MIN_RELOAD_INTERVAL_MS) {
    return Promise.resolve(runtimeConfig);
  }

  if (!forceReload && loadPromise) {
    return loadPromise;
  }

  loadPromise = (async () => {
    try {
      const remoteConfig = await fetchFileReferenceRuntimeConfig();
      return applyRuntimeConfig(remoteConfig);
    } catch (error) {
      console.warn('Failed to load file reference config, using current defaults:', error);
      return runtimeConfig;
    } finally {
      loadPromise = null;
      lastLoadedAt = Date.now();
    }
  })();

  return loadPromise;
}

export function buildFileReferencePreview(
  rawContent: string,
  config: FileReferencePreviewConfig = getFileReferencePreviewConfig()
): FileReferencePreviewResult {
  const normalized = rawContent.replace(/\r\n/g, '\n');
  const safeMaxLines = Math.max(1, config.maxLines);
  const safeMaxChars = Math.max(1, config.maxChars);

  const lines = normalized.split('\n');
  const lineLimited = lines.slice(0, safeMaxLines).join('\n');
  const charLimited = lineLimited.slice(0, safeMaxChars);

  const shownChars = charLimited.length;
  const shownLines = shownChars > 0 ? charLimited.split('\n').length : 0;
  const totalChars = normalized.length;
  const totalLines = lines.length;
  const hiddenChars = Math.max(0, totalChars - shownChars);
  const hiddenLines = Math.max(0, totalLines - shownLines);

  return {
    text: charLimited,
    totalChars,
    shownChars,
    hiddenChars,
    totalLines,
    shownLines,
    hiddenLines,
    truncated: hiddenChars > 0 || hiddenLines > 0,
  };
}
