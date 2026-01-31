/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect, useRef } from 'react';
import type { Message, TokenUsage, CostInfo, UploadedFile } from '../../../types/message';
import { getSession, sendMessageStream, deleteMessage as apiDeleteMessage } from '../../../services/api';

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentModelId, setCurrentModelId] = useState<string | null>(null);
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null);
  const [totalUsage, setTotalUsage] = useState<TokenUsage | null>(null);
  const [totalCost, setTotalCost] = useState<CostInfo | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isProcessingRef = useRef(false);

  // Load session messages when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      setCurrentModelId(null);
      setCurrentAssistantId(null);
      setTotalUsage(null);
      setTotalCost(null);
      return;
    }

    const loadSession = async () => {
      try {
        setLoading(true);
        setError(null);
        const session = await getSession(sessionId);
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

    loadSession();
  }, [sessionId]);

  const sendMessage = async (content: string, options?: { reasoningEffort?: string; attachments?: UploadedFile[] }) => {
    if (!sessionId || (!content.trim() && !options?.attachments?.length) || isProcessingRef.current) return;

    isProcessingRef.current = true;

    // Optimistically add user message to UI (with attachments if any)
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

    // Add placeholder for assistant message
    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';

    try {
      await sendMessageStream(
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
        options?.attachments,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(prev => prev.slice(0, -2));
    }
  };

  const editMessage = async (messageIndex: number, newContent: string) => {
    if (!sessionId || isProcessingRef.current) return;

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
    const updatedUserMessage: Message = { role: 'user', content: newContent };
    setMessages([...truncatedMessages, updatedUserMessage]);

    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';

    try {
      await sendMessageStream(
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
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to edit message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      setMessages(originalMessages);
    }
  };

  const regenerateMessage = async (messageIndex: number) => {
    if (!sessionId || isProcessingRef.current) return;

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

    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';

    try {
      await sendMessageStream(
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

  const deleteMessage = async (messageIndex: number) => {
    if (!sessionId || isProcessingRef.current) return;

    isProcessingRef.current = true;
    const originalMessages = [...messages];

    // Optimistically remove the message from UI
    setMessages(prev => prev.filter((_, index) => index !== messageIndex));

    try {
      await apiDeleteMessage(sessionId, messageIndex);
    } catch (err) {
      // Revert on error
      setError(err instanceof Error ? err.message : 'Failed to delete message');
      setMessages(originalMessages);
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

  return {
    messages,
    loading,
    error,
    isStreaming,
    currentModelId,
    currentAssistantId,
    totalUsage,
    totalCost,
    sendMessage,
    editMessage,
    regenerateMessage,
    deleteMessage,
    stopGeneration,
    updateModelId,
    updateAssistantId,
  };
}
