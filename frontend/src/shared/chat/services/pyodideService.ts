import PyodideWorker from '../workers/pyodide.worker.ts?worker';

interface PyodideRunPayload {
  stdout: string;
  stderr: string;
  value: string;
}

interface PyodideWorkerResultMessage {
  type: 'result';
  id: string;
  payload?: PyodideRunPayload;
  error?: string;
}

export interface PyodideExecutionResult {
  stdout: string;
  stderr: string;
  value: string;
}

interface ResolverEntry {
  resolve: (value: PyodideExecutionResult) => void;
  reject: (error: Error) => void;
  timeoutId: number;
}

class PyodideService {
  private worker: Worker | null = null;
  private resolvers = new Map<string, ResolverEntry>();

  private getWorker(): Worker {
    if (!this.worker) {
      this.worker = new PyodideWorker();
      this.worker.onmessage = (event: MessageEvent<PyodideWorkerResultMessage>) => {
        const message = event.data;
        if (!message || message.type !== 'result' || !message.id) {
          return;
        }
        const resolver = this.resolvers.get(message.id);
        if (!resolver) {
          return;
        }
        this.resolvers.delete(message.id);
        window.clearTimeout(resolver.timeoutId);

        if (message.error) {
          resolver.reject(new Error(message.error));
          return;
        }
        resolver.resolve({
          stdout: message.payload?.stdout || '',
          stderr: message.payload?.stderr || '',
          value: message.payload?.value || '',
        });
      };
    }
    return this.worker;
  }

  runPython(code: string, timeoutMs: number = 30000): Promise<PyodideExecutionResult> {
    const worker = this.getWorker();
    const requestId = `pyodide_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    return new Promise<PyodideExecutionResult>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        this.resolvers.delete(requestId);
        reject(new Error('Python execution timed out'));
      }, timeoutMs);

      this.resolvers.set(requestId, { resolve, reject, timeoutId });
      worker.postMessage({
        type: 'run',
        id: requestId,
        code,
      });
    });
  }
}

export const pyodideService = new PyodideService();
