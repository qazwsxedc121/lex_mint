import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type KeyboardEvent, type MouseEvent, type RefObject, type SetStateAction } from 'react';
import { useTranslation } from 'react-i18next';
import type { PromptTemplate, PromptTemplateVariable, PromptTemplateVariableType } from '../../../types/promptTemplate';
import { listPromptTemplates } from '../../../services/api';

const TEMPLATE_PINNED_STORAGE_KEY = 'lex-mint.prompt-templates.pinned';
const TEMPLATE_RECENT_STORAGE_KEY = 'lex-mint.prompt-templates.recent';
const MAX_RECENT_TEMPLATE_COUNT = 12;
const TEMPLATE_VARIABLE_PATTERN = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/;
const TEMPLATE_CURSOR_VARIABLE = 'cursor';
const TEMPLATE_VARIABLE_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const TEMPLATE_TRIGGER_PATTERN = /^[a-z0-9][a-z0-9_-]*$/;

export interface SlashCommandMatch {
  query: string;
  start: number;
  end: number;
}

export interface TemplateReplacementRange {
  start: number;
  end: number;
}

type TemplateVariableResolvedType = NonNullable<PromptTemplateVariableType>;

export interface TemplateVariableDefinition {
  key: string;
  label: string;
  description?: string;
  type: TemplateVariableResolvedType;
  required: boolean;
  defaultValue?: string | number | boolean;
  options: string[];
}

export interface PendingTemplateInsert {
  template: PromptTemplate;
  variables: TemplateVariableDefinition[];
  values: Record<string, string>;
  replacementRange?: TemplateReplacementRange;
}

interface UsePromptTemplateComposerOptions {
  insertText: (text: string, options?: { cursorOffset?: number; replacementRange?: TemplateReplacementRange }) => void;
  setInput: Dispatch<SetStateAction<string>>;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}

const normalizeTemplateMatchValue = (value: string): string => value.trim().toLowerCase();

export const normalizeTemplateTrigger = (template: PromptTemplate): string | null => {
  const trigger = (template.trigger || '').trim();
  if (!trigger || !TEMPLATE_TRIGGER_PATTERN.test(trigger)) {
    return null;
  }
  return trigger;
};

const normalizeTemplateAliases = (template: PromptTemplate): string[] => {
  if (!Array.isArray(template.aliases)) {
    return [];
  }

  const aliases: string[] = [];
  const seen = new Set<string>();
  for (const item of template.aliases) {
    const alias = item.trim();
    if (!alias || !TEMPLATE_TRIGGER_PATTERN.test(alias)) {
      continue;
    }
    const lowered = alias.toLowerCase();
    if (seen.has(lowered)) {
      continue;
    }
    seen.add(lowered);
    aliases.push(alias);
  }
  return aliases;
};

const getTemplateMatchTier = (template: PromptTemplate, query: string): number | null => {
  const normalizedQuery = normalizeTemplateMatchValue(query);
  if (!normalizedQuery) {
    return 5;
  }

  const trigger = normalizeTemplateTrigger(template);
  const aliases = normalizeTemplateAliases(template);
  const normalizedTrigger = trigger ? trigger.toLowerCase() : null;
  const normalizedAliases = aliases.map((alias) => alias.toLowerCase());

  if (normalizedTrigger === normalizedQuery) {
    return 0;
  }
  if (normalizedAliases.includes(normalizedQuery)) {
    return 1;
  }
  if (normalizedTrigger && normalizedTrigger.startsWith(normalizedQuery)) {
    return 2;
  }
  if (normalizedAliases.some((alias) => alias.startsWith(normalizedQuery))) {
    return 3;
  }

  const fuzzyValues = [
    template.name,
    template.description || '',
    template.content,
    trigger || '',
    ...aliases,
  ].map((value) => value.toLowerCase());

  if (fuzzyValues.some((value) => value.includes(normalizedQuery))) {
    return 4;
  }

  return null;
};

const extractTemplateVariables = (content: string): string[] => {
  const variables: string[] = [];
  const seen = new Set<string>();
  const variablePattern = new RegExp(TEMPLATE_VARIABLE_PATTERN.source, 'g');

  for (const match of content.matchAll(variablePattern)) {
    const variableName = match[1];
    if (!variableName || variableName === TEMPLATE_CURSOR_VARIABLE || seen.has(variableName)) {
      continue;
    }
    seen.add(variableName);
    variables.push(variableName);
  }

  return variables;
};

const normalizeVariableType = (type: PromptTemplateVariable['type']): TemplateVariableResolvedType => {
  if (type === 'number' || type === 'boolean' || type === 'select') {
    return type;
  }
  return 'text';
};

const normalizeTemplateVariables = (template: PromptTemplate): TemplateVariableDefinition[] => {
  const definitions: TemplateVariableDefinition[] = [];
  const seen = new Set<string>();

  const schemaVariables = Array.isArray(template.variables) ? template.variables : [];
  for (const variable of schemaVariables) {
    const key = (variable.key || '').trim();
    if (!key || key.toLowerCase() === TEMPLATE_CURSOR_VARIABLE || !TEMPLATE_VARIABLE_KEY_PATTERN.test(key) || seen.has(key)) {
      continue;
    }

    const type = normalizeVariableType(variable.type);
    const options = type === 'select'
      ? (variable.options || [])
          .map((item) => item.trim())
          .filter((item, idx, arr) => !!item && arr.indexOf(item) === idx)
      : [];

    definitions.push({
      key,
      label: variable.label?.trim() || key,
      description: variable.description,
      type,
      required: variable.required === true,
      defaultValue: variable.default ?? undefined,
      options,
    });
    seen.add(key);
  }

  for (const key of extractTemplateVariables(template.content)) {
    if (seen.has(key)) {
      continue;
    }
    definitions.push({
      key,
      label: key,
      type: 'text',
      required: false,
      options: [],
    });
    seen.add(key);
  }

  return definitions;
};

const toTemplateValueString = (value: string | number | boolean | null | undefined): string => {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value);
};

const renderTemplateContent = (
  content: string,
  values: Record<string, string>,
): { text: string; cursorOffset: number | null } => {
  const variablePattern = new RegExp(TEMPLATE_VARIABLE_PATTERN.source, 'g');
  let rendered = '';
  let cursorOffset: number | null = null;
  let lastIndex = 0;

  for (const match of content.matchAll(variablePattern)) {
    const variableName = match[1];
    const matchIndex = match.index ?? 0;
    rendered += content.slice(lastIndex, matchIndex);

    if (variableName === TEMPLATE_CURSOR_VARIABLE) {
      if (cursorOffset === null) {
        cursorOffset = rendered.length;
      }
    } else if (variableName) {
      rendered += values[variableName] ?? '';
    }

    lastIndex = matchIndex + match[0].length;
  }

  rendered += content.slice(lastIndex);
  return { text: rendered, cursorOffset };
};

const readStoredTemplateIds = (storageKey: string): string[] => {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.filter((value): value is string => typeof value === 'string');
  } catch {
    return [];
  }
};

const writeStoredTemplateIds = (storageKey: string, templateIds: string[]) => {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(storageKey, JSON.stringify(templateIds));
  } catch {
    // Ignore localStorage write errors (private mode, quota, etc.)
  }
};

const findSlashCommand = (text: string, cursorPosition: number): SlashCommandMatch | null => {
  const safeCursor = Math.max(0, Math.min(cursorPosition, text.length));
  const beforeCursor = text.slice(0, safeCursor);
  const match = beforeCursor.match(/(^|\s)\/([^\s/]*)$/);

  if (!match) {
    return null;
  }

  const leading = match[1] || '';
  const slashStart = safeCursor - match[0].length + leading.length;

  return {
    query: match[2] || '',
    start: slashStart,
    end: safeCursor,
  };
};

export const usePromptTemplateComposer = ({
  insertText,
  setInput,
  textareaRef,
}: UsePromptTemplateComposerOptions) => {
  const { t } = useTranslation('chat');
  const [showTemplateMenu, setShowTemplateMenu] = useState(false);
  const [templateSearch, setTemplateSearch] = useState('');
  const [templateMenuIndex, setTemplateMenuIndex] = useState(0);
  const [slashCommand, setSlashCommand] = useState<SlashCommandMatch | null>(null);
  const [slashMenuIndex, setSlashMenuIndex] = useState(0);
  const [promptTemplates, setPromptTemplates] = useState<PromptTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [templatesFetched, setTemplatesFetched] = useState(false);
  const [pinnedTemplateIds, setPinnedTemplateIds] = useState<string[]>(() => readStoredTemplateIds(TEMPLATE_PINNED_STORAGE_KEY));
  const [recentTemplateIds, setRecentTemplateIds] = useState<string[]>(() => readStoredTemplateIds(TEMPLATE_RECENT_STORAGE_KEY));
  const [pendingTemplateInsert, setPendingTemplateInsert] = useState<PendingTemplateInsert | null>(null);
  const [templateVariableErrors, setTemplateVariableErrors] = useState<Record<string, string>>({});
  const templateSearchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    writeStoredTemplateIds(TEMPLATE_PINNED_STORAGE_KEY, pinnedTemplateIds);
  }, [pinnedTemplateIds]);

  useEffect(() => {
    writeStoredTemplateIds(TEMPLATE_RECENT_STORAGE_KEY, recentTemplateIds);
  }, [recentTemplateIds]);

  const recordTemplateUsage = useCallback((templateId: string) => {
    setRecentTemplateIds((prev) => [templateId, ...prev.filter((id) => id !== templateId)].slice(0, MAX_RECENT_TEMPLATE_COUNT));
  }, []);

  const toggleTemplatePinned = useCallback((templateId: string) => {
    setPinnedTemplateIds((prev) => {
      if (prev.includes(templateId)) {
        return prev.filter((id) => id !== templateId);
      }
      return [templateId, ...prev];
    });
  }, []);

  const pinnedTemplateSet = useMemo(() => new Set(pinnedTemplateIds), [pinnedTemplateIds]);
  const recentTemplateSet = useMemo(() => new Set(recentTemplateIds), [recentTemplateIds]);
  const recentTemplateIndex = useMemo(() => new Map(recentTemplateIds.map((id, index) => [id, index])), [recentTemplateIds]);

  const orderedTemplates = useMemo(() => {
    return [...promptTemplates].sort((a, b) => {
      const aPinned = pinnedTemplateSet.has(a.id);
      const bPinned = pinnedTemplateSet.has(b.id);
      if (aPinned !== bPinned) {
        return aPinned ? -1 : 1;
      }

      const aRecent = recentTemplateIndex.get(a.id);
      const bRecent = recentTemplateIndex.get(b.id);
      const aHasRecent = aRecent !== undefined;
      const bHasRecent = bRecent !== undefined;
      if (aHasRecent !== bHasRecent) {
        return aHasRecent ? -1 : 1;
      }
      if (aRecent !== undefined && bRecent !== undefined && aRecent !== bRecent) {
        return aRecent - bRecent;
      }

      return a.name.localeCompare(b.name);
    });
  }, [promptTemplates, pinnedTemplateSet, recentTemplateIndex]);

  const rankTemplates = useCallback((query: string): PromptTemplate[] => {
    const normalizedQuery = normalizeTemplateMatchValue(query);
    if (!normalizedQuery) {
      return orderedTemplates;
    }

    const ranked = orderedTemplates
      .map((template) => ({ template, tier: getTemplateMatchTier(template, normalizedQuery) }))
      .filter((item): item is { template: PromptTemplate; tier: number } => item.tier !== null);

    ranked.sort((a, b) => a.tier - b.tier);
    return ranked.map((item) => item.template);
  }, [orderedTemplates]);

  const filteredTemplateMenu = useMemo(() => {
    return rankTemplates(templateSearch);
  }, [rankTemplates, templateSearch]);

  const slashMatchedTemplates = useMemo(() => {
    if (!slashCommand) {
      return [];
    }
    return rankTemplates(slashCommand.query).slice(0, 8);
  }, [rankTemplates, slashCommand]);

  const updateSlashCommandFromText = useCallback((text: string, cursorPosition?: number | null) => {
    const cursor = cursorPosition ?? text.length;
    setSlashCommand(findSlashCommand(text, cursor));
    setSlashMenuIndex(0);
  }, []);

  const loadPromptTemplates = useCallback(async () => {
    try {
      setTemplatesLoading(true);
      setTemplatesError(null);
      const data = await listPromptTemplates();
      setPromptTemplates(data.filter((template) => template.enabled !== false));
      setTemplatesFetched(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load templates';
      setTemplatesError(message);
      setTemplatesFetched(false);
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!showTemplateMenu) {
      return;
    }

    setTemplateSearch('');
    setTemplateMenuIndex(0);
    loadPromptTemplates();

    requestAnimationFrame(() => {
      templateSearchInputRef.current?.focus();
    });
  }, [showTemplateMenu, loadPromptTemplates]);

  useEffect(() => {
    if (slashCommand && !templatesFetched && !templatesLoading && !templatesError) {
      loadPromptTemplates();
    }
  }, [slashCommand, templatesFetched, templatesLoading, templatesError, loadPromptTemplates]);

  useEffect(() => {
    if (filteredTemplateMenu.length === 0) {
      setTemplateMenuIndex(0);
      return;
    }

    setTemplateMenuIndex((prev) => Math.min(prev, filteredTemplateMenu.length - 1));
  }, [filteredTemplateMenu.length]);

  useEffect(() => {
    if (slashMatchedTemplates.length === 0) {
      setSlashMenuIndex(0);
      return;
    }

    setSlashMenuIndex((prev) => Math.min(prev, slashMatchedTemplates.length - 1));
  }, [slashMatchedTemplates.length]);

  const executeTemplateInsert = useCallback((
    template: PromptTemplate,
    values: Record<string, string>,
    replacementRange?: TemplateReplacementRange,
  ) => {
    const rendered = renderTemplateContent(template.content, values);
    insertText(rendered.text, {
      replacementRange,
      cursorOffset: rendered.cursorOffset ?? rendered.text.length,
    });
    recordTemplateUsage(template.id);
  }, [insertText, recordTemplateUsage]);

  const beginTemplateInsert = useCallback((
    template: PromptTemplate,
    replacementRange?: TemplateReplacementRange,
  ) => {
    const variables = normalizeTemplateVariables(template);
    if (variables.length === 0) {
      executeTemplateInsert(template, {}, replacementRange);
      return;
    }

    const values = variables.reduce<Record<string, string>>((acc, variable) => {
      if (variable.defaultValue === undefined) {
        acc[variable.key] = '';
      } else if (variable.type === 'boolean') {
        if (typeof variable.defaultValue === 'boolean') {
          acc[variable.key] = variable.defaultValue ? 'true' : 'false';
        } else {
          acc[variable.key] = '';
        }
      } else {
        acc[variable.key] = toTemplateValueString(variable.defaultValue);
      }
      return acc;
    }, {});

    setTemplateVariableErrors({});
    setPendingTemplateInsert({
      template,
      variables,
      values,
      replacementRange,
    });
  }, [executeTemplateInsert]);

  const handleInsertTemplate = useCallback((template: PromptTemplate) => {
    beginTemplateInsert(template);
    setShowTemplateMenu(false);
    setTemplateSearch('');
    setTemplateMenuIndex(0);
  }, [beginTemplateInsert]);

  const handleInsertSlashTemplate = useCallback((template: PromptTemplate) => {
    if (!slashCommand) {
      return;
    }

    beginTemplateInsert(template, {
      start: slashCommand.start,
      end: slashCommand.end,
    });
    setSlashCommand(null);
    setSlashMenuIndex(0);
  }, [beginTemplateInsert, slashCommand]);

  const handleTemplateVariableChange = useCallback((variable: string, value: string) => {
    setTemplateVariableErrors((prev) => {
      if (!prev[variable]) {
        return prev;
      }

      const next = { ...prev };
      delete next[variable];
      return next;
    });

    setPendingTemplateInsert((prev) => {
      if (!prev) {
        return prev;
      }

      return {
        ...prev,
        values: {
          ...prev.values,
          [variable]: value,
        },
      };
    });
  }, []);

  const clearPendingTemplateInsert = useCallback(() => {
    setPendingTemplateInsert(null);
    setTemplateVariableErrors({});
  }, []);

  const handleTemplateVariableSubmit = useCallback(() => {
    if (!pendingTemplateInsert) {
      return;
    }

    const nextErrors: Record<string, string> = {};
    for (const variable of pendingTemplateInsert.variables) {
      const value = pendingTemplateInsert.values[variable.key] ?? '';
      const trimmed = value.trim();

      if (variable.required && !trimmed) {
        nextErrors[variable.key] = t('input.templateVariableRequired');
        continue;
      }

      if (variable.type === 'number' && trimmed) {
        const parsed = Number(trimmed);
        if (!Number.isFinite(parsed)) {
          nextErrors[variable.key] = t('input.templateVariableInvalidNumber');
          continue;
        }
      }

      if (variable.type === 'boolean' && trimmed && trimmed !== 'true' && trimmed !== 'false') {
        nextErrors[variable.key] = t('input.templateVariableInvalidBoolean');
      }
    }

    if (Object.keys(nextErrors).length > 0) {
      setTemplateVariableErrors(nextErrors);
      return;
    }

    const normalizedValues = Object.fromEntries(
      Object.entries(pendingTemplateInsert.values).map(([key, value]) => {
        if (value === 'true') {
          return [key, 'true'];
        }
        if (value === 'false') {
          return [key, 'false'];
        }
        return [key, value];
      }),
    );

    executeTemplateInsert(
      pendingTemplateInsert.template,
      normalizedValues,
      pendingTemplateInsert.replacementRange,
    );
    clearPendingTemplateInsert();
  }, [pendingTemplateInsert, executeTemplateInsert, clearPendingTemplateInsert, t]);

  const handleTemplateSearchKeyDown = useCallback((event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      setShowTemplateMenu(false);
      return;
    }

    if (filteredTemplateMenu.length === 0) {
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setTemplateMenuIndex((prev) => (prev + 1) % filteredTemplateMenu.length);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setTemplateMenuIndex((prev) => (prev - 1 + filteredTemplateMenu.length) % filteredTemplateMenu.length);
      return;
    }

    if (event.key === 'Enter') {
      event.preventDefault();
      const selectedTemplate = filteredTemplateMenu[templateMenuIndex];
      if (selectedTemplate) {
        handleInsertTemplate(selectedTemplate);
      }
    }
  }, [filteredTemplateMenu, templateMenuIndex, handleInsertTemplate]);

  const handleTemplateVariableBackdropClick = useCallback((event: MouseEvent) => {
    if (event.target === event.currentTarget) {
      clearPendingTemplateInsert();
    }
  }, [clearPendingTemplateInsert]);

  const handleTemplateVariableCancel = useCallback(() => {
    clearPendingTemplateInsert();
  }, [clearPendingTemplateInsert]);

  const setTemplateSearchValue = useCallback((value: string) => {
    setTemplateSearch(value);
    setTemplateMenuIndex(0);
  }, []);

  const clearSlashCommand = useCallback(() => {
    setSlashCommand(null);
    setSlashMenuIndex(0);
  }, []);

  const resetTemplateComposer = useCallback(() => {
    setShowTemplateMenu(false);
    setTemplateSearch('');
    setTemplateMenuIndex(0);
    clearSlashCommand();
    clearPendingTemplateInsert();
  }, [clearSlashCommand, clearPendingTemplateInsert]);

  const handleInsertTemplateFromText = useCallback((text: string, cursorPosition?: number | null) => {
    setInput(text);
    const textarea = textareaRef.current;
    if (textarea && cursorPosition !== undefined && cursorPosition !== null) {
      requestAnimationFrame(() => {
        textarea.focus();
        textarea.setSelectionRange(cursorPosition, cursorPosition);
      });
    }
    updateSlashCommandFromText(text, cursorPosition);
  }, [setInput, textareaRef, updateSlashCommandFromText]);

  return {
    clearSlashCommand,
    filteredTemplateMenu,
    handleInsertSlashTemplate,
    handleInsertTemplate,
    handleInsertTemplateFromText,
    handleTemplateSearchKeyDown,
    handleTemplateVariableBackdropClick,
    handleTemplateVariableCancel,
    handleTemplateVariableChange,
    handleTemplateVariableSubmit,
    loadPromptTemplates,
    normalizeTemplateTrigger,
    pendingTemplateInsert,
    pinnedTemplateSet,
    promptTemplates,
    recentTemplateSet,
    resetTemplateComposer,
    setShowTemplateMenu,
    setSlashMenuIndex,
    setTemplateMenuIndex,
    setTemplateSearchValue,
    showTemplateMenu,
    slashCommand,
    slashMatchedTemplates,
    slashMenuIndex,
    templateMenuIndex,
    templateSearch,
    templateSearchInputRef,
    templateVariableErrors,
    templatesError,
    templatesLoading,
    toggleTemplatePinned,
    updateSlashCommandFromText,
  };
};
