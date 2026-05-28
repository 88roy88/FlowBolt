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
    // Landing screen is shown — prompt input is visible with no project selected
    await expect(page.getByPlaceholder(/describe what you want/i)).toBeVisible({ timeout: 10_000 });
  });

  test('can create first project from empty state', async ({ page }) => {
    await page.goto('/');
    // Landing screen shows the prompt input as the entry point
    const promptInput = page.getByPlaceholder(/describe what you want/i);
    await expect(promptInput).toBeVisible({ timeout: 10_000 });

    // Submitting a message creates the project and navigates to it
    await promptInput.fill('My First Project');
    await promptInput.press('Enter');

    // After creation the project view renders with Preview/Code tabs
    await expect(
      page.getByRole('button', { name: /^(Preview|Code)$/i }).first()
    ).toBeVisible({ timeout: 15_000 });
  });
});

test.describe('Delete project', () => {
  test('can delete a project from sidebar', async ({ page }) => {
    await page.goto('/');

    // Wait for project to load — sidebar may be pinned (row visible) or collapsed (icon-rail button visible)
    const rail = page.getByRole('button', { name: 'ET', exact: true });
    const row = page.getByTestId(`project-item-${MOCK_PROJECT.id}`);
    await expect(rail.or(row)).toBeVisible({ timeout: 10_000 });

    // Expand if collapsed
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
