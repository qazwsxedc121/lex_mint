import { test, expect } from '@playwright/test';
import { RagSettingsPage } from '../pages/RagSettingsPage';

const PRESETS = {
  fast: { top_k: 3, recall_k: 10, max_per_doc: 1, score_threshold: 0.4 },
  balanced: { top_k: 5, recall_k: 20, max_per_doc: 2, score_threshold: 0.3 },
  deep: { top_k: 10, recall_k: 50, max_per_doc: 3, score_threshold: 0.2 },
} as const;

test.describe('RAG Retrieval Presets', () => {
  let ragPage: RagSettingsPage;

  test.beforeEach(async ({ page }) => {
    ragPage = new RagSettingsPage(page);
    await ragPage.goto();
  });

  test('preset buttons are visible', async () => {
    await expect(ragPage.presetGroup).toBeVisible();
    await expect(ragPage.presetFast).toBeVisible();
    await expect(ragPage.presetBalanced).toBeVisible();
    await expect(ragPage.presetDeep).toBeVisible();
  });

  test('clicking Fast preset updates field values', async () => {
    await ragPage.presetFast.click();

    const values = await ragPage.getPresetFieldValues();
    expect(values).toEqual(PRESETS.fast);
  });

  test('clicking Balanced preset updates field values', async () => {
    await ragPage.presetBalanced.click();

    const values = await ragPage.getPresetFieldValues();
    expect(values).toEqual(PRESETS.balanced);
  });

  test('clicking Deep preset updates field values', async () => {
    await ragPage.presetDeep.click();

    const values = await ragPage.getPresetFieldValues();
    expect(values).toEqual(PRESETS.deep);
  });

  test('active preset is highlighted with ring style', async () => {
    await ragPage.presetFast.click();

    const fastClasses = await ragPage.presetFast.getAttribute('class');
    expect(fastClasses).toContain('ring-blue-500');

    // Other presets should NOT have the active ring
    const balancedClasses = await ragPage.presetBalanced.getAttribute('class');
    expect(balancedClasses).not.toContain('ring-blue-500');
  });

  test('switching presets changes highlight', async () => {
    await ragPage.presetFast.click();
    let fastClasses = await ragPage.presetFast.getAttribute('class');
    expect(fastClasses).toContain('ring-blue-500');

    // Switch to Deep
    await ragPage.presetDeep.click();
    fastClasses = await ragPage.presetFast.getAttribute('class');
    const deepClasses = await ragPage.presetDeep.getAttribute('class');

    expect(fastClasses).not.toContain('ring-blue-500');
    expect(deepClasses).toContain('ring-blue-500');
  });

  test('manually changing a field value deactivates preset highlight', async () => {
    await ragPage.presetBalanced.click();

    // Verify highlight is active
    const classes = await ragPage.presetBalanced.getAttribute('class');
    expect(classes).toContain('ring-blue-500');

    // Manually change top_k to a non-preset value
    await ragPage.topKInput.fill('7');
    // Trigger change event
    await ragPage.topKInput.press('Tab');

    // No preset should be highlighted now
    const activePreset = await ragPage.getActivePreset();
    expect(activePreset).toBeNull();
  });

  test('saving does not send retrieval_preset to API', async ({ page }) => {
    // Click a preset first
    await ragPage.presetFast.click();

    // Intercept the save API call
    const savePromise = page.waitForRequest(
      (req) => req.url().includes('/api/rag/config') && req.method() === 'PUT'
    );

    await ragPage.saveButton.click();

    const saveRequest = await savePromise;
    const body = saveRequest.postDataJSON();

    // retrieval_preset should be stripped by transformSave
    expect(body).not.toHaveProperty('retrieval_preset');

    // But the preset effect values should be present
    expect(body.top_k).toBe(3);
    expect(body.recall_k).toBe(10);
  });
});
