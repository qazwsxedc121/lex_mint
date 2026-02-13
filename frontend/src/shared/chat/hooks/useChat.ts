/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect, useRef } from 'react';
import type { Message, TokenUsage, CostInfo, UploadedFile, ParamOverrides, ContextInfo } from '../../../types/message';
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
  const abortControllerRef = useRef<AbortController | null>(null);
  const isProcessingRef = useRef(false);

  // Extract loadSession as a standalone function so it can be called after sending messages
  const loadSession = async () => {
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
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setFollowupQuestions([]);
      const session = await api.getSession(sessionId);
      let loadedMessages = session.state.messages;

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
    } finally {
      setLoading(false);
    }
  };

  // Load session messages when sessionId changes
  useEffect(() => {
    loadSession();
  }, [sessionId]);

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

    // Add placeholder for assistant message (without message_id, wait for backend)
    const assistantMessage: Message = {
      role: 'assistant',
      content: '',
      created_at: nowTimestamp(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';
    let latestUserMessageId: string | null = null;

    try {
      await api.sendMessageStream(
        sessionId,
        content,
        null,
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
          if (latestUserMessageId) {
            void hydrateUserMessageFromServer(latestUserMessageId);
          }
        },
        (error: string) => {
          setError(error);
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
          setMessages(prev => prev.slice(0, -2));
        },
        abortControllerRef,
        options?.reasoningEffort,
        (usage: TokenUsage, cost?: CostInfo) => {
          // Update the last assistant message with usage/cost data
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], usage, cost };
            }
            return newMessages;
          });
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
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], sources };
            }
            return newMessages;
          });
        },
        options?.attachments,
        (userMessageId: string) => {
          latestUserMessageId = userMessageId;
          // Backend returned user message ID, update the user message
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
          // Backend returned assistant message ID, update the assistant message
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
        options?.useWebSearch,
        (questions: string[]) => {
          // Backend returned follow-up questions
          setFollowupQuestions(questions);
        },
        (info: ContextInfo) => {
          setContextInfo(info);
        },
        (durationMs: number) => {
          // Backend returned thinking duration
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], thinkingDurationMs: durationMs };
            }
            return newMessages;
          });
        },
        options?.fileReferences
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(prev => prev.slice(0, -2));
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

    // Keep messages up to and including truncateIndex
    const truncatedMessages = messages.slice(0, truncateIndex + 1);
    setMessages(truncatedMessages);

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
        userMessageContent,
        truncateIndex,
        true, // skip user message since it already exists
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
        (sources) => {
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { ...newMessages[lastIndex], sources };
            }
            return newMessages;
          });
        },
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
    clearFollowupQuestions,
    generateFollowups,
    paramOverrides,
    hasActiveOverrides,
    updateParamOverrides,
  };
}
