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
