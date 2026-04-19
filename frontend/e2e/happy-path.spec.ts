/**
 * Happy path E2E tests.
 *
 * Mock mode (default): Playwright route handlers mock all REST + WebSocket.
 * Real mode (BACKEND_URL=...): tests hit the actual backend.
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT } from './mocks/data';

function isProjectsListGet(url: string): boolean {
  try {
    return new URL(url).pathname === '/api/projects';
  } catch {
    return false;
  }
}

/** Home navigation + wait until the app has fetched projects (avoids white-screen races under parallel load). */
async function gotoHomeReady(page: import('@playwright/test').Page) {
  const projectsList = page.waitForResponse(
    (r) => r.request().method() === 'GET' && isProjectsListGet(r.url()) && r.ok(),
    { timeout: 60_000 }
  );
  await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 60_000 });
  await projectsList;
}

/** Wait for projects to load, expand sidebar if collapsed. */
async function ensureSidebar(page: import('@playwright/test').Page) {
  // Icon rail uses a button with initials; full sidebar uses a non-button row.
  const rail = page.getByRole('button', { name: 'ET', exact: true });
  const row = page.getByTestId(`project-item-${MOCK_PROJECT.id}`);
  await expect(rail.or(row)).toBeVisible({ timeout: 30_000 });
  // Expand if collapsed
  const expandBtn = page.getByRole('button', { name: 'Expand sidebar' });
  if (await expandBtn.isVisible()) {
    await expandBtn.click();
    await page.waitForTimeout(300);
  }
}

test.describe('Happy path', () => {
  test.describe.configure({ mode: 'serial' });

  test('app loads and shows project in sidebar', async ({ page }) => {
    await gotoHomeReady(page);
    await ensureSidebar(page);
    await expect(page.getByText(MOCK_PROJECT.name)).toBeAttached();
  });

  test('can create a new project via sidebar', async ({ page }) => {
    await page.goto('/');
    await ensureSidebar(page);

    await page.getByRole('button', { name: /new project/i }).click();

    // New UI: project is created immediately and sidebar enters inline rename mode.
    const renameInput = page.getByPlaceholder('Rename project');
    await expect(renameInput).toBeVisible({ timeout: 10_000 });
    await renameInput.press('Escape');

    // Mock always returns MOCK_PROJECT, so its name should still be there
    await expect(page.getByText(MOCK_PROJECT.name)).toBeAttached();
  });

  test('chat input is functional', async ({ page }) => {
    await gotoHomeReady(page);
    await ensureSidebar(page);

    // The chat textarea should be ready
    const chatInput = page.getByPlaceholder(/describe what you want/i);
    await expect(chatInput).toBeVisible({ timeout: 5_000 });

    // Type a message
    await chatInput.fill('Build a todo app');
    await expect(chatInput).toHaveValue('Build a todo app');

    // Send button should be enabled now
    const sendBtn = page.getByRole('button', { name: /send message/i });
    await expect(sendBtn).toBeEnabled();
  });

  test('model selector shows mock model', async ({ page }) => {
    await gotoHomeReady(page);
    // The model selector should display our mock model
    await expect(page.getByText('Test Model')).toBeVisible({ timeout: 30_000 });
  });

  test('suggestion buttons are visible', async ({ page }) => {
    await gotoHomeReady(page);
    await expect(page.getByRole('button', { name: /todo app/i })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('button', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /landing page/i })).toBeVisible();
  });
});
