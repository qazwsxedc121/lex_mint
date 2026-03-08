import type { GroupTimelineEvent, Message } from '../../../types/message';

export const TOOL_CALL_CACHE_STORAGE_KEY = 'lex-mint.tool-calls.cache.v1';
export const TOOL_CALL_CACHE_LIMIT = 300;

export function nowTimestamp(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function loadToolCallCache(): Record<string, NonNullable<Message['toolCalls']>> {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const raw = window.sessionStorage.getItem(TOOL_CALL_CACHE_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') {
      return {};
    }

    const hydrated: Record<string, NonNullable<Message['toolCalls']>> = {};
    for (const [messageId, value] of Object.entries(parsed)) {
      if (!messageId || !Array.isArray(value) || value.length === 0) {
        continue;
      }
      hydrated[messageId] = value as NonNullable<Message['toolCalls']>;
    }
    return hydrated;
  } catch {
    return {};
  }
}

export function persistToolCallCache(cache: Record<string, NonNullable<Message['toolCalls']>>): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.sessionStorage.setItem(TOOL_CALL_CACHE_STORAGE_KEY, JSON.stringify(cache));
  } catch {
    // Ignore storage quota/availability errors.
  }
}

export function rememberToolCallsInCache(
  cache: Record<string, NonNullable<Message['toolCalls']>>,
  items: Message[],
  limit: number = TOOL_CALL_CACHE_LIMIT,
): boolean {
  let updated = false;
  for (const item of items) {
    if (
      item.role === 'assistant' &&
      item.message_id &&
      Array.isArray(item.toolCalls) &&
      item.toolCalls.length > 0
    ) {
      cache[item.message_id] = item.toolCalls;
      updated = true;
    }
  }

  if (!updated) {
    return false;
  }

  const messageIds = Object.keys(cache);
  if (messageIds.length > limit) {
    const trimCount = messageIds.length - limit;
    for (let i = 0; i < trimCount; i += 1) {
      delete cache[messageIds[i]];
    }
  }

  return true;
}

export function mergeToolCallsFromCache(
  items: Message[],
  cache: Record<string, NonNullable<Message['toolCalls']>>,
): Message[] {
  return items.map((item) => {
    if (item.role !== 'assistant' || !item.message_id || (item.toolCalls && item.toolCalls.length > 0)) {
      return item;
    }

    const cachedToolCalls = cache[item.message_id];
    if (!cachedToolCalls || cachedToolCalls.length === 0) {
      return item;
    }

    return {
      ...item,
      toolCalls: cachedToolCalls,
    };
  });
}

type RawGroupTimelineEvent = {
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

export function buildGroupTimelineEvent(event: RawGroupTimelineEvent): GroupTimelineEvent | null {
  const eventType = event.type;
  if (
    eventType !== 'group_round_start' &&
    eventType !== 'group_action' &&
    eventType !== 'group_done'
  ) {
    return null;
  }

  return {
    event_id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    created_at: nowTimestamp(),
    type: eventType,
    mode: event.mode,
    round: event.round,
    max_rounds: event.max_rounds,
    action: event.action,
    reason: event.reason,
    supervisor_id: event.supervisor_id,
    supervisor_name: event.supervisor_name,
    assistant_id: event.assistant_id,
    assistant_name: event.assistant_name,
    assistant_ids: event.assistant_ids,
    assistant_names: event.assistant_names,
    instruction: event.instruction,
    rounds: event.rounds,
  };
}
