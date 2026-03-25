import { test, expect, request as pwRequest, type APIRequestContext, type Page } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

async function waitForAssistantMessageId(api: APIRequestContext, sessionId: string): Promise<string> {
  let assistantMessageId = '';

  await expect
    .poll(
      async () => {
        const sessionRes = await api.get(`/api/sessions/${sessionId}?context_type=chat`);
        if (!sessionRes.ok()) {
          return '';
        }
        const session = await sessionRes.json();
        const messages = Array.isArray(session?.state?.messages) ? session.state.messages : [];
        const latestAssistant = [...messages]
          .reverse()
          .find((msg: { role?: string; content?: string; message_id?: string }) => {
            const candidate = (msg?.content || '').trim();
            const isPlaceholder = /^Generating\.\.\.$/i.test(candidate) || /^生成中/.test(candidate);
            return msg?.role === 'assistant' && Boolean(msg?.message_id) && candidate.length > 0 && !isPlaceholder;
          });
        return latestAssistant?.message_id || '';
      },
      {
        timeout: 180000,
        intervals: [1000, 2000, 3000, 5000],
      },
    )
    .not.toBe('');

  const sessionRes = await api.get(`/api/sessions/${sessionId}?context_type=chat`);
  const session = await sessionRes.json();
  const messages = Array.isArray(session?.state?.messages) ? session.state.messages : [];
  const latestAssistant = [...messages]
    .reverse()
    .find((msg: { role?: string; message_id?: string }) => msg?.role === 'assistant' && msg?.message_id);
  assistantMessageId = latestAssistant?.message_id || '';

  expect(assistantMessageId).not.toBe('');
  return assistantMessageId;
}

function buildOverflowFixtureContent(): string {
  const longToken = 'overflowtoken'.repeat(180);
  const longUrl = `https://example.com/${'segment'.repeat(180)}`;
  const longTableCell = 'tablecell'.repeat(140);

  return [
    `<think>${longToken}</think>`,
    '',
    `Long URL: ${longUrl}`,
    '',
    '```text',
    longToken,
    '```',
    '',
    '```mermaid',
    'graph TD',
    'A["Start"] --> B["Reasoning"]',
    'B --> C["Finish"]',
    '```',
    '',
    '```svg',
    `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="120" viewBox="0 0 1600 120"><rect width="1600" height="120" fill="#0f172a"/><text x="20" y="70" fill="#e2e8f0" font-size="20">${'svglabel'.repeat(80)}</text></svg>`,
    '```',
    '',
    '| Column | Value |',
    '| --- | --- |',
    `| long | ${longTableCell} |`,
    '',
    `Inline code: \`${longToken}\``,
  ].join('\n');
}

async function assertNoHorizontalOverflow(page: Page) {
  const metrics = await page.evaluate(() => {
    const root = document.querySelector('[data-name="chat-view-root"]') as HTMLElement | null;
    const messageList = document.querySelector('[data-name="message-list"]') as HTMLElement | null;
    const bubble = document.querySelector('[data-name="message-bubble-content"]') as HTMLElement | null;
    const thinkingBlock = document.querySelector('[data-name="thinking-block"]') as HTMLElement | null;
    const codeBlock = document.querySelector('[data-name="code-block-root"]') as HTMLElement | null;
    const mermaidBlock = document.querySelector('[data-name="mermaid-block-root"]') as HTMLElement | null;
    const svgBlock = document.querySelector('[data-name="svg-block-root"]') as HTMLElement | null;

    const readBox = (element: HTMLElement | null) =>
      element
        ? {
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
            rectWidth: element.getBoundingClientRect().width,
          }
        : null;

    return {
      viewportWidth: document.documentElement.clientWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      root: readBox(root),
      messageList: readBox(messageList),
      bubble: readBox(bubble),
      thinkingBlock: readBox(thinkingBlock),
      codeBlock: readBox(codeBlock),
      mermaidBlock: readBox(mermaidBlock),
      svgBlock: readBox(svgBlock),
    };
  });

  expect(metrics.documentScrollWidth).toBeLessThanOrEqual(metrics.viewportWidth + 2);
  expect(metrics.root?.scrollWidth ?? 0).toBeLessThanOrEqual((metrics.root?.clientWidth ?? 0) + 2);
  expect(metrics.messageList?.scrollWidth ?? 0).toBeLessThanOrEqual((metrics.messageList?.clientWidth ?? 0) + 2);
  expect(metrics.bubble?.scrollWidth ?? 0).toBeLessThanOrEqual((metrics.bubble?.clientWidth ?? 0) + 2);
  expect(metrics.thinkingBlock?.rectWidth ?? 0).toBeLessThanOrEqual((metrics.bubble?.rectWidth ?? 0) + 2);
  expect(metrics.codeBlock?.rectWidth ?? 0).toBeLessThanOrEqual((metrics.bubble?.rectWidth ?? 0) + 2);
  expect(metrics.mermaidBlock?.rectWidth ?? 0).toBeLessThanOrEqual((metrics.bubble?.rectWidth ?? 0) + 2);
  expect(metrics.svgBlock?.rectWidth ?? 0).toBeLessThanOrEqual((metrics.bubble?.rectWidth ?? 0) + 2);
}

test.describe('Chat layout overflow', () => {
  test('long thinking and block content do not stretch the chat layout', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let sessionId = '';

    try {
      const createRes = await api.post('/api/sessions?context_type=chat', { data: {} });
      expect(createRes.ok()).toBeTruthy();

      const created = await createRes.json();
      sessionId = created.session_id;
      expect(sessionId).toMatch(/^[a-f0-9-]+$/);

      await page.setViewportSize({ width: 900, height: 1200 });
      await page.goto(`/chat/${sessionId}`);
      await expect(page.locator('[data-name="chat-view-root"]')).toBeVisible();

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();

      const marker = `E2E-layout-${Date.now()}`;
      await input.fill(`${marker}: reply briefly so this layout regression can rewrite your message.`);
      await page.locator('[data-name="input-box-root"] button').filter({ hasText: /Send|发送/ }).click();

      const assistantMessageId = await waitForAssistantMessageId(api, sessionId);

      const updateRes = await api.put('/api/chat/message', {
        data: {
          session_id: sessionId,
          message_id: assistantMessageId,
          content: buildOverflowFixtureContent(),
          context_type: 'chat',
        },
      });
      expect(updateRes.ok()).toBeTruthy();

      await page.reload();
      await expect(page.locator('[data-name="message-bubble-content"]').last()).toBeVisible();
      await expect(page.locator('[data-name="thinking-block"]')).toBeVisible();
      await expect(page.locator('[data-name="code-block-root"]')).toBeVisible();
      await expect(page.locator('[data-name="mermaid-block-root"]')).toBeVisible();
      await expect(page.locator('[data-name="svg-block-root"]')).toBeVisible();

      await assertNoHorizontalOverflow(page);
    } finally {
      if (sessionId) {
        await api.delete(`/api/sessions/${sessionId}?context_type=chat`);
      }
      await api.dispose();
    }
  });
});
