import type { Dispatch, SetStateAction } from 'react';
import type { Message } from '../../../types/message';
import type { GroupProjectionEvent } from './useChatGroupProjection';

type UpdateAssistantMessage = (
  updater: (message: Message) => Message,
  options?: { assistantId?: string | null; assistantTurnId?: string | null; allowSingleFallback?: boolean },
) => void;

type ApplyGroupEventProjection = (
  event: GroupProjectionEvent,
  runtimeIsGroupChat: boolean,
  activateRuntimeGroupChatMode: () => void,
  updateAssistantMessage: UpdateAssistantMessage,
  activeAssistantTurnIdRef: { current: string | null },
) => void;

type CreateChatStreamProjectionRuntimeArgs = {
  getRuntimeIsGroupChat: () => boolean;
  setRuntimeIsGroupChat: (value: boolean) => void;
  getActiveAssistantTurnId: () => string | null;
  setActiveAssistantTurnId: (value: string | null) => void;
  nowTimestamp: () => string;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  applyGroupEventProjection: ApplyGroupEventProjection;
};

export function createChatStreamProjectionRuntime({
  getRuntimeIsGroupChat,
  setRuntimeIsGroupChat,
  getActiveAssistantTurnId,
  setActiveAssistantTurnId,
  nowTimestamp,
  setMessages,
  applyGroupEventProjection,
}: CreateChatStreamProjectionRuntimeArgs) {
  const activateRuntimeGroupChatMode = () => {
    if (getRuntimeIsGroupChat()) {
      return;
    }
    setRuntimeIsGroupChat(true);
    setMessages((prev) => {
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

  const updateAssistantMessage: UpdateAssistantMessage = (updater, options) => {
    setMessages((prev) => {
      const newMessages = [...prev];
      let targetIndex = -1;
      const assistantTurnId = options?.assistantTurnId;
      const assistantId = options?.assistantId;
      const allowSingleFallback = options?.allowSingleFallback ?? true;
      const hasGroupAssistantMessages = newMessages.some(
        (message) => message.role === 'assistant' && !!message.assistant_id,
      );

      if (assistantTurnId) {
        for (let i = newMessages.length - 1; i >= 0; i -= 1) {
          if (newMessages[i].role === 'assistant' && newMessages[i].assistant_turn_id === assistantTurnId) {
            targetIndex = i;
            break;
          }
        }
      }

      if (targetIndex < 0 && assistantId) {
        for (let i = newMessages.length - 1; i >= 0; i -= 1) {
          if (newMessages[i].role === 'assistant' && newMessages[i].assistant_id === assistantId) {
            targetIndex = i;
            break;
          }
        }
      }

      if (targetIndex < 0) {
        if (!allowSingleFallback || getRuntimeIsGroupChat() || hasGroupAssistantMessages) {
          return prev;
        }
        for (let i = newMessages.length - 1; i >= 0; i -= 1) {
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

  const handleAssistantStart = (assistantId: string, name: string, icon?: string) => {
    if (!getRuntimeIsGroupChat()) {
      activateRuntimeGroupChatMode();
    }
    setActiveAssistantTurnId(null);
    setMessages((prev) => {
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
      }
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
  };

  const applyGroupEvent = (event: GroupProjectionEvent) => {
    const activeAssistantTurnIdRef = {
      get current() {
        return getActiveAssistantTurnId();
      },
      set current(value: string | null) {
        setActiveAssistantTurnId(value);
      },
    };

    applyGroupEventProjection(
      event,
      getRuntimeIsGroupChat(),
      activateRuntimeGroupChatMode,
      updateAssistantMessage,
      activeAssistantTurnIdRef,
    );
  };

  return {
    activateRuntimeGroupChatMode,
    updateAssistantMessage,
    handleAssistantStart,
    applyGroupEvent,
  };
}
