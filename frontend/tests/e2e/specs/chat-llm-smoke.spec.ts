import { test, expect, request as pwRequest } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

test.describe('Chat LLM smoke', () => {
  test('send one message and receive one assistant reply', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let sessionId = '';

    try {
      const createRes = await api.post('/api/sessions?context_type=chat', { data: {} });
      expect(createRes.ok()).toBeTruthy();

      const created = await createRes.json();
      sessionId = created.session_id;
      expect(sessionId).toMatch(/^[a-f0-9-]+$/);

      await page.goto(`/chat/${sessionId}`);
      await expect(page.locator('[data-name="chat-view-root"]')).toBeVisible();

      const assistantBubbles = page.locator('[data-name="message-bubble-assistant"]');
      const beforeAssistantCount = await assistantBubbles.count();

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();

      const message = 'Please reply with one short sentence for this e2e smoke test.';
      await input.fill(message);
      await page.locator('[data-name="input-box-root"] button').filter({ hasText: /Send|发送/ }).click();

      await expect(page.locator('[data-name="message-bubble-user"]').last()).toContainText(message);

      await expect
        .poll(async () => await assistantBubbles.count(), {
          timeout: 180000,
          intervals: [1000, 2000, 3000, 5000],
        })
        .toBeGreaterThan(beforeAssistantCount);

      const lastAssistantContent = assistantBubbles
        .last()
        .locator('[data-name="message-bubble-content"]')
        .first();

      await expect(lastAssistantContent).toBeVisible();
      await expect(page.locator('[data-name="input-box-root"] button').filter({ hasText: /Stop|停止/ })).toHaveCount(0, {
        timeout: 180000,
      });

      await expect
        .poll(async () => {
          const text = (await lastAssistantContent.innerText()).trim();
          const isPlaceholder = /^Generating\.\.\.$/i.test(text) || /^生成中/.test(text);
          return isPlaceholder ? 0 : text.length;
        }, {
          timeout: 60000,
          intervals: [500, 1000, 2000],
        })
        .toBeGreaterThan(5);

      const assistantReply = (await lastAssistantContent.innerText()).trim();
      console.log(`[e2e-chat-smoke] user: ${message}`);
      console.log(`[e2e-chat-smoke] assistant: ${assistantReply}`);
    } finally {
      if (sessionId) {
        await api.delete(`/api/sessions/${sessionId}?context_type=chat`);
      }
      await api.dispose();
    }
  });
});
