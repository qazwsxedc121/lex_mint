import fs from 'fs';
import os from 'os';
import path from 'path';
import { test, expect, request as pwRequest } from '@playwright/test';

if (!process.env.API_PORT) {
  throw new Error('API_PORT is required for e2e tests.');
}
const API_BASE = `http://127.0.0.1:${process.env.API_PORT}`;

test.describe('Projects smoke', () => {
  test('can open a project and view file tree + file content', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lex-mint-e2e-project-'));
    const projectName = `e2e-project-${Date.now()}`;
    const topFileName = 'README.e2e.md';
    const topFileContent = '# Projects Smoke\nhello projects e2e\n';
    let projectId = '';

    fs.writeFileSync(path.join(tempRoot, topFileName), topFileContent, 'utf-8');
    fs.mkdirSync(path.join(tempRoot, 'src'));
    fs.writeFileSync(path.join(tempRoot, 'src', 'app.py'), 'print("ok")\n', 'utf-8');

    try {
      const createRes = await api.post('/api/projects', {
        data: {
          name: projectName,
          root_path: tempRoot,
          description: 'e2e projects smoke',
        },
      });
      expect(createRes.ok()).toBeTruthy();

      const created = await createRes.json();
      projectId = created.id;
      expect(projectId).toMatch(/^proj_[a-f0-9]{12}$/);

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
      await expect(page.locator('[data-name="file-viewer-panel"]')).toBeVisible();

      const topFileNode = page.locator('[data-name="file-tree"]').getByText(topFileName, { exact: true });
      await expect(topFileNode).toBeVisible();
      await topFileNode.click();

      await expect(page.locator('[data-name="file-viewer-breadcrumb-row"]')).toContainText(topFileName);
      await expect(page.locator('.cm-content')).toContainText('hello projects e2e');
    } finally {
      if (projectId) {
        await api.delete(`/api/projects/${projectId}`);
      }
      await api.dispose();
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });

  test('can search project text and open matched file', async ({ page }) => {
    const api = await pwRequest.newContext({ baseURL: API_BASE });
    const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lex-mint-e2e-project-'));
    const projectName = `e2e-project-search-${Date.now()}`;
    const topFileName = 'README.e2e.md';
    const searchToken = `needle-project-search-${Date.now()}`;
    let projectId = '';

    fs.writeFileSync(path.join(tempRoot, topFileName), '# Projects Search Smoke\n', 'utf-8');
    fs.mkdirSync(path.join(tempRoot, 'src'));
    fs.writeFileSync(path.join(tempRoot, 'src', 'app.py'), `print("${searchToken}")\n`, 'utf-8');

    try {
      const createRes = await api.post('/api/projects', {
        data: {
          name: projectName,
          root_path: tempRoot,
          description: 'e2e projects text search',
        },
      });
      expect(createRes.ok()).toBeTruthy();

      const created = await createRes.json();
      projectId = created.id;
      expect(projectId).toMatch(/^proj_[a-f0-9]{12}$/);

      await page.goto('/projects');
      await expect(page.locator('[data-name="projects-module-root"]')).toBeVisible();

      const projectCard = page.getByRole('button', { name: new RegExp(projectName) });
      await expect(projectCard).toBeVisible();
      await projectCard.click();

      await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/project$`));
      await page.getByRole('link', { name: 'Search' }).click();
      await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/search$`));
      await expect(page.locator('[data-name="project-search-view"]')).toBeVisible();

      const textSearchInput = page.locator('[data-name="project-search-input"]');
      await expect(textSearchInput).toBeVisible();
      await textSearchInput.fill(searchToken);

      const resultItem = page.locator('[data-name="project-search-result-item"]').first();
      await expect(resultItem).toBeVisible({ timeout: 10000 });
      await expect(resultItem).toContainText('src/app.py');
      await resultItem.locator('button').first().click();

      await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/files$`));
      await expect(page.locator('[data-name="file-viewer-breadcrumb-row"]')).toContainText('src');
      await expect(page.locator('[data-name="file-viewer-breadcrumb-row"]')).toContainText('app.py');
      await expect(page.locator('.cm-content')).toContainText(searchToken);
    } finally {
      if (projectId) {
        await api.delete(`/api/projects/${projectId}`);
      }
      await api.dispose();
      fs.rmSync(tempRoot, { recursive: true, force: true });
    }
  });
});
