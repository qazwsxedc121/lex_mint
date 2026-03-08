export type FlowEventStage = 'transport' | 'content' | 'tool' | 'orchestration' | 'meta';

export interface FlowEvent {
  event_id: string;
  seq: number;
  ts: number;
  stream_id: string;
  conversation_id?: string;
  turn_id?: string;
  event_type: string;
  stage: FlowEventStage;
  payload: Record<string, unknown>;
}

export async function* iterateSSEData(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<string, void, unknown> {
  let buffer = '';
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replace(/\r\n/g, '\n');

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const dataLines = rawEvent
        .split('\n')
        .map((line) => line.trimEnd())
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart());

      if (dataLines.length > 0) {
        yield dataLines.join('\n');
      }

      boundary = buffer.indexOf('\n\n');
    }

    if (done) {
      break;
    }
  }

  const trailing = buffer.trim();
  if (!trailing) {
    return;
  }

  const trailingDataLines = trailing
    .split('\n')
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart());

  if (trailingDataLines.length > 0) {
    yield trailingDataLines.join('\n');
  }
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

export function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

export function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' ? value : undefined;
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function parseFlowEvent(value: unknown): FlowEvent | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }

  const stage = record.stage;
  if (
    stage !== 'transport' &&
    stage !== 'content' &&
    stage !== 'tool' &&
    stage !== 'orchestration' &&
    stage !== 'meta'
  ) {
    return null;
  }

  const eventId = asString(record.event_id);
  const eventType = asString(record.event_type);
  const streamId = asString(record.stream_id);
  const seq = asNumber(record.seq);
  const ts = asNumber(record.ts);
  const payload = asRecord(record.payload) || {};

  if (!eventId || !eventType || !streamId || seq === undefined || ts === undefined) {
    return null;
  }

  return {
    event_id: eventId,
    seq,
    ts,
    stream_id: streamId,
    conversation_id: asString(record.conversation_id),
    turn_id: asString(record.turn_id),
    event_type: eventType,
    stage,
    payload,
  };
}
