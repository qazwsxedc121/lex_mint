import { test, expect } from '@playwright/test';

test('provider advanced fields are collapsed by default', async ({ page }) => {
  await page.goto('/settings/providers/new');
  await expect(page.locator('[data-name="crud-create-page"]')).toBeVisible();

  const advancedField = page.locator('[data-name="form-field-__show_advanced"]');
  await expect(advancedField).toBeVisible();

  await expect(page.locator('[data-name="form-field-protocol"]')).toHaveCount(0);
  await expect(page.locator('[data-name="form-field-call_mode"]')).toHaveCount(0);

  await advancedField.locator('input[type="checkbox"]').click();

  await expect(page.locator('[data-name="form-field-protocol"]')).toBeVisible();
  await expect(page.locator('[data-name="form-field-call_mode"]')).toBeVisible();
});
