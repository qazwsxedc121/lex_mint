import { Page, Locator } from '@playwright/test';

/**
 * Page Object for the RAG Settings page (/settings/rag).
 */
export class RagSettingsPage {
  readonly page: Page;

  /** The preset button group container */
  readonly presetGroup: Locator;
  /** Individual preset buttons */
  readonly presetFast: Locator;
  readonly presetBalanced: Locator;
  readonly presetDeep: Locator;

  /** Number input fields affected by presets */
  readonly topKInput: Locator;
  readonly recallKInput: Locator;
  readonly maxPerDocInput: Locator;
  readonly scoreThresholdInput: Locator;

  /** Form actions */
  readonly saveButton: Locator;

  constructor(page: Page) {
    this.page = page;

    this.presetGroup = page.locator('[data-name="preset-retrieval_preset"]');
    // Preset buttons identified by their position in the group
    this.presetFast = this.presetGroup.locator('button').nth(0);
    this.presetBalanced = this.presetGroup.locator('button').nth(1);
    this.presetDeep = this.presetGroup.locator('button').nth(2);

    this.topKInput = page.locator('[data-name="form-field-top_k"] input[type="number"]');
    this.recallKInput = page.locator('[data-name="form-field-recall_k"] input[type="number"]');
    this.maxPerDocInput = page.locator('[data-name="form-field-max_per_doc"] input[type="number"]');
    this.scoreThresholdInput = page.locator('[data-name="form-field-score_threshold"] input[type="number"]');

    this.saveButton = page.locator('[data-name="config-form"] button[type="submit"]');
  }

  async goto() {
    await this.page.goto('/settings/rag');
    await this.page.waitForLoadState('networkidle');
  }

  /** Returns the currently active (highlighted) preset button, or null */
  async getActivePreset(): Promise<Locator | null> {
    for (const btn of [this.presetFast, this.presetBalanced, this.presetDeep]) {
      const classes = await btn.getAttribute('class');
      if (classes?.includes('ring-blue-500')) {
        return btn;
      }
    }
    return null;
  }

  /** Read the current numeric values of the 4 preset-affected fields */
  async getPresetFieldValues() {
    return {
      top_k: Number(await this.topKInput.inputValue()),
      recall_k: Number(await this.recallKInput.inputValue()),
      max_per_doc: Number(await this.maxPerDocInput.inputValue()),
      score_threshold: Number(await this.scoreThresholdInput.inputValue()),
    };
  }
}
