/**
 * InputBox component - message input field with send button and toolbar.
 */

import React, { useState, useRef, useCallback, useEffect, useMemo, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import {
  GlobeAltIcon,
  PaperClipIcon,
  XMarkIcon,
  DocumentTextIcon,
  PhotoIcon,
  PlusIcon,
  MinusIcon,
  PencilSquareIcon,
  TrashIcon,
  CheckIcon,
  LanguageIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';
import { Brain } from 'lucide-react';
import { useChatServices } from '../services/ChatServiceProvider';
import { useChatComposer } from '../contexts/ChatComposerContext';
import type { ChatComposerBlockInput } from '../contexts/ChatComposerContext';
import type { UploadedFile } from '../../../types/message';
import type { ParamOverrides } from '../../../types/message';
import type { PromptTemplate } from '../../../types/promptTemplate';
import { listPromptTemplates } from '../../../services/api';
import { ParamOverridePopover } from './ParamOverridePopover';
import { CompareModelButton } from './CompareModelButton';
import { FilePickerPopover } from './FilePickerPopover';
import { useFileSearch } from '../../../modules/projects/hooks/useFileSearch';
import { useProjectWorkspaceStore } from '../../../stores/projectWorkspaceStore';

// Reasoning effort options for supported models
const REASONING_EFFORT_OPTIONS = [
  { value: '', labelKey: 'input.reasoning.off', descKey: 'input.reasoning.offDesc' },
  { value: 'low', labelKey: 'input.reasoning.low', descKey: 'input.reasoning.lowDesc' },
  { value: 'medium', labelKey: 'input.reasoning.medium', descKey: 'input.reasoning.mediumDesc' },
  { value: 'high', labelKey: 'input.reasoning.high', descKey: 'input.reasoning.highDesc' },
];

// Shared toolbar button classes
const TOOLBAR_BTN = 'flex items-center justify-center p-1.5 rounded-md border transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const TOOLBAR_BTN_DEFAULT = `${TOOLBAR_BTN} bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600`;

const TRANSLATION_TARGET_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'auto', label: 'Auto' },
  { value: 'Chinese', label: 'Chinese' },
  { value: 'English', label: 'English' },
  { value: 'Japanese', label: 'Japanese' },
  { value: 'Korean', label: 'Korean' },
  { value: 'French', label: 'French' },
  { value: 'German', label: 'German' },
  { value: 'Spanish', label: 'Spanish' },
];

// Brain icon color by reasoning level
const getReasoningIconColor = (effort: string): string => {
  switch (effort) {
    case 'low':    return 'text-amber-400 dark:text-amber-500';
    case 'medium': return 'text-amber-600 dark:text-amber-400';
    case 'high':   return 'text-orange-500 dark:text-orange-400';
    default:       return '';
  }
};

const TEMPLATE_PINNED_STORAGE_KEY = 'lex-mint.prompt-templates.pinned';
const TEMPLATE_RECENT_STORAGE_KEY = 'lex-mint.prompt-templates.recent';
const MAX_RECENT_TEMPLATE_COUNT = 12;
const TEMPLATE_VARIABLE_PATTERN = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/;
const TEMPLATE_CURSOR_VARIABLE = 'cursor';

interface SlashCommandMatch {
  query: string;
  start: number;
  end: number;
}

interface TemplateReplacementRange {
  start: number;
  end: number;
}

interface PendingTemplateInsert {
  template: PromptTemplate;
  variables: string[];
  values: Record<string, string>;
  replacementRange?: TemplateReplacementRange;
}

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

const matchesTemplateQuery = (template: PromptTemplate, query: string): boolean => {
  const q = query.trim().toLowerCase();
  if (!q) {
    return true;
  }

  return [template.name, template.description || '', template.content]
    .some((value) => value.toLowerCase().includes(q));
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

interface AtFileMatch {
  query: string;
  start: number;
  end: number;
}

const findAtFileCommand = (text: string, cursorPosition: number): AtFileMatch | null => {
  const safeCursor = Math.max(0, Math.min(cursorPosition, text.length));
  const beforeCursor = text.slice(0, safeCursor);
  // Match @ at start or after whitespace, followed by non-whitespace
  const match = beforeCursor.match(/(^|\s)@([^\s@]*)$/);

  if (!match) {
    return null;
  }

  const leading = match[1] || '';
  const atStart = safeCursor - match[0].length + leading.length;

  return {
    query: match[2] || '',
    start: atStart,
    end: safeCursor,
  };
};

interface ChatBlock {
  id: string;
  title: string;
  content: string;
  collapsed: boolean;
  isEditing: boolean;
  kind: 'context' | 'note';
  language?: string;
  source?: { filePath: string; startLine: number; endLine: number };
  isAttachmentNote?: boolean;
  attachmentFilename?: string;
  draftTitle?: string;
  draftContent?: string;
}

const createBlockId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `block-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

interface InputBoxProps {
  onSend: (message: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean; fileReferences?: Array<{ path: string; project_id: string }> }) => void;
  onCompare?: (message: string, modelIds: string[], options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean; fileReferences?: Array<{ path: string; project_id: string }> }) => void;
  onStop?: () => void;
  onInsertSeparator?: () => void;
  onCompressContext?: () => void;
  isCompressing?: boolean;
  onClearAllMessages?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  // Toolbar props
  assistantSelector?: React.ReactNode;
  supportsReasoning?: boolean;
  supportsVision?: boolean;
  sessionId?: string;
  currentAssistantId?: string;
  paramOverrides?: ParamOverrides;
  hasActiveOverrides?: boolean;
  onParamOverridesChange?: (overrides: ParamOverrides) => void;
}

export const InputBox: React.FC<InputBoxProps> = ({
  onSend,
  onCompare,
  onStop,
  onInsertSeparator,
  onCompressContext,
  isCompressing = false,
  onClearAllMessages,
  disabled = false,
  isStreaming = false,
  assistantSelector,
  supportsReasoning = false,
  supportsVision = false,
  sessionId,
  currentAssistantId: _currentAssistantId,
  paramOverrides,
  hasActiveOverrides = false,
  onParamOverridesChange,
}) => {
  const { api } = useChatServices();
  const { t } = useTranslation('chat');
  const { registerComposer } = useChatComposer();
  const [input, setInput] = useState('');
  const [reasoningEffort, setReasoningEffort] = useState('');
  const [showReasoningMenu, setShowReasoningMenu] = useState(false);
  const [useWebSearch, setUseWebSearch] = useState(false);
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
  const [attachments, setAttachments] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [blocks, setBlocks] = useState<ChatBlock[]>([]);
  const [isTranslatingInput, setIsTranslatingInput] = useState(false);
  const [showTranslateInputMenu, setShowTranslateInputMenu] = useState(false);
  const [selectedInputTranslateTarget, setSelectedInputTranslateTarget] = useState('auto');
  const [pendingCompareModelIds, setPendingCompareModelIds] = useState<string[]>([]);

  // File reference state
  const [atFileCommand, setAtFileCommand] = useState<AtFileMatch | null>(null);
  const [fileMenuIndex, setFileMenuIndex] = useState(0);
  const location = useLocation();
  const { currentProjectId, getCurrentFile } = useProjectWorkspaceStore();
  const isProjectRoute = location.pathname.startsWith('/projects/');
  const routeProjectMatch = location.pathname.match(/^\/projects\/([^/]+)/);
  const routeProjectId = routeProjectMatch ? routeProjectMatch[1] : null;
  const activeProjectId = isProjectRoute ? (routeProjectId || currentProjectId) : null;
  const currentFile = activeProjectId ? getCurrentFile(activeProjectId) : null;
  const { results: fileSearchResults, setQuery: setFileQuery, loading: fileSearchLoading } = useFileSearch(activeProjectId, currentFile);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const templateSearchInputRef = useRef<HTMLInputElement>(null);
  const translateInputMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    writeStoredTemplateIds(TEMPLATE_PINNED_STORAGE_KEY, pinnedTemplateIds);
  }, [pinnedTemplateIds]);

  useEffect(() => {
    writeStoredTemplateIds(TEMPLATE_RECENT_STORAGE_KEY, recentTemplateIds);
  }, [recentTemplateIds]);

  useEffect(() => {
    if (!showTranslateInputMenu) return;

    const handleOutsideClick = (event: MouseEvent) => {
      if (translateInputMenuRef.current && !translateInputMenuRef.current.contains(event.target as Node)) {
        setShowTranslateInputMenu(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [showTranslateInputMenu]);

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

  const insertText = useCallback((
    text: string,
    options?: { cursorOffset?: number; replacementRange?: TemplateReplacementRange },
  ) => {
    const textarea = textareaRef.current;
    const rawCursorOffset = options?.cursorOffset ?? text.length;
    const boundedCursorOffset = Math.max(0, Math.min(rawCursorOffset, text.length));

    if (!textarea) {
      if (options?.replacementRange) {
        const { start, end } = options.replacementRange;
        setInput((prev) => `${prev.slice(0, start)}${text}${prev.slice(end)}`);
      } else {
        setInput((prev) => prev + text);
      }
      return;
    }

    const defaultStart = textarea.selectionStart ?? 0;
    const defaultEnd = textarea.selectionEnd ?? 0;
    const rawStart = options?.replacementRange?.start ?? defaultStart;
    const rawEnd = options?.replacementRange?.end ?? defaultEnd;
    const start = Math.max(0, Math.min(rawStart, textarea.value.length));
    const end = Math.max(start, Math.min(rawEnd, textarea.value.length));

    setInput((prev) => `${prev.slice(0, start)}${text}${prev.slice(end)}`);
    setSlashCommand(null);
    setSlashMenuIndex(0);

    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + boundedCursorOffset;
      textarea.setSelectionRange(cursor, cursor);
    });
  }, []);

  const appendText = useCallback((text: string) => {
    setInput((prev) => (prev ? `${prev}\n\n${text}` : text));
    setSlashCommand(null);
    setSlashMenuIndex(0);
    requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      textarea.focus();
      const cursor = textarea.value.length;
      textarea.setSelectionRange(cursor, cursor);
    });
  }, []);

  const orderedTemplates = useMemo(() => {
    const recentIndexById = new Map(recentTemplateIds.map((id, index) => [id, index]));
    const pinnedTemplateSet = new Set(pinnedTemplateIds);

    return [...promptTemplates].sort((a, b) => {
      const aPinned = pinnedTemplateSet.has(a.id);
      const bPinned = pinnedTemplateSet.has(b.id);
      if (aPinned !== bPinned) {
        return aPinned ? -1 : 1;
      }

      const aRecent = recentIndexById.get(a.id);
      const bRecent = recentIndexById.get(b.id);
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
  }, [promptTemplates, recentTemplateIds, pinnedTemplateIds]);

  const filteredTemplateMenu = useMemo(() => {
    return orderedTemplates.filter((template) => matchesTemplateQuery(template, templateSearch));
  }, [orderedTemplates, templateSearch]);

  const slashMatchedTemplates = useMemo(() => {
    if (!slashCommand) {
      return [];
    }

    const query = slashCommand.query.trim();
    return orderedTemplates
      .filter((template) => matchesTemplateQuery(template, query))
      .slice(0, 8);
  }, [orderedTemplates, slashCommand]);

  const updateSlashCommandFromText = useCallback((text: string, cursorPosition?: number | null) => {
    const cursor = cursorPosition ?? text.length;
    setSlashCommand(findSlashCommand(text, cursor));
    setSlashMenuIndex(0);
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const nextInput = e.target.value;
    setInput(nextInput);

    const cursorPos = e.target.selectionStart;

    // Check for @ file command
    const atMatch = findAtFileCommand(nextInput, cursorPos);
    if (atMatch) {
      setAtFileCommand(atMatch);
      setFileQuery(atMatch.query);
      setFileMenuIndex(0);
    } else {
      setAtFileCommand(null);
    }

    // Existing slash command logic
    updateSlashCommandFromText(nextInput, cursorPos);
  }, [updateSlashCommandFromText, setFileQuery]);

  const handleTextareaSelectionChange = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    updateSlashCommandFromText(textarea.value, textarea.selectionStart);
  }, [updateSlashCommandFromText]);

  const loadPromptTemplates = useCallback(async () => {
    try {
      setTemplatesLoading(true);
      setTemplatesError(null);
      const data = await listPromptTemplates();
      setPromptTemplates(data.filter((template) => template.enabled !== false));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load templates';
      setTemplatesError(message);
    } finally {
      setTemplatesLoading(false);
      setTemplatesFetched(true);
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
    if (slashCommand && !templatesFetched && !templatesLoading) {
      loadPromptTemplates();
    }
  }, [slashCommand, templatesFetched, templatesLoading, loadPromptTemplates]);

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
    const variables = extractTemplateVariables(template.content);
    if (variables.length === 0) {
      executeTemplateInsert(template, {}, replacementRange);
      return;
    }

    const values = variables.reduce<Record<string, string>>((acc, variable) => {
      acc[variable] = '';
      return acc;
    }, {});

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

  const handleTemplateVariableCancel = useCallback(() => {
    setPendingTemplateInsert(null);
  }, []);

  const handleTemplateVariableSubmit = useCallback(() => {
    if (!pendingTemplateInsert) {
      return;
    }

    executeTemplateInsert(
      pendingTemplateInsert.template,
      pendingTemplateInsert.values,
      pendingTemplateInsert.replacementRange,
    );
    setPendingTemplateInsert(null);
  }, [pendingTemplateInsert, executeTemplateInsert]);

  const handleFileReferenceSelect = useCallback((filePath: string) => {
    if (!atFileCommand) return;

    const beforeAt = input.slice(0, atFileCommand.start);
    const afterCursor = input.slice(atFileCommand.end);

    // Insert file reference marker
    const newInput = `${beforeAt}@[file:${filePath}] ${afterCursor}`;
    setInput(newInput);
    setAtFileCommand(null);

    // Focus back to textarea
    if (textareaRef.current) {
      textareaRef.current.focus();
      const newCursorPos = beforeAt.length + `@[file:${filePath}] `.length;
      textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
    }
  }, [input, atFileCommand]);

  const handleTemplateSearchKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setShowTemplateMenu(false);
      return;
    }

    if (filteredTemplateMenu.length === 0) {
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setTemplateMenuIndex((prev) => (prev + 1) % filteredTemplateMenu.length);
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setTemplateMenuIndex((prev) => (prev - 1 + filteredTemplateMenu.length) % filteredTemplateMenu.length);
      return;
    }

    if (e.key === 'Enter') {
      e.preventDefault();
      const selectedTemplate = filteredTemplateMenu[templateMenuIndex];
      if (selectedTemplate) {
        handleInsertTemplate(selectedTemplate);
      }
    }
  }, [filteredTemplateMenu, templateMenuIndex, handleInsertTemplate]);

  const focusComposer = useCallback(() => {
    textareaRef.current?.focus();
  }, []);

  const attachTextFile = useCallback(async (options: { filename: string; content: string; mimeType?: string }) => {
    if (!sessionId) {
      throw new Error('No active session');
    }

    const mimeType = options.mimeType || 'text/plain';
    const file = new File([options.content], options.filename, { type: mimeType });

    if (file.size > 10 * 1024 * 1024) {
      alert(`Attachment ${options.filename} exceeds 10MB limit`);
      return;
    }

    setUploading(true);
    try {
      const result = await api.uploadFile(sessionId, file);
      setAttachments(prev => [...prev, result]);
    } finally {
      setUploading(false);
    }
  }, [api, sessionId]);

  const normalizeBlock = useCallback((inputBlock: ChatComposerBlockInput, options?: { isEditing?: boolean }) => {
    const title = inputBlock.title?.trim() || 'Block';
    const isEditing = options?.isEditing ?? false;
    return {
      id: createBlockId(),
      title,
      content: inputBlock.content ?? '',
      collapsed: inputBlock.collapsed ?? !isEditing,
      isEditing,
      kind: inputBlock.kind ?? 'note',
      language: inputBlock.language,
      source: inputBlock.source,
      isAttachmentNote: inputBlock.isAttachmentNote,
      attachmentFilename: inputBlock.attachmentFilename,
      draftTitle: isEditing ? title : undefined,
      draftContent: isEditing ? (inputBlock.content ?? '') : undefined,
    };
  }, []);

  const addBlock = useCallback((inputBlock: ChatComposerBlockInput) => {
    setBlocks(prev => [...prev, normalizeBlock(inputBlock)]);
  }, [normalizeBlock]);

  const handleCreateBlock = () => {
    const newBlock = normalizeBlock(
      {
        title: 'New block',
        content: '',
        collapsed: false,
        kind: 'note',
      },
      { isEditing: true }
    );
    setBlocks(prev => [...prev, newBlock]);
  };

  const toggleBlockCollapsed = (blockId: string) => {
    setBlocks(prev => prev.map(block => (
      block.id === blockId
        ? { ...block, collapsed: !block.collapsed }
        : block
    )));
  };

  const startEditBlock = (blockId: string) => {
    setBlocks(prev => prev.map(block => (
      block.id === blockId
        ? {
          ...block,
          isEditing: true,
          collapsed: false,
          draftTitle: block.title,
          draftContent: block.content,
        }
        : block
    )));
  };

  const updateBlockDraft = (blockId: string, updates: { draftTitle?: string; draftContent?: string }) => {
    setBlocks(prev => prev.map(block => (
      block.id === blockId
        ? { ...block, ...updates }
        : block
    )));
  };

  const saveBlockEdit = (blockId: string) => {
    setBlocks(prev => prev.map(block => (
      block.id === blockId
        ? {
          ...block,
          title: block.draftTitle?.trim() || block.title,
          content: block.draftContent ?? block.content,
          isEditing: false,
          collapsed: true,
          draftTitle: undefined,
          draftContent: undefined,
        }
        : block
    )));
  };

  const cancelBlockEdit = (blockId: string) => {
    setBlocks(prev => prev.map(block => (
      block.id === blockId
        ? {
          ...block,
          isEditing: false,
          draftTitle: undefined,
          draftContent: undefined,
        }
        : block
    )));
  };

  const removeBlock = (blockId: string) => {
    setBlocks(prev => prev.filter(block => block.id !== blockId));
  };

  const buildBlocksMessage = useCallback(() => {
    const parts: string[] = [];

    blocks.forEach((block) => {
      const contentSource = block.isEditing ? (block.draftContent ?? block.content) : block.content;
      const content = contentSource.trim();
      const title = block.isEditing ? (block.draftTitle ?? block.title) : block.title;
      if (!content && !block.isAttachmentNote) {
        return;
      }

      if (block.isAttachmentNote) {
        const header = block.source
          ? `[Context: ${block.source.filePath} lines ${block.source.startLine}-${block.source.endLine}]`
          : `[Block: ${title}]`;
        const filename = block.attachmentFilename ? ` ${block.attachmentFilename}` : ' file';
        parts.push(`${header}\n(Attached as${filename})`);
        return;
      }

      const header = block.source
        ? `[Context: ${block.source.filePath} lines ${block.source.startLine}-${block.source.endLine}]`
        : `[Block: ${title}]`;
      const fence = block.language ? `\`\`\`${block.language}` : '```';
      parts.push(`${header}\n${fence}\n${content}\n\`\`\``);
    });

    return parts.join('\n\n');
  }, [blocks]);

  useEffect(() => {
    registerComposer({
      insertText,
      appendText,
      focus: focusComposer,
      attachTextFile,
      addBlock,
    });

    return () => registerComposer(null);
  }, [registerComposer, insertText, appendText, focusComposer, attachTextFile, addBlock]);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || !sessionId) return;

    setUploading(true);
    try {
      const uploaded: UploadedFile[] = [];
      for (const file of Array.from(files)) {
        // Validate size on client side (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
          alert(t('input.fileSizeExceeded', { name: file.name }));
          continue;
        }

        // Check if file is an image
        const isImage = file.type.startsWith('image/');
        if (isImage && !supportsVision) {
          alert(t('input.noVisionSupport'));
          continue;
        }

        const result = await api.uploadFile(sessionId, file);
        uploaded.push(result);
      }
      setAttachments(prev => [...prev, ...uploaded]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      alert(t('input.uploadFailed', { message }));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemoveAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const handleSend = () => {
    const blocksMessage = buildBlocksMessage();
    const messageParts = [blocksMessage, input.trim()].filter(Boolean);
    const message = messageParts.join('\n\n');

    if (message || attachments.length > 0) {
      // Parse file references from message
      const fileReferencePattern = /@\[file:(.*?)\]/g;
      const matches = [...message.matchAll(fileReferencePattern)];
      const fileReferences = activeProjectId
        ? matches.map(match => ({
            path: match[1],
            project_id: activeProjectId
          }))
        : [];

      const sendOptions = {
        reasoningEffort: reasoningEffort || undefined,
        attachments: attachments.length > 0 ? attachments : undefined,
        useWebSearch,
        fileReferences: fileReferences.length > 0 ? fileReferences : undefined,
      };

      if (pendingCompareModelIds.length >= 2 && onCompare) {
        onCompare(message, pendingCompareModelIds, sendOptions);
        setPendingCompareModelIds([]);
      } else {
        onSend(message, sendOptions);
      }

      setInput('');
      setSlashCommand(null);
      setSlashMenuIndex(0);
      setAtFileCommand(null);
      setAttachments([]);
      setBlocks([]);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Handle @ file reference navigation
    if (atFileCommand && fileSearchResults.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setFileMenuIndex((prev) =>
          prev < fileSearchResults.length - 1 ? prev + 1 : 0
        );
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setFileMenuIndex((prev) =>
          prev > 0 ? prev - 1 : fileSearchResults.length - 1
        );
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        handleFileReferenceSelect(fileSearchResults[fileMenuIndex].path);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setAtFileCommand(null);
        return;
      }
    }

    // Handle slash command navigation
    if (slashCommand) {
      if (e.key === 'ArrowDown' && slashMatchedTemplates.length > 0) {
        e.preventDefault();
        setSlashMenuIndex((prev) => (prev + 1) % slashMatchedTemplates.length);
        return;
      }

      if (e.key === 'ArrowUp' && slashMatchedTemplates.length > 0) {
        e.preventDefault();
        setSlashMenuIndex((prev) => (prev - 1 + slashMatchedTemplates.length) % slashMatchedTemplates.length);
        return;
      }

      if (e.key === 'Enter' && !e.shiftKey) {
        if (slashMatchedTemplates.length > 0) {
          e.preventDefault();
          const selectedTemplate = slashMatchedTemplates[slashMenuIndex];
          if (selectedTemplate) {
            handleInsertSlashTemplate(selectedTemplate);
          }
          return;
        }
      }

      if (e.key === 'Escape') {
        e.preventDefault();
        setSlashCommand(null);
        setSlashMenuIndex(0);
        return;
      }
    }

    // Send on Enter, new line on Shift+Enter
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming) {
        handleSend();
      }
    }
  };

  const handleClearClick = () => {
    setShowClearConfirm(true);
  };

  const handleClearConfirm = () => {
    setShowClearConfirm(false);
    onClearAllMessages?.();
  };

  const handleClearCancel = () => {
    setShowClearConfirm(false);
  };

  const handleTranslateInput = async (targetLanguage?: string) => {
    if (isTranslatingInput || !input.trim()) return;
    setIsTranslatingInput(true);
    setShowTranslateInputMenu(false);
    setSlashCommand(null);
    setSlashMenuIndex(0);
    let translated = '';
    try {
      await api.translateText(
        input.trim(),
        (chunk) => {
          translated += chunk;
          setInput(translated);
        },
        () => setIsTranslatingInput(false),
        (error) => {
          console.error('Input translation failed:', error);
          setIsTranslatingInput(false);
        },
        targetLanguage,
      );
    } catch (err) {
      console.error('Input translation failed:', err);
      setIsTranslatingInput(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      setShowClearConfirm(false);
    }
  };

  const handleTemplateVariableBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      setPendingTemplateInsert(null);
    }
  };

  const currentOption = REASONING_EFFORT_OPTIONS.find(o => o.value === reasoningEffort) || REASONING_EFFORT_OPTIONS[0];
  const blocksMessage = buildBlocksMessage();
  const canSend = !!input.trim() || !!blocksMessage || attachments.length > 0;
  const selectedInputTranslateLabel = useMemo(
    () => TRANSLATION_TARGET_OPTIONS.find((option) => option.value === selectedInputTranslateTarget)?.label || 'Auto',
    [selectedInputTranslateTarget]
  );
  const pinnedTemplateSet = useMemo(() => new Set(pinnedTemplateIds), [pinnedTemplateIds]);
  const recentTemplateSet = useMemo(() => new Set(recentTemplateIds), [recentTemplateIds]);

  return (
    <div data-name="input-box-root" className="border-t border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800">
      {/* Toolbar */}
      <div data-name="input-box-toolbar" className="flex items-center gap-1.5 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        {/* Group 1: Assistant & Model */}
        {assistantSelector}

        {/* Parameter overrides button */}
        {sessionId && _currentAssistantId && !_currentAssistantId.startsWith('__legacy_model_') && onParamOverridesChange && (
          <ParamOverridePopover
            sessionId={sessionId}
            currentAssistantId={_currentAssistantId}
            paramOverrides={paramOverrides || {}}
            onOverridesChange={onParamOverridesChange}
            hasActiveOverrides={hasActiveOverrides}
          />
        )}

        {/* Separator */}
        <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-0.5" />

        {/* Group 2: Context Management */}
        {/* Create block button */}
        <button
          onClick={handleCreateBlock}
          className={TOOLBAR_BTN_DEFAULT}
          title={t('input.createBlock')}
        >
          <PlusIcon className="h-4 w-4" />
        </button>

        {/* Clear context button */}
        {onInsertSeparator && (
          <button
            onClick={onInsertSeparator}
            disabled={isStreaming}
            className="flex items-center justify-center p-1.5 rounded-md border bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 hover:text-amber-700 dark:hover:text-amber-300 hover:border-amber-200 dark:hover:border-amber-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('input.clearContext')}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}

        {/* Compress context button */}
        {onCompressContext && (
          <button
            onClick={onCompressContext}
            disabled={isStreaming || isCompressing}
            className={`${TOOLBAR_BTN} ${
              isCompressing
                ? 'bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-800'
                : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-violet-50 dark:hover:bg-violet-900/30 hover:text-violet-700 dark:hover:text-violet-300 hover:border-violet-200 dark:hover:border-violet-800'
            }`}
            title={t('input.compressContext')}
          >
            <svg className={`h-4 w-4 ${isCompressing ? 'animate-pulse' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
        )}

        {/* Clear all messages button */}
        {onClearAllMessages && (
          <button
            onClick={handleClearClick}
            disabled={isStreaming}
            className="flex items-center justify-center p-1.5 rounded-md border bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-700 dark:hover:text-red-300 hover:border-red-200 dark:hover:border-red-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('input.clearAllMessages')}
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        )}

        {/* Separator */}
        <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-0.5" />

        {/* Group 3: Message Enhancements */}
        {/* Reasoning effort selector */}
        {supportsReasoning && (
          <div className="relative">
            <button
              onClick={() => setShowReasoningMenu(!showReasoningMenu)}
              className={`${TOOLBAR_BTN} ${
                reasoningEffort
                  ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                  : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
              }`}
              title={`${t('input.reasoning.prefix', { defaultValue: 'Reasoning' })}: ${t(currentOption.labelKey)}`}
            >
              <Brain className={`h-4 w-4 ${getReasoningIconColor(reasoningEffort)}`} />
            </button>

            {showReasoningMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowReasoningMenu(false)} />
                <div className="absolute left-0 bottom-full mb-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700">
                  <div className="py-1">
                    {REASONING_EFFORT_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        onClick={() => {
                          setReasoningEffort(option.value);
                          setShowReasoningMenu(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 ${
                          reasoningEffort === option.value
                            ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        <div className="font-medium">{t(option.labelKey)}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{t(option.descKey)}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Web search toggle */}
        <button
          type="button"
          onClick={() => setUseWebSearch(prev => !prev)}
          disabled={disabled || isStreaming}
          data-name="input-box-web-search-toggle"
          className={`${TOOLBAR_BTN} ${
            useWebSearch
              ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
              : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
          title={useWebSearch ? t('input.webSearchEnabled') : t('input.enableWebSearch')}
        >
          <GlobeAltIcon className="h-4 w-4" />
        </button>

        {/* Compare models button */}
        <CompareModelButton
          disabled={disabled}
          isStreaming={isStreaming}
          onCompareActivate={(modelIds) => setPendingCompareModelIds(modelIds)}
        />

        {/* Prompt templates */}
        <div className="relative" data-name="input-box-prompt-templates">
          <button
            type="button"
            onClick={() => setShowTemplateMenu((prev) => !prev)}
            disabled={disabled || isStreaming}
            className={`${TOOLBAR_BTN} ${
              showTemplateMenu
                ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
            }`}
            title={t('input.insertTemplate')}
          >
            <DocumentTextIcon className="h-4 w-4" />
          </button>

          {showTemplateMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowTemplateMenu(false)} />
              <div className="absolute left-0 bottom-full mb-2 w-80 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700" data-name="input-box-template-menu">
                <div className="p-2 border-b border-gray-200 dark:border-gray-700 space-y-2">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {t('input.promptTemplates')}
                  </div>
                  <input
                    ref={templateSearchInputRef}
                    value={templateSearch}
                    onChange={(e) => {
                      setTemplateSearch(e.target.value);
                      setTemplateMenuIndex(0);
                    }}
                    onKeyDown={handleTemplateSearchKeyDown}
                    placeholder={t('input.searchTemplates')}
                    className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="max-h-72 overflow-auto">
                  {templatesLoading && (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('input.loadingTemplates')}
                    </div>
                  )}
                  {!templatesLoading && templatesError && (
                    <div className="px-3 py-2 space-y-2">
                      <div className="text-sm text-red-600 dark:text-red-400">
                        {templatesError}
                      </div>
                      <button
                        type="button"
                        onClick={loadPromptTemplates}
                        className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
                      >
                        {t('common:retry')}
                      </button>
                    </div>
                  )}
                  {!templatesLoading && !templatesError && promptTemplates.length === 0 && (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('input.noTemplates')}
                    </div>
                  )}
                  {!templatesLoading && !templatesError && promptTemplates.length > 0 && filteredTemplateMenu.length === 0 && (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('input.noMatchingTemplates')}
                    </div>
                  )}
                  {!templatesLoading && !templatesError && filteredTemplateMenu.map((template, index) => {
                    const isPinned = pinnedTemplateSet.has(template.id);
                    const isRecent = recentTemplateSet.has(template.id);
                    const isActive = index === templateMenuIndex;

                    return (
                      <div
                        key={template.id}
                        onMouseEnter={() => setTemplateMenuIndex(index)}
                        className={`flex items-start gap-2 px-2 py-2 border-b border-gray-100 dark:border-gray-700/60 ${
                          isActive ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                        }`}
                        data-name="input-box-template-row"
                      >
                        <button
                          type="button"
                          onClick={() => handleInsertTemplate(template)}
                          className="flex-1 min-w-0 text-left"
                        >
                          <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                            {template.name}
                          </div>
                          {template.description && (
                            <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                              {template.description}
                            </div>
                          )}
                          {(isPinned || isRecent) && (
                            <div className="mt-1 flex items-center gap-1 text-[10px] uppercase tracking-wide">
                              {isPinned && (
                                <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
                                  {t('input.pinned')}
                                </span>
                              )}
                              {isRecent && (
                                <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                                  {t('input.recent')}
                                </span>
                              )}
                            </div>
                          )}
                        </button>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleTemplatePinned(template.id);
                          }}
                          className={`px-2 py-1 text-xs rounded border ${
                            isPinned
                              ? 'border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30'
                              : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                          }`}
                          title={isPinned ? t('input.unpinTemplate') : t('input.pinTemplate')}
                        >
                          {isPinned ? t('input.pinned') : t('input.pin')}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Translate input button with target selector */}
        <div data-name="input-box-translate-control" ref={translateInputMenuRef} className="relative">
          <div
            className={`group relative flex rounded-md border transition-colors ${
              isTranslatingInput
                ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800'
                : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/30 hover:text-teal-700 dark:hover:text-teal-300 hover:border-teal-200 dark:hover:border-teal-800'
            }`}
          >
            <button
              type="button"
              onClick={() => handleTranslateInput(selectedInputTranslateTarget === 'auto' ? undefined : selectedInputTranslateTarget)}
              disabled={disabled || isStreaming || isTranslatingInput || !input.trim()}
              data-name="input-box-translate-toggle"
              className="flex items-center gap-1 px-2 py-1.5 rounded-l-md disabled:opacity-50 disabled:cursor-not-allowed"
              title={`${isTranslatingInput ? t('input.translating') : t('input.translateInput')} (${selectedInputTranslateLabel})`}
            >
              <LanguageIcon className={`h-4 w-4 ${isTranslatingInput ? 'animate-pulse' : ''}`} />
              <span className="text-[10px] font-medium leading-none">{selectedInputTranslateLabel}</span>
            </button>
            <button
              type="button"
              onClick={() => setShowTranslateInputMenu((prev) => !prev)}
              disabled={disabled || isStreaming || isTranslatingInput}
              className="px-1.5 py-1.5 border-l border-gray-300/80 dark:border-gray-600/80 rounded-r-md disabled:opacity-50 disabled:cursor-not-allowed"
              title="Select translation target"
            >
              <ChevronDownIcon className={`h-3.5 w-3.5 transition-transform ${showTranslateInputMenu ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {showTranslateInputMenu && (
            <div data-name="input-box-translate-menu" className="absolute z-20 mt-1 min-w-[132px] rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg py-1">
              {TRANSLATION_TARGET_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    setSelectedInputTranslateTarget(option.value);
                    setShowTranslateInputMenu(false);
                  }}
                  className={`w-full px-3 py-1.5 text-left text-xs transition-colors ${
                    selectedInputTranslateTarget === option.value
                      ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                      : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* File upload button */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || isStreaming || !sessionId}
          className={`${TOOLBAR_BTN} ${
            uploading
              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800 animate-pulse'
              : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
          title={uploading ? t('input.uploading') : supportsVision ? t('input.attachFileImage') : t('input.attachTextFile')}
        >
          <PaperClipIcon className="h-4 w-4" />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={supportsVision
            ? "text/*,.txt,.md,.json,.csv,.log,.xml,.yaml,.yml,.py,.js,.ts,.java,.cpp,.go,.rs,.html,.css,image/*,.jpg,.jpeg,.png,.gif,.webp"
            : "text/*,.txt,.md,.json,.csv,.log,.xml,.yaml,.yml,.py,.js,.ts,.java,.cpp,.go,.rs,.html,.css"
          }
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Block list */}
      {blocks.length > 0 && (
        <div data-name="input-box-blocks" className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 space-y-2 bg-gray-50 dark:bg-gray-900/40">
          {blocks.map((block) => {
            const draftTitle = block.draftTitle ?? block.title;
            const displayTitle = block.title || 'Block';
            const draftContent = block.draftContent ?? block.content;
            const contentLength = block.isEditing
              ? (draftContent?.length || 0)
              : block.content.length;
              const metaLabel = block.isAttachmentNote
              ? t('input.block.attachment')
              : t('input.block.chars', { count: contentLength });
            const collapseDisabled = block.isEditing;
            return (
              <div
                key={block.id}
                data-name="input-block"
                className="rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden"
              >
                <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-700">
                  <button
                    onClick={() => toggleBlockCollapsed(block.id)}
                    disabled={collapseDisabled}
                    className={`p-1 rounded ${
                      collapseDisabled
                        ? 'text-gray-400 dark:text-gray-500 cursor-not-allowed'
                        : 'hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                    title={collapseDisabled ? t('input.block.finishEditing') : block.collapsed ? t('input.block.expandBlock') : t('input.block.collapseBlock')}
                  >
                    {block.collapsed ? (
                      <PlusIcon className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                    ) : (
                      <MinusIcon className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                    )}
                  </button>
                  {block.isEditing ? (
                    <input
                      value={draftTitle}
                      onChange={(e) => updateBlockDraft(block.id, { draftTitle: e.target.value })}
                      className="flex-1 min-w-0 text-sm font-medium px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                      placeholder={t('input.block.blockTitle')}
                    />
                  ) : (
                    <div className="flex-1 text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                      {displayTitle}
                    </div>
                  )}
                  <span className="text-xs text-gray-500 dark:text-gray-400">{metaLabel}</span>
                  {block.isEditing ? (
                    <>
                      <button
                        onClick={() => saveBlockEdit(block.id)}
                        className="p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-300"
                        title={t('input.block.saveBlock')}
                      >
                        <CheckIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => cancelBlockEdit(block.id)}
                        className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300"
                        title={t('input.block.cancelEdit')}
                      >
                        <XMarkIcon className="h-4 w-4" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => startEditBlock(block.id)}
                        className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300"
                        title={t('input.block.editBlock')}
                      >
                        <PencilSquareIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => removeBlock(block.id)}
                        className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400"
                        title={t('input.block.removeBlock')}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </>
                  )}
                </div>

                {!block.collapsed && (
                  <div className="px-3 py-2 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
                    {block.isEditing ? (
                      <div className="space-y-2">
                        {block.isAttachmentNote ? (
                          <div className="text-xs text-gray-600 dark:text-gray-300">
                            Attachment: {block.attachmentFilename || 'file'}
                          </div>
                        ) : (
                          <textarea
                            value={draftContent}
                            onChange={(e) => updateBlockDraft(block.id, { draftContent: e.target.value })}
                            className="w-full min-h-[120px] max-h-64 resize-none rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-2 overflow-auto"
                            placeholder={t('input.block.blockContent')}
                          />
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-gray-700 dark:text-gray-200 whitespace-pre-wrap max-h-64 overflow-auto">
                        {block.isAttachmentNote
                          ? `Attachment: ${block.attachmentFilename || 'file'}`
                          : block.content}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Attachment preview */}
      {attachments.length > 0 && (
        <div data-name="input-box-attachments" className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 space-y-1">
          {attachments.map((att, idx) => {
            const isImage = att.mime_type.startsWith('image/');
            return (
              <div
                key={idx}
                className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800"
              >
                {isImage ? (
                  <PhotoIcon className="h-4 w-4 flex-shrink-0" />
                ) : (
                  <DocumentTextIcon className="h-4 w-4 flex-shrink-0" />
                )}
                <span className="flex-1 text-sm truncate">{att.filename}</span>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  ({(att.size / 1024).toFixed(1)} KB)
                </span>
                <button
                  onClick={() => handleRemoveAttachment(idx)}
                  className="flex-shrink-0 hover:text-red-600 dark:hover:text-red-400"
                  title={t('input.removeFile')}
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Input area */}
      <div data-name="input-box-input-area" className="p-4">
        <div data-name="input-box-input-controls" className="flex gap-2 items-end">
          <div className="relative flex-1" data-name="input-box-textarea-wrap">
            {slashCommand && (
              <div className="absolute left-0 right-0 bottom-full mb-2 bg-white dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700 shadow-lg z-20" data-name="input-box-slash-menu">
                <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
                  {t('input.slashHint')}
                </div>
                <div className="max-h-60 overflow-auto">
                  {templatesLoading && (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('input.loadingTemplates')}
                    </div>
                  )}
                  {!templatesLoading && templatesError && (
                    <div className="px-3 py-2 space-y-2">
                      <div className="text-sm text-red-600 dark:text-red-400">
                        {templatesError}
                      </div>
                      <button
                        type="button"
                        onClick={loadPromptTemplates}
                        className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
                      >
                        {t('common:retry')}
                      </button>
                    </div>
                  )}
                  {!templatesLoading && !templatesError && promptTemplates.length === 0 && (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('input.noTemplates')}
                    </div>
                  )}
                  {!templatesLoading && !templatesError && promptTemplates.length > 0 && slashMatchedTemplates.length === 0 && (
                    <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                      {t('input.noMatchingSlash', { query: slashCommand.query })}
                    </div>
                  )}
                  {!templatesLoading && !templatesError && slashMatchedTemplates.map((template, index) => {
                    const isActive = index === slashMenuIndex;
                    const isPinned = pinnedTemplateSet.has(template.id);
                    const isRecent = recentTemplateSet.has(template.id);

                    return (
                      <button
                        key={template.id}
                        type="button"
                        onMouseEnter={() => setSlashMenuIndex(index)}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => handleInsertSlashTemplate(template)}
                        className={`w-full text-left px-3 py-2 border-b border-gray-100 dark:border-gray-700/60 ${
                          isActive
                            ? 'bg-blue-50 dark:bg-blue-900/20'
                            : 'hover:bg-gray-100 dark:hover:bg-gray-700'
                        }`}
                      >
                        <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {template.name}
                        </div>
                        {template.description && (
                          <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                            {template.description}
                          </div>
                        )}
                        {(isPinned || isRecent) && (
                          <div className="mt-1 flex items-center gap-1 text-[10px] uppercase tracking-wide">
                            {isPinned && (
                              <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
                                {t('input.pinned')}
                              </span>
                            )}
                            {isRecent && (
                              <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                                {t('input.recent')}
                              </span>
                            )}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* File picker popover */}
            {atFileCommand && activeProjectId && (
              <FilePickerPopover
                isOpen={true}
                projectId={activeProjectId}
                query={atFileCommand.query}
                results={fileSearchResults}
                selectedIndex={fileMenuIndex}
                loading={fileSearchLoading}
                onSelect={handleFileReferenceSelect}
                onClose={() => setAtFileCommand(null)}
              />
            )}

            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onSelect={handleTextareaSelectionChange}
              onClick={handleTextareaSelectionChange}
              onKeyDown={handleKeyDown}
              placeholder={t('input.placeholder')}
              disabled={disabled || isStreaming}
              className="w-full resize-none rounded-lg border border-gray-300 dark:border-gray-600 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white disabled:opacity-50"
              rows={3}
            />
          </div>
          {isStreaming ? (
            <button
              onClick={onStop}
              className="px-6 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
            >
              {t('input.stop')}
            </button>
          ) : (
            <div className="flex flex-col items-center gap-1">
              {pendingCompareModelIds.length >= 2 && (
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-purple-600 dark:text-purple-400 font-medium">
                    {t('input.compareActive', { count: pendingCompareModelIds.length })}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPendingCompareModelIds([])}
                    className="text-[10px] text-gray-400 hover:text-red-500 dark:hover:text-red-400"
                    title={t('input.compareCancel')}
                  >
                    &times;
                  </button>
                </div>
              )}
              <button
                onClick={handleSend}
                disabled={disabled || !canSend}
                className={`px-6 py-2 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
                  pendingCompareModelIds.length >= 2
                    ? 'bg-purple-600 hover:bg-purple-700'
                    : 'bg-blue-500 hover:bg-blue-600'
                }`}
              >
                {pendingCompareModelIds.length >= 2
                  ? t('input.compareConfirm')
                  : t('input.send')}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Template variable fill dialog */}
      {pendingTemplateInsert && (
        <div
          data-name="input-box-template-variables-backdrop"
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={handleTemplateVariableBackdropClick}
        >
          <div
            data-name="input-box-template-variables-modal"
            className="bg-white dark:bg-gray-800 rounded-lg p-5 w-full max-w-lg mx-4 shadow-xl"
          >
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
              {t('input.templateVariablesTitle')}
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              {t('input.templateVariablesDescription', { name: pendingTemplateInsert.template.name })}
            </p>

            <form
              data-name="input-box-template-variables-form"
              onSubmit={(e) => {
                e.preventDefault();
                handleTemplateVariableSubmit();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  e.preventDefault();
                  handleTemplateVariableCancel();
                }
              }}
            >
              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {pendingTemplateInsert.variables.map((variable, index) => (
                  <div key={variable} data-name="input-box-template-variable-row">
                    <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                      {variable}
                    </label>
                    <input
                      autoFocus={index === 0}
                      value={pendingTemplateInsert.values[variable] || ''}
                      onChange={(event) => handleTemplateVariableChange(variable, event.target.value)}
                      placeholder={t('input.templateVariablePlaceholder', { name: variable })}
                      className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-3 mt-5">
                <button
                  type="button"
                  onClick={handleTemplateVariableCancel}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                >
                  {t('common:cancel')}
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
                >
                  {t('input.insertFilledTemplate')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Clear messages confirmation dialog */}
      {showClearConfirm && (
        <div
          data-name="input-box-clear-confirm-backdrop"
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={handleBackdropClick}
        >
          <div data-name="input-box-clear-confirm-modal" className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-sm mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              {t('input.clearConfirmTitle')}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              {t('input.clearConfirmMessage')}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleClearCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                {t('common:cancel')}
              </button>
              <button
                onClick={handleClearConfirm}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors"
              >
                {t('common:clearAll')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
