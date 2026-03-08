import type {
  ChatTargetType,
  CostInfo,
  GroupChatMode,
  GroupTimelineEvent,
  Message,
  ParamOverrides,
  SessionDetail,
  TokenUsage,
} from '../../../types/message';

export interface ChatSessionSnapshot {
  messages: Message[];
  currentModelId: string | null;
  currentAssistantId: string | null;
  currentTargetType: ChatTargetType;
  totalUsage: TokenUsage | null;
  totalCost: CostInfo | null;
  lastPromptTokens: number | null;
  paramOverrides: ParamOverrides;
  isTemporary: boolean;
  groupAssistants: string[] | null;
  groupMode: GroupChatMode | null;
  groupTimeline: GroupTimelineEvent[];
}

export function createEmptyChatSessionSnapshot(): ChatSessionSnapshot {
  return {
    messages: [],
    currentModelId: null,
    currentAssistantId: null,
    currentTargetType: 'model',
    totalUsage: null,
    totalCost: null,
    lastPromptTokens: null,
    paramOverrides: {},
    isTemporary: false,
    groupAssistants: null,
    groupMode: null,
    groupTimeline: [],
  };
}

export function deriveLastPromptTokens(messages: Message[]): number | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === 'assistant' && messages[i].usage?.prompt_tokens) {
      return messages[i].usage.prompt_tokens;
    }
  }
  return null;
}

export function inferSessionTargetType(session: SessionDetail): ChatTargetType {
  return session.target_type
    || (session.assistant_id && !session.assistant_id.startsWith('__legacy_model_') ? 'assistant' : 'model');
}

export function buildChatSessionSnapshot(
  session: SessionDetail,
  messages: Message[],
): ChatSessionSnapshot {
  return {
    messages,
    currentModelId: session.model_id || null,
    currentAssistantId: session.assistant_id || null,
    currentTargetType: inferSessionTargetType(session),
    totalUsage: session.total_usage || null,
    totalCost: session.total_cost || null,
    lastPromptTokens: deriveLastPromptTokens(session.state.messages),
    paramOverrides: session.param_overrides || {},
    isTemporary: session.temporary || false,
    groupAssistants: session.group_assistants || null,
    groupMode: session.group_mode || (session.group_assistants && session.group_assistants.length >= 2 ? 'round_robin' : null),
    groupTimeline: [],
  };
}
