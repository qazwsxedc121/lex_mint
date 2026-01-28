/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect, useRef } from 'react';
import type { Message } from '../types/message';
import { getSession, sendMessageStream } from '../services/api';

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentModelId, setCurrentModelId] = useState<string | null>(null);
  const [currentAssistantId, setCurrentAssistantId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isProcessingRef = useRef(false); // Prevent concurrent operations

  // Load session messages when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      setCurrentModelId(null);
      setCurrentAssistantId(null);
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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load session');
        setMessages([]);
        setCurrentModelId(null);
        setCurrentAssistantId(null);
      } finally {
        setLoading(false);
      }
    };

    loadSession();
  }, [sessionId]);

  const sendMessage = async (content: string) => {
    if (!sessionId || !content.trim() || isProcessingRef.current) return;

    isProcessingRef.current = true;

    // Optimistically add user message to UI
    const userMessage: Message = { role: 'user', content };
    setMessages(prev => [...prev, userMessage]);

    // Add placeholder for assistant message (will be updated with streaming content)
    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    // 使用局部变量累积流式内容（避免闭包问题）
    let streamedContent = '';

    try {
      // 流式接收 AI 响应
      await sendMessageStream(
        sessionId,
        content,
        null, // truncateAfterIndex
        false, // skipUserMessage
        // onChunk: 收到每个 token
        (chunk: string) => {
          // 累积内容
          streamedContent += chunk;

          // 更新消息（创建新对象而不是修改）
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;

            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              // 创建新的消息对象
              newMessages[lastIndex] = {
                role: 'assistant',
                content: streamedContent
              };
            }

            return newMessages;
          });
        },
        // onDone: 流式传输完成
        () => {
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
        },
        // onError: 错误处理
        (error: string) => {
          setError(error);
          setLoading(false);
          setIsStreaming(false);
          isProcessingRef.current = false;
          // Remove both the user message and the placeholder assistant message on error
          setMessages(prev => prev.slice(0, -2));
        },
        abortControllerRef
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      // Remove both messages on error
      setMessages(prev => prev.slice(0, -2));
    }
  };

  const editMessage = async (messageIndex: number, newContent: string) => {
    if (!sessionId || isProcessingRef.current) return;

    // 验证是用户消息
    if (messages[messageIndex]?.role !== 'user') {
      console.error('Can only edit user messages');
      return;
    }

    // 确认操作（如果是中间消息）
    if (messageIndex < messages.length - 1) {
      const confirmed = window.confirm('编辑此消息将删除后续所有消息。是否继续？');
      if (!confirmed) return;
    }

    isProcessingRef.current = true;

    // 保存原始消息用于回滚
    const originalMessages = [...messages];

    // 截断并更新消息列表（本地更新）
    const truncatedMessages = messages.slice(0, messageIndex);
    const updatedUserMessage: Message = { role: 'user', content: newContent };
    setMessages([...truncatedMessages, updatedUserMessage]);

    // 添加占位符助手消息
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
        messageIndex - 1, // 截断到当前消息的前一条
        false, // 不跳过用户消息
        (chunk: string) => {
          streamedContent += chunk;
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { role: 'assistant', content: streamedContent };
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
          // 回滚到原始状态
          setMessages(originalMessages);
        },
        abortControllerRef
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to edit message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      // 回滚到原始状态
      setMessages(originalMessages);
    }
  };

  const regenerateMessage = async (messageIndex: number) => {
    if (!sessionId || isProcessingRef.current) return;

    // 验证是助手消息
    if (messages[messageIndex]?.role !== 'assistant') {
      console.error('Can only regenerate assistant messages');
      return;
    }

    // 确认操作（如果不是最后一条）
    if (messageIndex < messages.length - 1) {
      const confirmed = window.confirm('重新生成此消息将删除后续所有消息。是否继续？');
      if (!confirmed) return;
    }

    // 获取前一条用户消息
    const previousUserMessage = messages[messageIndex - 1];
    if (!previousUserMessage || previousUserMessage.role !== 'user') {
      console.error('No user message found before assistant message');
      return;
    }

    isProcessingRef.current = true;

    // 保存原始消息用于回滚
    const originalMessages = [...messages];

    // 截断到助手消息之前，保留用户消息
    const truncatedMessages = messages.slice(0, messageIndex);
    setMessages(truncatedMessages);

    // 添加新的占位符助手消息
    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setIsStreaming(true);
    setError(null);

    let streamedContent = '';

    try {
      await sendMessageStream(
        sessionId,
        previousUserMessage.content, // 使用之前的用户消息
        messageIndex - 1, // 截断到用户消息（包含）
        true, // 跳过追加用户消息（因为已经存在）
        (chunk: string) => {
          streamedContent += chunk;
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
              newMessages[lastIndex] = { role: 'assistant', content: streamedContent };
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
          // 回滚到原始状态
          setMessages(originalMessages);
        },
        abortControllerRef
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate message');
      setLoading(false);
      setIsStreaming(false);
      isProcessingRef.current = false;
      // 回滚到原始状态
      setMessages(originalMessages);
    }
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      console.log('Stopping generation...');
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
    sendMessage,
    editMessage,
    regenerateMessage,
    stopGeneration,
    updateModelId,
    updateAssistantId,
  };
}
