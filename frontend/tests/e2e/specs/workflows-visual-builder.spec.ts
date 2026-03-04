import { expect, request as pwRequest, test, type APIRequestContext, type Page } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}

const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;
const MODIFIER_KEY = process.platform === 'darwin' ? 'Meta' : 'Control';

const setEditorText = async (page: Page, text: string) => {
  const content = page.locator('[data-name="workflow-editor-panel"] .cm-content');
  await content.click();
  await page.keyboard.press(`${MODIFIER_KEY}+A`);
  await page.keyboard.type(text);
};

const createWorkflow = async (
  api: APIRequestContext,
  payload: Record<string, unknown>
): Promise<string> => {
  const response = await api.post('/api/workflows', { data: payload });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return body.id as string;
};

const cleanupWorkflow = async (api: APIRequestContext, workflowId: string) => {
  try {
    await api.delete(`/api/workflows/${workflowId}`);
  } catch {
    // Ignore cleanup errors.
  }
};

test.describe('Workflows visual builder', () => {
  test('renders visual graph, surfaces parse errors, and updates when workflow switches', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let conditionWorkflowId = '';
    let basicWorkflowId = '';

    const conditionWorkflowPayload = {
      name: `e2e-visual-condition-${Date.now()}`,
      description: 'condition graph for visual builder',
      enabled: true,
      scenario: 'general',
      input_schema: [{ key: 'input', type: 'string', required: true }],
      entry_node_id: 'start_a',
      nodes: [
        { id: 'start_a', type: 'start', next_id: 'condition_a' },
        {
          id: 'condition_a',
          type: 'condition',
          expression: '{{inputs.input}}',
          true_next_id: 'llm_a',
          false_next_id: 'end_b',
        },
        {
          id: 'llm_a',
          type: 'llm',
          prompt_template: '{{inputs.input}}',
          output_key: 'answer',
          next_id: 'end_a',
        },
        { id: 'end_a', type: 'end', result_template: '{{ctx.answer}}' },
        { id: 'end_b', type: 'end', result_template: 'skipped' },
      ],
    };

    const basicWorkflowPayload = {
      name: `e2e-visual-basic-${Date.now()}`,
      description: 'basic graph for visual builder',
      enabled: true,
      scenario: 'general',
      input_schema: [{ key: 'input', type: 'string', required: true }],
      entry_node_id: 'start_b',
      nodes: [
        { id: 'start_b', type: 'start', next_id: 'llm_b' },
        {
          id: 'llm_b',
          type: 'llm',
          prompt_template: '{{inputs.input}}',
          output_key: 'answer',
          next_id: 'end_c',
        },
        { id: 'end_c', type: 'end', result_template: '{{ctx.answer}}' },
      ],
    };

    try {
      conditionWorkflowId = await createWorkflow(api, conditionWorkflowPayload);
      basicWorkflowId = await createWorkflow(api, basicWorkflowPayload);

      await page.goto('/workflows');
      await expect(page.locator('[data-name="workflows-module"]')).toBeVisible();
      await expect(page.locator('[data-name="workflow-visual-panel"]')).toBeVisible();

      await page.locator(`[data-name="workflow-launcher-item-${conditionWorkflowId}"]`).click();
      await expect(page.locator('[data-name="workflow-visual-node-condition_a"]')).toBeVisible();
      await expect(
        page.locator('[data-name="workflow-visual-panel"] .react-flow__edge-text').filter({ hasText: 'true' })
      ).toHaveCount(1);
      await expect(
        page.locator('[data-name="workflow-visual-panel"] .react-flow__edge-text').filter({ hasText: 'false' })
      ).toHaveCount(1);

      await setEditorText(page, '{');
      await expect(page.locator('[data-name="workflow-visual-parse-error"]')).toBeVisible();

      await setEditorText(page, JSON.stringify(conditionWorkflowPayload, null, 2));
      await expect(page.locator('[data-name="workflow-visual-parse-error"]')).toHaveCount(0);
      await expect(page.locator('[data-name="workflow-visual-node-condition_a"]')).toBeVisible();

      await page.locator(`[data-name="workflow-launcher-item-${basicWorkflowId}"]`).click();
      await expect(page.locator('[data-name="workflow-visual-node-start_b"]')).toBeVisible();
      await expect(page.locator('[data-name="workflow-visual-node-condition_a"]')).toHaveCount(0);
    } finally {
      if (conditionWorkflowId) {
        await cleanupWorkflow(api, conditionWorkflowId);
      }
      if (basicWorkflowId) {
        await cleanupWorkflow(api, basicWorkflowId);
      }
      await api.dispose();
    }
  });
});
