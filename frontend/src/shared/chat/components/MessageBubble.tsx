/**
 * MessageBubble component - displays a single message.
 */

import React, { useState, useMemo, useEffect, useRef, useCallback, useSyncExternalStore } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { PencilSquareIcon, ArrowPathIcon, ClipboardDocumentIcon, ClipboardDocumentCheckIcon, TrashIcon, ChevronDownIcon, ChevronRightIcon, DocumentTextIcon, PhotoIcon, ArrowDownTrayIcon, ArrowUturnRightIcon, LanguageIcon, SpeakerWaveIcon, StopCircleIcon } from '@heroicons/react/24/outline';
import type { ChatTargetType, Message } from '../../../types/message';
import { CodeBlock } from './CodeBlock';
import { MermaidBlock } from './MermaidBlock';
import { ThinkingBlock } from './ThinkingBlock';
import { ToolCallBlock } from './ToolCallBlock';
import { TranslationBlock } from './TranslationBlock';
import { CompareResponseView } from './CompareResponseView';
import { useChatServices } from '../services/ChatServiceProvider';
import { useTTS } from '../hooks/useTTS';
import { normalizeMathDelimiters } from '../utils/markdownMath';
import { useDeveloperMode } from '../../../hooks/useDeveloperMode';
import { getAssistantIcon } from '../../constants/assistantIcons';
import { useTranslation } from 'react-i18next';
import {
  buildFileReferencePreview,
  ensureFileReferencePreviewConfigLoaded,
  getFileReferencePreviewConfig,
  subscribeFileReferencePreviewConfig,
} from '../config/fileReferencePreview';

interface MessageBubbleProps {
  message: Message;
  messageId: string;
  messageIndex: number;  // Still needed for file attachment URLs (backward compatibility)
  isStreaming: boolean;
  sessionId?: string;
  currentTargetType?: ChatTargetType;
  currentAssistantId?: string | null;
  currentModelId?: string | null;
  assistantNameById?: Record<string, string>;
  assistantModelIdById?: Record<string, string>;
  modelNameById?: Record<string, string>;
  onEdit?: (messageId: string, content: string) => void;
  onSaveOnly?: (messageId: string, content: string) => void;
  onRegenerate?: (messageId: string) => void;
  onDelete?: (messageId: string) => void;
  onBranch?: (messageId: string) => void;
  customActions?: (message: Message, messageId: string) => React.ReactNode;
  hasSubsequentMessages?: boolean;
}

interface ParsedUserBlock {
  id: string;
  kind: 'context' | 'block';
  title: string;
  content: string;
  language: string;
  isCodeFence: boolean;
  isAttachmentNote: boolean;
  attachmentLabel?: string;
}

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

const MODEL_PARTICIPANT_PREFIX = 'model::';

const normalizeNewlines = (text: string) => text.replace(/\r\n/g, '\n');

const parseUserBlocks = (rawContent: string): { blocks: ParsedUserBlock[]; message: string } => {
  const content = normalizeNewlines(rawContent);
  const blocks: ParsedUserBlock[] = [];
  let index = 0;

  const skipNewlines = () => {
    while (index < content.length && content[index] === '\n') {
      index += 1;
    }
  };

  skipNewlines();

  while (index < content.length) {
    const headerMatch = content.slice(index).match(/^\[(Context|Block):([^\]]+)\]\n/);
    if (!headerMatch) {
      const legacyFileHeaderMatch = content.slice(index).match(/^\[File:\s*([^\]]+)\]\n/);
      if (!legacyFileHeaderMatch) {
        break;
      }

      const title = `File Reference: ${legacyFileHeaderMatch[1].trim()}`;
      index += legacyFileHeaderMatch[0].length;

      // Legacy injected file contexts are followed by two newlines before user input
      // (or another file block). Capture that segment as a synthetic block.
      let legacyEnd = content.length;
      let scanIndex = index;
      while (scanIndex < content.length) {
        const separatorIndex = content.indexOf('\n\n', scanIndex);
        if (separatorIndex < 0) {
          break;
        }

        const nextSegment = content.slice(separatorIndex + 2);
        if (
          nextSegment.startsWith('[File:') ||
          nextSegment.startsWith('[Context:') ||
          nextSegment.startsWith('[Block:') ||
          nextSegment.startsWith('@[') ||
          (!nextSegment.startsWith('[') && nextSegment.trim().length > 0)
        ) {
          legacyEnd = separatorIndex;
          break;
        }

        scanIndex = separatorIndex + 2;
      }

      const legacyContent = content.slice(index, legacyEnd).replace(/^\n+|\n+$/g, '');
      blocks.push({
        id: `block-${blocks.length}-${title}`,
        kind: 'block',
        title,
        content: legacyContent,
        language: '',
        isCodeFence: false,
        isAttachmentNote: false,
      });
      index = legacyEnd;
      skipNewlines();
      continue;
    }

    const kind = headerMatch[1].toLowerCase() as 'context' | 'block';
    const title = headerMatch[2].trim();
    index += headerMatch[0].length;

    let language = '';
    let blockContent = '';
    let isCodeFence = false;
    let isAttachmentNote = false;
    let attachmentLabel: string | undefined;

    if (content.startsWith('```', index)) {
      isCodeFence = true;
      const fenceLineEnd = content.indexOf('\n', index);
      const fenceLine = fenceLineEnd >= 0 ? content.slice(index, fenceLineEnd) : content.slice(index);
      language = fenceLine.slice(3).trim();
      index = fenceLineEnd >= 0 ? fenceLineEnd + 1 : content.length;

      const fenceClose = content.indexOf('\n```', index);
      if (fenceClose >= 0) {
        blockContent = content.slice(index, fenceClose);
        index = fenceClose + 4;
        if (content[index] === '\n') {
          index += 1;
        }
      } else {
        blockContent = content.slice(index);
        index = content.length;
      }
    } else if (content.startsWith('(Attached as', index)) {
      const lineEnd = content.indexOf('\n', index);
      const line = lineEnd >= 0 ? content.slice(index, lineEnd) : content.slice(index);
      isAttachmentNote = true;
      attachmentLabel = line;
      index = lineEnd >= 0 ? lineEnd + 1 : content.length;
    } else {
      const nextHeaderOffset = content.slice(index).search(/\n\n(?=\[(Context|Block):)/);
      if (nextHeaderOffset >= 0) {
        blockContent = content.slice(index, index + nextHeaderOffset);
        index = index + nextHeaderOffset + 2;
      } else {
        const messageSplit = content.indexOf('\n\n', index);
        if (messageSplit >= 0) {
          const remainder = content.slice(messageSplit + 2);
          if (remainder.trim().length > 0) {
            blockContent = content.slice(index, messageSplit);
            index = messageSplit + 2;
          } else {
            blockContent = content.slice(index);
            index = content.length;
          }
        } else {
          blockContent = content.slice(index);
          index = content.length;
        }
      }
    }

    blockContent = blockContent.replace(/^\n+|\n+$/g, '');

    blocks.push({
      id: `block-${blocks.length}-${title}`,
      kind,
      title,
      content: blockContent,
      language,
      isCodeFence,
      isAttachmentNote,
      attachmentLabel,
    });

    skipNewlines();
  }

  const message = content.slice(index).trimStart();
  return { blocks, message };
};

/**
 * Parse content to extract thinking blocks and regular content.
 * Thinking content is wrapped in <think>...</think> tags.
 * Also handles streaming case where </think> hasn't arrived yet.
 */
function parseThinkingContent(content: string, isStreaming: boolean): { thinking: string; mainContent: string; isThinkingInProgress: boolean } {
  // Check for complete thinking blocks first
  const completeThinkRegex = /<think>([\s\S]*?)<\/think>/g;
  let thinking = '';
  let mainContent = content;
  let isThinkingInProgress = false;

  // Extract all complete thinking blocks
  let match;
  while ((match = completeThinkRegex.exec(content)) !== null) {
    thinking += match[1];
  }

  // Remove complete thinking tags from main content
  mainContent = content.replace(completeThinkRegex, '');

  // Handle streaming case: <think> started but </think> not yet received
  if (isStreaming && mainContent.includes('<think>') && !mainContent.includes('</think>')) {
    const thinkStart = mainContent.indexOf('<think>');
    // Everything after <think> is thinking content in progress
    thinking += mainContent.slice(thinkStart + 7); // 7 = length of '<think>'
    mainContent = mainContent.slice(0, thinkStart);
    isThinkingInProgress = true;
  }

  return { thinking: thinking.trim(), mainContent: mainContent.trim(), isThinkingInProgress };
}

/**
 * Format cost value for display.
 * Shows enough precision to be meaningful.
 */
function formatCost(cost: number): string {
  if (cost === 0) return '$0';
  if (cost < 0.000001) return `<$0.000001`;
  if (cost < 0.01) return `$${cost.toFixed(6)}`;
  if (cost < 1) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

/**
 * Format a message timestamp for display as YYYY-MM-DD HH:MM:SS.
 */
function formatMessageTime(timestamp: string | undefined): string | null {
  if (!timestamp) return null;
  // Already in YYYY-MM-DD HH:MM:SS format, return as-is
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(timestamp)) return timestamp;
  return null;
}

const GROUP_ASSISTANT_STYLE_TOKENS = [
  {
    avatar: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-200',
    label: 'text-rose-700 dark:text-rose-300',
    accent: 'border-l-rose-400 dark:border-l-rose-500',
    surface: 'bg-rose-50/70 dark:bg-rose-900/15',
  },
  {
    avatar: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200',
    label: 'text-emerald-700 dark:text-emerald-300',
    accent: 'border-l-emerald-400 dark:border-l-emerald-500',
    surface: 'bg-emerald-50/70 dark:bg-emerald-900/15',
  },
  {
    avatar: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-200',
    label: 'text-sky-700 dark:text-sky-300',
    accent: 'border-l-sky-400 dark:border-l-sky-500',
    surface: 'bg-sky-50/70 dark:bg-sky-900/15',
  },
  {
    avatar: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200',
    label: 'text-amber-700 dark:text-amber-300',
    accent: 'border-l-amber-400 dark:border-l-amber-500',
    surface: 'bg-amber-50/70 dark:bg-amber-900/15',
  },
];

function getAssistantStyle(seed: string | undefined) {
  if (!seed) {
    return {
      avatar: 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-200',
      label: 'text-gray-500 dark:text-gray-400',
      accent: 'border-l-gray-300 dark:border-l-gray-600',
      surface: 'bg-gray-200 dark:bg-gray-700',
    };
  }

  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  const index = Math.abs(hash) % GROUP_ASSISTANT_STYLE_TOKENS.length;
  return GROUP_ASSISTANT_STYLE_TOKENS[index];
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  messageId,
  messageIndex,
  isStreaming,
  sessionId,
  currentTargetType = 'model',
  currentAssistantId,
  currentModelId,
  assistantNameById = {},
  assistantModelIdById = {},
  modelNameById = {},
  onEdit,
  onSaveOnly,
  onRegenerate,
  onDelete,
  onBranch,
  customActions,
  hasSubsequentMessages,
}) => {
  const { api } = useChatServices();
  const { t } = useTranslation('chat');
  const isUser = message.role === 'user';
  const isSeparator = message.role === 'separator';
  const isSummary = message.role === 'summary';
  const isGroupAssistantMessage = !isUser && !!message.assistant_id;
  const assistantDisplayName = message.assistant_name || (message.assistant_id ? `AI-${message.assistant_id.slice(0, 4)}` : '');
  const assistantStyle = useMemo(
    () => getAssistantStyle(message.assistant_id || message.assistant_name),
    [message.assistant_id, message.assistant_name]
  );
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [isCopied, setIsCopied] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [expandedUserBlocks, setExpandedUserBlocks] = useState<Record<string, boolean>>({});
  const [showSummaryContent, setShowSummaryContent] = useState(false);
  const [translatedText, setTranslatedText] = useState('');
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);
  const [showTranslateMenu, setShowTranslateMenu] = useState(false);
  const [selectedTranslateTarget, setSelectedTranslateTarget] = useState('auto');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const translateMenuRef = useRef<HTMLDivElement>(null);
  const { isPlaying: ttsPlaying, isLoading: ttsLoading, speak: ttsSpeak, stop: ttsStop } = useTTS();
  const fileReferencePreviewConfig = useSyncExternalStore(
    subscribeFileReferencePreviewConfig,
    getFileReferencePreviewConfig,
    getFileReferencePreviewConfig
  );

  // Parse thinking content from message
  const { thinking, mainContent, isThinkingInProgress } = useMemo(
    () => parseThinkingContent(message.content, isStreaming),
    [message.content, isStreaming]
  );
  const { blocks: userBlocks, message: userMessage } = useMemo(
    () => parseUserBlocks(message.content),
    [message.content]
  );

  const displayUserMessage = userBlocks.length > 0 ? userMessage : message.content;
  const sources = message.sources || [];
  const { enabled: developerModeEnabled } = useDeveloperMode();
  const ragDiagnostics = developerModeEnabled
    ? sources.filter((source) => source.type === 'rag_diagnostics')
    : [];
  const ragSources = sources.filter((source) => source.type === 'rag');
  const otherSources = sources.filter((source) => source.type !== 'rag' && source.type !== 'rag_diagnostics');
  const latestRagDiagnostics = ragDiagnostics.length > 0 ? ragDiagnostics[ragDiagnostics.length - 1] : null;
  const responderInfoText = useMemo(() => {
    if (message.role !== 'assistant') {
      return null;
    }

    let resolvedAssistantName = (message.assistant_name || '').trim();
    let resolvedModelId: string | undefined;

    const assistantId = message.assistant_id;
    if (assistantId) {
      if (assistantId.startsWith(MODEL_PARTICIPANT_PREFIX)) {
        resolvedModelId = assistantId.slice(MODEL_PARTICIPANT_PREFIX.length);
        if (!resolvedAssistantName) {
          resolvedAssistantName = modelNameById[resolvedModelId] || resolvedModelId;
        }
      } else {
        if (!resolvedAssistantName) {
          resolvedAssistantName = assistantNameById[assistantId] || assistantId;
        }
        resolvedModelId = assistantModelIdById[assistantId];
      }
    }

    if (!resolvedAssistantName) {
      if (currentTargetType === 'assistant' && currentAssistantId) {
        resolvedAssistantName = assistantNameById[currentAssistantId] || currentAssistantId;
      } else if (currentTargetType === 'model') {
        resolvedAssistantName = t('bubble.modelTargetLabel');
      }
    }

    if (!resolvedModelId) {
      if (currentTargetType === 'assistant' && currentAssistantId) {
        resolvedModelId = assistantModelIdById[currentAssistantId] || currentModelId || undefined;
      } else {
        resolvedModelId = currentModelId || undefined;
      }
    }

    const resolvedModelName = resolvedModelId ? (modelNameById[resolvedModelId] || resolvedModelId) : '';
    if (!resolvedAssistantName && !resolvedModelName) {
      return null;
    }

    return t('bubble.responderInfo', {
      assistant: resolvedAssistantName || '-',
      model: resolvedModelName || '-',
    });
  }, [
    assistantModelIdById,
    assistantNameById,
    currentAssistantId,
    currentModelId,
    currentTargetType,
    message.assistant_id,
    message.assistant_name,
    message.role,
    modelNameById,
    t,
  ]);

  const formatRagSnippet = (content?: string) => {
    if (!content) return '';
    const normalized = content.replace(/\s+/g, ' ').trim();
    return normalized.length > 240 ? `${normalized.slice(0, 240)}...` : normalized;
  };

  useEffect(() => {
    setExpandedUserBlocks({});
  }, [message.content]);

  useEffect(() => {
    void ensureFileReferencePreviewConfigLoaded();
  }, []);

  useEffect(() => {
    if (!showTranslateMenu) return;

    const handleOutsideClick = (event: MouseEvent) => {
      if (translateMenuRef.current && !translateMenuRef.current.contains(event.target as Node)) {
        setShowTranslateMenu(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [showTranslateMenu]);

  const canEdit = !isStreaming && !isSeparator && !isSummary && (isUser ? (onEdit || onSaveOnly) : onSaveOnly);
  const canRegenerate = !isStreaming && onRegenerate && message.content.trim() !== '';
  const canDelete = !isStreaming && onDelete;

  // Auto-resize textarea
  const autoResize = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 400) + 'px';
    }
  }, []);

  useEffect(() => {
    if (isEditing) {
      autoResize();
    }
  }, [isEditing, editContent, autoResize]);

  const handleDownloadAttachment = async (filename: string) => {
    if (!sessionId) return;

    try {
      const blob = await api.downloadFile(sessionId, messageIndex, filename);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    }
  };

  const handleSaveEdit = () => {
    if (editContent.trim() && onEdit) {
      onEdit(messageId, editContent.trim());
      setIsEditing(false);
    }
  };

  const handleSaveOnly = () => {
    if (editContent.trim() && onSaveOnly) {
      // For assistant messages, reconstruct full content preserving thinking tags
      let fullContent = editContent.trim();
      if (!isUser && thinking) {
        fullContent = `<think>${thinking}</think>${fullContent}`;
      }
      onSaveOnly(messageId, fullContent);
      setIsEditing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditContent(isUser ? message.content : mainContent);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (isUser && onEdit) {
        handleSaveEdit();
      } else {
        handleSaveOnly();
      }
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  const handleCopy = async () => {
    try {
      // Copy mainContent (without thinking tags) for assistant messages
      const textToCopy = isUser ? message.content : mainContent;
      await navigator.clipboard.writeText(textToCopy);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleTranslate = async (targetLanguage?: string) => {
    if (isTranslating) return;
    setTranslatedText('');
    setIsTranslating(true);
    setShowTranslation(true);
    setShowTranslateMenu(false);
    try {
      await api.translateText(
        mainContent,
        (chunk) => setTranslatedText(prev => prev + chunk),
        () => setIsTranslating(false),
        (error) => {
          console.error('Translation failed:', error);
          setIsTranslating(false);
        },
        targetLanguage,
      );
    } catch (err) {
      console.error('Translation failed:', err);
      setIsTranslating(false);
    }
  };

  const selectedTranslateLabel = useMemo(
    () => TRANSLATION_TARGET_OPTIONS.find((option) => option.value === selectedTranslateTarget)?.label || 'Auto',
    [selectedTranslateTarget]
  );

  const handleDismissTranslation = () => {
    setShowTranslation(false);
    setTranslatedText('');
    setIsTranslating(false);
  };

  const handleDeleteClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDelete) {
      onDelete(messageId);
    }
    setShowDeleteConfirm(false);
  };

  const handleDeleteCancel = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDeleteConfirm(false);
  };

  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      e.preventDefault();
      e.stopPropagation();
      setShowDeleteConfirm(false);
    }
  };

  const handleDeleteSeparator = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (onDelete) {
      onDelete(messageId);
    }
  };

  // Separator rendering (centered display)
  if (isSeparator) {
    return (
      <div data-name="message-bubble-separator" className="flex flex-col items-center mb-4 group">
        <div data-name="message-bubble-separator-content" className="w-full max-w-[80%] relative">
          {/* Separator line */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-amber-400 dark:via-amber-600 to-transparent" />
            <div className="flex items-center gap-2 px-4 py-2 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded-lg text-amber-700 dark:text-amber-300 text-sm font-medium">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              <span>Context Cleared</span>
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-amber-400 dark:via-amber-600 to-transparent" />
          </div>

          {/* Delete button (on hover) */}
          {canDelete && (
            <div className="absolute -right-10 top-1/2 -translate-y-1/2">
              <button
                type="button"
                onClick={handleDeleteSeparator}
                className="p-1.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 border border-gray-300 dark:border-gray-600 opacity-0 group-hover:opacity-100 transition-all"
                title="Delete separator"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Summary rendering (violet-themed collapsible block)
  if (isSummary) {
    const isSummaryStreaming = !message.message_id;
    return (
      <div data-name="message-bubble-summary" className="flex flex-col items-center mb-4 group">
        <div data-name="message-bubble-summary-content" className="w-full max-w-[80%] relative">
          {/* Summary header line */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-violet-400 dark:via-violet-600 to-transparent" />
            <button
              onClick={() => setShowSummaryContent(!showSummaryContent)}
              className="flex items-center gap-2 px-4 py-2 bg-violet-50 dark:bg-violet-900/30 border border-violet-200 dark:border-violet-800 rounded-lg text-violet-700 dark:text-violet-300 text-sm font-medium hover:bg-violet-100 dark:hover:bg-violet-900/50 transition-colors"
            >
              {showSummaryContent ? (
                <ChevronDownIcon className="w-4 h-4" />
              ) : (
                <ChevronRightIcon className="w-4 h-4" />
              )}
              <svg className={`w-4 h-4 ${isSummaryStreaming ? 'animate-pulse' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span>{isSummaryStreaming ? 'Compressing Context...' : 'Context Compressed'}</span>
            </button>
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-violet-400 dark:via-violet-600 to-transparent" />
          </div>

          {/* Collapsible summary content */}
          {showSummaryContent && message.content && (
            <div className="mt-2 px-4 py-3 bg-violet-50/50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-lg text-sm text-gray-700 dark:text-gray-300 max-h-96 overflow-y-auto">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {normalizeMathDelimiters(message.content)}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {/* Delete button (on hover) */}
          {canDelete && (
            <div className="absolute -right-10 top-1/2 -translate-y-1/2">
              <button
                type="button"
                onClick={handleDeleteSeparator}
                className="p-1.5 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 border border-gray-300 dark:border-gray-600 opacity-0 group-hover:opacity-100 transition-all"
                title="Delete summary"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div data-name={`message-bubble-${isUser ? 'user' : 'assistant'}`} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4`}>
      <div data-name="message-bubble-content-wrapper" className={isUser ? 'max-w-[80%]' : 'w-full'}>
        {/* Group chat: assistant identity label */}
        {!isUser && assistantDisplayName && (
          <div data-name="message-bubble-assistant-label" className="flex items-center gap-1.5 mb-1 ml-1">
            <span
              data-name="message-bubble-assistant-avatar"
              className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${assistantStyle.avatar}`}
            >
              {React.createElement(getAssistantIcon(message.assistant_icon), { className: 'w-3 h-3' })}
            </span>
            <span className={`text-xs font-semibold ${isGroupAssistantMessage ? assistantStyle.label : 'text-gray-500 dark:text-gray-400'}`}>
              {assistantDisplayName}
            </span>
          </div>
        )}
        <div
          data-name="message-bubble-content"
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? 'bg-blue-500 text-white'
              : isGroupAssistantMessage
                ? `border border-gray-200 dark:border-gray-600 border-l-4 ${assistantStyle.accent} ${assistantStyle.surface} text-gray-900 dark:text-gray-100`
                : 'bg-gray-200 text-gray-900 dark:bg-gray-700 dark:text-gray-100'
          }`}
        >
          {isEditing ? (
            <div className="space-y-2">
              <textarea
                ref={textareaRef}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleKeyDown}
                className={`w-full min-h-[60px] px-3 py-2 text-sm rounded-md focus:outline-none focus:ring-2 resize-none ${
                  isUser
                    ? 'bg-blue-400/20 text-white placeholder-blue-200 border border-blue-300/40 focus:ring-blue-300'
                    : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-300 dark:border-gray-500 focus:ring-blue-500'
                }`}
                autoFocus
              />
              {isUser && hasSubsequentMessages && onEdit && (
                <p className={`text-[11px] ${isUser ? 'text-blue-200/80' : 'text-gray-500 dark:text-gray-400'}`}>
                  "Save & Regenerate" will remove all subsequent messages.
                </p>
              )}
              <div className="flex items-center gap-2 justify-end">
                <span className={`text-[11px] mr-auto ${isUser ? 'text-blue-200/60' : 'text-gray-400 dark:text-gray-500'}`}>
                  Ctrl+Enter save, Esc cancel
                </span>
                <button
                  onClick={handleCancelEdit}
                  className={`px-3 py-1 text-xs rounded transition-colors ${
                    isUser
                      ? 'bg-blue-400/30 text-blue-100 hover:bg-blue-400/50'
                      : 'bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-400 dark:hover:bg-gray-500'
                  }`}
                >
                  Cancel
                </button>
                {onSaveOnly && (
                  <button
                    onClick={handleSaveOnly}
                    disabled={!editContent.trim() || editContent.trim() === (isUser ? message.content.trim() : mainContent.trim())}
                    className={`px-3 py-1 text-xs rounded disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                      isUser
                        ? 'bg-blue-400/30 text-blue-100 hover:bg-blue-400/50'
                        : 'bg-blue-500 text-white font-medium hover:bg-blue-600'
                    }`}
                  >
                    Save
                  </button>
                )}
                {isUser && onEdit && (
                  <button
                    onClick={handleSaveEdit}
                    disabled={!editContent.trim()}
                    className="px-3 py-1 text-xs bg-white/90 text-blue-600 font-medium rounded hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Save & Regenerate
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm">
              {/* Attachments display (for user messages) */}
              {isUser && message.attachments && message.attachments.length > 0 && (
                <div className="mb-3 space-y-2">
                  {message.attachments.map((att, idx) => {
                    const isImage = att.mime_type.startsWith('image/');

                    return isImage ? (
                      // Image attachment: show thumbnail
                      <div key={idx} className="max-w-xs">
                        <img
                          src={`/api/chat/attachment/${sessionId}/${messageIndex}/${encodeURIComponent(att.filename)}`}
                          alt={att.filename}
                          className="w-full rounded border border-blue-400 dark:border-blue-600 cursor-pointer hover:opacity-90"
                          onClick={() => handleDownloadAttachment(att.filename)}
                          title="Click to download"
                          loading="lazy"
                        />
                        <div className="flex items-center gap-1 mt-1 text-xs opacity-80">
                          <PhotoIcon className="h-3 w-3" />
                          <span className="truncate">{att.filename}</span>
                          <span>({(att.size / 1024).toFixed(1)} KB)</span>
                        </div>
                      </div>
                    ) : (
                      // Text file: show file name with icon
                      <div
                        key={idx}
                        className="flex items-center gap-2 px-3 py-2 bg-blue-600 dark:bg-blue-400/20 rounded border border-blue-400 dark:border-blue-600"
                      >
                        <DocumentTextIcon className="h-4 w-4 flex-shrink-0" />
                        <span className="flex-1 text-sm truncate">{att.filename}</span>
                        <span className="text-xs opacity-80">
                          ({(att.size / 1024).toFixed(1)} KB)
                        </span>
                        <button
                          onClick={() => handleDownloadAttachment(att.filename)}
                          className="flex-shrink-0 hover:opacity-80"
                          title="Download"
                        >
                          <ArrowDownTrayIcon className="h-4 w-4" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
              {isUser ? (
                <>
                  {userBlocks.length > 0 && (
                    <div data-name="user-message-blocks" className="mb-3 rounded-md border border-blue-300/40 bg-blue-600/30 overflow-hidden">
                      <div className="flex items-center justify-between px-2.5 py-1 text-[11px] uppercase tracking-wide text-blue-100/80">
                        <span>Blocks</span>
                        <span>{userBlocks.length}</span>
                      </div>
                      <div className="divide-y divide-blue-400/30">
                        {userBlocks.map((block) => {
                          const isExpanded = !!expandedUserBlocks[block.id];
                          const isFileReferenceBlock = block.title.toLowerCase().startsWith('file reference:');
                          const filePreview = isFileReferenceBlock
                            ? buildFileReferencePreview(block.content, fileReferencePreviewConfig)
                            : null;
                          const previewHiddenParts: string[] = [];
                          if (filePreview?.hiddenLines) {
                            previewHiddenParts.push(`${filePreview.hiddenLines} lines`);
                          }
                          if (filePreview?.hiddenChars) {
                            previewHiddenParts.push(`${filePreview.hiddenChars} chars`);
                          }
                          const previewHiddenLabel = previewHiddenParts.join(', ');
                          const blockDisplayContent = filePreview?.truncated
                            ? `${filePreview.text}\n...\n[Preview only: ${previewHiddenLabel} hidden]`
                            : block.content;
                          const metaLabel = block.isAttachmentNote
                            ? 'Attachment'
                            : filePreview?.truncated
                              ? `preview ${filePreview.shownLines}/${filePreview.totalLines} lines, ${filePreview.shownChars}/${filePreview.totalChars} chars`
                              : `${block.content.length} chars`;
                          return (
                            <div key={block.id}>
                              <button
                                type="button"
                                onClick={() => setExpandedUserBlocks((prev) => ({
                                  ...prev,
                                  [block.id]: !prev[block.id],
                                }))}
                                className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-xs text-blue-50 hover:bg-blue-600/40 transition-colors"
                                title={isExpanded ? 'Collapse block' : 'Expand block'}
                              >
                                {isExpanded ? (
                                  <ChevronDownIcon className="w-4 h-4 text-blue-100" />
                                ) : (
                                  <ChevronRightIcon className="w-4 h-4 text-blue-100" />
                                )}
                                <span className="text-[10px] uppercase tracking-wide text-blue-100/70">
                                  {block.kind}
                                </span>
                                <span className="flex-1 truncate text-blue-50">{block.title || 'Block'}</span>
                                <span className="text-[11px] text-blue-100/70">{metaLabel}</span>
                              </button>
                              {isExpanded && (
                                <div className="px-2.5 py-2 bg-blue-600/20 text-blue-50">
                                  {block.isAttachmentNote ? (
                                    <div className="text-xs text-blue-100/80">
                                      {block.attachmentLabel || 'Attachment'}
                                    </div>
                                  ) : block.isCodeFence ? (
                                    <CodeBlock language={block.language} value={blockDisplayContent} />
                                  ) : (
                                    <div className="prose prose-sm max-w-none prose-invert">
                                      <ReactMarkdown
                                        remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}
                                        components={{
                                          code({ className, children, ...props }: any) {
                                            const match = /language-(\w+)/.exec(className || '');
                                            const language = match ? match[1] : '';
                                            const value = String(children).replace(/\n$/, '');
                                            const isInline = !className;

                                            return !isInline && language ? (
                                              language === 'mermaid'
                                                ? <MermaidBlock value={value} />
                                                : <CodeBlock language={language} value={value} />
                                            ) : (
                                              <code className={className} {...props}>
                                                {children}
                                              </code>
                                            );
                                          },
                                        }}
                                      >
                                        {normalizeMathDelimiters(blockDisplayContent || '_Empty block_')}
                                      </ReactMarkdown>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {userBlocks.length > 0 && displayUserMessage && (
                    <div className="mb-2">
                      <div className="h-px bg-blue-300/40" />
                    </div>
                  )}
                  <p className="whitespace-pre-wrap m-0">{displayUserMessage}</p>
                </>
              ) : message.compareResponses && message.compareResponses.length > 0 ? (
                <CompareResponseView
                  responses={message.compareResponses}
                  isStreaming={isStreaming && !message.message_id}
                />
              ) : (
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  {latestRagDiagnostics && (
                    <div data-name="message-bubble-rag-diagnostics" className="not-prose mb-3 rounded-md border border-amber-200 dark:border-amber-700 bg-amber-50/70 dark:bg-amber-900/30">
                      <div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-amber-800 dark:text-amber-200">
                        <span>RAG Diagnostics</span>
                        <span>
                          {(latestRagDiagnostics.retrieval_mode || 'vector')}
                          {' / '}
                          {(latestRagDiagnostics.reorder_strategy || 'long_context')}
                        </span>
                      </div>
                      <div className="px-3 pb-2 text-[11px] text-amber-800/90 dark:text-amber-200/90 space-y-1">
                        <div>
                          raw {latestRagDiagnostics.raw_count ?? 0}{' -> '}dedup {latestRagDiagnostics.deduped_count ?? 0}{' -> '}diversified {latestRagDiagnostics.diversified_count ?? 0}{' -> '}selected {latestRagDiagnostics.selected_count ?? 0}
                        </div>
                        <div>
                          top_k {latestRagDiagnostics.top_k ?? '-'}
                          {' | '}recall_k {latestRagDiagnostics.recall_k ?? '-'}
                          {' | '}max_per_doc {latestRagDiagnostics.max_per_doc ?? '-'}
                          {' | '}threshold {latestRagDiagnostics.score_threshold != null ? latestRagDiagnostics.score_threshold.toFixed(2) : '-'}
                          {' | '}kb {(latestRagDiagnostics.searched_kb_count ?? 0)}/{(latestRagDiagnostics.requested_kb_count ?? latestRagDiagnostics.searched_kb_count ?? 0)}
                          {' | '}best {latestRagDiagnostics.best_score != null ? latestRagDiagnostics.best_score.toFixed(3) : '-'}
                        </div>
                        <div>
                          vector_raw {latestRagDiagnostics.vector_raw_count ?? '-'}
                          {' | '}bm25_raw {latestRagDiagnostics.bm25_raw_count ?? '-'}
                          {' | '}bm25_cov {latestRagDiagnostics.bm25_min_term_coverage != null ? latestRagDiagnostics.bm25_min_term_coverage.toFixed(2) : '-'}
                        </div>
                        <div>
                          tool_search {latestRagDiagnostics.tool_search_count ?? 0}
                          {' | '}tool_unique {latestRagDiagnostics.tool_search_unique_count ?? 0}
                          {' | '}tool_dup {latestRagDiagnostics.tool_search_duplicate_count ?? 0}
                          {' | '}tool_read {latestRagDiagnostics.tool_read_count ?? 0}
                          {' | '}tool_finalize {latestRagDiagnostics.tool_finalize_reason || '-'}
                        </div>
                      </div>
                    </div>
                  )}
                  {ragSources.length > 0 && (
                    <div data-name="message-bubble-rag-sources" className="not-prose mb-3 rounded-md border border-emerald-200 dark:border-emerald-700 bg-emerald-50/60 dark:bg-emerald-900/30">
                      <div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-emerald-800 dark:text-emerald-200">
                        <span>Knowledge Base</span>
                        <span>{ragSources.length}</span>
                      </div>
                      <div className="px-3 pb-2 space-y-2">
                        {ragSources.map((source, index) => (
                          <div key={`rag-${source.kb_id || 'kb'}-${source.doc_id || index}`} className="text-xs">
                            <div className="font-medium text-emerald-900 dark:text-emerald-100">
                              {source.filename || source.title || `Chunk ${source.chunk_index ?? index + 1}`}
                            </div>
                            <div className="text-[11px] text-emerald-700/90 dark:text-emerald-300/90">
                              {source.kb_id && `KB: ${source.kb_id}`}
                              {source.chunk_index != null && ` • Chunk ${source.chunk_index}`}
                              {source.score != null && ` • Score ${source.score.toFixed(3)}`}
                            </div>
                            {source.content && (
                              <div className="text-[11px] text-emerald-800/90 dark:text-emerald-200/90 mt-1">
                                {formatRagSnippet(source.content)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {otherSources.length > 0 && (
                    <div data-name="message-bubble-sources" className="not-prose mb-3 rounded-md border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40">
                      <div className="flex items-center justify-between px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300">
                        <span>Sources</span>
                        <span>{otherSources.length}</span>
                      </div>
                      <div className="px-3 pb-2 space-y-2">
                        {otherSources.map((source, index) => {
                          const isMemorySource = source.type === 'memory';
                          const memoryScope = source.scope || 'global';
                          const memoryLayer = source.layer || 'preference';

                          return (
                            <div key={`${source.id || source.url || source.title || 'source'}-${index}`} className="text-xs">
                              {isMemorySource ? (
                                <>
                                  <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                                    <span className="rounded border border-violet-200 dark:border-violet-700 bg-violet-50 dark:bg-violet-900/30 px-1.5 py-0.5 text-[11px] font-medium text-violet-700 dark:text-violet-300">
                                      Memory
                                    </span>
                                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                      {memoryScope}/{memoryLayer}
                                    </span>
                                    {source.score != null && (
                                      <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                        Score {source.score.toFixed(3)}
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1 whitespace-pre-wrap break-all">
                                    {source.content || source.snippet || source.title || 'Memory entry'}
                                  </div>
                                </>
                              ) : source.url ? (
                                <>
                                  <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-blue-600 dark:text-blue-400 hover:underline break-all"
                                  >
                                    {source.title || source.url}
                                  </a>
                                  <div className="text-[11px] text-slate-500 dark:text-slate-400 break-all">
                                    {source.url}
                                  </div>
                                </>
                              ) : (
                                <div className="text-slate-700 dark:text-slate-300 break-all">
                                  {source.title || 'Source'}
                                </div>
                              )}
                              {!isMemorySource && source.snippet && (
                                <div className="text-[11px] text-slate-600 dark:text-slate-400 mt-1">
                                  {source.snippet}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {/* Thinking block (collapsible, auto-expand during streaming) */}
                  {thinking && (
                    <ThinkingBlock
                      thinking={thinking}
                      isThinkingInProgress={isThinkingInProgress}
                      thinkingDurationMs={message.thinkingDurationMs}
                    />
                  )}
                  {/* Tool call block */}
                  {message.toolCalls && message.toolCalls.length > 0 && (
                    <ToolCallBlock toolCalls={message.toolCalls} />
                  )}
                  {/* Main content */}
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}
                    components={{
                      code({ className, children, ...props }: any) {
                        const match = /language-(\w+)/.exec(className || '');
                        const language = match ? match[1] : '';
                        const value = String(children).replace(/\n$/, '');
                        const isInline = !className;

                        return !isInline && language ? (
                          language === 'mermaid'
                            ? <MermaidBlock value={value} />
                            : <CodeBlock language={language} value={value} />
                        ) : (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        );
                      },
                      table({ children }) {
                        return (
                          <div className="overflow-x-auto my-4">
                            <table className="min-w-full divide-y divide-gray-300 dark:divide-gray-600">
                              {children}
                            </table>
                          </div>
                        );
                      },
                      thead({ children }) {
                        return (
                          <thead className="bg-gray-100 dark:bg-gray-800">
                            {children}
                          </thead>
                        );
                      },
                      tbody({ children }) {
                        return (
                          <tbody className="bg-white dark:bg-gray-700 divide-y divide-gray-200 dark:divide-gray-600">
                            {children}
                          </tbody>
                        );
                      },
                      th({ children }) {
                        return (
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-300 uppercase tracking-wider">
                            {children}
                          </th>
                        );
                      },
                      td({ children }) {
                        return (
                          <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                            {children}
                          </td>
                        );
                      },
                    }}
                  >
                    {normalizeMathDelimiters(mainContent || '*Generating...*')}
                  </ReactMarkdown>
                  {/* Translation block */}
                  {showTranslation && (
                    <TranslationBlock
                      translatedText={translatedText}
                      isTranslating={isTranslating}
                      onDismiss={handleDismissTranslation}
                    />
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Message timestamp and usage info */}
        {!isEditing && (
          <div className={`flex items-center gap-2 mt-1 px-1 text-xs text-gray-400 dark:text-gray-500 ${isUser ? 'justify-end' : ''}`}>
            {message.created_at && (
              <span>{formatMessageTime(message.created_at)}</span>
            )}
            {!isUser && responderInfoText && (
              <>
                {message.created_at && <span className="text-gray-300 dark:text-gray-600">|</span>}
                <span>{responderInfoText}</span>
              </>
            )}
            {!isUser && message.usage && !isStreaming && (
              <>
                {(message.created_at || responderInfoText) && <span className="text-gray-300 dark:text-gray-600">|</span>}
                <span>{message.usage.prompt_tokens} in</span>
                <span className="text-gray-300 dark:text-gray-600">|</span>
                <span>{message.usage.completion_tokens} out</span>
                {message.cost && message.cost.total_cost > 0 && (
                  <>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>{formatCost(message.cost.total_cost)}</span>
                  </>
                )}
              </>
            )}
          </div>
        )}

        {/* Action buttons */}
        {!isEditing && (
          <div data-name="message-bubble-actions" className="flex gap-1 mt-1">
            <button
              onClick={handleCopy}
              className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
              title={isCopied ? 'Copied' : 'Copy'}
            >
              {isCopied ? (
                <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
              ) : (
                <ClipboardDocumentIcon className="w-4 h-4" />
              )}
              <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                {isCopied ? 'Copied' : 'Copy'}
              </span>
            </button>

            {/* Translate button (assistant messages only) */}
            {!isUser && !isStreaming && mainContent.trim() && (
              <div data-name="message-bubble-translate-control" ref={translateMenuRef} className="relative">
                <div
                  className={`group relative flex rounded border overflow-hidden transition-colors ${
                    isTranslating
                      ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/30 hover:text-teal-700 dark:hover:text-teal-300 hover:border-teal-200 dark:hover:border-teal-800'
                  }`}
                >
                  <button
                    onClick={() => handleTranslate(selectedTranslateTarget === 'auto' ? undefined : selectedTranslateTarget)}
                    disabled={isTranslating}
                    className="px-1.5 py-1 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                    title={`Translate (${selectedTranslateLabel})`}
                  >
                    <LanguageIcon className={`w-4 h-4 ${isTranslating ? 'animate-pulse' : ''}`} />
                    <span className="text-[10px] font-medium leading-none">{selectedTranslateLabel}</span>
                  </button>
                  <button
                    onClick={() => setShowTranslateMenu((prev) => !prev)}
                    disabled={isTranslating}
                    className="px-1 py-1 border-l border-gray-300/80 dark:border-gray-600/80 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Select translation target"
                  >
                    <ChevronDownIcon className={`w-3 h-3 transition-transform ${showTranslateMenu ? 'rotate-180' : ''}`} />
                  </button>
                  <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    {`Translate (${selectedTranslateLabel})`}
                  </span>
                </div>

                {showTranslateMenu && (
                  <div className="absolute z-20 mt-1 min-w-[132px] rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg py-1">
                    {TRANSLATION_TARGET_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => {
                          setSelectedTranslateTarget(option.value);
                          setShowTranslateMenu(false);
                        }}
                        className={`w-full px-3 py-1.5 text-left text-xs transition-colors ${
                          selectedTranslateTarget === option.value
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
            )}

            {/* TTS button (assistant messages only) */}
            {!isUser && !isStreaming && mainContent.trim() && (
              <button
                onClick={() => ttsPlaying ? ttsStop() : ttsSpeak(mainContent)}
                disabled={ttsLoading}
                className={`group relative p-1 rounded border transition-colors ${
                  ttsPlaying
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-700 dark:hover:text-blue-300 hover:border-blue-200 dark:hover:border-blue-800'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
                title={ttsLoading ? 'Loading...' : ttsPlaying ? 'Stop' : 'Listen'}
              >
                {ttsLoading ? (
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                ) : ttsPlaying ? (
                  <StopCircleIcon className="w-4 h-4" />
                ) : (
                  <SpeakerWaveIcon className="w-4 h-4" />
                )}
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  {ttsLoading ? 'Loading...' : ttsPlaying ? 'Stop' : 'Listen'}
                </span>
              </button>
            )}

            {canEdit && (
              <button
                onClick={() => {
                  // For assistant messages, edit mainContent only (exclude thinking tags)
                  setEditContent(isUser ? message.content : mainContent);
                  setIsEditing(true);
                }}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Edit message"
              >
                <PencilSquareIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Edit
                </span>
              </button>
            )}

            {canRegenerate && (
              <button
                onClick={() => onRegenerate?.(messageId)}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Regenerate"
              >
                <ArrowPathIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Regenerate
                </span>
              </button>
            )}

            {/* Branch action */}
            {!isStreaming && onBranch && (
              <button
                onClick={() => onBranch(messageId)}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-700 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Branch"
              >
                <ArrowUturnRightIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Branch
                </span>
              </button>
            )}

            {/* Custom actions slot */}
            {customActions?.(message, messageId)}

            {canDelete && (
              <button
                type="button"
                onClick={handleDeleteClick}
                className="group relative p-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400 border border-gray-300 dark:border-gray-600 transition-colors"
                title="Delete"
              >
                <TrashIcon className="w-4 h-4" />
                <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  Delete
                </span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div
          data-name="message-bubble-delete-confirm-backdrop"
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={handleBackdropClick}
        >
          <div data-name="message-bubble-delete-confirm-modal" className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-sm mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
              Delete Message
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Are you sure you want to delete this message? This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={handleDeleteCancel}
                className="px-4 py-2 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="px-4 py-2 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
