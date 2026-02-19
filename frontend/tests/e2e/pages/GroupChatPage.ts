import { Page, Locator, expect, APIRequestContext, request as pwRequest } from '@playwright/test';

const API_BASE = `http://localhost:${process.env.API_PORT || '8901'}`;

/**
 * Page Object for Group Chat interactions.
 * Covers the sidebar button, creation modal, and in-chat group elements.
 */
export class GroupChatPage {
  readonly page: Page;
  private _apiContext: APIRequestContext | null = null;

  // Sidebar
  readonly sidebar: Locator;
  readonly groupChatButton: Locator;
  readonly newChatButton: Locator;

  // GroupChatCreateModal
  readonly modalBackdrop: Locator;
  readonly modal: Locator;
  readonly modalTitle: Locator;
  readonly modalHint: Locator;
  readonly modalCancelButton: Locator;
  readonly modalCreateButton: Locator;

  // ChatView group indicators
  readonly participantsBadge: Locator;
  readonly assistantLabels: Locator;

  constructor(page: Page) {
    this.page = page;

    // Sidebar elements
    this.sidebar = page.locator('[data-name="chat-sidebar"]');
    this.groupChatButton = this.sidebar.locator('button', { has: page.locator('svg.h-5.w-5') }).filter({ hasText: '' }).locator('xpath=..').locator('button').nth(1);
    // More reliable: find by title attribute
    this.groupChatButton = page.locator('button[title="Group Chat"], button[title="群聊"]');
    this.newChatButton = page.locator('[data-name="chat-sidebar-toolbar"] button').first();

    // Modal elements
    this.modalBackdrop = page.locator('[data-name="group-chat-modal-backdrop"]');
    this.modal = page.locator('[data-name="group-chat-modal"]');
    this.modalTitle = this.modal.locator('h3');
    this.modalHint = this.modal.locator('p').first();
    this.modalCancelButton = this.modal.locator('button').filter({ hasText: /Cancel|取消/ });
    this.modalCreateButton = this.modal.locator('button').filter({ hasText: /Create|创建|\.\.\./ });

    // Group chat view elements
    this.participantsBadge = page.locator('[data-name="group-chat-participants"]');
    this.assistantLabels = page.locator('[data-name="message-bubble-assistant-label"]');
  }

  /** Navigate to the main chat page */
  async goto() {
    await this.page.goto('/chat');
    await this.page.waitForLoadState('networkidle');
  }

  /** Navigate to a specific session */
  async gotoSession(sessionId: string) {
    await this.page.goto(`/chat/${sessionId}`);
    await this.page.waitForLoadState('networkidle');
  }

  /** Open the group chat creation modal */
  async openGroupChatModal() {
    await this.groupChatButton.click();
    await expect(this.modal).toBeVisible();
  }

  /** Get all assistant checkboxes in the modal */
  getAssistantCheckboxes(): Locator {
    return this.modal.locator('input[type="checkbox"]');
  }

  /** Get all assistant labels in the modal */
  getAssistantLabels(): Locator {
    return this.modal.locator('label');
  }

  /** Toggle an assistant checkbox by index (0-based) */
  async toggleAssistant(index: number) {
    await this.getAssistantCheckboxes().nth(index).click();
  }

  /** Toggle an assistant checkbox by name text */
  async toggleAssistantByName(name: string) {
    const label = this.modal.locator('label').filter({ hasText: name });
    await label.click();
  }

  /** Get number of checked assistants */
  async getSelectedCount(): Promise<number> {
    const checkboxes = this.getAssistantCheckboxes();
    const count = await checkboxes.count();
    let selected = 0;
    for (let i = 0; i < count; i++) {
      if (await checkboxes.nth(i).isChecked()) {
        selected++;
      }
    }
    return selected;
  }

  /** Check if the Create button is enabled */
  async isCreateButtonEnabled(): Promise<boolean> {
    return !(await this.modalCreateButton.isDisabled());
  }

  /** Click the Create button to create the group chat session */
  async clickCreate() {
    await this.modalCreateButton.click();
  }

  /** Close the modal via the Cancel button */
  async closeModal() {
    await this.modalCancelButton.click();
  }

  /** Close the modal via backdrop click */
  async closeModalByBackdrop() {
    // Click the backdrop (outside the modal)
    await this.modalBackdrop.click({ position: { x: 5, y: 5 } });
  }

  /** Wait for navigation to a group chat session */
  async waitForSessionNavigation(): Promise<string> {
    await this.page.waitForURL(/\/chat\/[a-f0-9-]+/);
    const url = this.page.url();
    const match = url.match(/\/chat\/([a-f0-9-]+)/);
    return match ? match[1] : '';
  }

  /** Get the participant count from the badge */
  async getParticipantCount(): Promise<number | null> {
    if (!(await this.participantsBadge.isVisible())) return null;
    const text = await this.participantsBadge.textContent();
    const match = text?.match(/(\d+)/);
    return match ? parseInt(match[1], 10) : null;
  }

  /** Get all assistant names shown on message bubbles */
  async getMessageAssistantNames(): Promise<string[]> {
    const labels = this.assistantLabels;
    const count = await labels.count();
    const names: string[] = [];
    for (let i = 0; i < count; i++) {
      const text = await labels.nth(i).textContent();
      if (text) names.push(text.trim());
    }
    return names;
  }

  /** Get or create a standalone API request context (bypasses page baseURL) */
  private async apiContext(): Promise<APIRequestContext> {
    if (!this._apiContext) {
      this._apiContext = await pwRequest.newContext({ baseURL: API_BASE });
    }
    return this._apiContext;
  }

  /** Create a group chat session via API (for test setup) */
  async createGroupSessionViaAPI(assistantIds: string[]): Promise<string> {
    const api = await this.apiContext();
    const response = await api.post('/api/sessions?context_type=chat', {
      data: { group_assistants: assistantIds },
    });
    const body = await response.json();
    return body.session_id;
  }

  /** Delete a session via API (for cleanup) */
  async deleteSessionViaAPI(sessionId: string): Promise<void> {
    const api = await this.apiContext();
    await api.delete(`/api/sessions/${sessionId}?context_type=chat`);
  }

  /** Get available assistants via API (for test setup) */
  async getAssistantsViaAPI(): Promise<Array<{ id: string; name: string; enabled: boolean }>> {
    const api = await this.apiContext();
    const response = await api.get('/api/assistants');
    return response.json();
  }

  /** Dispose the API context (call in afterAll/afterEach) */
  async dispose(): Promise<void> {
    if (this._apiContext) {
      await this._apiContext.dispose();
      this._apiContext = null;
    }
  }
}
