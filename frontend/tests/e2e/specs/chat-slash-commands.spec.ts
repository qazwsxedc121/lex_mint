import { test, expect, request as pwRequest } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

test.describe('Chat slash commands', () => {
  test('autocomplete /btw and send temporary turn payload', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let sessionId = '';
    let streamRequestBody: Record<string, unknown> | null = null;

    try {
      const createRes = await api.post('/api/sessions?context_type=chat', { data: {} });
      expect(createRes.ok()).toBeTruthy();

      const created = await createRes.json();
      sessionId = created.session_id as string;
      expect(sessionId).toMatch(/^[a-f0-9-]+$/);

      await page.route('**/api/chat/stream', async (route) => {
        if (route.request().method() !== 'POST') {
          await route.continue();
          return;
        }

        streamRequestBody = route.request().postDataJSON() as Record<string, unknown>;
        const sseBody = [
          'data: {"flow_event":{"event_id":"e1","seq":1,"ts":1,"stream_id":"stream-e2e-slash","event_type":"stream_started","stage":"transport","payload":{}}}',
          '',
          'data: {"flow_event":{"event_id":"e2","seq":2,"ts":2,"stream_id":"stream-e2e-slash","event_type":"stream_ended","stage":"transport","payload":{}}}',
          '',
        ].join('\n');

        await route.fulfill({
          status: 200,
          headers: {
            'content-type': 'text/event-stream',
            'cache-control': 'no-cache',
            connection: 'keep-alive',
          },
          body: sseBody,
        });
      });

      await page.goto(`/chat/${sessionId}`);
      await expect(page.locator('[data-name="chat-view-root"]')).toBeVisible();

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();

      await input.fill('/b');
      const slashMenu = page.locator('[data-name="input-box-slash-menu"]');
      await expect(slashMenu).toBeVisible();
      await expect(slashMenu).toContainText(/\/btw/i);
      await expect(slashMenu).toContainText(/temporary|临时/i);

      await input.press('Enter');
      await expect(input).toHaveValue('/btw ');

      const marker = `slash-e2e-${Date.now()}`;
      await input.type(marker);
      await input.press('Enter');

      await expect.poll(() => streamRequestBody !== null, { timeout: 10000 }).toBeTruthy();
      expect(streamRequestBody?.temporary_turn).toBe(true);
      expect(streamRequestBody?.message).toBe(marker);
    } finally {
      if (sessionId) {
        await api.delete(`/api/sessions/${sessionId}?context_type=chat`);
      }
      await api.dispose();
    }
  });
});
