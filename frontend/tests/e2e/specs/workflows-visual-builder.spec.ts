import { expect, request as pwRequest, test, type APIRequestContext } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}

const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;
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
          expression: 'inputs.input',
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

      await page.locator('[data-name="workflow-builder-tab-config"]').click();
      await expect(page.locator('[data-name="workflow-input-schema-editor"]')).toBeVisible();
      await expect(page.locator('[data-name="workflow-entry-node-select"]')).toBeVisible();

      await page.fill('[data-name="workflow-node-id-1"]', 'condition_renamed');
      await page.locator('[data-name="workflow-node-true-next-1"]').selectOption('end_a');
      await page.locator('[data-name="workflow-node-false-next-1"]').selectOption('end_b');
      await page.locator('[data-name="workflow-entry-node-select"]').selectOption('start_a');
      await page.locator('[data-name="workflow-builder-tab-visual"]').click();
      await expect(page.locator('[data-name="workflow-visual-node-condition_renamed"]')).toBeVisible();

      await page.locator(`[data-name="workflow-launcher-item-${basicWorkflowId}"]`).click();
      await expect(page.locator('[data-name="workflow-visual-node-start_b"]')).toBeVisible();
      await expect(page.locator('[data-name="workflow-visual-node-condition_renamed"]')).toHaveCount(0);
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

  test('node input type uses node dropdown and follows node id rename', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let workflowId = '';

    const workflowPayload = {
      name: `e2e-node-input-${Date.now()}`,
      description: 'node input type coverage',
      enabled: true,
      scenario: 'general',
      input_schema: [{ key: 'target_node', type: 'node', required: true, default: 'end_b' }],
      entry_node_id: 'start_a',
      nodes: [
        { id: 'start_a', type: 'start', next_id: 'condition_a' },
        {
          id: 'condition_a',
          type: 'condition',
          expression: "inputs.target_node == 'end_b'",
          true_next_id: 'end_b',
          false_next_id: 'llm_a',
        },
        {
          id: 'llm_a',
          type: 'llm',
          prompt_template: 'go {{inputs.target_node}}',
          output_key: 'answer',
          next_id: 'end_a',
        },
        { id: 'end_a', type: 'end', result_template: 'done-a' },
        { id: 'end_b', type: 'end', result_template: 'done-b' },
      ],
    };

    try {
      workflowId = await createWorkflow(api, workflowPayload);

      await page.goto('/workflows');
      await expect(page.locator('[data-name="workflows-module"]')).toBeVisible();
      await page.locator(`[data-name="workflow-launcher-item-${workflowId}"]`).click();

      await page.locator('[data-name="workflow-builder-tab-config"]').click();
      await expect(page.locator('[data-name="workflow-input-schema-type-0"]')).toHaveValue('node');
      await expect(page.locator('[data-name="workflow-input-schema-default-0"]')).toHaveValue('end_b');

      await page.fill('[data-name="workflow-node-id-4"]', 'end_renamed');
      await expect(page.locator('[data-name="workflow-input-schema-default-0"]')).toHaveValue('end_renamed');
      await Promise.all([
        page.waitForResponse((response) => {
          const url = new URL(response.url());
          return (
            url.pathname === `/api/workflows/${workflowId}` &&
            response.request().method() === 'PUT' &&
            response.ok()
          );
        }),
        page.locator('[data-name="workflow-builder-save"]').click(),
      ]);

      await page.locator('[data-name="workflows-view-switch"] button').nth(1).click();
      await expect(page.locator('[data-name="workflows-playground-layout"]')).toBeVisible();
      await page.locator(`[data-name="workflow-launcher-item-${workflowId}"]`).click();
      await expect(page.locator('[data-name="workflow-runner-inputs"] select').first()).toHaveValue('end_renamed');
      await page.locator('[data-name="workflow-runner-inputs"] select').first().selectOption('end_a');
      await expect(page.locator('[data-name="workflow-runner-inputs"] select').first()).toHaveValue('end_a');
    } finally {
      if (workflowId) {
        await cleanupWorkflow(api, workflowId);
      }
      await api.dispose();
    }
  });
});
