/**
 * MessageBubble component - displays a single message.
 */

import React, { useState, useMemo, useEffect, useRef, useCallback, useSyncExternalStore } from 'react';
import type { ChatTargetType, Message } from '../../../types/message';
import { MessageBubbleAssistantContent } from './MessageBubbleAssistantContent';
import { MessageBubbleUserContent } from './MessageBubbleUserContent';
import { SeparatorBubble, SummaryBubble } from './MessageBubbleSpecialStates';
import { CompareResponseView } from './CompareResponseView';
import { useChatServices } from '../services/ChatServiceProvider';
import { useTTS } from '../hooks/useTTS';
import { normalizeMathDelimiters } from '../utils/markdownMath';
import { extractSvgBlocks } from '../utils/svgMarkdown';
import { useDeveloperMode } from '../../../hooks/useDeveloperMode';
import { getAssistantIcon } from '../../constants/assistantIcons';
import { useTranslation } from 'react-i18next';
import {
  buildFileReferencePreview,
  ensureFileReferencePreviewConfigLoaded,
  getFileReferencePreviewConfig,
  subscribeFileReferencePreviewConfig,
} from '../config/fileReferencePreview';
import { MessageBubbleActions, MessageDeleteConfirmModal } from './MessageBubbleControls';

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
const prepareMarkdownForRender = (text: string) => normalizeMathDelimiters(extractSvgBlocks(text));

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
      <SeparatorBubble
        canDelete={Boolean(canDelete)}
        onDelete={handleDeleteSeparator}
      />
    );
  }

  // Summary rendering (violet-themed collapsible block)
  if (isSummary) {
    const isSummaryStreaming = !message.message_id;
    return (
      <SummaryBubble
        canDelete={Boolean(canDelete)}
        content={message.content}
        isExpanded={showSummaryContent}
        isStreaming={isSummaryStreaming}
        onDelete={handleDeleteSeparator}
        onToggleExpanded={() => setShowSummaryContent(!showSummaryContent)}
        prepareMarkdownForRender={prepareMarkdownForRender}
      />
    );
  }

  return (
    <div
      data-name={`message-bubble-${isUser ? 'user' : 'assistant'}`}
      className={`mb-4 flex min-w-0 flex-col ${isUser ? 'items-end' : 'items-start'}`}
    >
      <div
        data-name="message-bubble-content-wrapper"
        className={isUser ? 'max-w-[80%] min-w-0' : 'w-full min-w-0'}
      >
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
          className={`min-w-0 max-w-full rounded-lg px-4 py-3 ${
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
              {isUser ? (
                <MessageBubbleUserContent
                  buildFileReferencePreview={buildFileReferencePreview}
                  displayUserMessage={displayUserMessage}
                  expandedUserBlocks={expandedUserBlocks}
                  fileReferencePreviewConfig={fileReferencePreviewConfig}
                  handleDownloadAttachment={handleDownloadAttachment}
                  message={message}
                  messageIndex={messageIndex}
                  onToggleUserBlock={(blockId) => setExpandedUserBlocks((prev) => ({
                    ...prev,
                    [blockId]: !prev[blockId],
                  }))}
                  prepareMarkdownForRender={prepareMarkdownForRender}
                  sessionId={sessionId}
                  userBlocks={userBlocks}
                />
              ) : message.compareResponses && message.compareResponses.length > 0 ? (
                <CompareResponseView
                  responses={message.compareResponses}
                  isStreaming={isStreaming && !message.message_id}
                />
              ) : (
                <MessageBubbleAssistantContent
                  formatRagSnippet={formatRagSnippet}
                  isStreaming={isStreaming}
                  isThinkingInProgress={isThinkingInProgress}
                  isTranslating={isTranslating}
                  latestRagDiagnostics={latestRagDiagnostics}
                  mainContent={mainContent}
                  message={message}
                  onDismissTranslation={handleDismissTranslation}
                  otherSources={otherSources}
                  prepareMarkdownForRender={prepareMarkdownForRender}
                  ragSources={ragSources}
                  sessionId={sessionId}
                  showTranslation={showTranslation}
                  thinking={thinking}
                  translatedText={translatedText}
                />
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
          <MessageBubbleActions
            canDelete={Boolean(canDelete)}
            canEdit={Boolean(canEdit)}
            canRegenerate={Boolean(canRegenerate)}
            copiedLabel="Copied"
            copyLabel="Copy"
            customActions={customActions?.(message, messageId)}
            deleteLabel="Delete"
            editLabel="Edit"
            isCopied={isCopied}
            isStreaming={isStreaming}
            isTranslating={isTranslating}
            isUser={isUser}
            listenLabel="Listen"
            loadingLabel="Loading..."
            mainContent={mainContent}
            onBranch={onBranch ? () => onBranch(messageId) : undefined}
            onCopy={handleCopy}
            onDelete={() => setShowDeleteConfirm(true)}
            onEdit={() => {
              setEditContent(isUser ? message.content : mainContent);
              setIsEditing(true);
            }}
            onRegenerate={() => onRegenerate?.(messageId)}
            onSelectTranslateTarget={(target) => {
              setSelectedTranslateTarget(target);
              setShowTranslateMenu(false);
            }}
            onToggleTranslateMenu={() => setShowTranslateMenu((prev) => !prev)}
            onTranslate={() => handleTranslate(selectedTranslateTarget === 'auto' ? undefined : selectedTranslateTarget)}
            onTtsToggle={() => ttsPlaying ? ttsStop() : ttsSpeak(mainContent)}
            selectedTranslateLabel={selectedTranslateLabel}
            selectedTranslateTarget={selectedTranslateTarget}
            showTranslateMenu={showTranslateMenu}
            stopLabel="Stop"
            translateLabel="Translate"
            translateMenuRef={translateMenuRef}
            translateOptions={TRANSLATION_TARGET_OPTIONS}
            ttsLoading={ttsLoading}
            ttsPlaying={ttsPlaying}
          />
        )}
      </div>

      <MessageDeleteConfirmModal
        isOpen={showDeleteConfirm}
        onBackdropClick={handleBackdropClick}
        onCancel={handleDeleteCancel}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
};
