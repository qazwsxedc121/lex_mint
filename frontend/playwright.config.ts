import { defineConfig, devices } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const isWindows = process.platform === 'win32';
const configDir = path.dirname(fileURLToPath(import.meta.url));

function loadRootEnv(): Record<string, string> {
  const envPath = path.resolve(configDir, '..', '.env');
  if (!fs.existsSync(envPath)) {
    return {};
  }

  const parsed: Record<string, string> = {};
  const content = fs.readFileSync(envPath, 'utf-8');
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }
    const eqIndex = line.indexOf('=');
    if (eqIndex <= 0) {
      continue;
    }
    const key = line.slice(0, eqIndex).trim();
    let value = line.slice(eqIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    parsed[key] = value;
  }
  return parsed;
}

function parsePort(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

const rootEnv = loadRootEnv();
const frontendPort = parsePort(process.env.FRONTEND_PORT ?? rootEnv.FRONTEND_PORT, 5181);
const backendPort = parsePort(process.env.API_PORT ?? rootEnv.API_PORT, 8901);

// Keep test process and child processes aligned with root .env defaults.
process.env.FRONTEND_PORT = String(frontendPort);
process.env.API_PORT = String(backendPort);

const backendCommand = isWindows
  ? `.\\venv\\Scripts\\python -m uvicorn src.api.main:app --host 127.0.0.1 --port ${backendPort}`
  : `./venv/bin/python -m uvicorn src.api.main:app --host 127.0.0.1 --port ${backendPort}`;
const frontendCommand = `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`;

export default defineConfig({
  testDir: './tests/e2e/specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: backendCommand,
      cwd: '..',
      url: `http://localhost:${backendPort}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: frontendCommand,
      url: `http://localhost:${frontendPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
