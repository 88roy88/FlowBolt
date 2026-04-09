import { defineConfig, devices } from '@playwright/test';

const headed = process.env.HEADED === '1';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,       // single long flow — no parallelism needed
  forbidOnly: !!process.env.CI,
  retries: 0,                 // no retries: each step depends on the previous
  workers: 1,
  reporter: process.env.CI ? 'github' : [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:5173',
    headless: !headed,
    slowMo: headed ? 120 : 0, // 120ms per keystroke/action — natural typing speed
    trace: 'on',              // always capture trace for debugging
    screenshot: 'on',
    video: 'on',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
  ],

  // globalSetup/Teardown spawn all services (backend, frontend, mocks)
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',

  // Generous timeout: real sandbox takes time to scaffold + build
  timeout: 5 * 60 * 1000,          // 5 min per test
  expect: { timeout: 30_000 },     // 30s for assertions
});
