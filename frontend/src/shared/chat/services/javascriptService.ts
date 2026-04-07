import JavaScriptWorker from '../workers/javascript.worker.ts?worker';

interface JavaScriptRunPayload {
  stdout: string;
  stderr: string;
  value: string;
}

interface JavaScriptWorkerResultMessage {
  type: 'result';
  id: string;
  payload?: JavaScriptRunPayload;
  error?: string;
}

export interface JavaScriptExecutionResult {
  stdout: string;
  stderr: string;
  value: string;
}

interface ResolverEntry {
  resolve: (value: JavaScriptExecutionResult) => void;
  reject: (error: Error) => void;
  timeoutId: number;
}

class JavaScriptService {
  private worker: Worker | null = null;
  private resolvers = new Map<string, ResolverEntry>();

  private getWorker(): Worker {
    if (!this.worker) {
      this.worker = new JavaScriptWorker();
      this.worker.onmessage = (event: MessageEvent<JavaScriptWorkerResultMessage>) => {
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

  runJavaScript(code: string, timeoutMs: number = 30000): Promise<JavaScriptExecutionResult> {
    const worker = this.getWorker();
    const requestId = `js_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    return new Promise<JavaScriptExecutionResult>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        this.resolvers.delete(requestId);
        reject(new Error('JavaScript execution timed out'));
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

export const javascriptService = new JavaScriptService();
