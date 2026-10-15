/**
 * Home page navigation E2E tests:
 * - Which page the app opens on (admins vs. everyone else)
 * - Getting back to the home page (Back button, logo)
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT, PROJECT_ID } from './mocks/data';

const PROJECT_URL = new RegExp(`#/project/${PROJECT_ID}$`);
const IN_ANY_PROJECT = /#\/project\//;

/** The project view (seeded with chat history) is up. */
async function expectProjectView(page: import('@playwright/test').Page) {
  await expect(page.getByRole('button', { name: 'Code', exact: true })).toBeVisible({ timeout: 20_000 });
}

/** The home page is up, with no project open. */
async function expectHomePage(page: import('@playwright/test').Page) {
  await expect(page.getByRole('button', { name: /todo app/i })).toBeVisible({ timeout: 10_000 });
  await expect(page).not.toHaveURL(IN_ANY_PROJECT);
}

test.describe('Startup as admin', () => {
  test.use({ mockOptions: { seedChatHistory: true } });

  test('stays on the home page instead of opening a project', async ({ page }) => {
    await page.goto('/');

    // Projects are loaded, but none is opened
    const rail = page.getByRole('button', { name: 'ET', exact: true });
    const row = page.getByTestId(`project-item-${MOCK_PROJECT.id}`);
    await expect(rail.or(row).first()).toBeVisible({ timeout: 10_000 });
    await expectHomePage(page);
  });

  test('still opens the project named in the URL', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    await expectProjectView(page);
  });
});

test.describe('Startup as non-admin', () => {
  test.use({ mockOptions: { seedChatHistory: true, userStatus: { is_admin: false, is_platform_user: true } } });

  test('opens the first project', async ({ page }) => {
    await page.goto('/');
    await expectProjectView(page);
    await expect(page).toHaveURL(PROJECT_URL);
  });

  test('Back after auto-opening leaves the app', async ({ page }) => {
    await page.goto('/');
    await expectProjectView(page);

    // The hash was replaced, not pushed, so there is no empty home page to go back to
    await page.goBack();
    expect(page.url()).toBe('about:blank');
  });
});

test.describe('Returning home', () => {
  test.use({ mockOptions: { seedChatHistory: true } });

  test('Back from a project returns to the home page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'ET', exact: true })).toBeVisible({ timeout: 10_000 });

    await page.getByRole('button', { name: 'ET', exact: true }).click();
    await expectProjectView(page);
    await expect(page).toHaveURL(PROJECT_URL);

    await page.goBack();
    await expectHomePage(page);
  });

  test('clicking the logo returns to the home page', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    await expectProjectView(page);

    await page.getByRole('button', { name: 'Expand sidebar' }).click();
    await page.getByRole('button', { name: 'BuildApp' }).click();
    await expectHomePage(page);
  });
});
