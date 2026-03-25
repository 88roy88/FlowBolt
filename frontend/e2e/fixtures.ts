/**
 * Shared Playwright fixtures for E2E tests.
 *
 * In mock mode (default): sets up route handlers + mock WebSockets.
 * In real mode (BACKEND_URL set): no mocks, tests hit the real backend.
 */
import { test as base } from '@playwright/test';
import { setupMockAPI, type MockAPIOptions } from './mocks/api';
import { setupMockWS, sendChatEvents } from './mocks/ws';

const isMock = !process.env.BACKEND_URL;

export const test = base.extend<{
  /** Set up mocks with custom options. Call before page.goto(). */
  mockOptions: MockAPIOptions;
  /** Send events to the mock chat WebSocket. No-op in real mode. */
  sendChatEvents: (events: Record<string, unknown>[], delay?: number) => Promise<void>;
}>({
  mockOptions: [{}, { option: true }],
  page: async ({ page, mockOptions }, use) => {
    if (isMock) {
      await setupMockWS(page);
      await setupMockAPI(page, mockOptions);
      // Avoid cross-test leakage in the same worker (e.g. editor sets has-projects; AppShell caches
      // project-has-messages). Register first so describe-level addInitScript can override.
      await page.addInitScript(() => {
        try {
          localStorage.removeItem('has-projects');
          for (const k of Object.keys(localStorage)) {
            if (k.startsWith('project-has-messages:')) localStorage.removeItem(k);
          }
        } catch {
          /* ignore */
        }
      });
    }
    await use(page);
  },
  sendChatEvents: async ({ page }, use) => {
    await use(async (events, delay) => {
      if (isMock) {
        await sendChatEvents(page, events, delay);
      }
    });
  },
});

export { expect } from '@playwright/test';
