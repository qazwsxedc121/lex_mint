/**
 * InputBox component - message input field with send button and toolbar.
 */

import React, { useState, useRef, useCallback, useEffect, useMemo, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import {
  GlobeAltIcon,
  PaperClipIcon,
  DocumentTextIcon,
  PlusIcon,
} from '@heroicons/react/24/outline';
import { Brain } from 'lucide-react';
import { useChatServices } from '../services/ChatServiceProvider';
import { useChatComposer } from '../contexts/ChatComposerContext';
import type { ChatComposerBlockInput } from '../contexts/ChatComposerContext';
import type { UploadedFile } from '../../../types/message';
import type { ParamOverrides } from '../../../types/message';
import { ParamOverridePopover } from './ParamOverridePopover';
import { CompareModelButton } from './CompareModelButton';
import { FilePickerPopover } from './FilePickerPopover';
import { ClearMessagesConfirmModal, TranslateInputControl } from './InputBoxAuxiliaryControls';
import { InputComposerAttachments, InputComposerBlocks, type ChatBlock } from './InputComposerPanels';
import { PromptTemplateMenu, SlashSuggestionMenu, TemplateVariableModal } from './PromptTemplateMenus';
import { useFileSearch } from '../../../modules/projects/hooks/useFileSearch';
import { useProjectWorkspaceStore } from '../../../stores/projectWorkspaceStore';
import type { ReasoningControls } from '../../../types/model';
import { usePromptTemplateComposer } from '../hooks/usePromptTemplateComposer';
import {
  applyOutgoingSlashCommandEffects,
  buildSlashCommandSuggestions,
  type SlashCommandSuggestion,
} from '../slashCommands';

// Legacy fallback reasoning options.
const LEGACY_REASONING_OPTIONS = [
  { value: 'default', labelKey: 'input.reasoning.default', descKey: 'input.reasoning.defaultDesc' },
  { value: 'none', labelKey: 'input.reasoning.none', descKey: 'input.reasoning.noneDesc' },
  { value: 'low', labelKey: 'input.reasoning.low', descKey: 'input.reasoning.lowDesc' },
  { value: 'medium', labelKey: 'input.reasoning.medium', descKey: 'input.reasoning.mediumDesc' },
  { value: 'high', labelKey: 'input.reasoning.high', descKey: 'input.reasoning.highDesc' },
];

const LEGACY_REASONING_LABEL_KEY: Record<string, string> = LEGACY_REASONING_OPTIONS.reduce(
  (acc, option) => {
    acc[option.value] = option.labelKey;
    return acc;
  },
  {} as Record<string, string>
);

interface ReasoningMenuOption {
  value: string;
  label: string;
  description?: string;
}

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
    case 'none':   return 'text-red-500 dark:text-red-400';
    case 'low':    return 'text-amber-400 dark:text-amber-500';
    case 'medium': return 'text-amber-600 dark:text-amber-400';
    case 'high':   return 'text-orange-500 dark:text-orange-400';
    case 'minimal': return 'text-amber-300 dark:text-amber-500';
    case 'enabled': return 'text-amber-600 dark:text-amber-400';
    default:       return '';
  }
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

const createBlockId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `block-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

interface InputBoxProps {
  onSend: (message: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean; fileReferences?: Array<{ path: string; project_id: string }>; temporaryTurn?: boolean }) => void;
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
  reasoningControls?: ReasoningControls | null;
  reasoningEffort?: string;
  onReasoningEffortChange?: (reasoningEffort: string) => void;
  supportsVision?: boolean;
  useWebSearch?: boolean;
  onUseWebSearchChange?: (enabled: boolean) => void;
  showWebSearchToggle?: boolean;
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
  reasoningControls = null,
  reasoningEffort: controlledReasoningEffort,
  onReasoningEffortChange,
  supportsVision = false,
  useWebSearch: controlledUseWebSearch,
  onUseWebSearchChange,
  showWebSearchToggle = true,
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
  const [uncontrolledReasoningEffort, setUncontrolledReasoningEffort] = useState('default');
  const [showReasoningMenu, setShowReasoningMenu] = useState(false);
  const [uncontrolledUseWebSearch, setUncontrolledUseWebSearch] = useState(false);
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
  const translateInputMenuRef = useRef<HTMLDivElement>(null);
  const reasoningEffort = controlledReasoningEffort ?? uncontrolledReasoningEffort;
  const setReasoningEffort = onReasoningEffortChange ?? setUncontrolledReasoningEffort;
  const useWebSearch = controlledUseWebSearch ?? uncontrolledUseWebSearch;
  const setUseWebSearch = onUseWebSearchChange ?? setUncontrolledUseWebSearch;

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

  const insertText = useCallback((
    text: string,
    options?: { cursorOffset?: number; replacementRange?: { start: number; end: number } },
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

    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + boundedCursorOffset;
      textarea.setSelectionRange(cursor, cursor);
    });
  }, []);

  const appendText = useCallback((text: string) => {
    setInput((prev) => (prev ? `${prev}\n\n${text}` : text));
    requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      textarea.focus();
      const cursor = textarea.value.length;
      textarea.setSelectionRange(cursor, cursor);
    });
  }, []);

  const {
    clearSlashCommand,
    filteredTemplateMenu,
    handleInsertSlashTemplate,
    handleInsertTemplate,
    handleTemplateSearchKeyDown,
    handleTemplateVariableBackdropClick,
    handleTemplateVariableCancel,
    handleTemplateVariableChange,
    handleTemplateVariableSubmit,
    loadPromptTemplates,
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
  } = usePromptTemplateComposer({
    insertText,
    setInput,
    textareaRef,
  });

  const slashCommandSuggestions = useMemo<SlashCommandSuggestion[]>(() => {
    if (!slashCommand) {
      return [];
    }

    return buildSlashCommandSuggestions(slashCommand.query, t);
  }, [slashCommand, t]);

  const slashSuggestionCount = slashCommandSuggestions.length + slashMatchedTemplates.length;
  const activeSlashIndex = slashSuggestionCount > 0 ? Math.min(slashMenuIndex, slashSuggestionCount - 1) : 0;

  const handleSelectSlashCommand = useCallback((command: SlashCommandSuggestion) => {
    if (!slashCommand) {
      return;
    }

    const replacement = `/${command.trigger} `;
    const cursorPosition = slashCommand.start + replacement.length;
    setInput((prev) => `${prev.slice(0, slashCommand.start)}${replacement}${prev.slice(slashCommand.end)}`);
    clearSlashCommand();

    requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) {
        return;
      }
      textarea.focus();
      textarea.setSelectionRange(cursorPosition, cursorPosition);
    });
  }, [clearSlashCommand, slashCommand]);

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
    const rawMessage = messageParts.join('\n\n');
    const { temporaryTurn, strippedMessage } = applyOutgoingSlashCommandEffects(rawMessage);
    const message = strippedMessage;

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
        reasoningEffort: reasoningEffort === 'default' ? undefined : reasoningEffort,
        attachments: attachments.length > 0 ? attachments : undefined,
        useWebSearch,
        fileReferences: fileReferences.length > 0 ? fileReferences : undefined,
        temporaryTurn,
      };

      if (!temporaryTurn && pendingCompareModelIds.length >= 2 && onCompare) {
        onCompare(message, pendingCompareModelIds, sendOptions);
        setPendingCompareModelIds([]);
      } else {
        onSend(message, sendOptions);
        if (pendingCompareModelIds.length >= 2) {
          setPendingCompareModelIds([]);
        }
      }

      setInput('');
      resetTemplateComposer();
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
      if (e.key === 'ArrowDown' && slashSuggestionCount > 0) {
        e.preventDefault();
        setSlashMenuIndex((prev) => (prev + 1) % slashSuggestionCount);
        return;
      }

      if (e.key === 'ArrowUp' && slashSuggestionCount > 0) {
        e.preventDefault();
        setSlashMenuIndex((prev) => (prev - 1 + slashSuggestionCount) % slashSuggestionCount);
        return;
      }

      if (e.key === 'Enter' && !e.shiftKey) {
        if (slashSuggestionCount > 0) {
          e.preventDefault();
          if (activeSlashIndex < slashCommandSuggestions.length) {
            const selectedCommand = slashCommandSuggestions[activeSlashIndex];
            if (selectedCommand) {
              handleSelectSlashCommand(selectedCommand);
            }
          } else {
            const selectedTemplate = slashMatchedTemplates[activeSlashIndex - slashCommandSuggestions.length];
            if (selectedTemplate) {
              handleInsertSlashTemplate(selectedTemplate);
            }
          }
          return;
        }
      }

      if (e.key === 'Escape') {
        e.preventDefault();
        clearSlashCommand();
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
    clearSlashCommand();
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

  const reasoningOptions = useMemo<ReasoningMenuOption[]>(() => {
    if (!supportsReasoning) {
      return [];
    }

    if (!reasoningControls) {
      return LEGACY_REASONING_OPTIONS.map((option) => ({
        value: option.value,
        label: t(option.labelKey),
        description: t(option.descKey),
      }));
    }

    const items: ReasoningMenuOption[] = [
      {
        value: 'default',
        label: t('input.reasoning.default'),
        description: t('input.reasoning.defaultDesc'),
      },
    ];

    if (reasoningControls.disable_supported) {
      items.push({
        value: 'none',
        label: t('input.reasoning.none'),
        description: t('input.reasoning.noneDesc'),
      });
    }

    reasoningControls.options.forEach((optionValue) => {
      const normalized = optionValue.toLowerCase();
      const labelKey = LEGACY_REASONING_LABEL_KEY[normalized];
      items.push({
        value: optionValue,
        label: labelKey ? t(labelKey) : optionValue,
        description: reasoningControls.param,
      });
    });

    return items;
  }, [supportsReasoning, reasoningControls, t]);

  useEffect(() => {
    if (!reasoningOptions.length) {
      return;
    }
    const exists = reasoningOptions.some((option) => option.value === reasoningEffort);
    if (!exists) {
      setReasoningEffort('default');
    }
  }, [reasoningEffort, reasoningOptions, setReasoningEffort]);

  const currentOption = reasoningOptions.find((o) => o.value === reasoningEffort) || reasoningOptions[0];
  const blocksMessage = buildBlocksMessage();
  const canSend = !!input.trim() || !!blocksMessage || attachments.length > 0;
  const selectedInputTranslateLabel = useMemo(
    () => TRANSLATION_TARGET_OPTIONS.find((option) => option.value === selectedInputTranslateTarget)?.label || 'Auto',
    [selectedInputTranslateTarget]
  );

  return (
    <div data-name="input-box-root" className="border-t border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800">
      {/* Toolbar */}
      <div data-name="input-box-toolbar" className="flex items-center gap-1.5 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
        {/* Group 1: Assistant & Model */}
        {assistantSelector}

        {/* Parameter overrides button */}
        {sessionId && _currentAssistantId && onParamOverridesChange && (
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
                reasoningEffort === 'none'
                  ? 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800'
                  : reasoningEffort !== 'default'
                    ? 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                    : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
              }`}
              title={`${t('input.reasoning.prefix', { defaultValue: 'Reasoning' })}: ${currentOption?.label || t('input.reasoning.default')}`}
            >
              <Brain className={`h-4 w-4 ${getReasoningIconColor(reasoningEffort)}`} />
            </button>

            {showReasoningMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowReasoningMenu(false)} />
                <div className="absolute left-0 bottom-full mb-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700">
                  <div className="py-1">
                    {reasoningOptions.map((option) => (
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
                        <div className="font-medium">{option.label}</div>
                        {option.description && (
                          <div className="text-xs text-gray-500 dark:text-gray-400">{option.description}</div>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* Web search toggle */}
        {showWebSearchToggle && (
          <button
            type="button"
            onClick={() => setUseWebSearch(!useWebSearch)}
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
        )}

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

          <PromptTemplateMenu
            filteredTemplates={filteredTemplateMenu}
            isOpen={showTemplateMenu}
            loading={templatesLoading}
            error={templatesError}
            onClose={() => setShowTemplateMenu(false)}
            onInsertTemplate={handleInsertTemplate}
            onRetry={loadPromptTemplates}
            onSearchChange={setTemplateSearchValue}
            onSearchKeyDown={handleTemplateSearchKeyDown}
            onSetActiveIndex={setTemplateMenuIndex}
            onTogglePinned={toggleTemplatePinned}
            pinnedTemplateSet={pinnedTemplateSet}
            promptTemplates={promptTemplates}
            recentTemplateSet={recentTemplateSet}
            searchInputRef={templateSearchInputRef}
            searchValue={templateSearch}
            selectedIndex={templateMenuIndex}
          />
        </div>

        {/* Translate input button with target selector */}
        <TranslateInputControl
          disabled={disabled}
          inputValue={input}
          isOpen={showTranslateInputMenu}
          isStreaming={isStreaming}
          isTranslating={isTranslatingInput}
          menuRef={translateInputMenuRef}
          menuTitle="Select translation target"
          onSelectTarget={(target) => {
            setSelectedInputTranslateTarget(target);
            setShowTranslateInputMenu(false);
          }}
          onToggleMenu={() => setShowTranslateInputMenu((prev) => !prev)}
          onTranslate={() => handleTranslateInput(selectedInputTranslateTarget === 'auto' ? undefined : selectedInputTranslateTarget)}
          options={TRANSLATION_TARGET_OPTIONS}
          selectedTarget={selectedInputTranslateTarget}
          selectedTargetLabel={selectedInputTranslateLabel}
          translateTitle={t('input.translateInput')}
          translatingTitle={t('input.translating')}
        />

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

      <InputComposerBlocks
        blocks={blocks}
        onCancelEdit={cancelBlockEdit}
        onRemove={removeBlock}
        onSaveEdit={saveBlockEdit}
        onStartEdit={startEditBlock}
        onToggleCollapsed={toggleBlockCollapsed}
        onUpdateDraft={updateBlockDraft}
      />

      <InputComposerAttachments
        attachments={attachments}
        onRemoveAttachment={handleRemoveAttachment}
      />

      {/* Input area */}
      <div data-name="input-box-input-area" className="p-4">
        <div data-name="input-box-input-controls" className="flex gap-2 items-end">
          <div className="relative flex-1" data-name="input-box-textarea-wrap">
            {slashCommand && (
              <SlashSuggestionMenu
                commandSuggestions={slashCommandSuggestions}
                loading={templatesLoading}
                error={templatesError}
                onSelectCommand={handleSelectSlashCommand}
                onInsertTemplate={handleInsertSlashTemplate}
                onRetry={loadPromptTemplates}
                onSetActiveIndex={setSlashMenuIndex}
                pinnedTemplateSet={pinnedTemplateSet}
                promptTemplates={promptTemplates}
                query={slashCommand.query}
                recentTemplateSet={recentTemplateSet}
                selectedIndex={activeSlashIndex}
                templates={slashMatchedTemplates}
              />
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
      <TemplateVariableModal
        errors={templateVariableErrors}
        pendingInsert={pendingTemplateInsert}
        onBackdropClick={handleTemplateVariableBackdropClick}
        onCancel={handleTemplateVariableCancel}
        onChangeValue={handleTemplateVariableChange}
        onSubmit={handleTemplateVariableSubmit}
      />

      {/* Clear messages confirmation dialog */}
      <ClearMessagesConfirmModal
        isOpen={showClearConfirm}
        onBackdropClick={handleBackdropClick}
        onCancel={handleClearCancel}
        onConfirm={handleClearConfirm}
        cancelLabel={t('common:cancel')}
        confirmLabel={t('common:clearAll')}
        message={t('input.clearConfirmMessage')}
        title={t('input.clearConfirmTitle')}
      />
    </div>
  );
};
