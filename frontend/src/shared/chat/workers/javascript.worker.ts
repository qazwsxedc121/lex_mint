/// <reference lib="webworker" />

interface JavaScriptRunRequest {
  type: 'run';
  id: string;
  code: string;
}

interface JavaScriptRunResult {
  stdout: string;
  stderr: string;
  value: string;
}

interface JavaScriptRunSuccessMessage {
  type: 'result';
  id: string;
  payload: JavaScriptRunResult;
}

interface JavaScriptRunErrorMessage {
  type: 'result';
  id: string;
  error: string;
}

type JavaScriptWorkerResponse = JavaScriptRunSuccessMessage | JavaScriptRunErrorMessage;

const AsyncFunction = Object.getPrototypeOf(async function () {
  return undefined;
}).constructor as new (code: string) => () => Promise<unknown>;

const stringifyValue = (value: unknown): string => {
  if (value == null) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  } catch {
    return String(value);
  }
};

self.onmessage = async (event: MessageEvent<JavaScriptRunRequest>) => {
  const message = event.data;
  if (!message || message.type !== 'run') {
    return;
  }

  const { id, code } = message;
  let stdout = '';
  let stderr = '';

  const originalConsole = {
    log: console.log,
    info: console.info,
    warn: console.warn,
    error: console.error,
  };

  const append = (buffer: 'stdout' | 'stderr', args: unknown[]) => {
    const text = args.map((item) => stringifyValue(item)).join(' ');
    if (buffer === 'stderr') {
      stderr += `${text}\n`;
      return;
    }
    stdout += `${text}\n`;
  };

  try {
    console.log = (...args: unknown[]) => append('stdout', args);
    console.info = (...args: unknown[]) => append('stdout', args);
    console.warn = (...args: unknown[]) => append('stderr', args);
    console.error = (...args: unknown[]) => append('stderr', args);

    const fn = new AsyncFunction(`"use strict";\n${code}`);
    const value = await fn();

    const response: JavaScriptWorkerResponse = {
      type: 'result',
      id,
      payload: {
        stdout,
        stderr,
        value: stringifyValue(value),
      },
    };
    self.postMessage(response);
  } catch (error) {
    const response: JavaScriptWorkerResponse = {
      type: 'result',
      id,
      error: error instanceof Error ? `${error.name}: ${error.message}` : String(error),
    };
    self.postMessage(response);
  } finally {
    console.log = originalConsole.log;
    console.info = originalConsole.info;
    console.warn = originalConsole.warn;
    console.error = originalConsole.error;
  }
};
