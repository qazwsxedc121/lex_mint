/// <reference lib="webworker" />

interface PyodideRunRequest {
  type: 'run';
  id: string;
  code: string;
}

interface PyodideRunResult {
  stdout: string;
  stderr: string;
  value: string;
}

interface PyodideRunSuccessMessage {
  type: 'result';
  id: string;
  payload: PyodideRunResult;
}

interface PyodideRunErrorMessage {
  type: 'result';
  id: string;
  error: string;
}

type PyodideWorkerResponse = PyodideRunSuccessMessage | PyodideRunErrorMessage;

type PyodideGlobal = {
  runPythonAsync: (code: string) => Promise<unknown>;
  setStdout: (options: { raw: (charCode: number) => void }) => void;
  setStderr: (options: { raw: (charCode: number) => void }) => void;
};

const PYODIDE_INDEX_URL = new URL('/pyodide/', self.location.origin).toString();
const PYODIDE_MODULE_URL = new URL('pyodide.mjs', PYODIDE_INDEX_URL).toString();

let pyodidePromise: Promise<PyodideGlobal> | null = null;

const getPyodide = async (): Promise<PyodideGlobal> => {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const pyodideModule = await import(/* @vite-ignore */ PYODIDE_MODULE_URL);
      const pyodide = await pyodideModule.loadPyodide({
        indexURL: PYODIDE_INDEX_URL,
      });
      return pyodide as PyodideGlobal;
    })();
  }
  return pyodidePromise;
};

const stringifyValue = (value: unknown): string => {
  if (value == null) {
    return '';
  }
  if (typeof value === 'string') {
    return value;
  }
  try {
    if (typeof value === 'object' && value && 'toJs' in value) {
      const maybeToJs = value as { toJs?: () => unknown };
      if (typeof maybeToJs.toJs === 'function') {
        return stringifyValue(maybeToJs.toJs());
      }
    }
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  } catch {
    return String(value);
  }
};

self.onmessage = async (event: MessageEvent<PyodideRunRequest>) => {
  const message = event.data;
  if (!message || message.type !== 'run') {
    return;
  }

  const { id, code } = message;
  let stdout = '';
  let stderr = '';

  try {
    const pyodide = await getPyodide();

    pyodide.setStdout({
      raw: (charCode: number) => {
        stdout += String.fromCharCode(charCode);
      },
    });
    pyodide.setStderr({
      raw: (charCode: number) => {
        stderr += String.fromCharCode(charCode);
      },
    });

    const value = await pyodide.runPythonAsync(code);

    const response: PyodideWorkerResponse = {
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
    const response: PyodideWorkerResponse = {
      type: 'result',
      id,
      error: error instanceof Error ? error.message : String(error),
    };
    self.postMessage(response);
  }
};
