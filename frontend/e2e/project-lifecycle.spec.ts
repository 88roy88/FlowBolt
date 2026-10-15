/**
 * Project lifecycle E2E tests:
 * - Empty state (no projects)
 * - Create first project
 * - Delete a project
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT, PROJECT_ID } from './mocks/data';

test.describe('Empty state', () => {
  test.use({ mockOptions: { projects: [] } });

  test('shows the home page with no projects', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 10_000 });
  });

  test('can create first project from the home prompt', async ({ page }) => {
    await page.goto('/');
    const promptInput = page.getByTestId('chat-input');
    await expect(promptInput).toBeEnabled({ timeout: 10_000 });

    await promptInput.fill('Build a todo app');
    await promptInput.press('Enter');

    // An untitled project is created, opened, and receives the prompt
    await expect(page).toHaveURL(/#\/project\/project-\d+$/, { timeout: 10_000 });
    await expect(page.getByText('Build a todo app')).toBeVisible();
  });
});

test.describe('Empty state without create access', () => {
  test.use({ mockOptions: { projects: [], userStatus: { is_admin: false, is_platform_user: false } } });

  test('shows the no-access message', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText(/don't have access to create projects/i)).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('Delete project', () => {
  test('can delete a project from sidebar', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);

    // Wait for project to load
    await expect(page.getByRole('button', { name: 'ET', exact: true })).toBeVisible({ timeout: 10_000 });

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

    // Deleting the open project returns to the home page
    await expect(page).not.toHaveURL(/#\/project\//);
  });
});
