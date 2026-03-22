/**
 * Project lifecycle E2E tests:
 * - Empty state (no projects)
 * - Create first project
 * - Delete a project
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT } from './mocks/data';

test.describe('Empty state', () => {
  test.use({ mockOptions: { projects: [] } });

  test('shows welcome screen with no projects', async ({ page }) => {
    await page.goto('/');
    // Should show the empty state prompt — no project in sidebar
    await expect(page.getByText(/create your first project/i)).toBeVisible({ timeout: 10_000 });
  });

  test('can create first project from empty state', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText(/create your first project/i)).toBeVisible({ timeout: 10_000 });

    // The empty state should have a name input and create button
    const nameInput = page.getByPlaceholder('Project name');
    await nameInput.fill('My First Project');
    await nameInput.press('Enter');

    // After creation, the chat input should appear
    await expect(page.getByPlaceholder(/describe what you want/i)).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('Delete project', () => {
  test('can delete a project from sidebar', async ({ page }) => {
    await page.goto('/');

    // Wait for project to load
    await expect(page.getByRole('button', { name: 'ET' })).toBeVisible({ timeout: 10_000 });

    // Expand sidebar
    const expandBtn = page.getByRole('button', { name: 'Expand sidebar' });
    if (await expandBtn.isVisible()) {
      await expandBtn.click();
      await page.waitForTimeout(300);
    }

    // Hover over the project to reveal the delete/options button
    const projectItem = page.getByText(MOCK_PROJECT.name).first();
    await projectItem.hover();

    // Click the options button (⋯) next to the project name
    const projectRow = projectItem.locator('..');
    const optionsBtn = projectRow.locator('button').last();
    await optionsBtn.click();

    // First click: "Delete" — changes to "Confirm delete?"
    await page.getByText('Delete').click();
    // Second click: "Confirm delete?"
    await page.getByText(/confirm delete/i).click();

    // The project name should no longer be in the DOM
    await expect(page.getByText(MOCK_PROJECT.name)).toBeHidden({ timeout: 5_000 });
  });
});
