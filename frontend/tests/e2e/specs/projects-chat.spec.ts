import fs from 'fs';
import os from 'os';
import path from 'path';
import { test, expect, request as pwRequest, type APIRequestContext, type Page } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

function buildFlowEvent(
  seq: number,
  eventType: string,
  stage: 'transport' | 'content' | 'tool' | 'orchestration' | 'meta',
  payload: Record<string, unknown>,
  streamId: string = 'stream-e2e-project-tools',
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

async function createTempProject(api: APIRequestContext) {
  const nonce = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lex-mint-e2e-project-chat-'));
  const projectName = `e2e-project-chat-${nonce}`;
  const topFileName = 'CHAT.e2e.md';
  const topFileContent = '# Project Chat Smoke\nhello project chat e2e\n';

  fs.writeFileSync(path.join(tempRoot, topFileName), topFileContent, 'utf-8');
  fs.mkdirSync(path.join(tempRoot, 'src'));
  fs.writeFileSync(path.join(tempRoot, 'src', 'app.py'), 'print("project chat")\n', 'utf-8');

  const createRes = await api.post('/api/projects', {
    data: {
      name: projectName,
      root_path: tempRoot,
      description: 'e2e projects chat smoke',
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

async function createProjectSession(api: APIRequestContext, projectId: string): Promise<string> {
  const createRes = await api.post(`/api/sessions?context_type=project&project_id=${projectId}`, {
    data: {},
  });
  expect(createRes.ok()).toBeTruthy();
  const created = await createRes.json();
  const sessionId = created.session_id as string;
  expect(sessionId).toMatch(/^[a-f0-9-]+$/);
  return sessionId;
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

async function openProjectAndSelectFile(
  page: Page,
  projectName: string,
  projectId: string,
  topFileName: string
) {
  await page.goto('/projects');
  await expect(page.locator('[data-name="projects-module-root"]')).toBeVisible();

  const projectCard = page.getByRole('button', { name: new RegExp(projectName) });
  await expect(projectCard).toBeVisible();
  await projectCard.click();

  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/project$`));
  await page.getByRole('link', { name: 'Files' }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/files$`));
  await expect(page.locator('[data-name="project-explorer-root"]')).toBeVisible();
  await expect(page.locator('[data-name="file-tree"]')).toBeVisible();

  const topFileNode = page.locator('[data-name="file-tree"]').getByText(topFileName, { exact: true });
  await expect(topFileNode).toBeVisible();
  await topFileNode.click();

  await expect(page.locator('[data-name="file-viewer-breadcrumb-row"]')).toContainText(topFileName);
  await expect(page.locator('[data-name="editor-insert-chat-button"]')).toBeVisible();
}

async function openChatSidebar(page: Page) {
  const sidebar = page.locator('[data-name="chat-sidebar-container"]');
  if (await sidebar.count() > 0 && await sidebar.first().isVisible()) {
    await expect(page.locator('[data-name="project-chat-sidebar-root"]')).toBeVisible();
    await expect(page.locator('[data-name="session-selector-panel"]')).toBeVisible();
    await expect(page.locator('[data-name="chat-view-container"]')).toBeVisible();
    return;
  }

  const chatToggleButton = page
    .locator('[data-name="editor-insert-chat-button"]')
    .locator('xpath=following-sibling::button[1]');

  await expect(chatToggleButton).toBeVisible();
  await chatToggleButton.click();

  await expect(page.locator('[data-name="chat-sidebar-container"]')).toBeVisible();
  await expect(page.locator('[data-name="project-chat-sidebar-root"]')).toBeVisible();
  await expect(page.locator('[data-name="session-selector-panel"]')).toBeVisible();
  await expect(page.locator('[data-name="chat-view-container"]')).toBeVisible();
}

async function ensureProjectChatSession(page: Page, projectId: string) {
  const chatViewRoot = page.locator('[data-name="chat-view-root"]');
  if (await chatViewRoot.count() > 0 && await chatViewRoot.first().isVisible()) {
    return;
  }

  const createReqPromise = page.waitForRequest((req) => {
    if (req.method() !== 'POST') return false;
    if (!req.url().includes('/api/sessions?')) return false;
    return req.url().includes(`project_id=${projectId}`);
  });

  const newSessionButton = page.locator('[data-name="session-selector-root"] > button');
  await expect(newSessionButton).toBeVisible();
  await newSessionButton.click();

  const createReq = await createReqPromise;
  const createReqUrl = new URL(createReq.url());
  expect(createReqUrl.searchParams.get('context_type')).toBe('project');
  expect(createReqUrl.searchParams.get('project_id')).toBe(projectId);

  await expect(chatViewRoot).toBeVisible({ timeout: 15000 });
}

test.describe('Projects chat smoke', () => {
  test('project explorer loads sessions with project context', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      const listReqPromise = page.waitForRequest((req) => {
        if (req.method() !== 'GET') return false;
        if (!req.url().includes('/api/sessions?')) return false;
        return req.url().includes(`project_id=${projectId}`);
      });

      await openProjectAndSelectFile(page, created.projectName, projectId, created.topFileName);
      await openChatSidebar(page);

      const listReq = await listReqPromise;
      const listReqUrl = new URL(listReq.url());
      expect(listReqUrl.searchParams.get('context_type')).toBe('project');
      expect(listReqUrl.searchParams.get('project_id')).toBe(projectId);
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('new project chat session request includes project context params', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      await openProjectAndSelectFile(page, created.projectName, projectId, created.topFileName);
      await openChatSidebar(page);

      const createReqPromise = page.waitForRequest((req) => {
        if (req.method() !== 'POST') return false;
        if (!req.url().includes('/api/sessions?')) return false;
        return req.url().includes(`project_id=${projectId}`);
      });

      const newSessionButton = page.locator('[data-name="session-selector-root"] > button');
      await expect(newSessionButton).toBeVisible();
      await newSessionButton.click();

      const createReq = await createReqPromise;
      const createReqUrl = new URL(createReq.url());
      expect(createReqUrl.searchParams.get('context_type')).toBe('project');
      expect(createReqUrl.searchParams.get('project_id')).toBe(projectId);
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('insert file context then send message with project chat payload', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      await openProjectAndSelectFile(page, created.projectName, projectId, created.topFileName);
      await openChatSidebar(page);
      await ensureProjectChatSession(page, projectId);

      const insertToChatButton = page.locator('[data-name="editor-insert-chat-button"]');
      await expect(insertToChatButton).toBeVisible();
      await insertToChatButton.click();

      await expect(page.locator('[data-name="input-box-blocks"]')).toBeVisible();
      await expect(page.locator('[data-name="input-block"]')).toHaveCount(1);

      const userPrompt = 'Please summarize this file context for e2e verification.';
      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();
      await input.fill(userPrompt);

      const streamReqPromise = page.waitForRequest((req) => (
        req.method() === 'POST' && req.url().includes('/api/chat/stream')
      ));

      const sendButton = page
        .locator('[data-name="input-box-input-controls"] button')
        .filter({ hasText: /Send|发送/ })
        .first();
      await expect(sendButton).toBeVisible();
      await sendButton.click();

      const streamReq = await streamReqPromise;
      const streamBody = streamReq.postDataJSON() as {
        session_id: string;
        message: string;
        context_type: string;
        project_id?: string;
      };

      expect(streamBody.context_type).toBe('project');
      expect(streamBody.project_id).toBe(projectId);
      expect(streamBody.message).toContain('[Context:');
      expect(streamBody.message).toContain(created.topFileName);
      expect(streamBody.message).toContain(created.topFileContent.trim());
      expect(streamBody.message).toContain(userPrompt);

      await expect(page.locator('[data-name="input-box-blocks"]')).toHaveCount(0);
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('move project chat session to another project via transfer modal', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let sourceProjectId = '';
    let targetProjectId = '';
    let sourceRoot = '';
    let targetRoot = '';
    let sourceSessionId = '';

    try {
      const sourceProject = await createTempProject(api);
      const targetProject = await createTempProject(api);
      sourceProjectId = sourceProject.projectId;
      targetProjectId = targetProject.projectId;
      sourceRoot = sourceProject.tempRoot;
      targetRoot = targetProject.tempRoot;

      sourceSessionId = await createProjectSession(api, sourceProjectId);

      await openProjectAndSelectFile(page, sourceProject.projectName, sourceProjectId, sourceProject.topFileName);
      await openChatSidebar(page);

      const sessionDropdownButton = page
        .locator('[data-name="session-selector-root"] > div')
        .locator('button')
        .first();
      await expect(sessionDropdownButton).toBeVisible();
      await sessionDropdownButton.click();

      const moveButton = page.getByTitle(/Move conversation|移动对话/).first();
      await expect(moveButton).toBeVisible();
      await moveButton.click();

      await expect(page.locator('[data-name="session-transfer-modal"]')).toBeVisible();

      const moveResPromise = page.waitForResponse((res) => {
        const req = res.request();
        return req.method() === 'POST' && req.url().includes(`/api/sessions/${sourceSessionId}/move?`);
      });

      const targetProjectButton = page
        .locator('[data-name="session-transfer-projects"] button')
        .filter({ hasText: targetProject.projectName })
        .first();
      await expect(targetProjectButton).toBeVisible();
      await targetProjectButton.click();

      const moveRes = await moveResPromise;
      expect(moveRes.ok()).toBeTruthy();

      const moveReq = moveRes.request();
      const moveReqUrl = new URL(moveReq.url());
      const moveReqBody = moveReq.postDataJSON() as {
        target_context_type: string;
        target_project_id?: string;
      };

      expect(moveReqUrl.searchParams.get('context_type')).toBe('project');
      expect(moveReqUrl.searchParams.get('project_id')).toBe(sourceProjectId);
      expect(moveReqBody.target_context_type).toBe('project');
      expect(moveReqBody.target_project_id).toBe(targetProjectId);

      await expect(page.locator('[data-name="session-transfer-modal"]')).toHaveCount(0);
      await expect(page.locator('[data-name="chat-view-welcome"]')).toBeVisible();

      const sourceSessionsRes = await api.get(`/api/sessions?context_type=project&project_id=${sourceProjectId}`);
      expect(sourceSessionsRes.ok()).toBeTruthy();
      const sourceSessionsBody = await sourceSessionsRes.json();
      const sourceSessions = Array.isArray(sourceSessionsBody?.sessions) ? sourceSessionsBody.sessions : [];
      expect(sourceSessions.some((s: { session_id: string }) => s.session_id === sourceSessionId)).toBeFalsy();

      const targetSessionsRes = await api.get(`/api/sessions?context_type=project&project_id=${targetProjectId}`);
      expect(targetSessionsRes.ok()).toBeTruthy();
      const targetSessionsBody = await targetSessionsRes.json();
      const targetSessions = Array.isArray(targetSessionsBody?.sessions) ? targetSessionsBody.sessions : [];
      expect(targetSessions.some((s: { session_id: string }) => s.session_id === sourceSessionId)).toBeTruthy();
    } finally {
      if (sourceProjectId && sourceRoot) {
        await cleanupProject(api, sourceProjectId, sourceRoot);
      }
      if (targetProjectId && targetRoot) {
        await cleanupProject(api, targetProjectId, targetRoot);
      }
      await api.dispose();
    }
  });

  test('project chat tool flow shows apply diff and confirms apply request', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      await openProjectAndSelectFile(page, created.projectName, projectId, created.topFileName);
      await openChatSidebar(page);
      await ensureProjectChatSession(page, projectId);

      const streamBodies: Array<Record<string, unknown>> = [];
      await page.route('**/api/chat/stream', async (route) => {
        const postData = route.request().postDataJSON() as Record<string, unknown>;
        streamBodies.push(postData);

        const applyResult = JSON.stringify({
          ok: true,
          mode: 'dry_run',
          applied: false,
          file_path: created.topFileName,
          base_hash: 'fnv1a:abcd1234',
          pending_patch_id: 'pending-e2e-1',
          preview: { additions: 2, deletions: 1, hunks: 1 },
        });

        const events = [
          buildFlowEvent(1, 'stream_started', 'transport', { context_type: 'project' }),
          buildFlowEvent(2, 'tool_call_started', 'tool', {
            calls: [
              { id: 'tool-read-1', name: 'read_current_document', args: { start_line: 1, end_line: 20 } },
              { id: 'tool-apply-1', name: 'apply_diff_current_document', args: { dry_run: true } },
            ],
          }),
          buildFlowEvent(3, 'tool_call_finished', 'tool', {
            results: [
              {
                name: 'read_current_document',
                tool_call_id: 'tool-read-1',
                result: JSON.stringify({ ok: true, file_path: created.topFileName }),
              },
              {
                name: 'apply_diff_current_document',
                tool_call_id: 'tool-apply-1',
                result: applyResult,
              },
            ],
          }),
          buildFlowEvent(4, 'text_delta', 'content', { text: 'Done.' }),
          buildFlowEvent(5, 'stream_ended', 'transport', { done: true }),
        ];
        const sseBody = events.map((evt) => `data: ${JSON.stringify(evt)}\n\n`).join('');

        await route.fulfill({
          status: 200,
          headers: { 'content-type': 'text/event-stream; charset=utf-8' },
          body: sseBody,
        });
      });

      let applyRequestBody: Record<string, unknown> | null = null;
      await page.route(`**/api/projects/${projectId}/chat/apply-diff`, async (route) => {
        applyRequestBody = route.request().postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            file_path: created.topFileName,
            new_content_hash: 'fnv1a:efgh5678',
            updated_at: Date.now(),
            content: '# Project Chat Smoke\nhello project chat e2e\n',
          }),
        });
      });

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();
      await input.fill('Please rewrite paragraph 3 with a stronger conflict.');

      const sendButton = page
        .locator('[data-name="input-box-input-controls"] button')
        .filter({ hasText: /Send|发送/ })
        .first();
      await expect(sendButton).toBeVisible();
      await sendButton.click();

      await expect(page.locator('[data-name="tool-call-block"]')).toBeVisible();
      const applyActions = page.locator('[data-name="tool-apply-diff-actions"]').first();
      if (!(await applyActions.isVisible())) {
        await page.getByRole('button', { name: /apply_diff_current_document/ }).first().click();
      }
      await expect(applyActions).toBeVisible();
      await expect(applyActions).toContainText('Diff preview ready');

      const applyButton = page.getByRole('button', { name: 'Apply Changes' });
      await expect(applyButton).toBeVisible();
      await applyButton.click();

      await expect(page.getByRole('button', { name: 'Applied' })).toBeVisible();

      expect(streamBodies.length).toBeGreaterThan(0);
      const streamBody = streamBodies[0];
      expect(streamBody.context_type).toBe('project');
      expect(streamBody.project_id).toBe(projectId);
      expect(streamBody.active_file_path).toBe(created.topFileName);
      expect(typeof streamBody.active_file_hash).toBe('string');
      expect((streamBody.active_file_hash as string).length).toBeGreaterThan(5);

      expect(applyRequestBody).not.toBeNull();
      expect(applyRequestBody?.session_id).toBeTruthy();
      expect(applyRequestBody?.pending_patch_id).toBe('pending-e2e-1');
      expect(applyRequestBody?.expected_hash).toBe('fnv1a:abcd1234');
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('real llm project tool flow applies diff to file', async ({ page }) => {
    test.slow();
    test.setTimeout(240000);
    test.skip(!process.env.E2E_REAL_LLM, 'Set E2E_REAL_LLM=1 to run real LLM tool e2e.');

    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      await openProjectAndSelectFile(page, created.projectName, projectId, created.topFileName);
      await openChatSidebar(page);
      await ensureProjectChatSession(page, projectId);

      const streamReqPromise = page.waitForRequest((req) => (
        req.method() === 'POST' && req.url().includes('/api/chat/stream')
      ));

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();
      await input.fill(
        'Use tools to edit the currently active document. ' +
        'First call read_current_document. Then call apply_diff_current_document (dry_run=true) ' +
        'to replace exact text "hello project chat e2e" with "hello project chat AGENTIC e2e". ' +
        'After tool preview, stop and wait for user confirmation.'
      );

      const sendButton = page
        .locator('[data-name="input-box-input-controls"] button')
        .filter({ hasText: /Send|发送/ })
        .first();
      await expect(sendButton).toBeVisible();
      await sendButton.click();

      const streamReq = await streamReqPromise;
      const streamBody = streamReq.postDataJSON() as {
        context_type: string;
        project_id?: string;
        active_file_path?: string;
        active_file_hash?: string;
      };
      expect(streamBody.context_type).toBe('project');
      expect(streamBody.project_id).toBe(projectId);
      expect(streamBody.active_file_path).toBe(created.topFileName);
      expect(typeof streamBody.active_file_hash).toBe('string');
      expect((streamBody.active_file_hash || '').length).toBeGreaterThan(5);

      const applyDiffHeader = page.getByRole('button', { name: /apply_diff_current_document/ }).first();
      await expect(applyDiffHeader).toBeVisible({ timeout: 180000 });

      const applyActions = page.locator('[data-name="tool-apply-diff-actions"]').first();
      if (!(await applyActions.isVisible())) {
        await applyDiffHeader.click();
      }

      const applyButton = page.getByRole('button', { name: 'Apply Changes' }).first();
      await expect(applyButton).toBeVisible({ timeout: 180000 });
      await applyButton.click();

      await expect(page.getByRole('button', { name: 'Applied' }).first()).toBeVisible({ timeout: 30000 });

      const fileRes = await api.get(`/api/projects/${projectId}/files?path=${encodeURIComponent(created.topFileName)}`);
      expect(fileRes.ok()).toBeTruthy();
      const fileBody = await fileRes.json() as { content: string };
      expect(fileBody.content).toContain('hello project chat AGENTIC e2e');
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });

  test('real llm cross-file tool flow applies diff to non-active file', async ({ page }) => {
    test.slow();
    test.setTimeout(240000);
    test.skip(!process.env.E2E_REAL_LLM, 'Set E2E_REAL_LLM=1 to run real LLM tool e2e.');

    const api = await pwRequest.newContext({ baseURL: API_BASE });
    let projectId = '';
    let tempRoot = '';

    try {
      const created = await createTempProject(api);
      projectId = created.projectId;
      tempRoot = created.tempRoot;

      await openProjectAndSelectFile(page, created.projectName, projectId, created.topFileName);
      await openChatSidebar(page);
      await ensureProjectChatSession(page, projectId);

      const streamReqPromise = page.waitForRequest((req) => (
        req.method() === 'POST' && req.url().includes('/api/chat/stream')
      ));

      const input = page.locator('[data-name="input-box-root"] textarea');
      await expect(input).toBeVisible();
      await input.fill(
        'Use cross-file project tools only. Do NOT use read_current_document or apply_diff_current_document. ' +
        'Edit file src/app.py (not the active file). ' +
        'First call read_project_document for src/app.py, then call apply_diff_project_document with dry_run=true ' +
        'to replace exact text print("project chat") with print("project chat AGENTIC"). ' +
        'After diff preview, stop and wait for user confirmation.'
      );

      const sendButton = page
        .locator('[data-name="input-box-input-controls"] button')
        .filter({ hasText: /Send|发送/ })
        .first();
      await expect(sendButton).toBeVisible();
      await sendButton.click();

      const streamReq = await streamReqPromise;
      const streamBody = streamReq.postDataJSON() as {
        context_type: string;
        project_id?: string;
      };
      expect(streamBody.context_type).toBe('project');
      expect(streamBody.project_id).toBe(projectId);

      const applyDiffHeader = page.getByRole('button', { name: /apply_diff_project_document/ }).first();
      await expect(applyDiffHeader).toBeVisible({ timeout: 180000 });

      const applyActions = page.locator('[data-name="tool-apply-diff-actions"]').first();
      if (!(await applyActions.isVisible())) {
        await applyDiffHeader.click();
      }

      const applyButton = page.getByRole('button', { name: 'Apply Changes' }).first();
      await expect(applyButton).toBeVisible({ timeout: 180000 });
      await applyButton.click();

      await expect(page.getByRole('button', { name: 'Applied' }).first()).toBeVisible({ timeout: 30000 });

      const fileRes = await api.get(`/api/projects/${projectId}/files?path=${encodeURIComponent('src/app.py')}`);
      expect(fileRes.ok()).toBeTruthy();
      const fileBody = await fileRes.json() as { content: string };
      expect(fileBody.content).toContain('print("project chat AGENTIC")');
    } finally {
      if (projectId && tempRoot) {
        await cleanupProject(api, projectId, tempRoot);
      }
      await api.dispose();
    }
  });
});
