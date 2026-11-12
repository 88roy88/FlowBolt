/**
 * Topbar project navigation (Settings → Project navigation → Top bar).
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT, PROJECT_ID } from './mocks/data';

test.describe('Topbar navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('nav-mode', 'topbar'));
  });

  test('replaces the sidebar with a project switcher', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);

    const trigger = page.getByTestId('project-switcher-trigger');
    await expect(trigger).toContainText(MOCK_PROJECT.name, { timeout: 10_000 });
    await expect(page.getByRole('button', { name: 'Expand sidebar' })).toHaveCount(0);

    await trigger.click();
    const switcher = page.getByTestId('project-switcher');
    await expect(switcher).toBeVisible();
    await expect(page.getByTestId('project-switcher-search')).toBeFocused();
    await expect(switcher.getByTestId(`switcher-item-${PROJECT_ID}`)).toBeVisible();

    await page.getByTestId('project-switcher-search').fill('no such project');
    await expect(switcher.getByText('No projects match')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(switcher).toBeHidden();
  });

  test('can delete a project from the switcher', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    await page.getByTestId('project-switcher-trigger').click();

    const row = page.getByTestId(`switcher-item-${PROJECT_ID}`);
    await row.hover();
    await row.locator('button').last().click();

    // Clicking inside the nested menu keeps the switcher open
    await page.getByText('Delete', { exact: true }).click();
    await expect(page.getByTestId('project-switcher')).toBeVisible();
    await page.getByText(/confirm delete/i).click();

    await expect(row).toHaveCount(0, { timeout: 5_000 });
  });

  test('can switch back to the sidebar from settings', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    await expect(page.getByTestId('topbar')).toBeVisible({ timeout: 10_000 });

    await page.getByTestId('topbar').getByTitle('Settings').click();
    await page.getByTestId('nav-mode-sidebar').click();

    await expect(page.getByTestId('topbar')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'ET', exact: true })).toBeVisible();
  });
});
