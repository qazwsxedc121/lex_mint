import type { Dispatch, SetStateAction } from 'react';

import type { CostInfo, Message, TokenUsage } from '../../../types/message';

export type GroupProjectionEvent = {
  type: string;
  [key: string]: unknown;
};

export type GroupTimelineProjectionInput = {
  type: string;
  mode?: string;
  round?: number;
  max_rounds?: number;
  action?: string;
  reason?: string;
  supervisor_id?: string;
  supervisor_name?: string;
  assistant_id?: string;
  assistant_name?: string;
  assistant_ids?: string[];
  assistant_names?: string[];
  instruction?: string;
  rounds?: number;
};

export function isGroupAssistantProjectionEvent(event: GroupProjectionEvent): boolean {
  return (
    event.type === 'assistant_start'
    || event.type === 'assistant_chunk'
    || event.type === 'assistant_done'
    || event.type === 'assistant_message_id'
    || event.type === 'usage'
    || event.type === 'sources'
    || event.type === 'thinking_duration'
  );
}

export function isGroupOrchestrationProjectionEvent(event: GroupProjectionEvent): boolean {
  return event.type === 'group_round_start' || event.type === 'group_action' || event.type === 'group_done';
}

export function shouldActivateGroupProjectionMode(event: GroupProjectionEvent): boolean {
  const hasGroupIdentity =
    typeof event.assistant_turn_id === 'string'
    || typeof event.assistant_id === 'string';
  return (isGroupAssistantProjectionEvent(event) && hasGroupIdentity) || isGroupOrchestrationProjectionEvent(event);
}

export function toGroupTimelineProjectionInput(event: GroupProjectionEvent): GroupTimelineProjectionInput | null {
  if (!isGroupOrchestrationProjectionEvent(event)) {
    return null;
  }

  return {
    type: event.type,
    mode: typeof event.mode === 'string' ? event.mode : undefined,
    round: typeof event.round === 'number' ? event.round : undefined,
    max_rounds: typeof event.max_rounds === 'number' ? event.max_rounds : undefined,
    action: typeof event.action === 'string' ? event.action : undefined,
    reason: typeof event.reason === 'string' ? event.reason : undefined,
    supervisor_id: typeof event.supervisor_id === 'string' ? event.supervisor_id : undefined,
    supervisor_name: typeof event.supervisor_name === 'string' ? event.supervisor_name : undefined,
    assistant_id: typeof event.assistant_id === 'string' ? event.assistant_id : undefined,
    assistant_name: typeof event.assistant_name === 'string' ? event.assistant_name : undefined,
    assistant_ids: Array.isArray(event.assistant_ids)
      ? event.assistant_ids.filter((value): value is string => typeof value === 'string')
      : undefined,
    assistant_names: Array.isArray(event.assistant_names)
      ? event.assistant_names.filter((value): value is string => typeof value === 'string')
      : undefined,
    instruction: typeof event.instruction === 'string' ? event.instruction : undefined,
    rounds: typeof event.rounds === 'number' ? event.rounds : undefined,
  };
}

export function parseAssistantStartProjectionEvent(event: GroupProjectionEvent): {
  assistantId: string;
  assistantTurnId: string;
  assistantName: string;
  assistantIcon?: string;
} | null {
  if (event.type !== 'assistant_start') {
    return null;
  }

  const assistantId = typeof event.assistant_id === 'string' ? event.assistant_id : null;
  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  const assistantName = typeof event.name === 'string' ? event.name : '';
  const assistantIcon = typeof event.icon === 'string' ? event.icon : undefined;
  if (!assistantId || !assistantTurnId) {
    return null;
  }

  return { assistantId, assistantTurnId, assistantName, assistantIcon };
}

export function parseAssistantChunkProjectionEvent(event: GroupProjectionEvent): {
  assistantTurnId: string;
  chunk: string;
} | null {
  if (event.type !== 'assistant_chunk') {
    return null;
  }

  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  const chunk = typeof event.chunk === 'string' ? event.chunk : '';
  if (!assistantTurnId || !chunk) {
    return null;
  }

  return { assistantTurnId, chunk };
}

export function parseUsageProjectionEvent(event: GroupProjectionEvent): {
  assistantTurnId: string;
  usage: TokenUsage;
  cost?: CostInfo;
} | null {
  if (event.type !== 'usage') {
    return null;
  }

  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  const usage = event.usage as TokenUsage | undefined;
  const cost = event.cost as CostInfo | undefined;
  if (!assistantTurnId || !usage) {
    return null;
  }

  return { assistantTurnId, usage, cost };
}

export function parseSourcesProjectionEvent(event: GroupProjectionEvent): {
  assistantTurnId: string;
  sources: Message['sources'];
} | null {
  if (event.type !== 'sources') {
    return null;
  }

  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  const sources = event.sources as Message['sources'];
  if (!assistantTurnId || !sources) {
    return null;
  }

  return { assistantTurnId, sources };
}

export function parseThinkingDurationProjectionEvent(event: GroupProjectionEvent): {
  assistantTurnId: string;
  durationMs: number;
} | null {
  if (event.type !== 'thinking_duration') {
    return null;
  }

  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  const durationMs = typeof event.duration_ms === 'number' ? event.duration_ms : null;
  if (!assistantTurnId || durationMs === null) {
    return null;
  }

  return { assistantTurnId, durationMs };
}

export function parseAssistantMessageIdProjectionEvent(event: GroupProjectionEvent): {
  assistantTurnId: string;
  messageId: string;
} | null {
  if (event.type !== 'assistant_message_id') {
    return null;
  }

  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  const messageId = typeof event.message_id === 'string' ? event.message_id : null;
  if (!assistantTurnId || !messageId) {
    return null;
  }

  return { assistantTurnId, messageId };
}

export function parseAssistantDoneProjectionEvent(event: GroupProjectionEvent): {
  assistantTurnId: string;
} | null {
  if (event.type !== 'assistant_done') {
    return null;
  }

  const assistantTurnId = typeof event.assistant_turn_id === 'string' ? event.assistant_turn_id : null;
  if (!assistantTurnId) {
    return null;
  }

  return { assistantTurnId };
}

type UpdateAssistantMessage = (
  updater: (message: Message) => Message,
  options?: { assistantTurnId?: string | null; allowSingleFallback?: boolean },
) => void;

type ApplyGroupProjectionEventArgs = {
  event: GroupProjectionEvent;
  activateRuntimeGroupChatMode: () => void;
  runtimeIsGroupChat: boolean;
  appendGroupTimelineEvent: (event: GroupTimelineProjectionInput) => void;
  updateAssistantMessage: UpdateAssistantMessage;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setTotalUsage?: Dispatch<SetStateAction<TokenUsage | null>>;
  setTotalCost?: Dispatch<SetStateAction<CostInfo | null>>;
  setLastPromptTokens?: Dispatch<SetStateAction<number | null>>;
  getActiveAssistantTurnId: () => string | null;
  setActiveAssistantTurnId: (value: string | null) => void;
  nowTimestamp: () => string;
};

export function applyGroupProjectionEvent({
  event,
  activateRuntimeGroupChatMode,
  runtimeIsGroupChat,
  appendGroupTimelineEvent,
  updateAssistantMessage,
  setMessages,
  setTotalUsage,
  setTotalCost,
  setLastPromptTokens,
  getActiveAssistantTurnId,
  setActiveAssistantTurnId,
  nowTimestamp,
}: ApplyGroupProjectionEventArgs): void {
  if (shouldActivateGroupProjectionMode(event)) {
    activateRuntimeGroupChatMode();
  }
  if (!runtimeIsGroupChat) {
    return;
  }

  const timelineEventInput = toGroupTimelineProjectionInput(event);
  if (timelineEventInput) {
    appendGroupTimelineEvent(timelineEventInput);
    return;
  }

  switch (event.type) {
    case 'assistant_start': {
      const assistantStart = parseAssistantStartProjectionEvent(event);
      if (!assistantStart) {
        return;
      }
      const { assistantId, assistantTurnId, assistantName, assistantIcon } = assistantStart;
      setActiveAssistantTurnId(assistantTurnId);
      setMessages((prev) => {
        const newMessages = [...prev];
        const exists = newMessages.some(
          (message) => message.role === 'assistant' && message.assistant_turn_id === assistantTurnId,
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
      const assistantChunk = parseAssistantChunkProjectionEvent(event);
      if (!assistantChunk) {
        return;
      }
      const { assistantTurnId, chunk } = assistantChunk;
      updateAssistantMessage(
        (message) => ({ ...message, content: `${message.content || ''}${chunk}` }),
        { assistantTurnId, allowSingleFallback: false },
      );
      return;
    }
    case 'usage': {
      const usageEvent = parseUsageProjectionEvent(event);
      if (!usageEvent) {
        return;
      }
      const { assistantTurnId, usage, cost } = usageEvent;
      updateAssistantMessage(
        (message) => ({ ...message, usage, cost }),
        { assistantTurnId, allowSingleFallback: false },
      );
      setTotalUsage?.((prev) => (prev ? {
        prompt_tokens: prev.prompt_tokens + usage.prompt_tokens,
        completion_tokens: prev.completion_tokens + usage.completion_tokens,
        total_tokens: prev.total_tokens + usage.total_tokens,
      } : usage));
      if (cost) {
        setTotalCost?.((prev) => (prev ? {
          ...prev,
          total_cost: prev.total_cost + cost.total_cost,
        } : cost));
      }
      setLastPromptTokens?.(usage.prompt_tokens);
      return;
    }
    case 'sources': {
      const sourcesEvent = parseSourcesProjectionEvent(event);
      if (!sourcesEvent) {
        return;
      }
      const { assistantTurnId, sources } = sourcesEvent;
      updateAssistantMessage(
        (message) => ({ ...message, sources }),
        { assistantTurnId, allowSingleFallback: false },
      );
      return;
    }
    case 'thinking_duration': {
      const thinkingDurationEvent = parseThinkingDurationProjectionEvent(event);
      if (!thinkingDurationEvent) {
        return;
      }
      const { assistantTurnId, durationMs } = thinkingDurationEvent;
      updateAssistantMessage(
        (message) => ({ ...message, thinkingDurationMs: durationMs }),
        { assistantTurnId, allowSingleFallback: false },
      );
      return;
    }
    case 'assistant_message_id': {
      const assistantMessageIdEvent = parseAssistantMessageIdProjectionEvent(event);
      if (!assistantMessageIdEvent) {
        return;
      }
      const { assistantTurnId, messageId } = assistantMessageIdEvent;
      updateAssistantMessage(
        (message) => ({ ...message, message_id: messageId }),
        { assistantTurnId, allowSingleFallback: false },
      );
      return;
    }
    case 'assistant_done': {
      const assistantDoneEvent = parseAssistantDoneProjectionEvent(event);
      if (assistantDoneEvent && getActiveAssistantTurnId() === assistantDoneEvent.assistantTurnId) {
        setActiveAssistantTurnId(null);
      }
      return;
    }
    default:
      return;
  }
}
