/** The mock preview loads the real `preview_toolbar.js` and calls a data source the way a generated app does. */
import { type Page } from '@playwright/test';
import { test, expect } from './fixtures';
import { PROJECT_ID } from './mocks/data';

const SALES = {
  data_source_id: '12', name: 'Sales', module_path: 'src/dataSources/Sales.ts',
  package_updated_date: '2024-02-11T00:00:00.000',
  params: [{ cube_id: 'cube', name: 'region', label: 'Sales region' }],
};
const USERS = { data_source_id: '7', name: 'Users', module_path: 'src/dataSources/Users.ts', package_updated_date: null, params: [] };

const PREVIEW_HTML = `<!doctype html><html><head>
<script src="/api/preview/preview_toolbar.js" defer></script></head><body>
<button id="again">Call again</button><button id="huge">Call with huge params</button><div id="out"></div>
<script type="module">
  const call = async (region = 'north') => {
    const res = await fetch('/api/data-source/12/run', { method: 'POST', body: JSON.stringify({ cube: { region } }) });
    document.getElementById('out').textContent = (await res.json()).data;
  };
  document.getElementById('again').onclick = () => call();
  document.getElementById('huge').onclick = () => call('x'.repeat(100001));
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

async function openPanel(page: Page, { updates = [] as { data_source_id: string; updated_date: string }[] } = {}) {
  await page.route('**/api/preview/*/proxy/**', (route) =>
    route.fulfill({ contentType: 'text/html', body: PREVIEW_HTML }),
  );
  await page.route('**/api/preview/preview_toolbar.js', (route) =>
    route.fulfill({ contentType: 'text/javascript', path: '../backend/src/flow44/static/preview_toolbar.js' }),
  );
  await page.route('**/api/data-source/12/run', (route) => route.fulfill({ json: { data: 'rows' } }));
  await page.route('**/api/projects/*/data-sources', (route) => route.fulfill({ json: [SALES, USERS] }));
  await page.route('**/api/projects/*/data-sources/updates', (route) => route.fulfill({ json: updates }));
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

    await expect(rows.first()).toContainText('Ran 1×');
    await expect(rows.last()).toContainText('Not run yet');
    await expect(rows.first()).toContainText('(12)');
    await preview.locator('#again').click();
    await expect(rows.first()).toContainText('Ran 2×');

    const history = page.getByTestId('data-source-history');
    const runs = history.getByTestId('data-source-run');
    await expect(history).toHaveText('Select a data source to see its recent runs');
    await rows.first().getByRole('button', { name: /Sales/ }).click();
    await expect(runs).toHaveCount(2);
    await expect(runs.first()).toContainText('Sales region"north"');
    await expect(runs.first()).toContainText('Succeeded');
    expect((await history.boundingBox())!.x).toBeGreaterThan((await rows.first().boundingBox())!.x);

    await rows.last().click();
    await expect(history).toContainText('Users');
    await expect(history).toContainText('No runs since the preview loaded');
    await rows.first().getByRole('button', { name: /Sales/ }).click();
    await expect(runs).toHaveCount(2);

    const tabs = page.getByRole('button', { name: /^(Data Sources|Server|Console)$/ });
    await expect(tabs.first()).toHaveText('Data Sources');
  });

  test('Adjust options add to the chat input without sending', async ({ page }) => {
    const { rows } = await openPanel(page);
    const input = page.getByTestId('chat-input');
    await input.fill('My draft');

    await rows.first().getByRole('button', { name: 'Adjust' }).click();
    await page.getByRole('button', { name: "This is running when it shouldn't" }).click();

    await expect(input).toHaveValue(
      'My draft\nThe "Sales" data source (src/dataSources/Sales.ts) is running when it shouldn\'t.',
    );
    await expect(input).toBeFocused();
    await expect(page.getByRole('button', { name: "This is running when it shouldn't" })).toBeHidden();
  });

  test('opens and closes the drawer from its single bar', async ({ page }) => {
    await page.goto(`/#/project/${PROJECT_ID}`);
    const bar = page.getByTestId('bottom-drawer-bar');
    const tab = bar.getByRole('button', { name: 'Data Sources', exact: true });
    const open = bar.getByRole('button', { name: 'Open panel' });
    const close = bar.getByRole('button', { name: 'Close panel' });

    await expect(page.getByText('Data Sources', { exact: true })).toHaveCount(1);
    await tab.click();
    await tab.click();
    await close.click();
    await expect(open).toBeVisible();

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
    await expect(bar.getByRole('button', { name: 'Close panel' })).toBeVisible();
  });

  test('marks Sync only where the package is newer', async ({ page }) => {
    const { rows } = await openPanel(page, {
      updates: [{ data_source_id: '12', updated_date: '2024-03-01T00:00:00.000' }],
    });
    const sync = rows.first().getByRole('button', { name: 'Sync', exact: true });

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

  test('copies exactly what a run sent', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const { rows } = await openPanel(page);
    await rows.first().click();
    const run = page.getByTestId('data-source-run').first();

    await run.getByRole('button', { name: 'Copy parameters' }).click();

    await expect(run.getByRole('button', { name: 'Copied' })).toBeVisible();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied.replace(/\r\n/g, '\n')).toBe(JSON.stringify({ cube: { region: 'north' } }, null, 2));
  });

  test('says so when copying fails', async ({ page }) => {
    const { rows } = await openPanel(page);
    await rows.first().click();
    await page.evaluate(() => {
      navigator.clipboard.writeText = () => Promise.reject(new Error('blocked'));
    });
    const run = page.getByTestId('data-source-run').first();

    await run.getByRole('button', { name: 'Copy parameters' }).click();

    await expect(run.getByRole('button', { name: "Couldn't copy" })).toBeVisible();
  });

  test('does not offer to copy params the preview had to cut short', async ({ page }) => {
    const { rows, preview } = await openPanel(page);
    await rows.first().click();

    await preview.locator('#huge').click();

    const runs = page.getByTestId('data-source-run');
    await expect(runs).toHaveCount(2);
    await expect(runs.first().getByRole('button', { name: 'Copy parameters' })).toBeDisabled();
    await expect(runs.first().getByTitle(/too large to copy/)).toBeVisible();
    await expect(runs.last().getByRole('button', { name: 'Copy parameters' })).toBeEnabled();
  });

  test('logs the BI events, without any params', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    const logged: { event: string; properties?: Record<string, unknown> }[] = [];
    await page.route('**/api/bi/events', (route) => {
      logged.push(...(route.request().postDataJSON() as typeof logged));
      return route.fulfill({ json: { status: 'ok' } });
    });
    const { rows } = await openPanel(page, {
      updates: [{ data_source_id: '12', updated_date: '2024-03-01T00:00:00.000' }],
    });
    await expect(rows.first().getByTestId('data-source-update-dot')).toBeVisible();

    await rows.first().getByRole('button', { name: 'Sync', exact: true }).click();
    await rows.last().getByRole('button', { name: 'Sync', exact: true }).click();
    for (const issue of ["This isn't running when it should", "This is running when it shouldn't", 'The parameters this gets are wrong']) {
      await rows.first().getByRole('button', { name: 'Adjust' }).click();
      await page.getByRole('button', { name: issue }).click();
    }
    await rows.first().click();
    await page.getByTestId('data-source-run').first().getByRole('button', { name: 'Copy parameters' }).click();

    const ours = () =>
      logged.filter((entry) => entry.event.startsWith('data_source_')).map((e) => [e.event, e.properties]);
    await expect.poll(ours).toEqual([
      ['data_source_sync_clicked', { data_source_id: '12', update_available: true }],
      ['data_source_sync_clicked', { data_source_id: '7', update_available: false }],
      ['data_source_adjust_selected', { data_source_id: '12', issue: 'not_running' }],
      ['data_source_adjust_selected', { data_source_id: '12', issue: 'running_when_it_should_not' }],
      ['data_source_adjust_selected', { data_source_id: '12', issue: 'wrong_params' }],
      ['data_source_params_copied', { data_source_id: '12' }],
    ]);
    expect(JSON.stringify(logged)).not.toContain('north');
  });
});
