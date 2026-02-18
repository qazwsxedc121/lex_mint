/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { Message, TokenUsage, CostInfo, UploadedFile, ParamOverrides, ContextInfo, GroupChatMode } from '../../../types/message';
import { useChatServices } from '../services/ChatServiceProvider';

type SendMessageOptions = {
  reasoningEffort?: string;
  attachments?: UploadedFile[];
  useWebSearch?: boolean;
  fileReferences?: Array<{ path: string; project_id: string }>;
};

export function useChat(sessionId: string | null) {
  const { api } = useChatServices();

  /** Generate current timestamp in YYYY-MM-DD HH:MM:SS format */
  const nowTimestamp = () => {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isCompressing, setIsCompressing] = useState(false);
  const [isComparing, setIsComparing] = useState(false);
  const [currentModelId, setCurrentModelId] = useState<string | null>(null);
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null);
  const [totalUsage, setTotalUsage] = useState<TokenUsage | null>(null);
  const [totalCost, setTotalCost] = useState<CostInfo | null>(null);
  const [followupQuestions, setFollowupQuestions] = useState<string[]>([]);
  const [contextInfo, setContextInfo] = useState<ContextInfo | null>(null);
  const [lastPromptTokens, setLastPromptTokens] = useState<number | null>(null);
  const [paramOverrides, setParamOverrides] = useState<ParamOverrides>({});
  const [isTemporary, setIsTemporary] = useState(false);
  const [groupAssistants, setGroupAssistants] = useState<string[] | null>(null);
  const [groupMode, setGroupMode] = useState<GroupChatMode | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isProcessingRef = useRef(false);

  // Extract loadSession as a standalone function so it can be called after sending messages
  const loadSession = useCallback(async () => {
    if (!sessionId) {
      setMessages([]);
      setCurrentModelId(null);
      setCurrentAssistantId(null);
      setTotalUsage(null);
      setTotalCost(null);
      setFollowupQuestions([]);
      setContextInfo(null);
      setLastPromptTokens(null);
      setParamOverrides({});
      setIsTemporary(false);
      setGroupAssistants(null);
      setGroupMode(null);
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
          (msg) =>
            msg.role === 'assistant' &&
            msg.assistant_id &&
            (!msg.assistant_name || !msg.assistant_icon)
        );

        if (needsAssistantMetadata) {
          try {
            const assistants = await api.listAssistants();
            const assistantMap = new Map(assistants.map((assistant) => [assistant.id, assistant]));
            loadedMessages = loadedMessages.map((msg) => {
              if (msg.role !== 'assistant' || !msg.assistant_id) {
                return msg;
              }
              const assistant = assistantMap.get(msg.assistant_id);
              if (!assistant) {
                return msg;
              }
              return {
                ...msg,
                assistant_name: msg.assistant_name || assistant.name,
                assistant_icon: msg.assistant_icon || assistant.icon,
              };
            });
          } catch {
            // Keep loaded messages as-is when assistant metadata cannot be fetched.
          }
        }
      }

      // Merge comparison data into messages
      if (session.compare_data) {
        loadedMessages = loadedMessages.map(msg => {
          if (msg.role === 'assistant' && msg.message_id && session.compare_data![msg.message_id]) {
            return {
              ...msg,
              compareResponses: session.compare_data![msg.message_id].responses,
            };
          }
          return msg;
        });
      }

      setMessages(loadedMessages);
      setCurrentModelId(session.model_id || null);
      setCurrentAssistantId(session.assistant_id || null);
      setTotalUsage(session.total_usage || null);
      setTotalCost(session.total_cost || null);
      setParamOverrides(session.param_overrides || {});
      setIsTemporary(session.temporary || false);
      setGroupAssistants(session.group_assistants || null);
      setGroupMode(
        session.group_mode ||
        (session.group_assistants && session.group_assistants.length >= 2 ? 'round_robin' : null)
      );

      // Derive lastPromptTokens from last assistant message's usage
      const msgs = session.state.messages;
      let derivedPromptTokens: number | null = null;
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant' && msgs[i].usage?.prompt_tokens) {
          derivedPromptTokens = msgs[i].usage!.prompt_tokens;
          break;
        }
      }
      setLastPromptTokens(derivedPromptTokens);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
      setMessages([]);
      setCurrentModelId(null);
      setCurrentAssistantId(null);
      setTotalUsage(null);
      setTotalCost(null);
      setContextInfo(null);
      setLastPromptTokens(null);
      setParamOverrides({});
      setIsTemporary(false);
      setGroupAssistants(null);
      setGroupMode(null);
    } finally {
      setLoading(false);
    }
  }, [api, sessionId]);

  // Load session messages when sessionId changes
  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Replace optimistic user message content with server-stored content
  // (important for @file injected blocks).
  const hydrateUserMessageFromServer = async (
    userMessageId: string,
    attempt: number = 0
  ): Promise<boolean> => {
    if (!sessionId) return false;
    try {
      const session = await api.getSession(sessionId);
      const serverUserMessage = session.state.messages.find(
        (m) => m.message_id === userMessageId && m.role === 'user'
      );
      if (!serverUserMessage) {
        if (attempt < 4) {
          await new Promise((resolve) => setTimeout(resolve, 150));
          return hydrateUserMessageFromServer(userMessageId, attempt + 1);
        }
        return false;
      }

      setMessages(prev => {
        const next = [...prev];
        let targetIndex = next.findIndex(
          (m) => m.message_id === userMessageId && m.role === 'user'
        );

        // Fallback for optimistic message race: fill the latest user message
        // that still has no backend message_id.
        if (targetIndex < 0) {
          for (let i = next.length - 1; i >= 0; i--) {
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
      // Keep optimistic content if hydration fails.
      console.warn('Failed to hydrate user message from server:', err);
      return false;
    }
  };

  const sendMessage = async (content: string, options?: SendMessageOptions) => {
    if (!sessionId || (!content.trim() && !options?.attachments?.length) || isProcessingRef.current) return;

    isProcessingRef.current = true;

    // Clear follow-up questions when sending a new message
    setFollowupQuestions([]);

    const initialIsGroupChat = groupAssistants && groupAssistants.length >= 2;

    // Optimistically add user message to UI (without message_id, wait for backend)
    const userMessage: Message = {
      role: 'user',
      content,
      created_at: nowTimestamp(),
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

    const activateRuntimeGroupChatMode = () => {
      if (runtimeIsGroupChat) {
        return;
      }
      runtimeIsGroupChat = true;
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        // If a single-chat placeholder was created before group metadata loaded,
        // remove it once group events are detected.
        if (
          lastMessage &&
          lastMessage.role === 'assistant' &&
          !lastMessage.assistant_id &&
          !lastMessage.message_id &&
          !lastMessage.content.trim()
        ) {
          newMessages.pop();
          return newMessages;
        }
        return prev;
      });
    };

    const updateAssistantMessage = (
      updater: (message: Message) => Message,
      options?: { assistantId?: string | null; assistantTurnId?: string | null; allowSingleFallback?: boolean }
    ) => {
      setMessages(prev => {
        const newMessages = [...prev];
        let targetIndex = -1;
        const assistantTurnId = options?.assistantTurnId;
        const assistantId = options?.assistantId;
        const allowSingleFallback = options?.allowSingleFallback ?? true;
        const hasGroupAssistantMessages = newMessages.some(
          (message) => message.role === 'assistant' && !!message.assistant_id
        );

        if (assistantTurnId) {
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && newMessages[i].assistant_turn_id === assistantTurnId) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0 && assistantId) {
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && newMessages[i].assistant_id === assistantId) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0) {
          if (!allowSingleFallback || runtimeIsGroupChat || hasGroupAssistantMessages) {
            return prev;
          }
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && !newMessages[i].assistant_id) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0) {
          return prev;
        }

        newMessages[targetIndex] = updater(newMessages[targetIndex]);
        return newMessages;
      });
    };

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
          if (latestUserMessageId) {
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
        (calls: Array<{ name: string; args: Record<string, unknown> }>) => {
          if (runtimeIsGroupChat) return;
          // Add tool calls with 'calling' status
          const toolCalls = calls.map(c => ({ name: c.name, args: c.args, status: 'calling' as const }));
          updateAssistantMessage(
            (message) => ({ ...message, toolCalls: [...(message.toolCalls || []), ...toolCalls] }),
            { allowSingleFallback: true }
          );
        },
        // Tool results: onToolResults
        (results: Array<{ name: string; result: string; tool_call_id: string }>) => {
          if (runtimeIsGroupChat) return;
          // Update tool calls with results
          updateAssistantMessage(
            (message) => {
              const updated = (message.toolCalls || []).map(tc => {
                const match = results.find(r => r.name === tc.name && tc.status === 'calling');
                if (match) {
                  return { ...tc, result: match.result, status: 'done' as const };
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
          if (!runtimeIsGroupChat) {
            activateRuntimeGroupChatMode();
          }
          // Reset streamed content for new assistant
          activeAssistantTurnId = null;
          // Add new empty assistant message with identity
          const newAssistantMsg: Message = {
            role: 'assistant',
            content: '',
            created_at: nowTimestamp(),
            assistant_id: assistantId,
            assistant_name: name,
            assistant_icon: icon,
          };
          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            // If group metadata loaded late, remove the single-chat placeholder
            // before appending the first assistant in group mode.
            if (
              lastMessage &&
              lastMessage.role === 'assistant' &&
              !lastMessage.assistant_id &&
              !lastMessage.message_id &&
              !lastMessage.content.trim()
            ) {
              newMessages.pop();
            }
            newMessages.push(newAssistantMsg);
            return newMessages;
          });
        },
        // Group chat: onAssistantDone
        () => {
          // Controlled by onGroupEvent when available.
        },
        (event) => {
          const isGroupEventType = (
            event.type === 'assistant_start' ||
            event.type === 'assistant_chunk' ||
            event.type === 'assistant_done' ||
            event.type === 'assistant_message_id' ||
            event.type === 'usage' ||
            event.type === 'sources' ||
            event.type === 'thinking_duration'
          );
          const hasGroupIdentity =
            typeof event.assistant_turn_id === 'string' ||
            typeof event.assistant_id === 'string';
          if (isGroupEventType && hasGroupIdentity) {
            activateRuntimeGroupChatMode();
          }
          if (!runtimeIsGroupChat) {
            return;
          }
          switch (event.type) {
            case 'assistant_start': {
              const assistantId = typeof event.assistant_id === 'string' ? event.assistant_id : null;
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const assistantName = typeof event.name === 'string' ? event.name : '';
              const assistantIcon = typeof event.icon === 'string' ? event.icon : undefined;
              if (!assistantId || !assistantTurnId) {
                return;
              }
              activeAssistantTurnId = assistantTurnId;
              setMessages(prev => {
                const newMessages = [...prev];
                const exists = newMessages.some(
                  (message) => message.role === 'assistant' && message.assistant_turn_id === assistantTurnId
                );
                if (exists) {
                  return prev;
                }
                newMessages.push({
                  role: 'assistant',
                  content: '',
                  created_at: nowTimestamp(),
                  assistant_id: assistantId,
                  assistant_turn_id: assistantTurnId,
                  assistant_name: assistantName || undefined,
                  assistant_icon: assistantIcon,
                });
                return newMessages;
              });
              return;
            }
            case 'assistant_chunk': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const chunk = typeof event.chunk === 'string' ? event.chunk : '';
              if (!assistantTurnId || !chunk) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, content: `${message.content || ''}${chunk}` }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'usage': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const usage = event.usage as TokenUsage | undefined;
              const cost = event.cost as CostInfo | undefined;
              if (!assistantTurnId || !usage) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, usage, cost }),
                { assistantTurnId, allowSingleFallback: false }
              );
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
              setLastPromptTokens(usage.prompt_tokens);
              return;
            }
            case 'sources': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const sources = event.sources as Message['sources'];
              if (!assistantTurnId || !sources) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, sources }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'thinking_duration': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const durationMs = typeof event.duration_ms === 'number' ? event.duration_ms : null;
              if (!assistantTurnId || durationMs === null) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, thinkingDurationMs: durationMs }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'assistant_message_id': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const messageId = typeof event.message_id === 'string' ? event.message_id : null;
              if (!assistantTurnId || !messageId) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, message_id: messageId }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'assistant_done': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              if (assistantTurnId && activeAssistantTurnId === assistantTurnId) {
                activeAssistantTurnId = null;
              }
              return;
            }
            default:
              return;
          }
        }
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

  const sendCompareMessage = async (content: string, modelIds: string[], options?: SendMessageOptions) => {
    if (!sessionId || (!content.trim() && !options?.attachments?.length) || isProcessingRef.current) return;

    isProcessingRef.current = true;
    setFollowupQuestions([]);
    setIsComparing(true);

    // Optimistically add user message
    const userMessage: Message = {
      role: 'user',
      content,
      created_at: nowTimestamp(),
      attachments: options?.attachments?.map(a => ({
        filename: a.filename,
        size: a.size,
        mime_type: a.mime_type,
      })),
    };
    setMessages(prev => [...prev, userMessage]);

    // Add placeholder assistant message with empty compareResponses
    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      created_at: nowTimestamp(),
      compareResponses: [],
    };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setError(null);

    // Track accumulated content per model
    const modelContentMap = new Map<string, string>();
    const modelNameMap = new Map<string, string>();

    let latestUserMessageId: string | null = null;
    try {
      await api.sendCompareStream(
        sessionId,
        content,
        modelIds,
        {
          onModelStart: (modelId: string, modelName: string) => {
            modelNameMap.set(modelId, modelName);
            modelContentMap.set(modelId, '');
            // Add initial empty entry
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                const responses = [...(newMessages[lastIndex].compareResponses || [])];
                responses.push({
                  model_id: modelId,
                  model_name: modelName,
                  content: '',
                });
                newMessages[lastIndex] = { ...newMessages[lastIndex], compareResponses: responses };
              }
              return newMessages;
            });
          },
          onModelChunk: (modelId: string, chunk: string) => {
            const current = modelContentMap.get(modelId) || '';
            modelContentMap.set(modelId, current + chunk);
            const updatedContent = current + chunk;

            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                const responses = (newMessages[lastIndex].compareResponses || []).map(r =>
                  r.model_id === modelId ? { ...r, content: updatedContent } : r
                );
                // Also set content to first model's content for display purposes
                const firstContent = modelContentMap.get(modelIds[0]) || '';
                newMessages[lastIndex] = { ...newMessages[lastIndex], content: firstContent, compareResponses: responses };
              }
              return newMessages;
            });
          },
          onModelDone: (modelId: string, fullContent: string, usage?: TokenUsage, cost?: CostInfo) => {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                const responses = (newMessages[lastIndex].compareResponses || []).map(r =>
                  r.model_id === modelId ? { ...r, content: fullContent, usage, cost } : r
                );
                newMessages[lastIndex] = { ...newMessages[lastIndex], compareResponses: responses };
              }
              return newMessages;
            });
          },
          onModelError: (modelId: string, error: string) => {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                const responses = (newMessages[lastIndex].compareResponses || []).map(r =>
                  r.model_id === modelId ? { ...r, error } : r
                );
                newMessages[lastIndex] = { ...newMessages[lastIndex], compareResponses: responses };
              }
              return newMessages;
            });
          },
          onUserMessageId: (messageId: string) => {
            latestUserMessageId = messageId;
            setMessages(prev => {
              const newMessages = [...prev];
              if (newMessages.length >= 2) {
                newMessages[newMessages.length - 2] = {
                  ...newMessages[newMessages.length - 2],
                  message_id: messageId,
                };
              }
              return newMessages;
            });
            void hydrateUserMessageFromServer(messageId);
          },
          onAssistantMessageId: (messageId: string) => {
            setMessages(prev => {
              const newMessages = [...prev];
              if (newMessages.length >= 1) {
                newMessages[newMessages.length - 1] = {
                  ...newMessages[newMessages.length - 1],
                  message_id: messageId,
                };
              }
              return newMessages;
            });
          },
          onSources: (sources) => {
            setMessages(prev => {
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                newMessages[lastIndex] = { ...newMessages[lastIndex], sources };
              }
              return newMessages;
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
            setMessages(prev => prev.slice(0, -2));
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
      setMessages(prev => prev.slice(0, -2));
    }
  };

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

  const regenerateMessage = async (messageId: string) => {
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
    const initialIsGroupChat = groupAssistants && groupAssistants.length >= 2;

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

    const activateRuntimeGroupChatMode = () => {
      if (runtimeIsGroupChat) {
        return;
      }
      runtimeIsGroupChat = true;
      setMessages(prev => {
        const newMessages = [...prev];
        const lastMessage = newMessages[newMessages.length - 1];
        if (
          lastMessage &&
          lastMessage.role === 'assistant' &&
          !lastMessage.assistant_id &&
          !lastMessage.message_id &&
          !lastMessage.content.trim()
        ) {
          newMessages.pop();
          return newMessages;
        }
        return prev;
      });
    };

    const updateAssistantMessage = (
      updater: (message: Message) => Message,
      options?: { assistantId?: string | null; assistantTurnId?: string | null; allowSingleFallback?: boolean }
    ) => {
      setMessages(prev => {
        const newMessages = [...prev];
        let targetIndex = -1;
        const assistantTurnId = options?.assistantTurnId;
        const assistantId = options?.assistantId;
        const allowSingleFallback = options?.allowSingleFallback ?? true;
        const hasGroupAssistantMessages = newMessages.some(
          (message) => message.role === 'assistant' && !!message.assistant_id
        );

        if (assistantTurnId) {
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && newMessages[i].assistant_turn_id === assistantTurnId) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0 && assistantId) {
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && newMessages[i].assistant_id === assistantId) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0) {
          if (!allowSingleFallback || runtimeIsGroupChat || hasGroupAssistantMessages) {
            return prev;
          }
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].role === 'assistant' && !newMessages[i].assistant_id) {
              targetIndex = i;
              break;
            }
          }
        }

        if (targetIndex < 0) {
          return prev;
        }

        newMessages[targetIndex] = updater(newMessages[targetIndex]);
        return newMessages;
      });
    };

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
        undefined,
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
        undefined,
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
        (calls: Array<{ name: string; args: Record<string, unknown> }>) => {
          if (runtimeIsGroupChat) return;
          const toolCalls = calls.map(c => ({ name: c.name, args: c.args, status: 'calling' as const }));
          updateAssistantMessage(
            (message) => ({ ...message, toolCalls: [...(message.toolCalls || []), ...toolCalls] }),
            { allowSingleFallback: true }
          );
        },
        // onToolResults (regenerate)
        (results: Array<{ name: string; result: string; tool_call_id: string }>) => {
          if (runtimeIsGroupChat) return;
          updateAssistantMessage(
            (message) => {
              const updated = (message.toolCalls || []).map(tc => {
                const match = results.find(r => r.name === tc.name && tc.status === 'calling');
                if (match) {
                  return { ...tc, result: match.result, status: 'done' as const };
                }
                return tc;
              });
              return { ...message, toolCalls: updated };
            },
            { allowSingleFallback: true }
          );
        },
        (assistantId: string, name: string, icon?: string) => {
          if (!runtimeIsGroupChat) {
            activateRuntimeGroupChatMode();
          }
          activeAssistantTurnId = null;
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages.push({
              role: 'assistant',
              content: '',
              created_at: nowTimestamp(),
              assistant_id: assistantId,
              assistant_name: name,
              assistant_icon: icon,
            });
            return newMessages;
          });
        },
        () => {
          // Controlled by onGroupEvent when available.
        },
        (event) => {
          const isGroupEventType = (
            event.type === 'assistant_start' ||
            event.type === 'assistant_chunk' ||
            event.type === 'assistant_done' ||
            event.type === 'assistant_message_id' ||
            event.type === 'usage' ||
            event.type === 'sources' ||
            event.type === 'thinking_duration'
          );
          const hasGroupIdentity =
            typeof event.assistant_turn_id === 'string' ||
            typeof event.assistant_id === 'string';
          if (isGroupEventType && hasGroupIdentity) {
            activateRuntimeGroupChatMode();
          }
          if (!runtimeIsGroupChat) {
            return;
          }
          switch (event.type) {
            case 'assistant_start': {
              const assistantId = typeof event.assistant_id === 'string' ? event.assistant_id : null;
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const assistantName = typeof event.name === 'string' ? event.name : '';
              const assistantIcon = typeof event.icon === 'string' ? event.icon : undefined;
              if (!assistantId || !assistantTurnId) {
                return;
              }
              activeAssistantTurnId = assistantTurnId;
              setMessages(prev => {
                const newMessages = [...prev];
                const exists = newMessages.some(
                  (message) => message.role === 'assistant' && message.assistant_turn_id === assistantTurnId
                );
                if (exists) {
                  return prev;
                }
                newMessages.push({
                  role: 'assistant',
                  content: '',
                  created_at: nowTimestamp(),
                  assistant_id: assistantId,
                  assistant_turn_id: assistantTurnId,
                  assistant_name: assistantName || undefined,
                  assistant_icon: assistantIcon,
                });
                return newMessages;
              });
              return;
            }
            case 'assistant_chunk': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const chunk = typeof event.chunk === 'string' ? event.chunk : '';
              if (!assistantTurnId || !chunk) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, content: `${message.content || ''}${chunk}` }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'usage': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const usage = event.usage as TokenUsage | undefined;
              const cost = event.cost as CostInfo | undefined;
              if (!assistantTurnId || !usage) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, usage, cost }),
                { assistantTurnId, allowSingleFallback: false }
              );
              setLastPromptTokens(usage.prompt_tokens);
              return;
            }
            case 'sources': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const sources = event.sources as Message['sources'];
              if (!assistantTurnId || !sources) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, sources }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'thinking_duration': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const durationMs = typeof event.duration_ms === 'number' ? event.duration_ms : null;
              if (!assistantTurnId || durationMs === null) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, thinkingDurationMs: durationMs }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'assistant_message_id': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              const messageIdFromEvent = typeof event.message_id === 'string' ? event.message_id : null;
              if (!assistantTurnId || !messageIdFromEvent) {
                return;
              }
              updateAssistantMessage(
                (message) => ({ ...message, message_id: messageIdFromEvent }),
                { assistantTurnId, allowSingleFallback: false }
              );
              return;
            }
            case 'assistant_done': {
              const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
              if (assistantTurnId && activeAssistantTurnId === assistantTurnId) {
                activeAssistantTurnId = null;
              }
              return;
            }
            default:
              return;
          }
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

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      console.log('Stopping generation...');
    }
  };

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
  };

  const updateAssistantId = (assistantId: string) => {
    setCurrentAssistantId(assistantId);
    // Clear overrides when switching assistants
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

  const clearFollowupQuestions = () => {
    setFollowupQuestions([]);
  };

  const generateFollowups = async () => {
    if (!sessionId) return;
    try {
      const questions = await api.generateFollowups(sessionId);
      setFollowupQuestions(questions);
    } catch (err) {
      console.error('Failed to generate follow-ups:', err);
    }
  };

  const compressContext = async () => {
    if (!sessionId || isProcessingRef.current || isCompressing) return;

    isProcessingRef.current = true;
    setIsCompressing(true);
    setError(null);

    // Add placeholder summary message (streaming)
    const placeholderMessage: Message = {
      role: 'summary',
      content: '',
      created_at: nowTimestamp(),
    };
    setMessages(prev => [...prev, placeholderMessage]);

    let streamedContent = '';

    try {
      await api.compressContext(
        sessionId,
        (chunk: string) => {
          streamedContent += chunk;
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'summary') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], content: streamedContent };
            }
            return newMessages;
          });
        },
        (data: { message_id: string; compressed_count: number }) => {
          // Update placeholder with final message_id
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'summary') {
              newMessages[lastIndex] = {
                ...newMessages[lastIndex],
                message_id: data.message_id,
              };
            }
            return newMessages;
          });
        },
        (error: string) => {
          setError(error);
          // Remove the placeholder on error
          setMessages(prev => prev.filter(m => m !== placeholderMessage));
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compress context');
      setMessages(prev => {
        // Remove the last summary message if it has no content
        const lastMsg = prev[prev.length - 1];
        if (lastMsg?.role === 'summary' && !lastMsg.content) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } finally {
      setIsCompressing(false);
      isProcessingRef.current = false;
    }
  };

  return {
    messages,
    loading,
    error,
    isStreaming,
    isCompressing,
    isComparing,
    currentModelId,
    currentAssistantId,
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
    updateGroupAssistantOrder,
    clearFollowupQuestions,
    generateFollowups,
    paramOverrides,
    hasActiveOverrides,
    updateParamOverrides,
    groupAssistants,
    groupMode,
  };
}
