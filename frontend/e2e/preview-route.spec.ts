/**
 * Preview route bar E2E tests, driven by the real toolbar script inside the preview iframe:
 * - The bar shows the app's <title>, following runtime changes
 * - Client-side navigation shows the inner path, and the root shows none
 * - "Open in new tab" opens the page currently showing
 * - Clicking the title renames the app in index.html
 */
import { readFileSync } from 'node:fs';
import { test, expect } from './fixtures';
import { PROJECT_ID } from './mocks/data';

const TOOLBAR_SCRIPT = readFileSync(
  new URL('../../backend/src/flow44/static/preview_toolbar.js', import.meta.url),
  'utf-8',
);

const APP_HTML = `<html><head><title>Todo App</title><script src="/api/preview/preview_toolbar.js" defer></script></head>
<body><h1>App</h1></body></html>`;

const INDEX_HTML = '<html><head><title>Todo App</title><script id="keep">var a = 1;</script></head><body></body></html>';

const PROXY_BASE = `/api/preview/${PROJECT_ID}/proxy`;

const appFrame = (page: import('@playwright/test').Page) =>
  page.frames().find((f) => f.url().includes('/proxy/'))!;

test.describe('Preview route bar', () => {
  test.use({ mockOptions: { seedChatHistory: true } });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('has-projects', 'true');
        localStorage.setItem('language', 'en');
      } catch { /* ignore */ }
    });
    await page.route('**/api/preview/preview_toolbar.js', (route) =>
      route.fulfill({ contentType: 'application/javascript', body: TOOLBAR_SCRIPT }),
    );
    await page.route('**/api/preview/*/proxy/**', (route) =>
      route.fulfill({ contentType: 'text/html', body: APP_HTML }),
    );
    await page.goto(`/#/project/${PROJECT_ID}`);
    await expect(page.getByTestId('preview-app-title')).toBeVisible({ timeout: 20_000 });
    await expect(page.frameLocator('[data-testid="preview-iframe"]').locator('h1')).toBeVisible();
    await appFrame(page).waitForFunction(() => '__BUILDAPP_TOOLBAR__' in window);
  });

  test('shows the app title, and the path only on subpages', async ({ page }) => {
    const path = page.getByTestId('preview-path');
    await expect(page.getByTestId('preview-app-title')).toHaveText('Todo App');
    await expect(path).toBeHidden();

    await appFrame(page).evaluate((base) => history.pushState({}, '', `${base}/settings/profile?tab=a`), PROXY_BASE);
    await expect(path).toHaveText('/settings/profile?tab=a');

    await appFrame(page).evaluate(() => history.back());
    await expect(path).toBeHidden();
  });

  test('follows titles the app sets at runtime', async ({ page }) => {
    await appFrame(page).evaluate(() => { document.title = 'Orders'; });
    await expect(page.getByTestId('preview-app-title')).toHaveText('Orders');
  });

  test('treats the base without a trailing slash as the root', async ({ page }) => {
    const path = page.getByTestId('preview-path');
    await appFrame(page).evaluate((base) => history.pushState({}, '', `${base}/about`), PROXY_BASE);
    await expect(path).toHaveText('/about');

    await appFrame(page).evaluate((base) => history.replaceState({}, '', base), PROXY_BASE);
    await expect(path).toBeHidden();
  });

  test('follows HashRouter routes', async ({ page }) => {
    await appFrame(page).evaluate(() => { location.hash = '#/orders'; });
    await expect(page.getByTestId('preview-path')).toHaveText('/orders');
  });

  test('opens the current page in a new tab', async ({ page, context }) => {
    await appFrame(page).evaluate((base) => history.pushState({}, '', `${base}/about`), PROXY_BASE);
    await expect(page.getByTestId('preview-path')).toHaveText('/about');

    const [popup] = await Promise.all([
      context.waitForEvent('page'),
      page.getByTitle('Open in new tab').click(),
    ]);
    expect(new URL(popup.url()).pathname).toBe(`${PROXY_BASE}/about`);
  });

  test.describe('renaming', () => {
    let saved: { path: string; content: string }[];

    test.beforeEach(async ({ page }) => {
      saved = [];
      await page.route('**/api/files/*/file/content**', (route) => {
        if (route.request().method() === 'PUT') {
          saved.push(route.request().postDataJSON());
          return route.fulfill({ status: 200, json: {} });
        }
        return route.fulfill({ json: { path: '/index.html', content: INDEX_HTML } });
      });
    });

    const rename = (page: import('@playwright/test').Page) => page.getByRole('textbox', { name: 'Rename app' });

    test('saves the new title to index.html without opening it', async ({ page }) => {
      await page.getByTestId('preview-app-title').click();
      await rename(page).fill('Shop & Go');
      await rename(page).press('Enter');

      await expect(page.getByTestId('preview-app-title')).toHaveText('Shop & Go');
      await expect.poll(() => saved.length).toBe(1);
      expect(saved[0]).toEqual({
        path: '/index.html',
        content: INDEX_HTML.replace('Todo App', 'Shop &amp; Go'),
      });
    });

    test('Escape cancels, and an empty or unchanged title saves nothing', async ({ page }) => {
      const title = page.getByTestId('preview-app-title');
      await title.click();
      await rename(page).fill('Nope');
      await rename(page).press('Escape');
      await expect(title).toHaveText('Todo App');

      await title.click();
      await rename(page).fill('   ');
      await rename(page).press('Enter');
      await expect(title).toHaveText('Todo App');

      await title.click();
      await rename(page).press('Enter');
      await expect(title).toHaveText('Todo App');
      expect(saved).toEqual([]);
    });

    test('restores the title when saving fails', async ({ page }) => {
      await page.route('**/api/files/*/file/content**', (route) =>
        route.request().method() === 'PUT'
          ? route.fulfill({ status: 500, json: {} })
          : route.fulfill({ json: { path: '/index.html', content: INDEX_HTML } }),
      );
      await page.getByTestId('preview-app-title').click();
      await rename(page).fill('Shop');
      await rename(page).press('Enter');
      await expect(page.getByTestId('preview-app-title')).toHaveText('Todo App');
    });
  });
});
