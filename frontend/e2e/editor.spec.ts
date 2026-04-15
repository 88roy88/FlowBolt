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

async function submitCreateDialog(page: import('@playwright/test').Page, value: string) {
  const input = page.getByPlaceholder('Enter a new file path');
  await expect(input).toBeVisible({ timeout: 5_000 });
  await input.fill(value);
  const dialog = input.locator('xpath=ancestor::div[contains(@class,"relative")][1]');
  await dialog.getByRole('button', { name: 'Create', exact: true }).click();
}

async function submitRenameDialog(page: import('@playwright/test').Page, value: string) {
  const input = page.getByPlaceholder('Enter a new name');
  await expect(input).toBeVisible({ timeout: 5_000 });
  await input.fill(value);
  const dialog = input.locator('xpath=ancestor::div[contains(@class,"relative")][1]');
  await dialog.getByRole('button', { name: 'Save', exact: true }).click();
}

async function submitDeleteDialog(page: import('@playwright/test').Page, targetName: string) {
  const message = page.getByText(`Delete ${targetName}?`);
  await expect(message).toBeVisible({ timeout: 5_000 });
  const dialog = message.locator('xpath=ancestor::div[contains(@class,"relative")][1]');
  await dialog.getByRole('button', { name: 'Delete' }).click();
}

function trackFileSaveRequests(page: import('@playwright/test').Page) {
  let putCount = 0;
  page.on('request', (req) => {
    if (
      req.method() === 'PUT' &&
      req.url().includes('/api/files/') &&
      req.url().includes('/content')
    ) {
      putCount += 1;
    }
  });
  return () => putCount;
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
    await srcRow.getByTitle('Create file').click();
    await submitCreateDialog(page, 'created-from-e2e.ts');
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
    await srcRow.getByTitle('Rename').click();
    await submitRenameDialog(page, 'src-renamed');
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
    await appFileRow.getByTitle('Rename').click();
    await submitRenameDialog(page, 'AppRenamed.tsx');
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
    await appFileRow.getByTitle('Delete').click();
    await submitDeleteDialog(page, 'App.tsx');
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
    await srcRow.getByTitle('Delete').click();
    await submitDeleteDialog(page, 'src');
    const req = await deleteReq;
    expect(decodeURIComponent(req.url())).toContain('path=/src');

    const tree = fileTreeContainer(page);
    await expect(tree.getByText('src', { exact: true })).toHaveCount(0);
    await expect(tree.getByText('package.json', { exact: true })).toBeVisible();
  });
});

test.describe('Editor read-only gating', () => {
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

  test.describe('before initial completion', () => {
    test.use({
      mockOptions: {
        seedEvents: [{ type: 'user_message', content: 'Seed only user event' }],
      },
    });

    test('stays locked until action_complete, then enables editing', async ({ page, sendChatEvents }) => {
      await goToEditor(page);

      await expect(page.getByText('Editing is enabled after the first AI build completes.').first()).toBeVisible();

      const createRoot = fileTreeContainer(page).getByRole('button', { name: 'Create file' }).first();
      await expect(createRoot).toBeDisabled();
      const srcRow = fileTreeRowByName(page, 'src');
      await srcRow.hover();
      await expect(srcRow.getByTitle('Rename')).toBeDisabled();
      await expect(srcRow.getByTitle('Delete')).toBeDisabled();

      const getPutCount = trackFileSaveRequests(page);
      const host = page.getByTestId('monaco-editor-host');
      await host.click();
      await page.keyboard.type('LOCKED_PHASE');
      await page.waitForTimeout(1200);
      expect(getPutCount()).toBe(0);

      await sendChatEvents([{ type: 'action_complete' }], 20);
      await expect(page.getByText('Editing is enabled after the first AI build completes.')).toHaveCount(0);
      await expect(createRoot).toBeEnabled({ timeout: 5_000 });

      await host.click();
      await page.keyboard.type('UNLOCKED_PHASE');
      await page.waitForTimeout(1200);
      expect(getPutCount()).toBeGreaterThan(0);
    });
  });

  test.describe('after initial completion', () => {
    test.use({ mockOptions: { seedChatHistory: true } });

    test('locks while AI is working and unlocks again on completion', async ({ page, sendChatEvents }) => {
      await goToEditor(page);

      const createRoot = fileTreeContainer(page).getByRole('button', { name: 'Create file' }).first();
      await expect(createRoot).toBeEnabled();

      const chatInput = page.getByPlaceholder(/describe what you want/i);
      await expect(chatInput).toBeVisible({ timeout: 10_000 });
      await chatInput.fill('Please continue with a tiny follow-up change');
      await page.getByRole('button', { name: /send message/i }).click();

      await expect(createRoot).toBeDisabled({ timeout: 5_000 });

      await sendChatEvents([{ type: 'action_complete' }], 20);
      await expect(createRoot).toBeEnabled({ timeout: 5_000 });
    });
  });
});
