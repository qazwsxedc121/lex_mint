import fs from 'fs';
import os from 'os';
import path from 'path';
import { test, expect, request as pwRequest, type APIRequestContext, type Page } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;
const MODIFIER_KEY = process.platform === 'darwin' ? 'Meta' : 'Control';

async function createTempProject(api: APIRequestContext) {
  const nonce = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lex-mint-e2e-workflow-launcher-'));
  const projectName = `e2e-workflow-launcher-${nonce}`;
  const topFileName = 'WORKFLOW_LAUNCHER.e2e.md';
  const topFileContent = '# Workflow Launcher\nNeed rewrite here.\n';

  fs.writeFileSync(path.join(tempRoot, topFileName), topFileContent, 'utf-8');

  const createRes = await api.post('/api/projects', {
    data: {
      name: projectName,
      root_path: tempRoot,
      description: 'e2e workflow launcher',
    },
  });
  expect(createRes.ok()).toBeTruthy();
  const created = await createRes.json();

  return {
    projectId: created.id as string,
    topFileName,
    tempRoot,
  };
}

async function cleanupProject(api: APIRequestContext, projectId: string, tempRoot: string) {
  try {
    await api.delete(`/api/projects/${projectId}`);
  } catch {
    // Ignore cleanup errors.
  }
  fs.rmSync(tempRoot, { recursive: true, force: true });
}

async function createEditorRewriteWorkflow(api: APIRequestContext, name: string): Promise<string> {
  const response = await api.post('/api/workflows', {
    data: {
      name,
      description: 'e2e launcher shared workflow',
      enabled: true,
      scenario: 'editor_rewrite',
      input_schema: [
        { key: 'selected_text', type: 'string', required: false, default: '' },
      ],
      entry_node_id: 'start_1',
      nodes: [
        { id: 'start_1', type: 'start', next_id: 'llm_1' },
        {
          id: 'llm_1',
          type: 'llm',
          prompt_template: '{{inputs.selected_text}}',
          output_key: 'answer',
          next_id: 'end_1',
        },
        { id: 'end_1', type: 'end', result_template: '{{ctx.answer}}' },
      ],
    },
  });
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  return body.id as string;
}

async function cleanupWorkflow(api: APIRequestContext, workflowId: string) {
  try {
    await api.delete(`/api/workflows/${workflowId}`);
  } catch {
    // Ignore cleanup errors.
  }
}

async function mockWorkflowRunStreamViaRunsApi(
  page: Page,
  runId: string,
  ssePayloads: Array<Record<string, unknown>>
) {
  await page.route('**/api/runs', async (route) => {
    const request = route.request();
    if (request.method() !== 'POST') {
      await route.continue();
      return;
    }
    const payload = request.postDataJSON() as Record<string, unknown>;
    const nowIso = new Date().toISOString();
    const workflowId =
      typeof payload.workflow_id === 'string' ? payload.workflow_id : null;

    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: runId,
        stream_id: `${runId}-stream`,
        kind: 'workflow',
        status: 'running',
        context_type: typeof payload.context_type === 'string' ? payload.context_type : 'workflow',
        project_id: typeof payload.project_id === 'string' ? payload.project_id : null,
        session_id: typeof payload.session_id === 'string' ? payload.session_id : null,
        workflow_id: workflowId,
        created_at: nowIso,
        updated_at: nowIso,
        started_at: nowIso,
        finished_at: null,
        request_payload: payload,
        result_summary: {},
        error: null,
        last_event_id: null,
        last_seq: 0,
      }),
    });
  });

  await page.route(`**/api/runs/${runId}/stream`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
      body: ssePayloads.map((payload) => `data: ${JSON.stringify(payload)}\n\n`).join(''),
    });
  });
}

test.describe('Workflows launcher', () => {
  test('shared launcher drives workflows views and persists favorites/recents into projects', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let workflowId = '';
    let projectId = '';
    let tempRoot = '';

    try {
      const nonce = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
      const workflowName = `e2e-launcher-${nonce}`;
      workflowId = await createEditorRewriteWorkflow(api, workflowName);

      const streamId = 'workflow-launcher-stream';
      const now = Date.now();
      await mockWorkflowRunStreamViaRunsApi(page, 'run-workflow-launcher-1', [
        {
          flow_event: {
            event_id: 'evt-1',
            seq: 1,
            ts: now,
            stream_id: streamId,
            event_type: 'stream_started',
            stage: 'transport',
            payload: {},
          },
        },
        {
          flow_event: {
            event_id: 'evt-2',
            seq: 2,
            ts: now + 1,
            stream_id: streamId,
            event_type: 'text_delta',
            stage: 'content',
            payload: { text: 'launcher output\n' },
          },
        },
        {
          flow_event: {
            event_id: 'evt-3',
            seq: 3,
            ts: now + 2,
            stream_id: streamId,
            event_type: 'stream_ended',
            stage: 'transport',
            payload: { done: true },
          },
        },
      ]);

      await page.goto('/workflows');
      await expect(page.locator('[data-name="workflows-module"]')).toBeVisible();
      await expect(page.locator('[data-name="workflow-launcher-list"]')).toBeVisible();

      await page.locator(`[data-name="workflow-launcher-item-${workflowId}"]`).click();
      await expect(page.locator('[data-name="workflow-meta-name"]')).toHaveValue(workflowName);
      await page.locator(`[data-name="workflow-launcher-favorite-${workflowId}"]`).click();
      await page.locator('[data-name="workflow-launcher-tab-favorites"]').click();
      await expect(page.locator('[data-name="workflow-launcher-section-favorites"]')).toBeVisible();

      await page.locator('[data-name="workflows-view-switch"] button').nth(1).click();
      await expect(page.locator('[data-name="workflows-playground-layout"]')).toBeVisible();
      await page.locator(`[data-name="workflow-launcher-item-${workflowId}"]`).click();
      await page.locator('[data-name="workflow-runner-panel"] button').first().click();
      await expect(page.locator('[data-name="workflow-runner-output"]')).toContainText('launcher output');

      await page.locator('[data-name="workflows-view-switch"] button').nth(2).click();
      await expect(page.locator('[data-name="workflows-history-layout"]')).toBeVisible();
      await page.locator('[data-name="workflow-launcher-tab-recent"]').click();
      await expect(page.locator('[data-name="workflow-launcher-section-recent"]')).toBeVisible();
      await expect(page.locator(`[data-name="workflow-launcher-item-${workflowId}"]`)).toBeVisible();

      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      await page.goto(`/projects/${projectId}`);
      await expect(page.locator('[data-name="project-explorer-root"]')).toBeVisible();
      await page.locator('[data-name="file-tree"]').getByText(created.topFileName, { exact: true }).click();
      await page.locator('.cm-content').click();
      await page.keyboard.press(`${MODIFIER_KEY}+A`);
      await page.keyboard.press(`${MODIFIER_KEY}+K`);

      await expect(page.locator('[data-name="inline-rewrite-panel"]')).toBeVisible();
      await page.locator('[data-name="workflow-launcher-tab-favorites"]').click();
      await expect(page.locator('[data-name="workflow-launcher-section-favorites"]')).toBeVisible();
      await page.locator('[data-name="workflow-launcher-tab-recent"]').click();
      await expect(page.locator('[data-name="workflow-launcher-section-recent"]')).toBeVisible();
      await expect(page.locator(`[data-name="workflow-launcher-item-${workflowId}"]`)).toBeVisible();
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      if (workflowId) {
        await cleanupWorkflow(api, workflowId);
      }
      await api.dispose();
    }
  });
});
