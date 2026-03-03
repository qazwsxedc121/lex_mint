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

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();

      const marker = `E2E-${Date.now()}`;
      const message = `${marker}: Please reply with one short sentence for this e2e smoke test.`;
      await input.fill(message);
      await page.locator('[data-name="input-box-root"] button').filter({ hasText: /Send|发送/ }).click();

      let assistantReply = '';
      await expect
        .poll(
          async () => {
            const sessionRes = await api.get(`/api/sessions/${sessionId}?context_type=chat`);
            if (!sessionRes.ok()) {
              return false;
            }
            const session = await sessionRes.json();
            const messages = Array.isArray(session?.state?.messages) ? session.state.messages : [];
            const hasUserMessage = messages.some(
              (msg: { role?: string; content?: string }) =>
                msg?.role === 'user' && typeof msg?.content === 'string' && msg.content.includes(marker)
            );
            const latestAssistant = [...messages]
              .reverse()
              .find((msg: { role?: string; content?: string }) => msg?.role === 'assistant' && typeof msg?.content === 'string');
            const candidate = (latestAssistant?.content || '').trim();
            const isPlaceholder = /^Generating\.\.\.$/i.test(candidate) || /^生成中/.test(candidate);
            if (hasUserMessage && candidate.length > 5 && !isPlaceholder) {
              assistantReply = candidate;
              return true;
            }
            return false;
          },
          {
            timeout: 180000,
            intervals: [1000, 2000, 3000, 5000],
          }
        )
        .toBeTruthy();

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
