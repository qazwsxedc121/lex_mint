import fs from 'fs';
import os from 'os';
import path from 'path';
import { test, expect, request as pwRequest, type APIRequestContext } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;
const MODIFIER_KEY = process.platform === 'darwin' ? 'Meta' : 'Control';

async function createTempProject(api: APIRequestContext) {
  const nonce = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lex-mint-e2e-inline-rewrite-'));
  const projectName = `e2e-inline-rewrite-${nonce}`;
  const topFileName = 'INLINE_REWRITE.e2e.md';
  const topFileContent = '# Inline Rewrite\nThis sentence should be rewritten.\n';

  fs.writeFileSync(path.join(tempRoot, topFileName), topFileContent, 'utf-8');

  const createRes = await api.post('/api/projects', {
    data: {
      name: projectName,
      root_path: tempRoot,
      description: 'e2e inline rewrite',
    },
  });
  expect(createRes.ok()).toBeTruthy();
  const created = await createRes.json();
  const projectId = created.id as string;
  expect(projectId).toMatch(/^proj_[a-f0-9]{12}$/);

  return {
    projectId,
    projectName,
    topFileName,
    topFileContent,
    tempRoot,
  };
}

async function cleanupProject(api: APIRequestContext, projectId: string, tempRoot: string) {
  try {
    const sessionsRes = await api.get(`/api/sessions?context_type=project&project_id=${projectId}`);
    if (sessionsRes.ok()) {
      const body = await sessionsRes.json();
      const sessions = Array.isArray(body?.sessions) ? body.sessions : [];
      for (const session of sessions) {
        if (session?.session_id) {
          await api.delete(`/api/sessions/${session.session_id}?context_type=project&project_id=${projectId}`);
        }
      }
    }
  } catch {
    // Ignore cleanup errors for sessions.
  }

  try {
    await api.delete(`/api/projects/${projectId}`);
  } catch {
    // Ignore cleanup errors for project.
  }

  fs.rmSync(tempRoot, { recursive: true, force: true });
}

async function cleanupWorkflow(api: APIRequestContext, workflowId: string) {
  if (!workflowId) {
    return;
  }
  try {
    await api.delete(`/api/workflows/${workflowId}`);
  } catch {
    // Ignore cleanup errors.
  }
}

test.describe('Projects inline rewrite', () => {
  test('rewrite selected text in editor and accept changes', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      let rewritePayload: Record<string, unknown> | null = null;
      await page.route('**/api/workflows/*/run/stream', async (route) => {
        const request = route.request();
        rewritePayload = request.postDataJSON() as Record<string, unknown>;

        const streamId = 'rewrite-stream-1';
        const now = Date.now();
        const ssePayloads = [
          {
            flow_event: {
              event_id: 'evt-1',
              seq: 1,
              ts: now,
              stream_id: streamId,
              event_type: 'stream_started',
              stage: 'transport',
              payload: { context_type: 'project' },
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
              payload: { text: 'Rewritten line for inline rewrite.\n' },
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
        ];
        const body = ssePayloads.map((payload) => `data: ${JSON.stringify(payload)}\n\n`).join('');

        await route.fulfill({
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
          },
          body,
        });
      });

      await page.goto('/projects');
      await expect(page.locator('[data-name="projects-module-root"]')).toBeVisible();

      const projectCard = page.getByRole('button', { name: new RegExp(created.projectName) });
      await expect(projectCard).toBeVisible();
      await projectCard.click();

      await expect(page).toHaveURL(new RegExp(`/projects/${projectId}$`));
      await expect(page.locator('[data-name="project-explorer-root"]')).toBeVisible();

      const topFileNode = page.locator('[data-name="file-tree"]').getByText(created.topFileName, { exact: true });
      await expect(topFileNode).toBeVisible();
      await topFileNode.click();

      await expect(page.locator('[data-name="file-viewer-breadcrumb-row"]')).toContainText(created.topFileName);
      await expect(page.locator('.cm-content')).toContainText('This sentence should be rewritten.');

      const createSessionReqPromise = page.waitForRequest((req) => {
        if (req.method() !== 'POST') return false;
        if (!req.url().includes('/api/sessions?')) return false;
        return req.url().includes(`project_id=${projectId}`);
      });

      await page.locator('.cm-content').click();
      await page.keyboard.press(`${MODIFIER_KEY}+A`);
      await page.keyboard.press(`${MODIFIER_KEY}+K`);

      await expect(page.locator('[data-name="inline-rewrite-panel"]')).toBeVisible();
      await expect(page.locator('[data-name="inline-rewrite-no-selection-dialog"]')).toHaveCount(0);
      await page.locator('[data-name="inline-rewrite-generate"]').click();

      const createSessionReq = await createSessionReqPromise;
      const createReqUrl = new URL(createSessionReq.url());
      expect(createReqUrl.searchParams.get('context_type')).toBe('project');
      expect(createReqUrl.searchParams.get('project_id')).toBe(projectId);
      const createReqBody = createSessionReq.postDataJSON() as { temporary?: boolean };
      expect(createReqBody.temporary).toBeTruthy();

      await expect(page.locator('[data-name="inline-rewrite-preview"]')).toContainText(
        'Rewritten line for inline rewrite.'
      );
      await expect.poll(() => rewritePayload).not.toBeNull();
      expect(rewritePayload?.context_type).toBe('project');
      expect(rewritePayload?.project_id).toBe(projectId);
      const inputs = rewritePayload?.inputs as Record<string, unknown> | undefined;
      expect(inputs?.selected_text).toContain('This sentence should be rewritten.');

      await page.locator('[data-name="inline-rewrite-accept"]').click();
      await expect(page.locator('.cm-content')).toContainText('Rewritten line for inline rewrite.');
      await expect(page.locator('[data-name="inline-rewrite-panel"]')).toHaveCount(0);
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('when no text is selected and workflow requires selection, show options and support full-file run', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      let rewritePayload: Record<string, unknown> | null = null;
      await page.route('**/api/workflows/*/run/stream', async (route) => {
        const request = route.request();
        rewritePayload = request.postDataJSON() as Record<string, unknown>;

        const streamId = 'rewrite-stream-no-selection';
        const now = Date.now();
        const ssePayloads = [
          {
            flow_event: {
              event_id: 'evt-n1',
              seq: 1,
              ts: now,
              stream_id: streamId,
              event_type: 'stream_started',
              stage: 'transport',
              payload: { context_type: 'project' },
            },
          },
          {
            flow_event: {
              event_id: 'evt-n2',
              seq: 2,
              ts: now + 1,
              stream_id: streamId,
              event_type: 'text_delta',
              stage: 'content',
              payload: { text: 'Rewrite from full-file mode.\n' },
            },
          },
          {
            flow_event: {
              event_id: 'evt-n3',
              seq: 3,
              ts: now + 2,
              stream_id: streamId,
              event_type: 'stream_ended',
              stage: 'transport',
              payload: { done: true },
            },
          },
        ];
        const body = ssePayloads.map((payload) => `data: ${JSON.stringify(payload)}\n\n`).join('');

        await route.fulfill({
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
          },
          body,
        });
      });

      await page.goto(`/projects/${projectId}`);
      await expect(page.locator('[data-name="project-explorer-root"]')).toBeVisible();
      const topFileNode = page.locator('[data-name="file-tree"]').getByText(created.topFileName, { exact: true });
      await expect(topFileNode).toBeVisible();
      await topFileNode.click();

      await page.locator('.cm-content').click();
      await page.keyboard.press('ArrowRight');
      await page.keyboard.press(`${MODIFIER_KEY}+K`);

      await expect(page.locator('[data-name="inline-rewrite-panel"]')).toBeVisible();
      await page.locator('[data-name="inline-rewrite-workflow"]').selectOption('wf_inline_rewrite_default');
      await page.locator('[data-name="inline-rewrite-generate"]').click();
      await expect(page.locator('[data-name="inline-rewrite-no-selection-dialog"]')).toBeVisible();
      await page.locator('[data-name="inline-rewrite-no-selection-full"]').click();

      await expect(page.locator('[data-name="inline-rewrite-preview"]')).toContainText(
        'Rewrite from full-file mode.'
      );
      await expect.poll(() => rewritePayload).not.toBeNull();

      const inputs = rewritePayload?.inputs as Record<string, unknown> | undefined;
      expect(inputs?._source_mode).toBe('full_file');
      expect(inputs?._selected_text).toContain('# Inline Rewrite');
      expect(inputs?._selected_text).toContain('This sentence should be rewritten.');
      expect(inputs?._full_text).toContain('This sentence should be rewritten.');
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('create editor rewrite workflow in workflows page and use it in projects', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';
    let customWorkflowId = '';
    let customWorkflowName = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      const nonce = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
      customWorkflowName = `e2e-inline-rewrite-ui-${nonce}`;

      await page.goto('/workflows');
      await expect(page.locator('[data-name="workflows-module"]')).toBeVisible();

      const createWorkflowResponsePromise = page.waitForResponse((response) => {
        if (response.request().method() !== 'POST') return false;
        return new URL(response.url()).pathname === '/api/workflows';
      });
      await page.locator('[data-name="workflow-list-create"]').click();

      const createWorkflowResponse = await createWorkflowResponsePromise;
      expect(createWorkflowResponse.ok()).toBeTruthy();
      const createWorkflowBody = await createWorkflowResponse.json();
      customWorkflowId = createWorkflowBody?.id as string;
      expect(customWorkflowId).toMatch(/^wf_[a-z0-9]{12}$/);

      await page.locator('[data-name="workflow-meta-name"]').fill(customWorkflowName);
      await page.locator('[data-name="workflow-meta-description"]').fill('e2e custom rewrite workflow from UI');
      await page.locator('[data-name="workflow-meta-scenario"]').selectOption('editor_rewrite');
      await expect(page.locator('[data-name="workflow-meta-scenario"]')).toHaveValue('editor_rewrite');

      const updateWorkflowResponsePromise = page.waitForResponse((response) => {
        if (response.request().method() !== 'PUT') return false;
        return new URL(response.url()).pathname === `/api/workflows/${customWorkflowId}`;
      });
      await page.locator('[data-name="workflow-editor-save"]').click();
      const updateWorkflowResponse = await updateWorkflowResponsePromise;
      expect(updateWorkflowResponse.ok()).toBeTruthy();
      await expect
        .poll(async () => {
          const workflowRes = await api.get(`/api/workflows/${customWorkflowId}`);
          if (!workflowRes.ok()) {
            return 'missing';
          }
          const workflow = await workflowRes.json();
          return workflow?.scenario ?? '';
        })
        .toBe('editor_rewrite');

      let runRequestUrl = '';
      let runPayload: Record<string, unknown> | null = null;
      await page.route('**/api/workflows/*/run/stream', async (route) => {
        const request = route.request();
        runRequestUrl = request.url();
        runPayload = request.postDataJSON() as Record<string, unknown>;

        const streamId = 'rewrite-stream-2';
        const now = Date.now();
        const ssePayloads = [
          {
            flow_event: {
              event_id: 'evt-a1',
              seq: 1,
              ts: now,
              stream_id: streamId,
              event_type: 'stream_started',
              stage: 'transport',
              payload: { context_type: 'project' },
            },
          },
          {
            flow_event: {
              event_id: 'evt-a2',
              seq: 2,
              ts: now + 1,
              stream_id: streamId,
              event_type: 'text_delta',
              stage: 'content',
              payload: { text: 'Custom workflow rewrite output.\n' },
            },
          },
          {
            flow_event: {
              event_id: 'evt-a3',
              seq: 3,
              ts: now + 2,
              stream_id: streamId,
              event_type: 'stream_ended',
              stage: 'transport',
              payload: { done: true },
            },
          },
        ];
        const body = ssePayloads.map((payload) => `data: ${JSON.stringify(payload)}\n\n`).join('');

        await route.fulfill({
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            Connection: 'keep-alive',
          },
          body,
        });
      });

      await page.goto(`/projects/${projectId}`);
      await expect(page.locator('[data-name="project-explorer-root"]')).toBeVisible();
      const topFileNode = page.locator('[data-name="file-tree"]').getByText(created.topFileName, { exact: true });
      await expect(topFileNode).toBeVisible();
      await topFileNode.click();

      await page.locator('.cm-content').click();
      await page.keyboard.press(`${MODIFIER_KEY}+A`);
      await page.keyboard.press(`${MODIFIER_KEY}+K`);

      await expect(page.locator('[data-name="inline-rewrite-panel"]')).toBeVisible();
      await expect(page.locator('[data-name="inline-rewrite-no-selection-dialog"]')).toHaveCount(0);
      await expect
        .poll(async () =>
          page.locator('[data-name="inline-rewrite-workflow"]').evaluate((element) =>
            Array.from((element as HTMLSelectElement).options).map((opt) => opt.value)
          )
        )
        .toContain(customWorkflowId);
      await page.locator('[data-name="inline-rewrite-workflow"]').selectOption(customWorkflowId);
      await page.locator('[data-name="inline-rewrite-generate"]').click();

      await expect(page.locator('[data-name="inline-rewrite-preview"]')).toContainText(
        'Custom workflow rewrite output.'
      );

      await expect.poll(() => runRequestUrl).toContain(`/api/workflows/${customWorkflowId}/run/stream`);
      await expect.poll(() => runPayload).not.toBeNull();
      expect(runPayload?.context_type).toBe('project');
      expect(runPayload?.project_id).toBe(projectId);
      expect(runPayload?.stream_mode).toBe('editor_rewrite');
      const inputs = runPayload?.inputs as Record<string, unknown> | undefined;
      expect(inputs?.input).toContain('This sentence should be rewritten.');
      expect(inputs?.selected_text).toContain('This sentence should be rewritten.');
    } finally {
      if (customWorkflowId) {
        await cleanupWorkflow(api, customWorkflowId);
      }
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });
});
