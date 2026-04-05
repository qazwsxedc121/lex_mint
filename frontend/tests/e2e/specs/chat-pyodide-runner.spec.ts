import { test, expect, request as pwRequest } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

function buildFlowEvent(
  seq: number,
  eventType: string,
  stage: 'transport' | 'content' | 'tool' | 'orchestration' | 'meta',
  payload: Record<string, unknown>,
  streamId: string = 'stream-e2e-pyodide',
) {
  return {
    flow_event: {
      event_id: `${streamId}-${seq}`,
      seq,
      ts: Date.now(),
      stream_id: streamId,
      event_type: eventType,
      stage,
      payload,
    },
  };
}

test.describe('Chat pyodide code runner', () => {
  test('runs assistant python code block and shows stdout/result', async ({ page }) => {
    test.slow();
    test.setTimeout(180000);

    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let sessionId = '';

    try {
      const createRes = await api.post('/api/sessions?context_type=chat', { data: {} });
      expect(createRes.ok()).toBeTruthy();
      const created = await createRes.json();
      sessionId = created.session_id as string;
      expect(sessionId).toMatch(/^[a-f0-9-]+$/);

      await page.route('**/pyodide/pyodide.mjs*', async (route) => {
        const mockModule = `
          export async function loadPyodide() {
            let stdoutHandler = null;
            let stderrHandler = null;
            return {
              async loadPackagesFromImports() {},
              setStdout({ batched }) { stdoutHandler = batched; },
              setStderr({ batched }) { stderrHandler = batched; },
              async runPythonAsync(code) {
                if (stdoutHandler && typeof code === 'string' && code.includes('e2e-pyodide-ok')) {
                  stdoutHandler('e2e-pyodide-ok\\n');
                } else if (stderrHandler) {
                  stderrHandler('');
                }
                return 21;
              }
            };
          }
        `;
        await route.fulfill({
          status: 200,
          contentType: 'application/javascript; charset=utf-8',
          body: mockModule,
        });
      });

      await page.route('**/api/chat/stream', async (route) => {
        const events = [
          buildFlowEvent(1, 'stream_started', 'transport', { context_type: 'chat' }),
          buildFlowEvent(2, 'text_delta', 'content', {
            text: [
              '```python',
              'print("e2e-pyodide-ok")',
              '7 * 3',
              '```',
            ].join('\n'),
          }),
          buildFlowEvent(3, 'stream_ended', 'transport', { done: true }),
        ];

        const sseBody = events.map((evt) => `data: ${JSON.stringify(evt)}\n\n`).join('');
        await route.fulfill({
          status: 200,
          headers: { 'content-type': 'text/event-stream; charset=utf-8' },
          body: sseBody,
        });
      });

      await page.goto(`/chat/${sessionId}`);
      await expect(page.locator('[data-name="chat-view-root"]')).toBeVisible();
      await expect(page).toHaveURL(new RegExp(`/chat/${sessionId}$`));

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();
      await input.fill('Please provide runnable python code.');

      const sendButton = page
        .locator('[data-name="input-box-input-controls"] button')
        .filter({ hasText: /Send|发送/ })
        .first();
      await expect(sendButton).toBeVisible();
      await sendButton.click();

      const codeBlock = page
        .locator('[data-name="code-block-root"]')
        .filter({ hasText: 'e2e-pyodide-ok' })
        .first();
      await expect(codeBlock).toBeVisible({ timeout: 15000 });

      const runButton = codeBlock.getByRole('button', { name: /^Run$/ });
      await expect(runButton).toBeVisible();
      for (let i = 0; i < 3; i += 1) {
        try {
          await runButton.click({ timeout: 10000 });
          break;
        } catch (error) {
          if (i === 2) {
            throw error;
          }
        }
      }
      await expect(codeBlock.getByRole('button', { name: /^Running$/ })).toBeVisible({ timeout: 5000 });

      const output = codeBlock.locator('[data-name="code-block-execution-output"]');
      await expect(output).toBeVisible({ timeout: 90000 });
      await expect(output).toContainText('stdout');
      await expect(output).toContainText('e2e-pyodide-ok', { timeout: 90000 });
      await expect(output).toContainText('result');
      await expect(output).toContainText('21');
    } finally {
      if (sessionId) {
        await api.delete(`/api/sessions/${sessionId}?context_type=chat`);
      }
      await api.dispose();
    }
  });
});
