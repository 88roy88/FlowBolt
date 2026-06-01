/**
 * Auth gate E2E tests.
 *
 * Mock mode (default): validates UI state transitions driven by localStorage
 * credentials — no real backend or SSO required.
 *
 * Real-backend mode (BACKEND_URL set): smoke-tests that authenticated requests
 * reach the API and unauthenticated requests stay gated in the UI.
 *
 * Strict-JWT smoke (BACKEND_URL + AUTH_REQUIRE_JWT env): verifies the backend
 * rejects unauthenticated requests with 401 rather than allowing 611noat access.
 */
import { test, expect, E2E_AUTH_TOKEN, AUTH_STORAGE_KEY } from './fixtures';

// Playwright specs run in Node; declare the env shape without requiring @types/node.
declare const process: { env: Record<string, string | undefined> };

const isMock = !process.env.BACKEND_URL;
const isStrictJwt = process.env.AUTH_REQUIRE_JWT === 'true';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Seed a valid opaque token into localStorage before page load. */
async function seedValidToken(page: import('@playwright/test').Page) {
  await page.addInitScript(
    ({ key, token }: { key: string; token: string }) => {
      try {
        localStorage.setItem(key, JSON.stringify({ auth_token: token }));
      } catch { /* ignore */ }
    },
    { key: AUTH_STORAGE_KEY, token: E2E_AUTH_TOKEN },
  );
}

/** Seed an already-expired token into localStorage before page load. */
async function seedExpiredToken(page: import('@playwright/test').Page) {
  await page.addInitScript(
    ({ key }: { key: string }) => {
      try {
        localStorage.setItem(
          key,
          JSON.stringify({ auth_token: 'expired-token', exp: 1577836800 }),
        );
      } catch { /* ignore */ }
    },
    { key: AUTH_STORAGE_KEY },
  );
}

// ---------------------------------------------------------------------------
// Mock-mode auth gate tests
// These run without a real backend; the Vite dev server's baked-in
// VITE_AUTH_PROVIDER_URL triggers AuthGate to enforce sign-in.
// ---------------------------------------------------------------------------

test.describe('Auth gate — sign-in required (mock mode)', () => {
  test.skip(!isMock, 'mock-mode only');
  test.use({ noAuth: true });

  test('unauthenticated user sees sign-in gate', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Sign in to continue')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('expired token is treated as unauthenticated', async ({ page }) => {
    // Override: seed an expired token instead of no token
    await seedExpiredToken(page);
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Sign in to continue')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('clicking Sign In opens iframe modal', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: 'Sign In' }).click();

    // IframeModal renders an <iframe> pointing at the provider URL
    await expect(page.locator('iframe')).toBeVisible({ timeout: 5_000 });
  });

  test('cancelling iframe modal returns to sign-in gate', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page.locator('iframe')).toBeVisible({ timeout: 5_000 });

    // The ✕ close button inside IframeModal cancels sign-in
    await page.locator('button').filter({ hasText: '✕' }).click();

    await expect(page.locator('iframe')).not.toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Sign in to continue')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Mock-mode authenticated state tests
// ---------------------------------------------------------------------------

test.describe('Auth gate — authenticated state (mock mode)', () => {
  test.skip(!isMock, 'mock-mode only');

  test('valid token bypasses sign-in gate and shows app', async ({ page }) => {
    // Default fixture seeds valid token — gate should not appear
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('Sign in to continue')).not.toBeVisible({ timeout: 10_000 });
    // App shell is up when at least one of its core landmarks appears
    await expect(
      page.getByRole('button', { name: /new project/i }).or(page.getByText('Test Model')),
    ).toBeVisible({ timeout: 15_000 });
  });

  test('clearing credentials transitions back to sign-in gate', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // Wait until app shell is rendered (gate is in ready state)
    await expect(
      page.getByRole('button', { name: /new project/i }).or(page.getByText('Test Model')),
    ).toBeVisible({ timeout: 15_000 });

    // Simulate token expiry/logout: clear storage and fire the event AuthGate listens for
    await page.evaluate(({ key }: { key: string }) => {
      window.localStorage.removeItem(key);
      window.dispatchEvent(new Event('auth:credentials-cleared'));
    }, { key: AUTH_STORAGE_KEY });

    await expect(page.getByText('Sign in to continue')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Real-backend smoke tests — authenticated
// ---------------------------------------------------------------------------

test.describe('Auth gate — real-backend smoke (authenticated)', () => {
  test.skip(isMock, 'real-backend mode only (set BACKEND_URL)');

  test('GET /api/projects returns 200 with valid token', async ({ page }) => {
    // Default fixture seeds valid token in real mode too
    const projectsResponse = page.waitForResponse(
      (r) => r.url().includes('/api/projects') && r.request().method() === 'GET',
      { timeout: 30_000 },
    );

    await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30_000 });
    const res = await projectsResponse;

    expect(res.status()).toBe(200);
    // Gate must NOT be shown for an authenticated user
    await expect(page.getByText('Sign in to continue')).not.toBeVisible({ timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// Real-backend smoke tests — unauthenticated
// ---------------------------------------------------------------------------

test.describe('Auth gate — real-backend smoke (unauthenticated)', () => {
  test.skip(isMock, 'real-backend mode only (set BACKEND_URL)');
  test.use({ noAuth: true });

  test('sign-in gate is shown without a token', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30_000 });

    await expect(page.getByText('Sign in to continue')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('strict JWT: direct API request returns 401', async ({ page }) => {
    test.skip(!isStrictJwt, 'requires AUTH_REQUIRE_JWT=true');

    // Make a direct API request without any auth token
    const res = await page.request.get('/api/projects');
    expect(res.status()).toBe(401);
  });
});
