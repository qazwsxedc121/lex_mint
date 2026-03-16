import { expect, test } from '@playwright/test';

test.describe('Async run center resume', () => {
  test('shows checkpoint and resumes a failed workflow run', async ({ page }) => {
    let resumeBody: Record<string, unknown> | null = null;
    let runStatus: 'failed' | 'running' = 'failed';

    await page.route('**/api/runs**', async (route) => {
      const request = route.request();
      if (request.method() !== 'GET') {
        await route.continue();
        return;
      }

      const nowIso = new Date().toISOString();
      const checkpointId = 'cp-42';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          runs: [
            {
              run_id: 'run-e2e-resume-1',
              stream_id: 'run-e2e-resume-1',
              kind: 'workflow',
              status: runStatus,
              context_type: 'workflow',
              project_id: null,
              session_id: null,
              workflow_id: 'wf-e2e',
              created_at: nowIso,
              updated_at: nowIso,
              started_at: nowIso,
              finished_at: runStatus === 'running' ? null : nowIso,
              request_payload: { checkpoint_id: checkpointId },
              result_summary: { last_checkpoint_id: checkpointId },
              error: runStatus === 'running' ? null : 'mock failed',
              last_event_id: null,
              last_seq: runStatus === 'running' ? 6 : 5,
            },
          ],
        }),
      });
    });

    await page.route('**/api/runs/run-e2e-resume-1/resume', async (route) => {
      resumeBody = (route.request().postDataJSON() || {}) as Record<string, unknown>;
      runStatus = 'running';
      const nowIso = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: 'run-e2e-resume-1',
          stream_id: 'run-e2e-resume-1',
          kind: 'workflow',
          status: 'running',
          context_type: 'workflow',
          project_id: null,
          session_id: null,
          workflow_id: 'wf-e2e',
          created_at: nowIso,
          updated_at: nowIso,
          started_at: nowIso,
          finished_at: null,
          request_payload: { checkpoint_id: 'cp-42' },
          result_summary: { last_checkpoint_id: 'cp-42' },
          error: null,
          last_event_id: null,
          last_seq: 6,
        }),
      });
    });

    await page.goto('/chat');
    await expect(page.locator('[data-name="async-run-center-toggle"]')).toBeVisible();

    await page.locator('[data-name="async-run-center-toggle"]').click();
    await expect(page.locator('[data-name="async-run-center-panel"]')).toBeVisible();

    const runItem = page.locator('[data-name="async-run-center-item"]').first();
    await expect(runItem).toContainText('workflow: wf-e2e');
    await expect(runItem.locator('[data-name="async-run-center-checkpoint"]')).toContainText('cp-42');
    await expect(runItem.locator('[data-name="async-run-center-resume"]')).toBeVisible();

    await runItem.locator('[data-name="async-run-center-resume"]').click();

    await expect.poll(() => resumeBody?.['checkpoint_id']).toBe('cp-42');
    await expect(runItem).toContainText('running');
  });
});
