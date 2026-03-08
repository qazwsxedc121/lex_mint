import type { MutableRefObject } from 'react';
import { asString, iterateSSEData, parseFlowEvent } from './flowEvents';
import type { FlowEvent } from './flowEvents';

type FlowEventConsumerResult = 'continue' | 'stop';

type ConsumeFlowEventResponseArgs = {
  response: Response;
  onInvalidPayload: () => void;
  onStreamError: (message: string) => void;
  onFlowEvent: (flowEvent: FlowEvent) => FlowEventConsumerResult | void;
};

type PostFlowEventStreamArgs = {
  url: string;
  body: unknown;
  abortControllerRef?: MutableRefObject<AbortController | null>;
  onAbort?: () => void;
  onInvalidPayload: () => void;
  onStreamError: (message: string) => void;
  onFlowEvent: (flowEvent: FlowEvent) => FlowEventConsumerResult | void;
};

export async function consumeFlowEventResponse({
  response,
  onInvalidPayload,
  onStreamError,
  onFlowEvent,
}: ConsumeFlowEventResponseArgs): Promise<void> {
  const reader = response.body?.getReader();

  if (!reader) {
    throw new Error('Response body is not readable');
  }

  try {
    for await (const dataStr of iterateSSEData(reader)) {
      try {
        const data = JSON.parse(dataStr);
        const flowEvent = parseFlowEvent(data.flow_event);
        if (!flowEvent) {
          onInvalidPayload();
          return;
        }

        if (flowEvent.event_type === 'stream_error') {
          onStreamError(asString(flowEvent.payload.error) || 'Stream error');
          return;
        }

        if (onFlowEvent(flowEvent) === 'stop') {
          return;
        }
      } catch {
        continue;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function postFlowEventStream({
  url,
  body,
  abortControllerRef,
  onAbort,
  onInvalidPayload,
  onStreamError,
  onFlowEvent,
}: PostFlowEventStreamArgs): Promise<void> {
  const controller = new AbortController();
  if (abortControllerRef) {
    abortControllerRef.current = controller;
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    await consumeFlowEventResponse({
      response,
      onInvalidPayload,
      onStreamError,
      onFlowEvent,
    });
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      onAbort?.();
      return;
    }
    throw error;
  } finally {
    if (abortControllerRef) {
      abortControllerRef.current = null;
    }
  }
}
