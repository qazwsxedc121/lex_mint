/**
 * Custom hook for managing chat functionality.
 */

import { useState, useEffect } from 'react';
import type { Message } from '../types/message';
import { getSession, sendMessageStream } from '../services/api';

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load session messages when sessionId changes
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    const loadSession = async () => {
      try {
        setLoading(true);
        setError(null);
        const session = await getSession(sessionId);
        setMessages(session.state.messages);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load session');
        setMessages([]);
      } finally {
        setLoading(false);
      }
    };

    loadSession();
  }, [sessionId]);

  const sendMessage = async (content: string) => {
    if (!sessionId || !content.trim()) return;

    // Optimistically add user message to UI
    const userMessage: Message = { role: 'user', content };
    setMessages(prev => [...prev, userMessage]);

    // Add placeholder for assistant message (will be updated with streaming content)
    const assistantMessage: Message = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMessage]);

    setLoading(true);
    setError(null);

    // 使用局部变量累积流式内容（避免闭包问题）
    let streamedContent = '';

    try {
      // 流式接收 AI 响应
      await sendMessageStream(
        sessionId,
        content,
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
        },
        // onError: 错误处理
        (error: string) => {
          setError(error);
          setLoading(false);
          // Remove both the user message and the placeholder assistant message on error
          setMessages(prev => prev.slice(0, -2));
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      setLoading(false);
      // Remove both messages on error
      setMessages(prev => prev.slice(0, -2));
    }
  };

  return {
    messages,
    loading,
    error,
    sendMessage,
  };
}
