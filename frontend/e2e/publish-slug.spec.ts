/**
 * Publish slug E2E tests:
 * - Create-mode: first-time publish shows slug input + "Use default link"
 * - Edit-mode (read-only): republish shows current URL, "Change URL", no slug input
 * - Edit-mode (editing): "Change URL" unlocks input, taken slug shows hint, new slug publishes
 */
import { test, expect } from './fixtures';
import { MOCK_PROJECT, MOCK_PROJECT_WITH_SLUG, PROJECT_ID } from './mocks/data';

/** Navigate directly to the given project so the Preview toolbar appears. */
async function goToPreview(page: import('@playwright/test').Page, projectId = PROJECT_ID) {
  await page.goto(`/#/project/${projectId}`);
  await expect(
    page.getByRole('button', { name: /Publish|Republish/i }).first()
  ).toBeVisible({ timeout: 20_000 });
}

// ---------------------------------------------------------------------------
// Create mode — first-time publish (no existing slug)
// ---------------------------------------------------------------------------

test.describe('Publish modal — create mode', () => {
  test.use({ mockOptions: { seedChatHistory: true } });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('has-projects', 'true');
        localStorage.setItem('language', 'en');
      } catch { /* ignore */ }
    });
  });

  test('shows slug input, "Use default link", and "Publish" button', async ({ page }) => {
    await goToPreview(page);
    // Click the toolbar Publish button (uses title attr for disambiguation)
    await page.getByTitle('Publish').click();

    // Modal title for create mode
    await expect(page.getByText('Choose a custom URL')).toBeVisible({ timeout: 5_000 });

    // Slug input is visible
    await expect(page.getByPlaceholder('my-awesome-app')).toBeVisible();

    // Both action buttons inside the modal
    await expect(page.getByRole('button', { name: 'Use default link' })).toBeVisible();
    // The modal's publish button (second one with name "Publish", after the toolbar)
    const modalPublishBtn = page.locator('button:has-text("Publish")').last();
    await expect(modalPublishBtn).toBeVisible();
  });

  test('can publish without a slug (default link)', async ({ page }) => {
    await goToPreview(page);
    await page.getByTitle('Publish').click();
    await expect(page.getByText('Choose a custom URL')).toBeVisible({ timeout: 5_000 });

    await page.getByRole('button', { name: 'Use default link' }).click();

    // Success phase
    await expect(page.getByText('Successfully Published!')).toBeVisible({ timeout: 10_000 });
  });
});

// ---------------------------------------------------------------------------
// Edit mode — republish with an existing slug
// ---------------------------------------------------------------------------

test.describe('Publish modal — edit mode', () => {
  test.describe.configure({ mode: 'serial' });

  const publishedProject = {
    ...MOCK_PROJECT,
    published_url: 'https://s3.local/published/e2e-test-project-001.html',
    published_slug: 'my-existing-app',
  };
  test.use({
    mockOptions: {
      projects: [publishedProject, MOCK_PROJECT_WITH_SLUG],
      seedChatHistory: true,
    },
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('has-projects', 'true');
        localStorage.setItem('language', 'en');
      } catch { /* ignore */ }
    });
  });

  test('opens in read-only state with current URL and Change URL button', async ({ page }) => {
    await goToPreview(page);

    // Button should say "Republish" since project is already published
    await page.getByTitle('Republish').click();

    // Modal title for edit mode
    await expect(page.getByText('Republish project')).toBeVisible({ timeout: 5_000 });

    // Current URL label and the slug displayed
    await expect(page.getByText('Current URL')).toBeVisible();
    await expect(page.getByText(/my-existing-app/)).toBeVisible();

    // "Change URL" button visible
    await expect(page.getByRole('button', { name: 'Change URL' })).toBeVisible();

    // "Use default link" should NOT be visible in edit mode
    await expect(page.getByRole('button', { name: 'Use default link' })).toBeHidden();

    // The editable slug input should NOT be visible
    await expect(page.getByPlaceholder('my-awesome-app')).toBeHidden();
  });

  test('can republish with existing slug without editing', async ({ page }) => {
    await goToPreview(page);
    await page.getByTitle('Republish').click();

    await expect(page.getByText('Republish project')).toBeVisible({ timeout: 5_000 });

    // Click the modal's Republish button (last "Republish" on page, after toolbar)
    const modalRepublish = page.getByRole('button', { name: 'Republish', exact: true }).last();
    await modalRepublish.click();

    // Success phase with the slug URL
    await expect(page.getByText('Successfully Published!')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/\/api\/share\/my-existing-app/)).toBeVisible();
  });

  test('Change URL unlocks editing and shows slug input', async ({ page }) => {
    await goToPreview(page);
    await page.getByTitle('Republish').click();
    await expect(page.getByText('Republish project')).toBeVisible({ timeout: 5_000 });

    await page.getByRole('button', { name: 'Change URL' }).click();

    // Slug input should now be visible and pre-filled
    const slugInput = page.getByPlaceholder('my-awesome-app');
    await expect(slugInput).toBeVisible();
    await expect(slugInput).toHaveValue('my-existing-app');

    // Cancel button visible
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible();
  });

  test('Cancel change reverts to read-only state', async ({ page }) => {
    await goToPreview(page);
    await page.getByTitle('Republish').click();
    await expect(page.getByText('Republish project')).toBeVisible({ timeout: 5_000 });

    await page.getByRole('button', { name: 'Change URL' }).click();
    await expect(page.getByPlaceholder('my-awesome-app')).toBeVisible();

    await page.getByRole('button', { name: 'Cancel' }).click();

    // Back to read-only: slug input hidden, "Change URL" visible again
    await expect(page.getByPlaceholder('my-awesome-app')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Change URL' })).toBeVisible();
  });

  test('taken slug shows "Already taken" hint', async ({ page }) => {
    await goToPreview(page);
    await page.getByTitle('Republish').click();
    await expect(page.getByText('Republish project')).toBeVisible({ timeout: 5_000 });

    await page.getByRole('button', { name: 'Change URL' }).click();
    const slugInput = page.getByPlaceholder('my-awesome-app');
    await slugInput.clear();
    await slugInput.fill('taken-slug');

    // Wait for the debounced availability check (500ms + network)
    await expect(page.getByText('Already taken')).toBeVisible({ timeout: 5_000 });
  });

  test('available new slug enables republish with new URL', async ({ page }) => {
    await goToPreview(page);
    await page.getByTitle('Republish').click();
    await expect(page.getByText('Republish project')).toBeVisible({ timeout: 5_000 });

    await page.getByRole('button', { name: 'Change URL' }).click();
    const slugInput = page.getByPlaceholder('my-awesome-app');
    await slugInput.clear();
    await slugInput.fill('brand-new-slug');

    // Wait for "Available" hint
    await expect(page.getByText('Available')).toBeVisible({ timeout: 5_000 });

    // Warning about old URL being disabled
    await expect(page.getByText(/permanently disable the old link/)).toBeVisible();

    // Button should say "Republish with new URL"
    const newUrlBtn = page.getByRole('button', { name: 'Republish with new URL' });
    await expect(newUrlBtn).toBeEnabled();
    await newUrlBtn.click();

    // Success
    await expect(page.getByText('Successfully Published!')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/\/api\/share\/brand-new-slug/)).toBeVisible();
  });
});
