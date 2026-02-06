/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect, useRef } from 'react';
import type { Message, TokenUsage, CostInfo, UploadedFile } from '../../../types/message';
import { useChatServices } from '../services/ChatServiceProvider';

export function useChat(sessionId: string | null) {
  const { api } = useChatServices();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentModelId, setCurrentModelId] = useState<string | null>(null);
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null);
  const [totalUsage, setTotalUsage] = useState<TokenUsage | null>(null);
  const [totalCost, setTotalCost] = useState<CostInfo | null>(null);
  const [followupQuestions, setFollowupQuestions] = useState<string[]>([]);
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
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const session = await api.getSession(sessionId);
      setMessages(session.state.messages);
      setCurrentModelId(session.model_id || null);
      setCurrentAssistantId(session.assistant_id || null);
      setTotalUsage(session.total_usage || null);
      setTotalCost(session.total_cost || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
      setMessages([]);
      setCurrentModelId(null);
      setCurrentAssistantId(null);
      setTotalUsage(null);
      setTotalCost(null);
    } finally {
      setLoading(false);
    }
  };

  // Load session messages when sessionId changes
  useEffect(() => {
    loadSession();
  }, [sessionId]);

  const sendMessage = async (content: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[]; useWebSearch?: boolean }) => {
    if (!sessionId || (!content.trim() && !options?.attachments?.length) || isProcessingRef.current) return;

    isProcessingRef.current = true;

    // Clear follow-up questions when sending a new message
    setFollowupQuestions([]);

    // Optimistically add user message to UI (without message_id, wait for backend)
    const userMessage: Message = {
      role: 'user',
      content,
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
      content: ''
    };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';

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
        undefined,  // contextType
        undefined,  // projectId
        (questions: string[]) => {
          // Backend returned follow-up questions
          setFollowupQuestions(questions);
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setLoading(false);
      setIsStreaming(false);
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

    if (messageIndex < messages.length - 1) {
      const confirmed = window.confirm('Editing this message will delete all subsequent messages. Continue?');
      if (!confirmed) return;
    }

    isProcessingRef.current = true;

    const originalMessages = [...messages];
    const truncatedMessages = messages.slice(0, messageIndex);
    const updatedUserMessage: Message = {
      message_id: messageId,  // Preserve message_id
      role: 'user',
      content: newContent
    };
    setMessages([...truncatedMessages, updatedUserMessage]);

    const assistantMessage: Message = {
      role: 'assistant',  // No UUID, wait for backend
      content: ''
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
        undefined
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to edit message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(originalMessages);
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
      content: ''
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
        undefined
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
        content: '--- Context cleared ---'
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
  };

  const clearFollowupQuestions = () => {
    setFollowupQuestions([]);
  };

  return {
    messages,
    loading,
    error,
    isStreaming,
    currentModelId,
    currentAssistantId,
    totalUsage,
    totalCost,
    followupQuestions,
    sendMessage,
    editMessage,
    regenerateMessage,
    deleteMessage,
    insertSeparator,
    clearAllMessages,
    stopGeneration,
    updateModelId,
    updateAssistantId,
    clearFollowupQuestions,
  };
}
