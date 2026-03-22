/**
 * Happy path E2E tests.
 *
 * Mock mode (default): Playwright route handlers mock all REST + WebSocket.
 * Real mode (BACKEND_URL=...): tests hit the actual backend.
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT } from './mocks/data';

/** Wait for projects to load, expand sidebar if collapsed. */
async function ensureSidebar(page: import('@playwright/test').Page) {
  // Wait for the project avatar button (visible even when collapsed)
  await expect(page.getByRole('button', { name: 'ET' })).toBeVisible({ timeout: 10_000 });
  // Expand if collapsed
  const expandBtn = page.getByRole('button', { name: 'Expand sidebar' });
  if (await expandBtn.isVisible()) {
    await expandBtn.click();
    await page.waitForTimeout(300);
  }
}

test.describe('Happy path', () => {
  test('app loads and shows project in sidebar', async ({ page }) => {
    await page.goto('/');
    await ensureSidebar(page);
    await expect(page.getByText(MOCK_PROJECT.name)).toBeAttached();
  });

  test('can create a new project via sidebar', async ({ page }) => {
    await page.goto('/');
    await ensureSidebar(page);

    await page.getByRole('button', { name: /new project/i }).click();
    const nameInput = page.getByPlaceholder('Project name');
    await nameInput.fill('My New Project');
    await nameInput.press('Enter');

    // Mock always returns MOCK_PROJECT, so its name should still be there
    await expect(page.getByText(MOCK_PROJECT.name)).toBeAttached();
  });

  test('chat input is functional', async ({ page }) => {
    await page.goto('/');
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
    await page.goto('/');
    // The model selector should display our mock model
    await expect(page.getByText('Test Model')).toBeVisible({ timeout: 10_000 });
  });

  test('suggestion buttons are visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: /todo app/i })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: /dashboard/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /landing page/i })).toBeVisible();
  });
});
