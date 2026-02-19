import { test, expect, request as pwRequest } from '@playwright/test';
import { GroupChatPage } from '../pages/GroupChatPage';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

test.describe('Group Chat', () => {
  let groupChat: GroupChatPage;
  const createdSessionIds: string[] = [];

  test.beforeEach(async ({ page }) => {
    groupChat = new GroupChatPage(page);
    await groupChat.goto();
  });

  test.afterEach(async ({ page }) => {
    // Clean up sessions navigated to via UI
    const url = page.url();
    const match = url.match(/\/chat\/([a-f0-9-]+)/);
    if (match) {
      createdSessionIds.push(match[1]);
    }

    // Delete all tracked sessions
    for (const sid of createdSessionIds) {
      try {
        await groupChat.deleteSessionViaAPI(sid);
      } catch {
        // Ignore cleanup errors
      }
    }
    createdSessionIds.length = 0;

    await groupChat.dispose();
  });

  // ──────────────────────────────────────────────
  // Sidebar button
  // ──────────────────────────────────────────────
  test('group chat button is visible in sidebar', async () => {
    await expect(groupChat.groupChatButton).toBeVisible();
  });

  // ──────────────────────────────────────────────
  // Modal open / close
  // ──────────────────────────────────────────────
  test('clicking group chat button opens the modal', async () => {
    await groupChat.openGroupChatModal();
    await expect(groupChat.modal).toBeVisible();
    await expect(groupChat.modalTitle).toBeVisible();
  });

  test('cancel button closes the modal', async () => {
    await groupChat.openGroupChatModal();
    await groupChat.closeModal();
    await expect(groupChat.modal).not.toBeVisible();
  });

  test('clicking backdrop closes the modal', async () => {
    await groupChat.openGroupChatModal();
    await groupChat.closeModalByBackdrop();
    await expect(groupChat.modal).not.toBeVisible();
  });

  // ──────────────────────────────────────────────
  // Assistant listing
  // ──────────────────────────────────────────────
  test('modal lists enabled assistants with checkboxes', async () => {
    const allAssistants = await groupChat.getAssistantsViaAPI();
    const enabledAssistants = allAssistants.filter(a => a.enabled);

    await groupChat.openGroupChatModal();
    await expect
      .poll(async () => groupChat.getAssistantCheckboxes().count(), {
        timeout: 8000,
        message: 'Group chat modal did not finish loading enabled assistants in time.',
      })
      .toBe(enabledAssistants.length);
  });

  // ──────────────────────────────────────────────
  // Selection & Create button state
  // ──────────────────────────────────────────────
  test('create button is disabled when fewer than 2 assistants selected', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    await groupChat.openGroupChatModal();

    // Initially: none selected => disabled
    expect(await groupChat.isCreateButtonEnabled()).toBe(false);

    // Select 1 => still disabled
    await groupChat.toggleAssistant(0);
    expect(await groupChat.getSelectedCount()).toBe(1);
    expect(await groupChat.isCreateButtonEnabled()).toBe(false);
  });

  test('create button is enabled when 2+ assistants selected', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    await groupChat.openGroupChatModal();

    await groupChat.toggleAssistant(0);
    await groupChat.toggleAssistant(1);
    expect(await groupChat.getSelectedCount()).toBe(2);
    expect(await groupChat.isCreateButtonEnabled()).toBe(true);
  });

  test('deselecting an assistant updates count correctly', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    await groupChat.openGroupChatModal();

    // Select 2
    await groupChat.toggleAssistant(0);
    await groupChat.toggleAssistant(1);
    expect(await groupChat.getSelectedCount()).toBe(2);

    // Deselect 1
    await groupChat.toggleAssistant(0);
    expect(await groupChat.getSelectedCount()).toBe(1);
    expect(await groupChat.isCreateButtonEnabled()).toBe(false);
  });

  // ──────────────────────────────────────────────
  // Session creation
  // ──────────────────────────────────────────────
  test('creating a group chat navigates to the new session', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    await groupChat.openGroupChatModal();
    await groupChat.toggleAssistant(0);
    await groupChat.toggleAssistant(1);
    await groupChat.clickCreate();

    // Modal should close
    await expect(groupChat.modal).not.toBeVisible();

    // Should navigate to the new session
    const sessionId = await groupChat.waitForSessionNavigation();
    expect(sessionId).toBeTruthy();
    expect(sessionId).toMatch(/^[a-f0-9-]+$/);
  });

  test('create session API sends group_assistants in request body', async ({ page }) => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    await groupChat.openGroupChatModal();
    await groupChat.toggleAssistant(0);
    await groupChat.toggleAssistant(1);

    // Intercept the session creation API call via browser network
    const createPromise = page.waitForRequest(
      (req) => req.url().includes('/api/sessions') && req.method() === 'POST'
    );

    await groupChat.clickCreate();

    const createRequest = await createPromise;
    const body = createRequest.postDataJSON();

    expect(body).toHaveProperty('group_assistants');
    expect(body.group_assistants).toBeInstanceOf(Array);
    expect(body.group_assistants.length).toBeGreaterThanOrEqual(2);
  });

  // ──────────────────────────────────────────────
  // Group chat view elements
  // ──────────────────────────────────────────────
  test('group chat session shows participant badge instead of assistant selector', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    // Create group session via API for faster setup
    const ids = enabled.slice(0, 2).map(a => a.id);
    const sessionId = await groupChat.createGroupSessionViaAPI(ids);
    createdSessionIds.push(sessionId);

    await groupChat.gotoSession(sessionId);

    // Participants badge should be visible
    await expect(groupChat.participantsBadge).toBeVisible();
    const count = await groupChat.getParticipantCount();
    expect(count).toBe(2);
  });

  // ──────────────────────────────────────────────
  // API: group-assistants endpoint
  // ──────────────────────────────────────────────
  test('update group assistants API validates minimum 2', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    // Create a group session first
    const ids = enabled.slice(0, 2).map(a => a.id);
    const sessionId = await groupChat.createGroupSessionViaAPI(ids);
    createdSessionIds.push(sessionId);

    // Try updating with only 1 assistant via direct API (should fail with 400)
    const apiCtx = await pwRequest.newContext({ baseURL: API_BASE });
    try {
      const response = await apiCtx.put(
        `/api/sessions/${sessionId}/group-assistants?context_type=chat`,
        { data: { group_assistants: [enabled[0].id] } }
      );
      expect(response.status()).toBe(400);
    } finally {
      await apiCtx.dispose();
    }
  });

  test('update group assistants API accepts valid list', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    const ids = enabled.slice(0, 2).map(a => a.id);
    const sessionId = await groupChat.createGroupSessionViaAPI(ids);
    createdSessionIds.push(sessionId);

    const apiCtx = await pwRequest.newContext({ baseURL: API_BASE });
    try {
      const response = await apiCtx.put(
        `/api/sessions/${sessionId}/group-assistants?context_type=chat`,
        { data: { group_assistants: ids } }
      );
      expect(response.status()).toBe(200);
    } finally {
      await apiCtx.dispose();
    }
  });

  // ──────────────────────────────────────────────
  // API: session detail includes group_assistants
  // ──────────────────────────────────────────────
  test('session detail API returns group_assistants field', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    const ids = enabled.slice(0, 2).map(a => a.id);
    const sessionId = await groupChat.createGroupSessionViaAPI(ids);
    createdSessionIds.push(sessionId);

    const apiCtx = await pwRequest.newContext({ baseURL: API_BASE });
    try {
      const response = await apiCtx.get(
        `/api/sessions/${sessionId}?context_type=chat`
      );
      expect(response.status()).toBe(200);

      const session = await response.json();
      expect(session.group_assistants).toBeDefined();
      expect(session.group_assistants).toEqual(expect.arrayContaining(ids));
      expect(session.group_assistants.length).toBe(2);
    } finally {
      await apiCtx.dispose();
    }
  });

  // ──────────────────────────────────────────────
  // Session list includes group_assistants
  // ──────────────────────────────────────────────
  test('session list API includes group_assistants for group sessions', async () => {
    const assistants = await groupChat.getAssistantsViaAPI();
    const enabled = assistants.filter(a => a.enabled);
    test.skip(enabled.length < 2, 'Need at least 2 enabled assistants');

    const ids = enabled.slice(0, 2).map(a => a.id);
    const sessionId = await groupChat.createGroupSessionViaAPI(ids);
    createdSessionIds.push(sessionId);

    const apiCtx = await pwRequest.newContext({ baseURL: API_BASE });
    try {
      const response = await apiCtx.get('/api/sessions?context_type=chat');
      expect(response.status()).toBe(200);

      const body = await response.json();
      const sessions = body.sessions ?? body;
      const groupSession = sessions.find((s: any) => s.session_id === sessionId);
      expect(groupSession).toBeDefined();
      expect(groupSession.group_assistants).toEqual(expect.arrayContaining(ids));
    } finally {
      await apiCtx.dispose();
    }
  });
});
