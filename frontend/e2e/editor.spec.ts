/**
 * Editor UX: quick open (Ctrl+P), search in files (Ctrl+Shift+F), ctrl+click import jump.
 */
import { test, expect } from './fixtures';
import { PROJECT_ID } from './mocks/data';

async function goToEditor(page: import('@playwright/test').Page) {
  await page.goto(`/#/project/${PROJECT_ID}`);
  await page.getByRole('button', { name: 'Code' }).click({ timeout: 20_000 });
  await page.getByText('App.tsx', { exact: true }).first().click();
  const host = page.getByTestId('monaco-editor-host');
  await expect(host).toBeVisible({ timeout: 20_000 });
  await host.locator('.view-line').first().waitFor({ state: 'visible', timeout: 20_000 });
  await host.click();
}

test.describe('Editor', () => {
  test.use({ mockOptions: { seedChatHistory: true } });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('has-projects', 'true');
        localStorage.setItem('language', 'en');
      } catch {
        /* ignore */
      }
    });
  });

  test('Ctrl+P opens quick open', async ({ page }) => {
    await goToEditor(page);
    await page.keyboard.press('Control+P');
    await expect(page.getByPlaceholder(/Type a file name \(Ctrl\+P\)/)).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByPlaceholder(/Type a file name \(Ctrl\+P\)/)).toBeHidden();
  });

  test('Ctrl+Shift+F focuses project search', async ({ page }) => {
    await goToEditor(page);
    await page.keyboard.press('Control+Shift+F');
    const searchInput = page.getByPlaceholder('Search in files...');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('E2E_TYPES_MARKER');
    await searchInput.press('Enter');
    await expect(page.getByRole('button', { name: /\/src\/types\.ts/ })).toBeVisible({ timeout: 10_000 });
  });

  test('Ctrl+click on import symbol opens types file', async ({ page }) => {
    await goToEditor(page);
    const host = page.getByTestId('monaco-editor-host');
    const importLine = host.locator('.view-lines .view-line').first();
    await expect(importLine).toContainText('Todo');

    const typesContentReq = page.waitForRequest(
      (req) =>
        req.method() === 'GET' &&
        req.url().includes('/api/files/') &&
        req.url().includes('/content') &&
        decodeURIComponent(req.url()).includes('types.ts'),
      { timeout: 15_000 }
    );

    // Click inside the first line's bbox on the "Todo" token (avoids a11y textarea / wrong line mapping).
    await importLine.click({ position: { x: 96, y: 8 }, modifiers: ['Control'] });
    await typesContentReq;

    // Tab row (FileTabs): shows basename; close control is icon-only (no "Close" text).
    await expect(page.locator('div.flex.overflow-auto.border-b').getByText('types.ts', { exact: true })).toBeVisible({
      timeout: 5_000,
    });
    await expect(host.getByText('E2E_TYPES_MARKER', { exact: false })).toBeVisible({ timeout: 10_000 });
  });
});
