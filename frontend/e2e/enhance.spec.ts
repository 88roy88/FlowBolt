/**
 * Prompt enhancement E2E tests. Mock mode only — the enhance route is stubbed.
 */
import { test, expect } from './fixtures';
import { ENHANCED_PROMPT } from './mocks/api';

declare const process: { env: Record<string, string | undefined> };

const isMock = !process.env.BACKEND_URL;

const DRAFT = 'a todo app';

async function openComposer(page: import('@playwright/test').Page) {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  const input = page.getByTestId('chat-input');
  // Enabled only once the projects fetch resolves and a project is selected.
  await expect(input).toBeEnabled({ timeout: 30_000 });
  return input;
}

test.describe('Prompt enhancement', () => {
  test.skip(!isMock, 'mock-mode only');

  test('is hidden until the draft has content', async ({ page }) => {
    const input = await openComposer(page);
    await expect(page.getByTestId('enhance-row')).toHaveCount(0);

    await input.fill(DRAFT);
    await expect(page.getByTestId('enhance-button')).toBeVisible();

    await input.fill('');
    await expect(page.getByTestId('enhance-row')).toHaveCount(0);
  });

  test('replaces the draft and restores it on undo', async ({ page }) => {
    const input = await openComposer(page);
    await input.fill(DRAFT);
    await page.getByTestId('enhance-button').click();

    await expect(input).toHaveValue(ENHANCED_PROMPT);
    await expect(page.getByText('Enhanced', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Undo', exact: true }).click();

    await expect(input).toHaveValue(DRAFT);
    await expect(page.getByTestId('enhance-button')).toBeVisible();
  });

  test('drops undo once the user edits the rewrite', async ({ page }) => {
    const input = await openComposer(page);
    await input.fill(DRAFT);
    await page.getByTestId('enhance-button').click();
    await expect(input).toHaveValue(ENHANCED_PROMPT);

    await input.press('End');
    await input.pressSequentially(' and a dark mode');

    await expect(page.getByRole('button', { name: 'Undo', exact: true })).toHaveCount(0);
    await expect(page.getByTestId('enhance-button')).toBeVisible();
  });

  test('restores the draft with Escape', async ({ page }) => {
    const input = await openComposer(page);
    await input.fill(DRAFT);
    await page.getByTestId('enhance-button').click();
    await expect(input).toHaveValue(ENHANCED_PROMPT);

    await input.press('Escape');

    await expect(input).toHaveValue(DRAFT);
  });
});

test.describe('Prompt enhancement — in flight', () => {
  test.skip(!isMock, 'mock-mode only');
  test.use({ mockOptions: { enhanceDelayMs: 3000 } });

  test('sending abandons the rewrite and submits the current draft', async ({ page }) => {
    const input = await openComposer(page);
    await input.fill(DRAFT);
    await page.getByTestId('enhance-button').click();

    await expect(page.getByText('Enhancing...')).toBeVisible();
    await page.getByTestId('send-button').click();

    await expect(input).toHaveValue('');
    await page.waitForTimeout(3500);
    await expect(input).toHaveValue('');
  });
});
