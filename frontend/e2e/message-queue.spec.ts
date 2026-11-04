/**
 * Message queue E2E tests:
 * - Messages typed during a run wait for the run to be released
 * - Stop moves queued messages back into the input
 */
import { type Page } from '@playwright/test';
import { test, expect } from './fixtures';
import { PROJECT_ID } from './mocks/data';

async function startRun(page: Page, sendChatEvents: (events: Record<string, unknown>[], delay?: number) => Promise<void>) {
  await page.goto(`/#/project/${PROJECT_ID}`);
  const input = page.getByTestId('chat-input');
  await expect(input).toBeEnabled({ timeout: 10_000 });

  await input.fill('Running prompt');
  await input.press('Enter');
  await sendChatEvents([{ type: 'phase', phase: 'exploring' }], 20);
  await expect(page.getByTestId('stop-button')).toBeVisible();
  return input;
}

test.describe('Message queue', () => {
  test('sends queued messages one at a time as runs are released', async ({ page, sendChatEvents }) => {
    const input = await startRun(page, sendChatEvents);
    const queued = page.getByTestId('queued-messages').getByRole('listitem');

    await expect(input).toBeEnabled();
    await expect(page.getByTestId('send-button')).toHaveCount(0);

    await input.fill('Queued one');
    await expect(page.getByTestId('send-button')).toBeVisible();
    await expect(page.getByTestId('stop-button')).toBeVisible();
    await input.press('Enter');
    await input.fill('Queued two');
    await input.press('Enter');

    await expect(input).toHaveValue('');
    await expect(queued).toHaveCount(2);

    await sendChatEvents([{ type: 'action_complete' }], 20);
    await expect(queued).toHaveCount(2);

    await sendChatEvents([{ type: 'run_released' }], 20);
    await expect(queued).toHaveText(['Queued two']);
    await expect(page.getByTestId('stop-button')).toBeVisible();

    await sendChatEvents([
      { type: 'phase', phase: 'exploring' },
      { type: 'action_complete' },
      { type: 'run_released' },
    ], 20);
    await expect(queued).toHaveCount(0);
  });

  test('removes a queued message', async ({ page, sendChatEvents }) => {
    const input = await startRun(page, sendChatEvents);

    await input.fill('Never mind');
    await input.press('Enter');
    await page.getByTestId('queued-remove').click();

    await expect(page.getByTestId('queued-messages')).toHaveCount(0);
  });

  test('moves queued messages back into the input on Stop', async ({ page, sendChatEvents }) => {
    const input = await startRun(page, sendChatEvents);

    await input.fill('Queued one');
    await input.press('Enter');
    await input.fill('Still typing');
    await page.getByTestId('stop-button').click();
    await sendChatEvents([{ type: 'turn_aborted' }], 20);

    await expect(input).toHaveValue('Queued one\n\nStill typing');
    await expect(page.getByTestId('queued-messages')).toHaveCount(0);
  });

  test('offers Send on a queue held after a failed turn', async ({ page, sendChatEvents }) => {
    const input = await startRun(page, sendChatEvents);

    await input.fill('Queued one');
    await input.press('Enter');
    await sendChatEvents([
      { type: 'phase', phase: 'idle' },
      { type: 'error', message: 'AI processing failed' },
      { type: 'run_released' },
    ], 20);

    await expect(page.getByTestId('queued-messages').getByRole('listitem')).toHaveCount(1);
    await page.getByTestId('queued-send').click();
    await expect(page.getByTestId('queued-messages')).toHaveCount(0);
  });
});
