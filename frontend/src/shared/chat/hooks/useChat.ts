/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect, useRef, useCallback, useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import type {
  Message,
  TokenUsage,
  CostInfo,
  UploadedFile,
  ParamOverrides,
  ContextInfo,
  GroupChatMode,
  GroupTimelineEvent,
  ChatTargetType,
} from '../../../types/message';
import { useChatServices } from '../services/ChatServiceProvider';
import {
  buildGroupTimelineEvent,
  loadToolCallCache,
  mergeToolCallsFromCache as mergeToolCallsFromCacheItems,
  nowTimestamp,
  persistToolCallCache,
  rememberToolCallsInCache,
} from './useChatHelpers';
import {
  buildChatSessionSnapshot,
  createEmptyChatSessionSnapshot,
  enrichGroupAssistantMessages,
  mergeCompareResponses,
} from './useChatSessionHelpers';
import { createChatStreamProjectionRuntime } from './useChatStreamProjectionRuntime';
import {
  applyGroupProjectionEvent,
  type GroupProjectionEvent,
  type GroupTimelineProjectionInput,
} from './useChatGroupProjection';
import { javascriptService } from '../services/javascriptService';
import { pyodideService } from '../services/pyodideService';
import { getCodeExecutionSettings } from '../config/codeExecution';

type SendMessageOptions = {
  reasoningEffort?: string;
  attachments?: UploadedFile[];
  useWebSearch?: boolean;
  fileReferences?: Array<{ path: string; project_id: string }>;
  temporaryTurn?: boolean;
};

type RegenerateMessageOptions = Pick<SendMessageOptions, 'reasoningEffort' | 'useWebSearch'>;

type MessageStateSetter = Dispatch<SetStateAction<Message[]>>;

type ToolCallPayload = {
  id?: string;
  name: string;
  args: Record<string, unknown>;
};

async function executeBrowserToolCallIfNeeded(params: {
  sessionId: string;
  api: ReturnType<typeof useChatServices>['api'];
  call: ToolCallPayload;
}): Promise<void> {
  const { sessionId, api, call } = params;
  if (call.name !== 'execute_python' && call.name !== 'execute_javascript') {
    return;
  }

  const toolCallId = call.id;
  if (!toolCallId) {
    return;
  }

  const rawCode = call.args.code;
  const code = typeof rawCode === 'string' ? rawCode : '';
  const rawTimeout = call.args.timeout_ms;
  const timeoutMs =
    typeof rawTimeout === 'number' && Number.isFinite(rawTimeout)
      ? Math.max(1000, Math.min(120000, Math.floor(rawTimeout)))
      : 30000;

  let resultPayload: string;
  try {
    const runnerSettings = getCodeExecutionSettings();
    if (call.name === 'execute_python' && !runnerSettings.enablePythonRunner) {
      resultPayload = JSON.stringify({
        ok: false,
        error: 'Python runner is disabled in settings',
      });
      await api.submitToolResult(sessionId, toolCallId, call.name, resultPayload);
      return;
    }
    if (call.name === 'execute_javascript' && !runnerSettings.enableJavaScriptRunner) {
      resultPayload = JSON.stringify({
        ok: false,
        error: 'JavaScript runner is disabled in settings',
      });
      await api.submitToolResult(sessionId, toolCallId, call.name, resultPayload);
      return;
    }

    const result =
      call.name === 'execute_javascript'
        ? await javascriptService.runJavaScript(code, timeoutMs)
        : await pyodideService.runPython(code, timeoutMs);
    resultPayload = JSON.stringify({
      ok: true,
      ...result,
    });
  } catch (error) {
    resultPayload = JSON.stringify({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }

  try {
    await api.submitToolResult(sessionId, toolCallId, call.name, resultPayload);
  } catch (error) {
    console.error('Failed to submit client tool result:', error);
  }
}

function createHydrateUserMessageFromServer(params: {
  sessionId: string | null;
  api: ReturnType<typeof useChatServices>['api'];
  setMessages: MessageStateSetter;
}) {
  const { sessionId, api, setMessages } = params;

  return async function hydrateUserMessageFromServer(
    userMessageId: string,
    attempt: number = 0
  ): Promise<boolean> {
    if (!sessionId) {
      return false;
    }

    try {
      const session = await api.getSession(sessionId);
      const serverUserMessage = session.state.messages.find(
        (message) => message.message_id === userMessageId && message.role === 'user'
      );
      if (!serverUserMessage) {
        if (attempt < 4) {
          await new Promise((resolve) => setTimeout(resolve, 150));
          return hydrateUserMessageFromServer(userMessageId, attempt + 1);
        }
        return false;
      }

      setMessages((prev) => {
        const next = [...prev];
        let targetIndex = next.findIndex(
          (message) => message.message_id === userMessageId && message.role === 'user'
        );

        if (targetIndex < 0) {
          for (let i = next.length - 1; i >= 0; i -= 1) {
            if (next[i].role === 'user' && !next[i].message_id) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0) {
          return prev;
        }

        next[targetIndex] = {
          ...next[targetIndex],
          message_id: userMessageId,
          content: serverUserMessage.content,
          attachments: serverUserMessage.attachments,
          created_at: serverUserMessage.created_at || next[targetIndex].created_at,
        };
        return next;
      });
      return true;
    } catch (err) {
      console.warn('Failed to hydrate user message from server:', err);
      return false;
    }
  };
}

function createLoadSession(params: {
  sessionId: string | null;
  api: ReturnType<typeof useChatServices>['api'];
  abortControllerRef: MutableRefObject<AbortController | null>;
  isProcessingRef: MutableRefObject<boolean>;
  applySessionSnapshot: (snapshot: ReturnType<typeof createEmptyChatSessionSnapshot>) => void;
  mergeToolCallsFromCache: (items: Message[]) => Message[];
  rememberToolCalls: (items: Message[]) => void;
  setIsStreaming: Dispatch<SetStateAction<boolean>>;
  setIsComparing: Dispatch<SetStateAction<boolean>>;
  setIsCompressing: Dispatch<SetStateAction<boolean>>;
  setFollowupQuestions: Dispatch<SetStateAction<string[]>>;
  setContextInfo: Dispatch<SetStateAction<ContextInfo | null>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string | null>>;
}) {
  const {
    sessionId,
    api,
    abortControllerRef,
    isProcessingRef,
    applySessionSnapshot,
    mergeToolCallsFromCache,
    rememberToolCalls,
    setIsStreaming,
    setIsComparing,
    setIsCompressing,
    setFollowupQuestions,
    setContextInfo,
    setLoading,
    setError,
  } = params;

  return async function loadSession() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    isProcessingRef.current = false;
    setIsStreaming(false);
    setIsComparing(false);
    setIsCompressing(false);

    if (!sessionId) {
      applySessionSnapshot(createEmptyChatSessionSnapshot());
      setFollowupQuestions([]);
      setContextInfo(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setFollowupQuestions([]);
      const session = await api.getSession(sessionId);
      let loadedMessages = session.state.messages;

      if (session.group_assistants && session.group_assistants.length >= 2) {
        const needsAssistantMetadata = loadedMessages.some(
          (message) =>
            message.role === 'assistant' &&
            message.assistant_id &&
            (!message.assistant_name || !message.assistant_icon)
        );

        if (needsAssistantMetadata) {
          try {
            const assistants = await api.listAssistants();
            loadedMessages = enrichGroupAssistantMessages(loadedMessages, assistants);
          } catch {
            // Keep loaded messages as-is when assistant metadata cannot be fetched.
          }
        }
      }

      loadedMessages = mergeCompareResponses(loadedMessages, session.compare_data);
      loadedMessages = mergeToolCallsFromCache(loadedMessages);
      rememberToolCalls(loadedMessages);
      applySessionSnapshot(buildChatSessionSnapshot(session, loadedMessages));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
      applySessionSnapshot(createEmptyChatSessionSnapshot());
      setContextInfo(null);
    } finally {
      setLoading(false);
    }
  };
}

function createSendCompareMessage(params: {
  sessionId: string | null;
  api: ReturnType<typeof useChatServices>['api'];
  isProcessingRef: MutableRefObject<boolean>;
  abortControllerRef: MutableRefObject<AbortController | null>;
  setMessages: MessageStateSetter;
  setFollowupQuestions: Dispatch<SetStateAction<string[]>>;
  setIsComparing: Dispatch<SetStateAction<boolean>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string | null>>;
  hydrateUserMessageFromServer: (userMessageId: string, attempt?: number) => Promise<boolean>;
}) {
  const {
    sessionId,
    api,
    isProcessingRef,
    abortControllerRef,
    setMessages,
    setFollowupQuestions,
    setIsComparing,
    setLoading,
    setError,
    hydrateUserMessageFromServer,
  } = params;

  return async function sendCompareMessage(
    content: string,
    modelIds: string[],
    options?: SendMessageOptions
  ) {
    if (!sessionId || (!content.trim() && !options?.attachments?.length) || isProcessingRef.current) {
      return;
    }

    isProcessingRef.current = true;
    try {
      if (api.beforeSendMessage) {
        const gate = await api.beforeSendMessage({ sessionId, message: content });
        if (!gate.proceed) {
          if (gate.reason) {
            setError(gate.reason);
          }
          isProcessingRef.current = false;
          return;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to prepare message send');
      isProcessingRef.current = false;
      return;
    }

    setFollowupQuestions([]);
    setIsComparing(true);

    const userMessage: Message = {
      role: 'user',
      content,
      created_at: nowTimestamp(),
      attachments: options?.attachments?.map((attachment) => ({
        filename: attachment.filename,
        size: attachment.size,
        mime_type: attachment.mime_type,
      })),
    };
    setMessages((prev) => [...prev, userMessage]);

    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      created_at: nowTimestamp(),
      compareResponses: [],
    };
    setMessages((prev) => [...prev, assistantMessage]);

    setLoading(true);
    setError(null);

    const modelContentMap = new Map<string, string>();
    let latestUserMessageId: string | null = null;

    try {
      await api.sendCompareStream(
        sessionId,
        content,
        modelIds,
        {
          onModelStart: (modelId: string, modelName: string) => {
            modelContentMap.set(modelId, '');
            setMessages((prev) => {
              const next = [...prev];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === 'assistant') {
                const responses = [...(next[lastIndex].compareResponses || [])];
                responses.push({ model_id: modelId, model_name: modelName, content: '' });
                next[lastIndex] = { ...next[lastIndex], compareResponses: responses };
              }
              return next;
            });
          },
          onModelChunk: (modelId: string, chunk: string) => {
            const updatedContent = (modelContentMap.get(modelId) || '') + chunk;
            modelContentMap.set(modelId, updatedContent);

            setMessages((prev) => {
              const next = [...prev];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === 'assistant') {
                const responses = (next[lastIndex].compareResponses || []).map((response) =>
                  response.model_id === modelId ? { ...response, content: updatedContent } : response
                );
                const firstContent = modelContentMap.get(modelIds[0]) || '';
                next[lastIndex] = { ...next[lastIndex], content: firstContent, compareResponses: responses };
              }
              return next;
            });
          },
          onModelDone: (modelId: string, fullContent: string, usage?: TokenUsage, cost?: CostInfo) => {
            setMessages((prev) => {
              const next = [...prev];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === 'assistant') {
                const responses = (next[lastIndex].compareResponses || []).map((response) =>
                  response.model_id === modelId ? { ...response, content: fullContent, usage, cost } : response
                );
                next[lastIndex] = { ...next[lastIndex], compareResponses: responses };
              }
              return next;
            });
          },
          onModelError: (modelId: string, error: string) => {
            setMessages((prev) => {
              const next = [...prev];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === 'assistant') {
                const responses = (next[lastIndex].compareResponses || []).map((response) =>
                  response.model_id === modelId ? { ...response, error } : response
                );
                next[lastIndex] = { ...next[lastIndex], compareResponses: responses };
              }
              return next;
            });
          },
          onUserMessageId: (messageId: string) => {
            latestUserMessageId = messageId;
            setMessages((prev) => {
              const next = [...prev];
              if (next.length >= 2) {
                next[next.length - 2] = { ...next[next.length - 2], message_id: messageId };
              }
              return next;
            });
            void hydrateUserMessageFromServer(messageId);
          },
          onAssistantMessageId: (messageId: string) => {
            setMessages((prev) => {
              const next = [...prev];
              if (next.length >= 1) {
                next[next.length - 1] = { ...next[next.length - 1], message_id: messageId };
              }
              return next;
            });
          },
          onSources: (sources) => {
            setMessages((prev) => {
              const next = [...prev];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === 'assistant') {
                next[lastIndex] = { ...next[lastIndex], sources };
              }
              return next;
            });
          },
          onDone: () => {
            setLoading(false);
            setIsComparing(false);
            isProcessingRef.current = false;
            if (latestUserMessageId) {
              void hydrateUserMessageFromServer(latestUserMessageId);
            }
          },
          onError: (error: string) => {
            setError(error);
            setLoading(false);
            setIsComparing(false);
            isProcessingRef.current = false;
            setMessages((prev) => prev.slice(0, -2));
          },
        },
        abortControllerRef,
        {
          reasoningEffort: options?.reasoningEffort,
          attachments: options?.attachments,
          useWebSearch: options?.useWebSearch,
          fileReferences: options?.fileReferences,
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compare models');
      setLoading(false);
      setIsComparing(false);
      isProcessingRef.current = false;
      setMessages((prev) => prev.slice(0, -2));
    }
  };
}

function createCompressContext(params: {
  sessionId: string | null;
  api: ReturnType<typeof useChatServices>['api'];
  isProcessingRef: MutableRefObject<boolean>;
  isCompressing: boolean;
  setIsCompressing: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setMessages: MessageStateSetter;
}) {
  const {
    sessionId,
    api,
    isProcessingRef,
    isCompressing,
    setIsCompressing,
    setError,
    setMessages,
  } = params;

  return async function compressContext() {
    if (!sessionId || isProcessingRef.current || isCompressing) {
      return;
    }

    isProcessingRef.current = true;
    setIsCompressing(true);
    setError(null);

    const placeholderMessage: Message = {
      role: 'summary',
      content: '',
      created_at: nowTimestamp(),
    };
    setMessages((prev) => [...prev, placeholderMessage]);

    let streamedContent = '';

    try {
      await api.compressContext(
        sessionId,
        (chunk: string) => {
          streamedContent += chunk;
          setMessages((prev) => {
            const next = [...prev];
            const lastIndex = next.length - 1;
            if (lastIndex >= 0 && next[lastIndex].role === 'summary') {
              next[lastIndex] = { ...next[lastIndex], content: streamedContent };
            }
            return next;
          });
        },
        (data: { message_id: string; compressed_count: number }) => {
          setMessages((prev) => {
            const next = [...prev];
            const lastIndex = next.length - 1;
            if (lastIndex >= 0 && next[lastIndex].role === 'summary') {
              next[lastIndex] = { ...next[lastIndex], message_id: data.message_id };
            }
            return next;
          });
        },
        (error: string) => {
          setError(error);
          setMessages((prev) => prev.filter((message) => message !== placeholderMessage));
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compress context');
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (lastMessage?.role === 'summary' && !lastMessage.content) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setIsCompressing(false);
      isProcessingRef.current = false;
    }
  };
}

function createClearFollowupQuestions(setFollowupQuestions: Dispatch<SetStateAction<string[]>>) {
  return function clearFollowupQuestions() {
    setFollowupQuestions([]);
  };
}

function createGenerateFollowups(params: {
  sessionId: string | null;
  api: ReturnType<typeof useChatServices>['api'];
  setFollowupQuestions: Dispatch<SetStateAction<string[]>>;
}) {
  const { sessionId, api, setFollowupQuestions } = params;

  return async function generateFollowups() {
    if (!sessionId) {
      return;
    }
    try {
      const questions = await api.generateFollowups(sessionId);
      setFollowupQuestions(questions);
    } catch (err) {
      console.error('Failed to generate follow-ups:', err);
    }
  };
}

function createStopGeneration(abortControllerRef: MutableRefObject<AbortController | null>) {
  return function stopGeneration() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      console.log('Stopping generation...');
    }
  };
}

export function useChat(sessionId: string | null) {
  const { api } = useChatServices();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isCompressing, setIsCompressing] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [currentModelId, setCurrentModelId] = useState<string | null>(null);
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null);
  const [currentTargetType, setCurrentTargetType] = useState<ChatTargetType>('model');
  const [totalUsage, setTotalUsage] = useState<TokenUsage | null>(null);
  const [totalCost, setTotalCost] = useState<CostInfo | null>(null);
  const [followupQuestions, setFollowupQuestions] = useState<string[]>([]);
  const [contextInfo, setContextInfo] = useState<ContextInfo | null>(null);
  const [lastPromptTokens, setLastPromptTokens] = useState<number | null>(null);
  const [paramOverrides, setParamOverrides] = useState<ParamOverrides>({});
  const [isTemporary, setIsTemporary] = useState(false);
  const [groupAssistants, setGroupAssistants] = useState<string[] | null>(null);
  const [groupMode, setGroupMode] = useState<GroupChatMode | null>(null);
  const [groupTimeline, setGroupTimeline] = useState<GroupTimelineEvent[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isProcessingRef = useRef(false);
  const toolCallsByMessageIdRef = useRef<Record<string, NonNullable<Message['toolCalls']>>>({});

  const applySessionSnapshot = useCallback((snapshot: ReturnType<typeof createEmptyChatSessionSnapshot>) => {
    setMessages(snapshot.messages);
    setCurrentModelId(snapshot.currentModelId);
    setCurrentAssistantId(snapshot.currentAssistantId);
    setCurrentTargetType(snapshot.currentTargetType);
    setTotalUsage(snapshot.totalUsage);
    setTotalCost(snapshot.totalCost);
    setLastPromptTokens(snapshot.lastPromptTokens);
    setParamOverrides(snapshot.paramOverrides);
    setIsTemporary(snapshot.isTemporary);
    setGroupAssistants(snapshot.groupAssistants);
    setGroupMode(snapshot.groupMode);
    setGroupTimeline(snapshot.groupTimeline);
  }, []);

  useEffect(() => {
    toolCallsByMessageIdRef.current = loadToolCallCache();
  }, []);

  const rememberToolCalls = useCallback((items: Message[]) => {
    const updated = rememberToolCallsInCache(toolCallsByMessageIdRef.current, items);
    if (!updated) {
      return;
    }
    persistToolCallCache(toolCallsByMessageIdRef.current);
  }, []);

  const mergeToolCallsFromCache = useCallback((items: Message[]): Message[] => {
    return mergeToolCallsFromCacheItems(items, toolCallsByMessageIdRef.current);
  }, []);

  const appendGroupTimelineEvent = useCallback((event: GroupTimelineProjectionInput) => {
    const timelineEvent = buildGroupTimelineEvent(event);
    if (!timelineEvent) {
      return;
    }
    setGroupTimeline(prev => [...prev.slice(-39), timelineEvent]);
  }, []);

  const applyGroupEventProjection = useCallback((
    event: GroupProjectionEvent,
    runtimeIsGroupChat: boolean,
    activateRuntimeGroupChatMode: () => void,
    updateAssistantMessage: (
      updater: (message: Message) => Message,
      options?: { assistantTurnId?: string | null; allowSingleFallback?: boolean },
    ) => void,
    activeAssistantTurnIdRef: { current: string | null },
  ) => {
    applyGroupProjectionEvent({
      event,
      activateRuntimeGroupChatMode,
      runtimeIsGroupChat,
      appendGroupTimelineEvent,
      updateAssistantMessage,
      setMessages,
      setTotalUsage,
      setTotalCost,
      setLastPromptTokens,
      getActiveAssistantTurnId: () => activeAssistantTurnIdRef.current,
      setActiveAssistantTurnId: (value) => {
        activeAssistantTurnIdRef.current = value;
      },
      nowTimestamp,
    });
  }, [appendGroupTimelineEvent, setLastPromptTokens, setMessages, setTotalCost, setTotalUsage]);

  const loadSession = useMemo(() => createLoadSession({
    sessionId,
    api,
    abortControllerRef,
    isProcessingRef,
    applySessionSnapshot,
    mergeToolCallsFromCache,
    rememberToolCalls,
    setIsStreaming,
    setIsComparing,
    setIsCompressing,
    setFollowupQuestions,
    setContextInfo,
    setLoading,
    setError,
  }),
    [api, applySessionSnapshot, mergeToolCallsFromCache, rememberToolCalls, sessionId]
  );

  useEffect(() => {
    rememberToolCalls(messages);
  }, [messages, rememberToolCalls]);

  // Load session messages when sessionId changes
  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const hydrateUserMessageFromServer = useMemo(
    () => createHydrateUserMessageFromServer({ sessionId, api, setMessages }),
    [api, sessionId]
  );

  const sendMessage = async (content: string, options?: SendMessageOptions) => {
    if (!sessionId || (!content.trim() && !options?.attachments?.length) || isProcessingRef.current) return;

    isProcessingRef.current = true;
    try {
      if (api.beforeSendMessage) {
        const gate = await api.beforeSendMessage({ sessionId, message: content });
        if (!gate.proceed) {
          if (gate.reason) {
            setError(gate.reason);
          }
          isProcessingRef.current = false;
          return;
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to prepare message send');
      isProcessingRef.current = false;
      return;
    }

    // Clear follow-up questions when sending a new message
    setFollowupQuestions([]);
    const isTemporaryTurn = options?.temporaryTurn === true;

    const initialIsGroupChat = Boolean(groupAssistants && groupAssistants.length >= 2);
    if (initialIsGroupChat) {
      setGroupTimeline([]);
    }

    // Optimistically add user message to UI (without message_id, wait for backend)
    const userMessage: Message = {
      role: 'user',
      content,
      created_at: nowTimestamp(),
      ephemeral: isTemporaryTurn,
      attachments: options?.attachments?.map(a => ({
        filename: a.filename,
        size: a.size,
        mime_type: a.mime_type,
      })),
    };
    setMessages(prev => [...prev, userMessage]);

    // For single-assistant: add placeholder. For group chat: no placeholder (added on assistant_start).
    if (!initialIsGroupChat) {
      const assistantMessage: Message = {
        role: 'assistant',
        content: '',
        created_at: nowTimestamp(),
        ephemeral: isTemporaryTurn,
      };
      setMessages(prev => [...prev, assistantMessage]);
    }

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';
    let latestUserMessageId: string | null = null;
    let activeAssistantTurnId: string | null = null;
    let runtimeIsGroupChat = initialIsGroupChat;
    const handledClientToolCallIds = new Set<string>();
    const {
      updateAssistantMessage,
      handleAssistantStart,
      applyGroupEvent,
    } = createChatStreamProjectionRuntime({
      getRuntimeIsGroupChat: () => runtimeIsGroupChat,
      setRuntimeIsGroupChat: (value) => {
        runtimeIsGroupChat = value;
      },
      getActiveAssistantTurnId: () => activeAssistantTurnId,
      setActiveAssistantTurnId: (value) => {
        activeAssistantTurnId = value;
      },
      nowTimestamp,
      setMessages,
      applyGroupEventProjection,
    });

    try {
      await api.sendMessageStream(
        sessionId,
        content,
        null,
        false,
        (chunk: string) => {
          if (runtimeIsGroupChat) {
            return;
          }
          streamedContent += chunk;
          const contentSnapshot = streamedContent;
          updateAssistantMessage(
            (message) => ({ ...message, content: contentSnapshot }),
            { allowSingleFallback: true }
          );
        },
        () => {
          activeAssistantTurnId = null;
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
          if (!isTemporaryTurn && latestUserMessageId) {
            void hydrateUserMessageFromServer(latestUserMessageId);
          }
        },
        (error: string) => {
          activeAssistantTurnId = null;
          setError(error);
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
          // Remove optimistic messages: for group chat only user msg, for single both user+assistant
          setMessages(prev => prev.slice(0, runtimeIsGroupChat ? -1 : -2));
        },
        abortControllerRef,
        options?.reasoningEffort,
        (usage: TokenUsage, cost?: CostInfo) => {
          if (runtimeIsGroupChat) {
            return;
          }
          updateAssistantMessage(
            (message) => ({ ...message, usage, cost }),
            { allowSingleFallback: true }
          );
          // Update session totals
          setTotalUsage(prev => prev ? {
            prompt_tokens: prev.prompt_tokens + usage.prompt_tokens,
            completion_tokens: prev.completion_tokens + usage.completion_tokens,
            total_tokens: prev.total_tokens + usage.total_tokens,
          } : usage);
          if (cost) {
            setTotalCost(prev => prev ? {
              ...prev,
              total_cost: prev.total_cost + cost.total_cost,
            } : cost);
          }
          // Track prompt tokens for context usage bar
          setLastPromptTokens(usage.prompt_tokens);
        },
        (sources) => {
          if (runtimeIsGroupChat) {
            return;
          }
          updateAssistantMessage(
            (message) => ({ ...message, sources }),
            { allowSingleFallback: true }
          );
        },
        options?.attachments,
        (userMessageId: string) => {
          if (isTemporaryTurn) {
            return;
          }
          latestUserMessageId = userMessageId;
          // Backend returned user message ID, update the user message
          setMessages(prev => {
            const newMessages = [...prev];
            let userMessageIndex = -1;
            for (let i = newMessages.length - 1; i >= 0; i--) {
              if (newMessages[i].role === 'user' && !newMessages[i].message_id) {
                userMessageIndex = i;
                break;
              }
            }
            if (userMessageIndex < 0) {
              for (let i = newMessages.length - 1; i >= 0; i--) {
                if (newMessages[i].role === 'user') {
                  userMessageIndex = i;
                  break;
                }
              }
            }
            if (userMessageIndex >= 0) {
              newMessages[userMessageIndex] = {
                ...newMessages[userMessageIndex],
                message_id: userMessageId
              };
              return newMessages;
            }
            return prev;
          });
          void hydrateUserMessageFromServer(userMessageId);
        },
        (assistantMessageId: string) => {
          if (isTemporaryTurn) {
            return;
          }
          if (runtimeIsGroupChat) {
            return;
          }
          // Backend returned assistant message ID, update the assistant message
          updateAssistantMessage(
            (message) => ({ ...message, message_id: assistantMessageId }),
            { allowSingleFallback: true }
          );
        },
        options?.useWebSearch,
        (questions: string[]) => {
          // Backend returned follow-up questions
          setFollowupQuestions(questions);
        },
        (info: ContextInfo) => {
          setContextInfo(info);
        },
        (durationMs: number) => {
          if (runtimeIsGroupChat) {
            return;
          }
          // Backend returned thinking duration
          updateAssistantMessage(
            (message) => ({ ...message, thinkingDurationMs: durationMs }),
            { allowSingleFallback: true }
          );
        },
        options?.fileReferences,
        // Tool calls: onToolCalls
        (calls: Array<{ id?: string; name: string; args: Record<string, unknown> }>) => {
          if (runtimeIsGroupChat) return;
          // Add tool calls with 'calling' status
          const toolCalls = calls.map(c => ({
            toolCallId: c.id,
            name: c.name,
            args: c.args,
            status: 'calling' as const,
          }));
          updateAssistantMessage(
            (message) => ({ ...message, toolCalls: [...(message.toolCalls || []), ...toolCalls] }),
            { allowSingleFallback: true }
          );
          for (const call of calls) {
            if (
              (call.name !== 'execute_python' && call.name !== 'execute_javascript') ||
              !call.id
            ) {
              continue;
            }
            if (handledClientToolCallIds.has(call.id)) {
              continue;
            }
            handledClientToolCallIds.add(call.id);
            void executeBrowserToolCallIfNeeded({
              sessionId,
              api,
              call,
            });
          }
        },
        // Tool results: onToolResults
        (results: Array<{ name: string; result: string; tool_call_id: string }>) => {
          if (runtimeIsGroupChat) return;
          // Update tool calls with results
          updateAssistantMessage(
            (message) => {
              const used = new Set<number>();
              const updated = (message.toolCalls || []).map(tc => {
                let matchIndex = -1;
                if (tc.toolCallId) {
                  matchIndex = results.findIndex(r => r.tool_call_id === tc.toolCallId);
                } else {
                  matchIndex = results.findIndex(
                    (r, idx) => !used.has(idx) && r.name === tc.name
                  );
                }
                if (matchIndex >= 0) {
                  const match = results[matchIndex];
                  used.add(matchIndex);
                  return {
                    ...tc,
                    toolCallId: tc.toolCallId || match.tool_call_id,
                    result: match.result,
                    status: 'done' as const,
                  };
                }
                return tc;
              });
              return { ...message, toolCalls: updated };
            },
            { allowSingleFallback: true }
          );
        },
        // Group chat: onAssistantStart
        (assistantId: string, name: string, icon?: string) => {
          handleAssistantStart(assistantId, name, icon);
        },
        // Group chat: onAssistantDone
        () => {
          // Controlled by onGroupEvent when available.
        },
        (event) => {
          applyGroupEvent(event);
        },
        undefined,
        undefined,
        isTemporaryTurn
      );
    } catch (err) {
      activeAssistantTurnId = null;
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(prev => prev.slice(0, runtimeIsGroupChat ? -1 : -2));
    }
  };

  const sendCompareMessage = useMemo(() => createSendCompareMessage({
    sessionId,
    api,
    isProcessingRef,
    abortControllerRef,
    setMessages,
    setFollowupQuestions,
    setIsComparing,
    setLoading,
    setError,
    hydrateUserMessageFromServer,
  }),
    [api, hydrateUserMessageFromServer, sessionId]
  );

  const editMessage = async (messageId: string, newContent: string) => {
    if (!sessionId || isProcessingRef.current) return;

    // Find message index by ID
    const messageIndex = messages.findIndex(m => m.message_id === messageId);
    if (messageIndex === -1) {
      console.error('Message not found');
      return;
    }

    if (messages[messageIndex]?.role !== 'user') {
      console.error('Can only edit user messages');
      return;
    }

    isProcessingRef.current = true;

    const originalMessages = [...messages];
    const truncatedMessages = messages.slice(0, messageIndex);
    const updatedUserMessage: Message = {
      message_id: messageId,  // Preserve message_id
      role: 'user',
      content: newContent,
      created_at: nowTimestamp(),
    };
    setMessages([...truncatedMessages, updatedUserMessage]);

    const assistantMessage: Message = {
      role: 'assistant',  // No UUID, wait for backend
      content: '',
      created_at: nowTimestamp(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';

    try {
      await api.sendMessageStream(
        sessionId,
        newContent,
        messageIndex - 1,
        false,
        (chunk: string) => {
          streamedContent += chunk;
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], role: 'assistant', content: streamedContent };
            }
            return newMessages;
          });
        },
        () => {
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
        },
        (error: string) => {
          setError(error);
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
          setMessages(originalMessages);
        },
        abortControllerRef,
        undefined,
        (usage: TokenUsage, cost?: CostInfo) => {
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], usage, cost };
            }
            return newMessages;
          });
          setLastPromptTokens(usage.prompt_tokens);
        },
        undefined,
        undefined,
        (userMessageId: string) => {
          // Backend returned user message ID
          setMessages(prev => {
            const newMessages = [...prev];
            if (newMessages.length >= 2) {
              newMessages[newMessages.length - 2] = {
                ...newMessages[newMessages.length - 2],
                message_id: userMessageId
              };
            }
            return newMessages;
          });
          void hydrateUserMessageFromServer(userMessageId);
        },
        (assistantMessageId: string) => {
          // Backend returned assistant message ID
          setMessages(prev => {
            const newMessages = [...prev];
            if (newMessages.length >= 1) {
              newMessages[newMessages.length - 1] = {
                ...newMessages[newMessages.length - 1],
                message_id: assistantMessageId
              };
            }
            return newMessages;
          });
        },
        undefined,
        undefined,
        (info: ContextInfo) => {
          setContextInfo(info);
        },
        (durationMs: number) => {
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], thinkingDurationMs: durationMs };
            }
            return newMessages;
          });
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to edit message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(originalMessages);
    }
  };

  const saveMessageOnly = async (messageId: string, newContent: string) => {
    if (!sessionId || isProcessingRef.current) return;

    isProcessingRef.current = true;
    const originalMessages = [...messages];

    // Optimistically update the message content in UI
    setMessages(prev => prev.map(m =>
      m.message_id === messageId ? { ...m, content: newContent } : m
    ));

    try {
      await api.updateMessageContent(sessionId, messageId, newContent);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save message');
      setMessages(originalMessages);
    } finally {
      isProcessingRef.current = false;
    }
  };

  const regenerateMessage = async (messageId: string, options?: RegenerateMessageOptions) => {
    if (!sessionId || isProcessingRef.current) return;

    // Find message index by ID
    const messageIndex = messages.findIndex(m => m.message_id === messageId);
    if (messageIndex === -1) {
      console.error('Message not found');
      return;
    }

    const targetMessage = messages[messageIndex];
    if (!targetMessage) return;

    // Determine the user message to use for regeneration
    let userMessageContent: string;
    let truncateIndex: number;

    if (targetMessage.role === 'assistant') {
      // For assistant message: use previous user message
      const previousUserMessage = messages[messageIndex - 1];
      if (!previousUserMessage || previousUserMessage.role !== 'user') {
        console.error('No user message found before assistant message');
        return;
      }
      userMessageContent = previousUserMessage.content;
      // Truncate after the user message (keep user message, remove assistant and after)
      truncateIndex = messageIndex - 1;
    } else {
      // For user message: use this user message itself
      userMessageContent = targetMessage.content;
      // Truncate after this user message (keep this user message, remove everything after)
      truncateIndex = messageIndex;
    }

    if (messageIndex < messages.length - 1) {
      const confirmed = window.confirm('Regenerating will delete all subsequent messages. Continue?');
      if (!confirmed) return;
    }

    isProcessingRef.current = true;
    const originalMessages = [...messages];
    const initialIsGroupChat = Boolean(groupAssistants && groupAssistants.length >= 2);

    // Keep messages up to and including truncateIndex
    const truncatedMessages = messages.slice(0, truncateIndex + 1);
    setMessages(truncatedMessages);

    if (!initialIsGroupChat) {
      const assistantMessage: Message = {
        role: 'assistant',  // No UUID, wait for backend
        content: '',
        created_at: nowTimestamp(),
      };
      setMessages(prev => [...prev, assistantMessage]);
    }

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';
    let runtimeIsGroupChat = initialIsGroupChat;
    let activeAssistantTurnId: string | null = null;
    const handledClientToolCallIds = new Set<string>();
    if (initialIsGroupChat) {
      setGroupTimeline([]);
    }
    const {
      updateAssistantMessage,
      handleAssistantStart,
      applyGroupEvent,
    } = createChatStreamProjectionRuntime({
      getRuntimeIsGroupChat: () => runtimeIsGroupChat,
      setRuntimeIsGroupChat: (value) => {
        runtimeIsGroupChat = value;
      },
      getActiveAssistantTurnId: () => activeAssistantTurnId,
      setActiveAssistantTurnId: (value) => {
        activeAssistantTurnId = value;
      },
      nowTimestamp,
      setMessages,
      applyGroupEventProjection,
    });

    try {
      await api.sendMessageStream(
        sessionId,
        userMessageContent,
        truncateIndex,
        true, // skip user message since it already exists
        (chunk: string) => {
          if (runtimeIsGroupChat) {
            return;
          }
          streamedContent += chunk;
          updateAssistantMessage(
            (message) => ({ ...message, role: 'assistant', content: streamedContent }),
            { allowSingleFallback: true }
          );
        },
        () => {
          activeAssistantTurnId = null;
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
        },
        (error: string) => {
          activeAssistantTurnId = null;
          setError(error);
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
          setMessages(originalMessages);
        },
        abortControllerRef,
        options?.reasoningEffort,
        (usage: TokenUsage, cost?: CostInfo) => {
          if (runtimeIsGroupChat) {
            return;
          }
          updateAssistantMessage(
            (message) => ({ ...message, usage, cost }),
            { allowSingleFallback: true }
          );
          setLastPromptTokens(usage.prompt_tokens);
        },
        (sources) => {
          if (runtimeIsGroupChat) {
            return;
          }
          updateAssistantMessage(
            (message) => ({ ...message, sources }),
            { allowSingleFallback: true }
          );
        },
        undefined,
        () => {
          // Regenerate uses skip_user_message=true, no user message should be appended.
        },
        (assistantMessageId: string) => {
          if (runtimeIsGroupChat) {
            return;
          }
          // Backend returned assistant message ID
          updateAssistantMessage(
            (message) => ({ ...message, message_id: assistantMessageId }),
            { allowSingleFallback: true }
          );
        },
        options?.useWebSearch,
        undefined,
        (info: ContextInfo) => {
          setContextInfo(info);
        },
        (durationMs: number) => {
          if (runtimeIsGroupChat) {
            return;
          }
          updateAssistantMessage(
            (message) => ({ ...message, thinkingDurationMs: durationMs }),
            { allowSingleFallback: true }
          );
        },
        undefined,
        // onToolCalls (regenerate)
        (calls: Array<{ id?: string; name: string; args: Record<string, unknown> }>) => {
          if (runtimeIsGroupChat) return;
          const toolCalls = calls.map(c => ({
            toolCallId: c.id,
            name: c.name,
            args: c.args,
            status: 'calling' as const,
          }));
          updateAssistantMessage(
            (message) => ({ ...message, toolCalls: [...(message.toolCalls || []), ...toolCalls] }),
            { allowSingleFallback: true }
          );
          for (const call of calls) {
            if (
              (call.name !== 'execute_python' && call.name !== 'execute_javascript') ||
              !call.id
            ) {
              continue;
            }
            if (handledClientToolCallIds.has(call.id)) {
              continue;
            }
            handledClientToolCallIds.add(call.id);
            void executeBrowserToolCallIfNeeded({
              sessionId,
              api,
              call,
            });
          }
        },
        // onToolResults (regenerate)
        (results: Array<{ name: string; result: string; tool_call_id: string }>) => {
          if (runtimeIsGroupChat) return;
          updateAssistantMessage(
            (message) => {
              const used = new Set<number>();
              const updated = (message.toolCalls || []).map(tc => {
                let matchIndex = -1;
                if (tc.toolCallId) {
                  matchIndex = results.findIndex(r => r.tool_call_id === tc.toolCallId);
                } else {
                  matchIndex = results.findIndex(
                    (r, idx) => !used.has(idx) && r.name === tc.name
                  );
                }
                if (matchIndex >= 0) {
                  const match = results[matchIndex];
                  used.add(matchIndex);
                  return {
                    ...tc,
                    toolCallId: tc.toolCallId || match.tool_call_id,
                    result: match.result,
                    status: 'done' as const,
                  };
                }
                return tc;
              });
              return { ...message, toolCalls: updated };
            },
            { allowSingleFallback: true }
          );
        },
        (assistantId: string, name: string, icon?: string) => {
          handleAssistantStart(assistantId, name, icon);
        },
        () => {
          // Controlled by onGroupEvent when available.
        },
        (event) => {
          applyGroupEvent(event);
        }
      );
    } catch (err) {
      activeAssistantTurnId = null;
      setError(err instanceof Error ? err.message : 'Failed to regenerate message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(originalMessages);
    }
  };

  const stopGeneration = useMemo(() => createStopGeneration(abortControllerRef), []);

  const deleteMessage = async (messageId: string) => {
    if (!sessionId || isProcessingRef.current) return;

    isProcessingRef.current = true;
    const originalMessages = [...messages];

    // Optimistically remove the message from UI
    setMessages(prev => prev.filter(m => m.message_id !== messageId));

    try {
      await api.deleteMessage(sessionId, messageId);
    } catch (err) {
      // Revert on error
      setError(err instanceof Error ? err.message : 'Failed to delete message');
      setMessages(originalMessages);
    } finally {
      isProcessingRef.current = false;
    }
  };

  const insertSeparator = async () => {
    if (!sessionId || isProcessingRef.current) return;

    isProcessingRef.current = true;

    try {
      const messageId = await api.insertSeparator(sessionId);

      // Add separator to UI
      const separatorMessage: Message = {
        message_id: messageId,
        role: 'separator',
        content: '--- Context cleared ---',
        created_at: nowTimestamp(),
      };

      setMessages(prev => [...prev, separatorMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to insert separator');
    } finally {
      isProcessingRef.current = false;
    }
  };

  const clearAllMessages = async () => {
    if (!sessionId || isProcessingRef.current) return;

    isProcessingRef.current = true;

    try {
      await api.clearAllMessages(sessionId);

      // Clear all messages from UI
      setMessages([]);

      // Reset usage and cost totals
      setTotalUsage(null);
      setTotalCost(null);

      // Reset context usage
      setContextInfo(null);
      setLastPromptTokens(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear messages');
    } finally {
      isProcessingRef.current = false;
    }
  };

  const updateModelId = (modelId: string) => {
    setCurrentModelId(modelId);
    setCurrentAssistantId(null);
    setCurrentTargetType('model');
    setParamOverrides({});
  };

  const updateAssistantId = (assistantId: string, modelId?: string) => {
    setCurrentAssistantId(assistantId);
    if (modelId) {
      setCurrentModelId(modelId);
    }
    setCurrentTargetType('assistant');
    // Clear overrides when switching assistants
    setParamOverrides({});
  };

  const updateTarget = (targetType: ChatTargetType, targetId: string, modelId?: string) => {
    if (targetType === 'assistant') {
      updateAssistantId(targetId, modelId);
      return;
    }
    setCurrentModelId(targetId);
    setCurrentAssistantId(null);
    setCurrentTargetType('model');
    setParamOverrides({});
  };

  const updateGroupAssistantOrder = async (nextGroupAssistants: string[]) => {
    if (!sessionId || nextGroupAssistants.length < 2) return;
    const previousOrder = groupAssistants;
    if (!previousOrder || previousOrder.length < 2) return;

    const orderUnchanged =
      previousOrder.length === nextGroupAssistants.length &&
      previousOrder.every((assistantId, index) => assistantId === nextGroupAssistants[index]);
    if (orderUnchanged) return;

    setGroupAssistants(nextGroupAssistants);
    try {
      await api.updateGroupAssistants(sessionId, nextGroupAssistants);
    } catch (err) {
      setGroupAssistants(previousOrder);
      setError(err instanceof Error ? err.message : 'Failed to update group assistant order');
      throw err;
    }
  };

  const updateParamOverrides = async (overrides: ParamOverrides) => {
    if (!sessionId) return;
    try {
      await api.updateSessionParamOverrides(sessionId, overrides);
      setParamOverrides(overrides);
    } catch (err) {
      console.error('Failed to update param overrides:', err);
    }
  };

  const hasActiveOverrides = Object.keys(paramOverrides).length > 0;

  const clearFollowupQuestions = useMemo(
    () => createClearFollowupQuestions(setFollowupQuestions),
    []
  );

  const generateFollowups = useMemo(
    () => createGenerateFollowups({ sessionId, api, setFollowupQuestions }),
    [api, sessionId]
  );

  const compressContext = useMemo(() => createCompressContext({
    sessionId,
    api,
    isProcessingRef,
    isCompressing,
    setIsCompressing,
    setError,
    setMessages,
  }),
    [api, isCompressing, sessionId]
  );

  return {
    messages,
    loading,
    error,
    isStreaming,
    isCompressing,
    isComparing,
    currentModelId,
    currentAssistantId,
    currentTargetType,
    totalUsage,
    totalCost,
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
    updateModelId,
    updateAssistantId,
    updateTarget,
    updateGroupAssistantOrder,
    clearFollowupQuestions,
    generateFollowups,
    paramOverrides,
    hasActiveOverrides,
    updateParamOverrides,
    groupAssistants,
    groupMode,
    groupTimeline,
  };
}
