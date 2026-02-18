/**
 * ChatView - Main chat view with messages and input
 *
 * Version 2.0: Uses currentSessionId from service
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { MessageList } from './MessageList';
import { InputBox } from './InputBox';
import { AssistantSelector } from './AssistantSelector';
import { FollowupChips } from './FollowupChips';
import { ContextUsageBar } from './ContextUsageBar';
import { useChat } from '../hooks/useChat';
import { useModelCapabilities } from '../hooks/useModelCapabilities';
import { useChatServices } from '../services/ChatServiceProvider';
import type { UploadedFile } from '../../../types/message';
import type { Message } from '../../../types/message';
import { Bars3Icon, LightBulbIcon, UsersIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';

type GroupAssistantStatus = 'waiting' | 'thinking' | 'done';

export interface ChatViewProps {
  /**
   * Whether to show the header with session title
   * Default: true (shown in chat module)
   * Set to false in project module where SessionSelector is used
   */
  showHeader?: boolean;
  /**
   * Custom action buttons to render for each message
   */
  customMessageActions?: (message: Message, messageId: string) => React.ReactNode;
}

export const ChatView: React.FC<ChatViewProps> = ({ showHeader = true, customMessageActions }) => {
  const { api, navigation, currentSessionId, currentSession, refreshSessions, context, saveTemporarySession } = useChatServices();
  const { t } = useTranslation('chat');

  // Use onAssistantRefresh from service context if available
  const { onAssistantRefresh } = context || {};

  const wasStreamingRef = useRef(false);
  const [isGeneratingFollowups, setIsGeneratingFollowups] = useState(false);
  const [groupAssistantNameMap, setGroupAssistantNameMap] = useState<Record<string, string>>({});
  const [isSavingGroupOrder, setIsSavingGroupOrder] = useState(false);
  const [draggingAssistantId, setDraggingAssistantId] = useState<string | null>(null);
  const [dragOverAssistantId, setDragOverAssistantId] = useState<string | null>(null);
  const {
    messages,
    loading,
    error,
    isStreaming,
    isCompressing,
    isComparing,
    currentAssistantId,
    followupQuestions,
    contextInfo,
    lastPromptTokens,
    isTemporary,
    setIsTemporary,
    sendMessage,
    sendCompareMessage,
    editMessage,
    saveMessageOnly,
    regenerateMessage,
    deleteMessage,
    insertSeparator,
    clearAllMessages,
    compressContext,
    stopGeneration,
    updateAssistantId,
    paramOverrides,
    hasActiveOverrides,
    updateParamOverrides,
    generateFollowups,
    groupAssistants,
    updateGroupAssistantOrder,
  } = useChat(currentSessionId);

  // Check model capabilities (vision, reasoning)
  const { supportsVision, supportsReasoning } = useModelCapabilities(currentAssistantId);
  const isGenerating = isStreaming || isComparing;

  // Auto-refresh title after streaming completes
  useEffect(() => {
    // Detect when streaming transitions from true to false
    if (wasStreamingRef.current && !isStreaming) {
      // Streaming just completed, schedule a refresh
      const timer = setTimeout(() => {
        if (onAssistantRefresh) {
          onAssistantRefresh();
        } else {
          refreshSessions();
        }
      }, 1000);

      return () => clearTimeout(timer);
    }

    // Update ref for next comparison
    wasStreamingRef.current = isStreaming;
  }, [isStreaming, onAssistantRefresh, refreshSessions]);

  // Auto-cleanup temporary session when navigating away
  // Use refs so the cleanup function always reads the latest values,
  // avoiding stale-closure deletion after "Save" flips isTemporary to false.
  const isTemporaryRef = useRef(isTemporary);
  const currentSessionIdRef = useRef(currentSessionId);
  useEffect(() => { isTemporaryRef.current = isTemporary; }, [isTemporary]);
  useEffect(() => { currentSessionIdRef.current = currentSessionId; }, [currentSessionId]);

  useEffect(() => {
    const prevSessionId = currentSessionId;
    return () => {
      // Only delete if the session is still temporary at cleanup time
      if (isTemporaryRef.current && prevSessionId) {
        api.deleteSession(prevSessionId).catch(() => {});
      }
    };
  }, [currentSessionId, api]);

  const handleSaveTemporary = async () => {
    if (!currentSessionId) return;
    try {
      await saveTemporarySession(currentSessionId);
      setIsTemporary(false);
    } catch (err) {
      console.error('Failed to save session:', err);
    }
  };

  const handleAssistantChange = async (assistantId: string) => {
    updateAssistantId(assistantId);
    if (onAssistantRefresh) {
      onAssistantRefresh();
    } else {
      await refreshSessions();
    }
  };

  const handleSendMessage = (message: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean; fileReferences?: Array<{ path: string; project_id: string }> }) => {
    sendMessage(message, options);
  };

  const handleCompare = (message: string, modelIds: string[], options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean; fileReferences?: Array<{ path: string; project_id: string }> }) => {
    sendCompareMessage(message, modelIds, options);
  };

  const handleInsertSeparator = () => {
    insertSeparator();
  };

  const handleClearAllMessages = () => {
    clearAllMessages();
  };

  const handleCompressContext = () => {
    compressContext();
  };

  const handleGenerateFollowups = async () => {
    setIsGeneratingFollowups(true);
    try {
      await generateFollowups();
    } finally {
      setIsGeneratingFollowups(false);
    }
  };

  const handleBranchMessage = async (messageId: string) => {
    if (!currentSessionId) return;
    try {
      const newSessionId = await api.branchSession(currentSessionId, messageId);
      await refreshSessions();
      if (navigation) {
        navigation.navigateToSession(newSessionId);
      }
    } catch (err: any) {
      console.error('Branch failed:', err);
    }
  };

  const isGroupChat = groupAssistants && groupAssistants.length >= 2;
  const canReorderGroupAssistants = !!isGroupChat && !isGenerating && !isSavingGroupOrder;
  const groupAssistantProgress = useMemo(() => {
    if (!isGroupChat || !groupAssistants) return [];

    const assistantNameFallbackMap = new Map<string, string>();
    for (const message of messages) {
      if (message.role === 'assistant' && message.assistant_id && message.assistant_name && !assistantNameFallbackMap.has(message.assistant_id)) {
        assistantNameFallbackMap.set(message.assistant_id, message.assistant_name);
      }
    }

    const activeAssistantId = isGenerating
      ? [...messages]
          .reverse()
          .find((message) => message.role === 'assistant' && message.assistant_id && !message.message_id)
          ?.assistant_id ?? null
      : null;

    const doneAssistantIds = new Set(
      messages
        .filter((message) => message.role === 'assistant' && message.assistant_id && (message.message_id || message.content.trim().length > 0))
        .map((message) => message.assistant_id as string)
    );

    return groupAssistants.map((assistantId, index) => {
      let status: GroupAssistantStatus = 'waiting';
      if (assistantId === activeAssistantId) {
        status = 'thinking';
      } else if (doneAssistantIds.has(assistantId)) {
        status = 'done';
      }

      return {
        assistantId,
        order: index + 1,
        status,
        name:
          groupAssistantNameMap[assistantId] ||
          assistantNameFallbackMap.get(assistantId) ||
          `AI-${assistantId.slice(0, 4)}`,
      };
    });
  }, [groupAssistants, groupAssistantNameMap, isGenerating, isGroupChat, messages]);

  const activeGroupAssistant = groupAssistantProgress.find((assistant) => assistant.status === 'thinking');
  const completedAssistantCount = groupAssistantProgress.filter((assistant) => assistant.status === 'done').length;

  const clearGroupDragState = () => {
    setDraggingAssistantId(null);
    setDragOverAssistantId(null);
  };

  const handleAssistantChipDragStart = (event: React.DragEvent<HTMLDivElement>, assistantId: string) => {
    if (!canReorderGroupAssistants) return;
    setDraggingAssistantId(assistantId);
    setDragOverAssistantId(assistantId);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', assistantId);
  };

  const handleAssistantChipDragOver = (event: React.DragEvent<HTMLDivElement>, assistantId: string) => {
    if (!canReorderGroupAssistants) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    if (dragOverAssistantId !== assistantId) {
      setDragOverAssistantId(assistantId);
    }
  };

  const handleAssistantChipDrop = async (event: React.DragEvent<HTMLDivElement>, targetAssistantId: string) => {
    event.preventDefault();
    if (!canReorderGroupAssistants || !groupAssistants) return;

    const sourceAssistantId = draggingAssistantId || event.dataTransfer.getData('text/plain');
    clearGroupDragState();
    if (!sourceAssistantId || sourceAssistantId === targetAssistantId) return;

    const sourceIndex = groupAssistants.indexOf(sourceAssistantId);
    const targetIndex = groupAssistants.indexOf(targetAssistantId);
    if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return;

    const nextOrder = [...groupAssistants];
    const [movedAssistant] = nextOrder.splice(sourceIndex, 1);
    nextOrder.splice(targetIndex, 0, movedAssistant);

    try {
      setIsSavingGroupOrder(true);
      await updateGroupAssistantOrder(nextOrder);
    } catch (err) {
      console.error('Failed to reorder group assistants:', err);
    } finally {
      setIsSavingGroupOrder(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    if (!isGroupChat || !groupAssistants) {
      setGroupAssistantNameMap({});
      return;
    }

    api.listAssistants()
      .then((assistants) => {
        if (cancelled) return;
        const nameMap: Record<string, string> = {};
        assistants.forEach((assistant) => {
          nameMap[assistant.id] = assistant.name;
        });
        setGroupAssistantNameMap(nameMap);
      })
      .catch(() => {
        if (!cancelled) {
          setGroupAssistantNameMap({});
        }
      });

    return () => {
      cancelled = true;
    };
  }, [api, groupAssistants, isGroupChat]);

  if (!currentSessionId) {
    return (
      <div data-name="chat-view-welcome" className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400">
        <div className="text-center">
          <p className="text-lg mb-4">{t('view.welcome')}</p>
          <p className="text-sm">{t('view.welcomeSubtitle')}</p>
        </div>
      </div>
    );
  }

  return (
    <div data-name="chat-view-root" className="flex flex-col flex-1 min-h-0">
      {/* Header (optional) */}
      {showHeader && (
        <div data-name="chat-view-header" className="border-b border-gray-300 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              {currentSession?.title || 'Chat'}
            </h1>
            {isTemporary && (
              <>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                  {t('view.temporary')}
                </span>
                <button
                  onClick={handleSaveTemporary}
                  className="inline-flex items-center px-3 py-1 rounded text-xs font-medium bg-green-500 text-white hover:bg-green-600 transition-colors"
                >
                  {t('view.save')}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      {isGroupChat && (
        <div
          data-name="group-chat-status-bar"
          className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-cyan-50/80 via-white to-sky-50/80 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800"
        >
          <div data-name="group-chat-status-header" className="flex items-center justify-between gap-2 text-xs text-gray-600 dark:text-gray-300">
            <div className="flex items-center gap-1.5">
              <UsersIcon className="w-3.5 h-3.5" />
              <span>{t('groupChat.roundRobinMode')}</span>
            </div>
            <div className="flex items-center gap-2">
              <span>{t('groupChat.progress', { done: completedAssistantCount, total: groupAssistantProgress.length })}</span>
              {isSavingGroupOrder && (
                <span className="rounded-full border border-blue-200 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-[10px] text-blue-700 dark:text-blue-300">
                  {t('groupChat.reorderSaving')}
                </span>
              )}
            </div>
          </div>
          <div data-name="group-chat-reorder-hint" className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">
            {isGenerating ? t('groupChat.reorderDisabled') : t('groupChat.reorderHint')}
          </div>
          <div data-name="group-chat-status-list" className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {groupAssistantProgress.map((assistant) => (
              <div
                key={assistant.assistantId}
                data-name="group-chat-status-chip"
                draggable={canReorderGroupAssistants}
                onDragStart={(event) => handleAssistantChipDragStart(event, assistant.assistantId)}
                onDragOver={(event) => handleAssistantChipDragOver(event, assistant.assistantId)}
                onDrop={(event) => void handleAssistantChipDrop(event, assistant.assistantId)}
                onDragEnd={clearGroupDragState}
                className={`flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs whitespace-nowrap ${
                  assistant.status === 'thinking'
                    ? 'border-amber-300 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-200'
                    : assistant.status === 'done'
                      ? 'border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-200'
                      : 'border-gray-300 dark:border-gray-600 bg-white/80 dark:bg-gray-800 text-gray-600 dark:text-gray-300'
                } ${
                  canReorderGroupAssistants ? 'cursor-grab active:cursor-grabbing' : 'cursor-not-allowed opacity-80'
                } ${
                  draggingAssistantId === assistant.assistantId ? 'opacity-45' : ''
                } ${
                  draggingAssistantId && dragOverAssistantId === assistant.assistantId && draggingAssistantId !== assistant.assistantId
                    ? 'ring-2 ring-blue-400 dark:ring-blue-500'
                    : ''
                }`}
              >
                <span className="text-[10px] font-semibold opacity-70">#{assistant.order}</span>
                <span
                  className={`w-2 h-2 rounded-full ${
                    assistant.status === 'thinking'
                      ? 'bg-amber-400 animate-pulse'
                      : assistant.status === 'done'
                        ? 'bg-emerald-500'
                        : 'bg-gray-300 dark:bg-gray-500'
                  }`}
                />
                <span className="font-medium">{assistant.name}</span>
                <Bars3Icon className="w-3.5 h-3.5 opacity-60" />
              </div>
            ))}
          </div>
        </div>
      )}
      <MessageList
        messages={messages}
        loading={loading}
        isStreaming={isGenerating}
        sessionId={currentSessionId}
        onEditMessage={editMessage}
        onSaveMessageOnly={saveMessageOnly}
        onRegenerateMessage={regenerateMessage}
        onDeleteMessage={deleteMessage}
        onBranchMessage={handleBranchMessage}
        customMessageActions={customMessageActions}
      />

      {/* Follow-up question suggestions */}
      <FollowupChips
        questions={followupQuestions}
        onSelect={(question) => sendMessage(question)}
        disabled={loading || isGenerating}
      />

      {/* Generate follow-ups button */}
      {messages.length > 0 && followupQuestions.length === 0 && !isGenerating && !loading && (
        <div data-name="generate-followups" className="px-4 py-2 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={handleGenerateFollowups}
            disabled={isGeneratingFollowups}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full border border-gray-300 dark:border-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <LightBulbIcon className={`w-3.5 h-3.5 ${isGeneratingFollowups ? 'animate-pulse' : ''}`} />
            {isGeneratingFollowups ? t('view.generatingFollowups') : t('view.suggestFollowups')}
          </button>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div data-name="chat-view-error" className="px-4 py-2 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 text-sm">
          Error: {error}
        </div>
      )}

      {/* Context usage bar */}
      <ContextUsageBar
        promptTokens={lastPromptTokens}
        contextBudget={contextInfo?.context_budget ?? null}
        contextWindow={contextInfo?.context_window ?? null}
      />

      {/* Input with toolbar */}
      <InputBox
        onSend={handleSendMessage}
        onCompare={handleCompare}
        onStop={stopGeneration}
        onInsertSeparator={handleInsertSeparator}
        onCompressContext={handleCompressContext}
        isCompressing={isCompressing}
        onClearAllMessages={handleClearAllMessages}
        disabled={loading || isComparing}
        isStreaming={isGenerating}
        supportsReasoning={supportsReasoning}
        supportsVision={supportsVision}
        sessionId={currentSessionId}
        currentAssistantId={currentAssistantId || undefined}
        paramOverrides={paramOverrides}
        hasActiveOverrides={hasActiveOverrides}
        onParamOverridesChange={updateParamOverrides}
        assistantSelector={
          isGroupChat ? (
            <div data-name="group-chat-participants" className="flex items-center gap-1.5 px-2 py-1 text-xs text-gray-500 dark:text-gray-400">
              <UsersIcon className="w-4 h-4" />
              <span>
                {activeGroupAssistant
                  ? t('groupChat.replying', { name: activeGroupAssistant.name })
                  : t('groupChat.participants', { count: groupAssistants.length })}
              </span>
            </div>
          ) : (
            <AssistantSelector
              sessionId={currentSessionId}
              currentAssistantId={currentAssistantId || undefined}
              onAssistantChange={handleAssistantChange}
            />
          )
        }
      />
    </div>
  );
};
