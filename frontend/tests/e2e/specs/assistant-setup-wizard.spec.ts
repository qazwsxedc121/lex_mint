import { test, expect, request as pwRequest } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}

const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

interface ProviderInfo {
  id: string;
  name: string;
  type?: string;
  has_api_key?: boolean;
  enabled?: boolean;
}

interface ModelInfo {
  id: string;
  name: string;
}

async function findBuiltinCandidate(api: Awaited<ReturnType<typeof pwRequest.newContext>>) {
  const providersRes = await api.get('/api/models/providers');
  expect(providersRes.ok()).toBeTruthy();
  const providers = (await providersRes.json()) as ProviderInfo[];

  const builtinCandidates = providers.filter((provider) => provider.type === 'builtin' && provider.enabled !== false && provider.has_api_key);

  for (const provider of builtinCandidates) {
    const modelsRes = await api.post(`/api/models/providers/${provider.id}/fetch-models`);
    if (!modelsRes.ok()) {
      continue;
    }
    const models = (await modelsRes.json()) as ModelInfo[];
    if (Array.isArray(models) && models.length > 0) {
      return {
        provider,
        model: models[0],
      };
    }
  }

  return null;
}

test.describe('Assistant setup wizard', () => {
  test('can create an assistant from the wizard and start a real conversation', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let createdAssistantId = '';
    let createdSessionId = '';
    let createdModelCompositeId = '';
    let createdModelWasNew = false;

    try {
      const candidate = await findBuiltinCandidate(api);
      test.skip(!candidate, 'Need one built-in provider with an existing API key and at least one discoverable model.');

      const { provider, model } = candidate!;
      const existingModelsRes = await api.get('/api/models/list');
      expect(existingModelsRes.ok()).toBeTruthy();
      const existingModels = (await existingModelsRes.json()) as Array<{ id: string; provider_id: string }>;
      createdModelCompositeId = `${provider.id}:${model.id}`;
      createdModelWasNew = !existingModels.some((item) => item.provider_id === provider.id && item.id === model.id);

      const uniqueSuffix = `${Date.now()}`;
      createdAssistantId = `e2e-wizard-${uniqueSuffix}`;
      const assistantName = `E2E Wizard ${uniqueSuffix}`;

      await page.goto('/settings');
      await expect(page).toHaveURL(/\/settings\/get-started$/);
      await expect(page.locator('[data-name="settings-get-started-page"]')).toBeVisible();

      const providerCard = page.locator(`[data-name="wizard-provider-card"][data-provider-id="${provider.id}"]`);
      if (await providerCard.count()) {
        await providerCard.click();
      } else {
        await page.locator('#more-provider-select').selectOption(provider.id);
      }

      await page.locator('[data-name="wizard-configure-provider"]').click();
      await expect(page.locator('[data-name="wizard-provider-config-step"]')).toBeVisible();
      await page.locator('[data-name="wizard-provider-next"]').click();

      await expect(page.locator('[data-name="wizard-model-step"]')).toBeVisible();
      await page.getByRole('button', { name: /Enter manually|手动填写/i }).click();
      await page.locator('#manual-model-id').fill(model.id);
      await page.locator('#manual-model-name').fill(model.name || model.id);
      await page.locator('[data-name="wizard-model-next"]').click();

      await expect(page.locator('[data-name="wizard-assistant-step"]')).toBeVisible();
      await page.locator('#assistant-id').fill(createdAssistantId);
      await page.locator('#assistant-name').fill(assistantName);
      await page.locator('#assistant-description').fill('Created by Playwright wizard e2e');
      await page.locator('#assistant-system-prompt').fill('Reply in one short sentence.');
      await page.locator('[data-name="wizard-create-assistant"]').click();

      await expect(page.locator('[data-name="wizard-done-step"]')).toBeVisible();
      await expect(page.getByText(/Assistant created|助手已创建/i)).toBeVisible();

      const createSessionRes = await api.post('/api/sessions?context_type=chat', {
        data: {
          assistant_id: createdAssistantId,
          target_type: 'assistant',
        },
      });
      expect(createSessionRes.ok()).toBeTruthy();
      const createdSession = await createSessionRes.json();
      createdSessionId = createdSession.session_id;
      expect(createdSessionId).toMatch(/^[a-f0-9-]+$/);

      await page.goto(`/chat/${createdSessionId}`);
      await expect(page.locator('[data-name="chat-view-root"]')).toBeVisible();

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();

      const marker = `E2E-WIZARD-${uniqueSuffix}`;
      await input.fill(`${marker}: Say hello from the newly created assistant.`);
      await page.locator('[data-name="input-box-root"] button').filter({ hasText: /Send|发送/i }).click();

      let assistantReply = '';
      await expect
        .poll(
          async () => {
            const sessionRes = await api.get(`/api/sessions/${createdSessionId}?context_type=chat`);
            if (!sessionRes.ok()) {
              return false;
            }
            const session = await sessionRes.json();
            const messages = Array.isArray(session?.state?.messages) ? session.state.messages : [];
            const lastAssistant = [...messages].reverse().find((msg: { role?: string; content?: string }) => msg?.role === 'assistant' && typeof msg.content === 'string' && msg.content.trim());
            assistantReply = lastAssistant?.content?.trim() || '';
            return assistantReply.length > 0 && !/Generating|思考|thinking/i.test(assistantReply);
          },
          {
            timeout: 120_000,
            intervals: [1000, 2000, 3000, 5000],
            message: 'Expected a real assistant reply from the wizard-created assistant.',
          }
        )
        .toBeTruthy();

      expect(assistantReply).not.toEqual('');
    } finally {
      if (createdSessionId) {
        await api.delete(`/api/sessions/${createdSessionId}?context_type=chat`);
      }
      if (createdAssistantId) {
        await api.delete(`/api/assistants/${createdAssistantId}`);
      }
      if (createdModelWasNew && createdModelCompositeId) {
        await api.delete(`/api/models/list/${encodeURIComponent(createdModelCompositeId)}`);
      }
      await api.dispose();
    }
  });
});
