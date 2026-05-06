/**
 * Shared Playwright fixtures for E2E tests.
 *
 * In mock mode (default): sets up route handlers + mock WebSockets.
 * In real mode (BACKEND_URL set): no mocks, tests hit the real backend.
 */
import { test as base } from '@playwright/test';
import { setupMockAPI, type MockAPIOptions } from './mocks/api';
import { setupMockWS, sendChatEvents } from './mocks/ws';

// Playwright specs run in Node; declare the env shape without requiring @types/node.
declare const process: { env: Record<string, string | undefined> };

const isMock = !process.env.BACKEND_URL;

/** Opaque token used to represent a valid authenticated user in E2E tests. */
export const E2E_AUTH_TOKEN = 'e2e-test-token';

/** localStorage key that the auth module uses (matches VITE_AUTH_STORAGE_KEY). */
export const AUTH_STORAGE_KEY = 'Auth';

export const test = base.extend<{
  /** Set up mocks with custom options. Call before page.goto(). */
  mockOptions: MockAPIOptions;
  /** Send events to the mock chat WebSocket. No-op in real mode. */
  sendChatEvents: (events: Record<string, unknown>[], delay?: number) => Promise<void>;
  /**
   * When true, skip seeding the auth token into localStorage so the auth gate
   * is shown. Defaults to false (auth token is seeded, sign-in screen is skipped).
   */
  noAuth: boolean;
}>({
  noAuth: [false, { option: true }],
  mockOptions: [{}, { option: true }],
  page: async ({ page, mockOptions, noAuth }, use) => {
    if (isMock) {
      await setupMockWS(page);
      await setupMockAPI(page, mockOptions);
      // Avoid cross-test leakage in the same worker (e.g. editor sets has-projects; AppShell caches
      // project-has-messages). Register first so describe-level addInitScript can override.
      await page.addInitScript(
        ({ skipAuth, storageKey, token }: { skipAuth: boolean; storageKey: string; token: string }) => {
          try {
            localStorage.removeItem('has-projects');
            for (const k of Object.keys(localStorage)) {
              if (k.startsWith('project-has-messages:')) localStorage.removeItem(k);
            }
            if (!skipAuth) {
              // Seed auth token so tests skip the sign-in screen
              localStorage.setItem(storageKey, JSON.stringify({ auth_token: token }));
            } else {
              // Ensure no stale token from a prior test run leaks in
              localStorage.removeItem(storageKey);
            }
          } catch {
            /* ignore */
          }
        },
        { skipAuth: noAuth, storageKey: AUTH_STORAGE_KEY, token: E2E_AUTH_TOKEN },
      );
    } else {
      // Real-backend mode: seed the auth token unless the test explicitly opts out.
      await page.addInitScript(
        ({ skipAuth, storageKey, token }: { skipAuth: boolean; storageKey: string; token: string }) => {
          try {
            if (!skipAuth) {
              localStorage.setItem(storageKey, JSON.stringify({ auth_token: token }));
            } else {
              localStorage.removeItem(storageKey);
            }
          } catch {
            /* ignore */
          }
        },
        { skipAuth: noAuth, storageKey: AUTH_STORAGE_KEY, token: E2E_AUTH_TOKEN },
      );
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
