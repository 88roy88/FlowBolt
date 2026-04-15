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

function fileTreeContainer(page: import('@playwright/test').Page) {
  return page.locator('div.py-1').filter({ has: page.getByRole('button', { name: 'Create file' }) }).first();
}

function fileTreeRowByName(page: import('@playwright/test').Page, name: string) {
  const tree = fileTreeContainer(page);
  const label = tree.getByText(name, { exact: true }).first();
  return label.locator('xpath=ancestor::div[contains(@class,"group")][1]');
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

  test('can create a new file inside a folder', async ({ page }) => {
    await goToEditor(page);
    const srcRow = fileTreeRowByName(page, 'src');
    await srcRow.hover();

    const createReq = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().includes('/api/files/') && req.url().includes('/entry'),
      { timeout: 10_000 }
    );
    page.once('dialog', (dialog) => dialog.accept('created-from-e2e.ts'));
    await srcRow.getByTitle('Create file').click();
    const req = await createReq;
    expect(req.postDataJSON()).toMatchObject({
      path: '/src/created-from-e2e.ts',
      content: '',
    });

    await expect(fileTreeContainer(page).getByText('created-from-e2e.ts', { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('div.flex.overflow-auto.border-b').getByText('created-from-e2e.ts', { exact: true })).toBeVisible({
      timeout: 5_000,
    });
  });

  test('can rename a folder from the file tree', async ({ page }) => {
    await goToEditor(page);
    const srcRow = fileTreeRowByName(page, 'src');
    await srcRow.hover();

    const renameReq = page.waitForRequest(
      (req) => req.method() === 'PATCH' && req.url().includes('/api/files/') && req.url().includes('/entry'),
      { timeout: 10_000 }
    );
    page.once('dialog', (dialog) => dialog.accept('src-renamed'));
    await srcRow.getByTitle('Rename').click();
    const req = await renameReq;
    expect(req.postDataJSON()).toMatchObject({
      old_path: '/src',
      new_path: '/src-renamed',
    });

    const tree = fileTreeContainer(page);
    await expect(tree.getByText('src-renamed', { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(tree.getByText('src', { exact: true })).toHaveCount(0);
  });

  test('renaming an open file updates its open tab label', async ({ page }) => {
    await goToEditor(page);
    const appFileRow = fileTreeRowByName(page, 'App.tsx');
    await appFileRow.hover();

    const renameReq = page.waitForRequest(
      (req) => req.method() === 'PATCH' && req.url().includes('/api/files/') && req.url().includes('/entry'),
      { timeout: 10_000 }
    );
    page.once('dialog', (dialog) => dialog.accept('AppRenamed.tsx'));
    await appFileRow.getByTitle('Rename').click();
    const req = await renameReq;
    expect(req.postDataJSON()).toMatchObject({
      old_path: '/src/App.tsx',
      new_path: '/src/AppRenamed.tsx',
    });

    const tabs = page.locator('div.flex.overflow-auto.border-b');
    await expect(tabs.getByText('AppRenamed.tsx', { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(tabs.getByText('App.tsx', { exact: true })).toHaveCount(0);
  });

  test('can delete a file from the file tree', async ({ page }) => {
    await goToEditor(page);
    const appFileRow = fileTreeRowByName(page, 'App.tsx');
    await appFileRow.hover();

    const deleteReq = page.waitForRequest(
      (req) => req.method() === 'DELETE' && req.url().includes('/api/files/') && req.url().includes('/entry'),
      { timeout: 10_000 }
    );
    page.once('dialog', (dialog) => dialog.accept());
    await appFileRow.getByTitle('Delete').click();
    const req = await deleteReq;
    expect(decodeURIComponent(req.url())).toContain('path=/src/App.tsx');

    const tree = fileTreeContainer(page);
    await expect(tree.getByText('App.tsx', { exact: true })).toHaveCount(0);
    const deletedTab = page.locator('[data-file-path="/src/App.tsx"][data-missing="true"]');
    await expect(deletedTab).toBeVisible({ timeout: 5_000 });
    await expect(deletedTab.locator('span').first()).toHaveClass(/line-through/);
  });

  test('can delete a folder from the file tree', async ({ page }) => {
    await goToEditor(page);
    const srcRow = fileTreeRowByName(page, 'src');
    await srcRow.hover();

    const deleteReq = page.waitForRequest(
      (req) => req.method() === 'DELETE' && req.url().includes('/api/files/') && req.url().includes('/entry'),
      { timeout: 10_000 }
    );
    page.once('dialog', (dialog) => dialog.accept());
    await srcRow.getByTitle('Delete').click();
    const req = await deleteReq;
    expect(decodeURIComponent(req.url())).toContain('path=/src');

    const tree = fileTreeContainer(page);
    await expect(tree.getByText('src', { exact: true })).toHaveCount(0);
    await expect(tree.getByText('package.json', { exact: true })).toBeVisible();
  });
});
