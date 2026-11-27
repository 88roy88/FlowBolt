/**
 * Data Sources panel E2E tests. The mock preview loads the real `preview_toolbar.js` the way the backend
 * injects it, and calls a data source from a module script the way a generated app does.
 */
import { type Page } from '@playwright/test';
import { test, expect } from './fixtures';
import { PROJECT_ID } from './mocks/data';

const SALES = {
  data_source_id: '12', name: 'Sales', module_path: 'src/dataSources/Sales.ts',
  package_updated_date: '2024-02-11T00:00:00.000',
};
const USERS = { data_source_id: '7', name: 'Users', module_path: 'src/dataSources/Users.ts', package_updated_date: null };

const PREVIEW_HTML = `<!doctype html><html><head>
<script src="/api/preview/preview_toolbar.js" defer></script></head><body>
<button id="again">Call again</button><div id="out"></div>
<script type="module">
  const call = async () => {
    const res = await fetch('/api/data-source/12/run', { method: 'POST', body: JSON.stringify({ cube: { region: 'north' } }) });
    document.getElementById('out').textContent = (await res.json()).data;
  };
  document.getElementById('again').onclick = call;
  call();
</script></body></html>`;

test.use({
  mockOptions: {
    seedEvents: [
      { type: 'user_message', content: 'Build a sales app' },
      { type: 'action_complete' },
    ],
  },
});

async function openPanel(
  page: Page,
  { usages = [] as { file: string; line: number }[], updates = [] as { data_source_id: string; updated_date: string }[] } = {},
) {
  let sources = [SALES, USERS];
  await page.route('**/api/preview/*/proxy/**', (route) =>
    route.fulfill({ contentType: 'text/html', body: PREVIEW_HTML }),
  );
  await page.route('**/api/preview/preview_toolbar.js', (route) =>
    route.fulfill({ contentType: 'text/javascript', path: '../backend/src/flow44/static/preview_toolbar.js' }),
  );
  await page.route('**/api/data-source/12/run', (route) => route.fulfill({ json: { data: 'rows' } }));
  await page.route('**/api/projects/*/data-sources', (route) => route.fulfill({ json: sources }));
  await page.route('**/api/projects/*/data-sources/updates', (route) => route.fulfill({ json: updates }));
  await page.route('**/api/projects/*/data-sources/*/usages', (route) => route.fulfill({ json: usages }));
  await page.route('**/api/projects/*/data-sources/12', (route) => {
    sources = [USERS];
    return route.fulfill({ status: 204, body: '' });
  });

  await page.goto(`/#/project/${PROJECT_ID}`);
  const preview = page.frameLocator('[data-testid="preview-iframe"]');
  await expect(preview.locator('#out')).toHaveText('rows', { timeout: 15_000 });
  await page.getByRole('button', { name: 'Data Sources', exact: true }).click();
  const rows = page.getByTestId('data-source-row');
  await expect(rows).toHaveCount(2);
  return { rows, preview };
}

test.describe('Data Sources panel', () => {
  test('is the leftmost tab and shows the calls the preview makes', async ({ page }) => {
    const { rows, preview } = await openPanel(page);

    // The first call was made while the drawer was closed.
    await expect(rows.first()).toContainText('Ran 1×');
    await expect(rows.last()).toContainText('Not run yet');
    await expect(rows.first()).toContainText('(12)');
    await preview.locator('#again').click();
    await expect(rows.first()).toContainText('Ran 2×');

    await rows.first().getByRole('button', { name: /Sales/ }).click();
    await expect(rows.first()).toContainText('cube.region: "north"');
    await expect(rows.first()).toContainText('Succeeded');

    const tabs = page.getByRole('button', { name: /^(Data Sources|Server|Console)$/ });
    await expect(tabs.first()).toHaveText('Data Sources');
  });

  test('Adjust options add to the chat input without sending', async ({ page }) => {
    const { rows } = await openPanel(page);
    const input = page.getByTestId('chat-input');
    await input.fill('My draft');

    await rows.first().getByRole('button', { name: 'Adjust' }).click();
    await page.getByRole('button', { name: 'This is running too much' }).click();

    await expect(input).toHaveValue(
      'My draft\nThe "Sales" data source (src/dataSources/Sales.ts) is running too much.',
    );
    await expect(input).toBeFocused();
    await expect(page.getByRole('button', { name: 'This is running too much' })).toBeHidden();
  });

  test('removes an unused data source after confirming', async ({ page }) => {
    const { rows } = await openPanel(page);

    await rows.first().getByRole('button', { name: 'Remove data source' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Remove', exact: true }).click();

    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(rows).toHaveCount(1);
  });

  test('blocks removal while in use and drafts a request to remove the usages', async ({ page }) => {
    const { rows } = await openPanel(page, { usages: [{ file: 'src/App.tsx', line: 3 }] });

    await rows.first().getByRole('button', { name: 'Remove data source' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('listitem')).toHaveText('src/App.tsx:3');
    await expect(dialog.getByRole('button', { name: 'Remove', exact: true })).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Ask AI to remove usages' }).click();

    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId('chat-input')).toHaveValue(/It's used in: src\/App\.tsx:3\./);
    await expect(rows).toHaveCount(2);
  });

  test('says how to add one when the project has none', async ({ page }) => {
    await page.route('**/api/projects/*/data-sources', (route) => route.fulfill({ json: [] }));
    await page.goto(`/#/project/${PROJECT_ID}`);
    await page.getByRole('button', { name: 'Data Sources', exact: true }).click();

    await expect(page.getByTestId('data-sources-add-hint')).toContainText('To add one, click');
  });

  test('opens and closes the drawer from its single bar', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    const bar = page.getByTestId('bottom-drawer-bar');
    const tab = bar.getByRole('button', { name: 'Data Sources', exact: true });
    const open = bar.getByRole('button', { name: 'Open panel' });
    const close = bar.getByRole('button', { name: 'Close panel' });

    // The name shows once, and a tab opens its panel. Clicking it again keeps it open.
    await expect(page.getByText('Data Sources', { exact: true })).toHaveCount(1);
    await tab.click();
    await tab.click();
    await close.click();
    await expect(open).toBeVisible();

    // The arrow works from the keyboard, and empty space on the bar toggles too.
    await open.press('Enter');
    await expect(close).toBeVisible();
    const box = (await bar.boundingBox())!;
    await bar.click({ position: { x: box.width - 20, y: box.height / 2 } });
    await expect(open).toBeVisible();
  });

  test('resizes the drawer by dragging its top edge', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    const bar = page.getByTestId('bottom-drawer-bar');
    await bar.getByRole('button', { name: 'Data Sources', exact: true }).click();
    const handle = page.locator('[role="separator"][aria-orientation="vertical"]').last();
    const before = (await bar.boundingBox())!;
    const edge = (await handle.boundingBox())!;
    expect(edge.y).toBeLessThan(before.y);

    await page.mouse.move(edge.x + 300, edge.y + 2);
    await page.mouse.down();
    await page.mouse.move(edge.x + 300, edge.y - 98, { steps: 5 });
    await page.mouse.up();

    expect(before.y - (await bar.boundingBox())!.y).toBeCloseTo(100, -1);
    // Letting go doesn't count as a click on the bar, so the drawer stays open.
    await expect(bar.getByRole('button', { name: 'Close panel' })).toBeVisible();
  });

  test('marks Sync only where the package is newer', async ({ page }) => {
    const { rows } = await openPanel(page, {
      updates: [{ data_source_id: '12', updated_date: '2024-03-01T00:00:00.000' }],
    });
    const sync = rows.first().getByRole('button', { name: 'Sync', exact: true });

    await expect(rows.first()).toContainText('Package updated');
    await expect(sync.getByTestId('data-source-update-dot')).toBeVisible();
    await expect(rows.first().getByTitle(/The package was updated on .*Sync to update your app/)).toBeVisible();
    await expect(rows.last().getByTestId('data-source-update-dot')).toHaveCount(0);
    await expect(rows.last().getByRole('button', { name: 'Sync', exact: true })).toBeVisible();

    await sync.click();

    await expect(page.getByTestId('chat-input')).toHaveValue(/^Sync the "Sales" data source/);
    await expect(page.getByTestId('data-source-chip')).toHaveText(['Sales']);
  });

  test('Sync fills the chat input and attaches the data source without sending', async ({ page }) => {
    const { rows } = await openPanel(page);
    const input = page.getByTestId('chat-input');
    await expect(rows.first().getByTestId('data-source-update-dot')).toHaveCount(0);

    // Clicking twice adds neither the text nor the attachment again.
    await rows.first().getByRole('button', { name: 'Sync', exact: true }).click();
    await rows.first().getByRole('button', { name: 'Sync', exact: true }).click();

    await expect(input).toHaveValue(
      'Sync the "Sales" data source (src/dataSources/Sales.ts) with the latest version of its package, ' +
        'and adjust the app if anything changed.',
    );
    await expect(input).toBeFocused();
    await expect(page.getByTestId('data-source-chip')).toHaveText(['Sales']);
    await expect(page.getByTestId('queued-messages')).toHaveCount(0);
  });
});
