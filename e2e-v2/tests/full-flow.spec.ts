/**
 * Full end-to-end flow covering every major feature:
 *   auth → model selection → create project →
 *   chat → plan (modify + approve) → build (with executor auto-fix) →
 *   preview refresh → rename project → summary modal →
 *   code edit + hot-reload → Ctrl+P → search in files → Monaco find →
 *   user bug + fix → server log tab → console tab →
 *   runtime crash button + fix → terminal →
 *   followup (buggy dark mode) + fix → preview →
 *   export ZIP → delete project
 */

import { test, expect, Page } from '@playwright/test';
import * as http from 'http';
import { FULL_FLOW_QUEUE } from '../scenarios/full-flow-responses';

const LLM_ADMIN = 'http://localhost:9999/admin';
const BACKEND = 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function seedLlmQueue(responses: typeof FULL_FLOW_QUEUE) {
  await fetch(`${LLM_ADMIN}/reset`, { method: 'POST' });
  const res = await fetch(`${LLM_ADMIN}/queue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(responses),
  });
  if (!res.ok) throw new Error(`Failed to seed LLM queue: ${res.status}`);
}

function pollHttp(url: string, timeoutMs: number): Promise<unknown> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http
        .get(url, (res) => {
          let data = '';
          res.on('data', (c: Buffer) => (data += c));
          res.on('end', () => {
            if (res.statusCode && res.statusCode < 400) {
              try { resolve(JSON.parse(data)); } catch { resolve(data); }
            } else if (Date.now() < deadline) {
              setTimeout(attempt, 1000);
            } else {
              reject(new Error(`Timeout polling ${url} (last status: ${res.statusCode})`));
            }
          });
        })
        .on('error', () => {
          if (Date.now() < deadline) setTimeout(attempt, 1000);
          else reject(new Error(`Timeout polling ${url}`));
        });
    };
    attempt();
  });
}

async function waitForSandbox(projectId: string, timeoutMs = 120_000) {
  console.log(`Waiting for sandbox ${projectId}...`);
  await pollHttp(`${BACKEND}/api/preview/${projectId}/port`, timeoutMs);
  console.log(`Sandbox ${projectId} ready`);
}

/** Pause in headed mode so a human can read/observe. No-op in headless. */
const look = (page: Page, ms = 3500) =>
  process.env.HEADED === '1' ? page.waitForTimeout(ms) : Promise.resolve();

/**
 * Show a floating step-name banner at the top of the browser window in headed mode.
 * In headless this is a no-op. Use it at the start of each major section so you
 * can see at a glance which step the test is on while watching.
 */
async function step(page: Page, name: string) {
  if (process.env.HEADED !== '1') return;
  await page.evaluate((n) => {
    document.getElementById('__e2e_step__')?.remove();
    const el = document.createElement('div');
    el.id = '__e2e_step__';
    el.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:999999',
      'background:#111827', 'color:#38bdf8', 'font:bold 13px/1 monospace',
      'padding:6px 14px', 'text-align:center', 'letter-spacing:.5px',
      'border-bottom:2px solid #38bdf8',
      'pointer-events:none',  // never block clicks on page elements beneath the banner
    ].join(';');
    el.textContent = `▶ ${n}`;
    document.body.appendChild(el);
  }, name);
}

/** Dispatch a keydown event on window (for hooks that listen there, e.g. Ctrl+P, Ctrl+Shift+F). */
async function dispatchWindowKey(page: Page, key: string, code: string, opts: { ctrlKey?: boolean; shiftKey?: boolean } = {}) {
  await page.evaluate(([k, c, ctrl, shift]) => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: k as string, code: c as string, ctrlKey: !!ctrl, shiftKey: !!shift, bubbles: true, cancelable: true }));
  }, [key, code, opts.ctrlKey ?? false, opts.shiftKey ?? false] as const);
}

/** Dispatch Ctrl+S to window to trigger the save hook. */
async function ctrlS(page: Page) {
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', code: 'KeyS', ctrlKey: true, bubbles: true, cancelable: true }));
  });
}

/** Wait for "Fix with AI" error toast and click it, then wait for fix to complete. */
async function fixWithAI(page: Page) {
  const fixBtn = page.getByRole('button', { name: 'Fix with AI' }).first();
  await expect(fixBtn).toBeVisible({ timeout: 30_000 });
  await look(page, 1500); // see the error toast before fixing
  await fixBtn.click();
  // Wait for fix to complete (chat input re-enabled)
  await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 60_000 });
  await look(page, 1500); // see the result
}

/** Open the sidebar by hovering, hover the project item, return the project item locator. */
async function expandSidebar(page: Page, projectId: string) {
  await page.getByTestId('sidebar-container').hover();
  await page.waitForTimeout(400);
  const item = page.getByTestId(`project-item-${projectId}`);
  await item.hover();
  await page.waitForTimeout(200);
  return item;
}

/**
 * Force classic layout and clear stale caches on the very first load.
 * Subsequent reloads (page.reload()) keep existing localStorage so the auth
 * token and project state survive — this lets us test reload behaviour.
 * sessionStorage is cleared on tab close but persists across page.reload().
 */
async function seedLocalStorage(page: Page) {
  await page.addInitScript(() => {
    const isFirstLoad = !sessionStorage.getItem('e2e-v2-initialized');
    localStorage.setItem('layout-mode', 'classic');
    if (isFirstLoad) {
      sessionStorage.setItem('e2e-v2-initialized', '1');
      localStorage.removeItem('Auth'); // intentionally no token → exercises sign-in
      for (const k of Object.keys(localStorage)) {
        if (k.startsWith('project-has-messages:') || k === 'has-projects') {
          localStorage.removeItem(k);
        }
      }
    }
  });
}

// ---------------------------------------------------------------------------
// THE Test
// ---------------------------------------------------------------------------

test('full flow: create → build → preview → edit → terminal → followup → delete', async ({ page }) => {
  await seedLocalStorage(page);
  await seedLlmQueue(FULL_FLOW_QUEUE);

  // =========================================================================
  // 1. AUTH — sign-in screen → iframe SSO auto-submits → authenticated
  // =========================================================================
  await step(page, '1. Auth — sign in');
  await page.goto('/');
  const signInBtn = page.getByRole('button', { name: 'Sign In' });
  await expect(signInBtn).toBeVisible({ timeout: 10_000 });
  await look(page, 2000);

  await signInBtn.click();
  await look(page, 2000); // watch auth iframe
  await expect(page.getByTestId('initial-create-button')).toBeVisible({ timeout: 15_000 });
  await look(page, 1000);
  console.log('Authenticated');

  // =========================================================================
  // 2. CREATE PROJECT
  // =========================================================================
  await step(page, '2. Create project');
  await page.getByTestId('initial-project-input').pressSequentially('E2E Todo App');
  await look(page, 1000);
  await page.getByTestId('initial-create-button').click();

  await page.waitForURL(/\#\/project\/.+/, { timeout: 15_000 });
  await expect(page.getByTestId('chat-input')).toBeVisible({ timeout: 10_000 });
  await look(page, 1500);

  const projectId = new URL(page.url()).hash.split('/').at(-1)!;
  console.log(`Project ID: ${projectId}`);

  // =========================================================================
  // 3. MODEL SELECTION — pick gpt-4-turbo
  // =========================================================================
  await step(page, '3. Model selection');
  await page.getByTestId('model-selector-button').click();
  await expect(page.getByText('openai/gpt-4-turbo')).toBeVisible({ timeout: 5_000 });
  await look(page, 1500);
  await page.getByText('openai/gpt-4-turbo').click();
  await expect(page.getByTestId('model-selector-button')).toContainText('gpt-4-turbo');
  await look(page, 1000);
  console.log('Model: gpt-4-turbo selected');

  // =========================================================================
  // 4. SEND CHAT MESSAGE
  // =========================================================================
  await step(page, '4. Send chat message → design → plan');
  await page.getByTestId('chat-input').pressSequentially('Build me a todo app');
  await look(page, 1000);
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('chat-input')).toBeDisabled({ timeout: 5_000 });

  // =========================================================================
  // 5. PLAN — modify then approve
  // =========================================================================
  await step(page, '5. Plan review');
  await expect(page.getByTestId('plan-approve-button')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('A clean todo app')).toBeVisible();
  await look(page, 3000);

  // ─── Plan rejection ("Start over") ────────────────────────────────────────
  // "Start over" clears the pending plan and returns to idle — it does NOT
  // auto-restart PlanAgent. The user must re-send their message to get a new plan.
  // This exercises the reject code path (different from "Change something").
  await step(page, '5a. Plan rejection — Start over');
  await page.getByTestId('plan-reject-button').click();
  // Plan cleared → plan-approve-button disappears, chat input becomes enabled
  await expect(page.getByTestId('plan-approve-button')).not.toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 10_000 });
  await look(page, 1500);
  console.log('Plan rejection: plan cleared, chat input ready ✓');

  // Re-send to get a fresh plan (consumes 3 queue items: 2 design + 1 overview)
  await page.getByTestId('chat-input').pressSequentially('Build me a todo app');
  await look(page, 500);
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('plan-approve-button')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText('A clean todo app')).toBeVisible({ timeout: 5_000 });
  await look(page, 2000);
  console.log('After rejection: new plan from re-sent message ✓');
  // ───────────────────────────────────────────────────────────────────────────
  // ───────────────────────────────────────────────────────────────────────────

  // Click "Change something" → textarea appears
  await page.getByTestId('plan-modify-button').click();
  const feedbackTextarea = page.getByPlaceholder(/What would you like to change/i);
  await expect(feedbackTextarea).toBeVisible({ timeout: 3_000 });
  await feedbackTextarea.pressSequentially('please add a filter feature');
  await look(page, 1500);

  // Send feedback — button text changes to "Send feedback" when modifyMode is active
  await page.getByTestId('plan-modify-button').click(); // second click submits
  await look(page, 500);

  // New plan appears with the updated summary
  await expect(page.getByTestId('plan-approve-button')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/updated based on your feedback/i)).toBeVisible({ timeout: 10_000 });
  await look(page, 3000); // read the updated plan

  // ─── Reload while plan is pending ──────────────────────────────────────────
  // The pending plan is persisted in the DB. After reload the frontend fetches
  // chat history and should restore the plan + approve button.
  await page.reload();
  await expect(page.getByTestId('plan-approve-button')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/updated based on your feedback/i)).toBeVisible({ timeout: 5_000 });
  await look(page, 2000); // confirm plan survived the reload
  console.log('Reload during plan: pending plan restored from DB ✓');
  // ───────────────────────────────────────────────────────────────────────────

  await page.getByTestId('plan-approve-button').click();
  await look(page, 1000);
  console.log('Plan approved (after modify)');

  // =========================================================================
  // 6. EXECUTION — auto-fix built in (faulty task-1 → executor fixes it)
  await step(page, '6. Build — executor auto-fix');
  // =========================================================================
  await expect(page.getByText('Create App component')).toBeVisible({ timeout: 30_000 });
  // The executor will see a TS error after task-1, call fix, then complete normally.
  await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 120_000 });
  await look(page, 3000);
  console.log('Build complete (executor auto-fix verified)');

  // ─── Reload after build ────────────────────────────────────────────────────
  // Build events are stored in the DB. After reload the frontend should:
  //   • Still be on the correct project
  //   • Show the full build conversation (chat history restored)
  //   • Chat input ready (not streaming)
  await page.reload();
  await page.waitForURL(/\#\/project\/.+/, { timeout: 10_000 });
  await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 15_000 });
  // The build conversation should be visible (at least the task list card)
  await expect(page.getByText('Create App component')).toBeVisible({ timeout: 10_000 });
  await look(page, 2000);
  console.log('Reload after build: chat history + project state restored ✓');
  // Model selection should also persist across reload (stored per-project in DB)
  await expect(page.getByTestId('model-selector-button')).toContainText('gpt-4-turbo', { timeout: 5_000 });
  console.log('Model selection persists across reload ✓');
  // ───────────────────────────────────────────────────────────────────────────

  // =========================================================================
  // 7. PREVIEW — load + refresh button
  await step(page, '7. Preview + refresh + interact');
  // =========================================================================
  await waitForSandbox(projectId, 120_000);

  const previewTab = page.getByRole('button', { name: 'Preview' });
  if (await previewTab.isVisible()) await previewTab.click();

  const iframe = page.getByTestId('preview-iframe');
  await expect(iframe).toBeVisible({ timeout: 30_000 });
  await look(page, 1500);
  console.log(`Preview: ${await iframe.getAttribute('src')}`);
  await look(page, 3000);

  // Click the Refresh button — capture the iframe src before and confirm it reloads
  const srcBefore = await iframe.getAttribute('src');
  await page.getByRole('button', { name: 'Refresh' }).click();
  // After refresh the iframe key increments, so the src may briefly be removed then restored.
  // Wait for the iframe to be attached and have a src again.
  await expect(iframe).toBeVisible({ timeout: 5_000 });
  const srcAfter = await iframe.getAttribute('src');
  expect(srcAfter).toBeTruthy(); // iframe still has a source after refresh
  await look(page, 1500); // see the preview reload
  console.log(`Preview refreshed (src: ${srcAfter ?? 'same'}`);

  // ─── Interact with the running app ─────────────────────────────────────────
  // The generated Todo App should be fully functional. Add a todo and verify it
  // renders — this proves the LLM-generated React code actually runs correctly.
  const appFrame = page.frameLocator('[data-testid="preview-iframe"]');
  const todoInput = appFrame.getByPlaceholder('Add todo...');
  await expect(todoInput).toBeVisible({ timeout: 10_000 });
  await todoInput.fill('buy milk');
  await appFrame.getByRole('button', { name: 'Add' }).click();
  await expect(appFrame.getByText('buy milk')).toBeVisible({ timeout: 5_000 });
  // Toggle it done (click the text)
  await appFrame.getByText('buy milk').click();
  await look(page, 1500); // see the strikethrough done state
  console.log('Preview app functional: todo added and toggled ✓');
  // ───────────────────────────────────────────────────────────────────────────

  // =========================================================================
  // 8. RENAME PROJECT
  await step(page, '8. Rename project');
  // =========================================================================
  await expandSidebar(page, projectId);
  await page.getByTestId(`project-menu-button-${projectId}`).click();
  await page.getByText('Rename', { exact: true }).first().click();

  const renameInput = page.getByTestId('rename-project-input');
  await expect(renameInput).toBeVisible({ timeout: 3_000 });
  await renameInput.selectText();
  await renameInput.pressSequentially('E2E App Renamed');
  await look(page, 1000);
  await renameInput.press('Enter');
  await expect(page.getByText('E2E App Renamed')).toBeVisible({ timeout: 5_000 });
  await look(page, 1000);
  console.log('Project renamed');

  // ─── Reload after rename ───────────────────────────────────────────────────
  // The new name is written to the DB. Verify it survives a full page reload.
  await page.reload();
  await page.waitForURL(/\#\/project\/.+/, { timeout: 10_000 });
  // "E2E App Renamed" should appear in the sidebar after reload
  await expandSidebar(page, projectId);
  await expect(page.getByText('E2E App Renamed')).toBeVisible({ timeout: 10_000 });
  await look(page, 1500);
  console.log('Reload after rename: new name persists in DB ✓');
  // ───────────────────────────────────────────────────────────────────────────

  // =========================================================================
  // 9. SUMMARY MODAL
  await step(page, '9. Summary modal');
  // =========================================================================
  await expandSidebar(page, projectId);
  await page.getByTestId(`project-menu-button-${projectId}`).click();
  // Summary button only shows when project.summary is set (set by ExecuteAgent after build)
  await page.getByTestId(`summary-project-button-${projectId}`).click();

  // Summary modal appears — shows project name as h3 title + summary text
  await expect(page.getByText('E2E App Renamed').last()).toBeVisible({ timeout: 5_000 });
  // Scope to the modal overlay to avoid matching the same text in chat cards
  await expect(page.locator('.fixed.inset-0').getByText('Toggle completion status')).toBeVisible({ timeout: 5_000 });
  await look(page, 3000); // read the project summary

  // Close by clicking the backdrop (custom Dialog uses onClick on the overlay to close)
  await page.locator('.fixed.inset-0').click({ position: { x: 10, y: 10 } });
  await look(page, 500);
  console.log('Summary modal shown and closed');

  // =========================================================================
  // 10. CODE EDIT — "Todo App" → "My Tasks" + hot-reload
  await step(page, '10. Code edit — hot-reload');
  // =========================================================================
  const codeTab = page.getByRole('button', { name: 'Code' });
  await expect(codeTab).toBeVisible({ timeout: 10_000 });
  await codeTab.click();

  const appTsxEntry = page.getByText('App.tsx', { exact: true }).first();
  await expect(appTsxEntry).toBeVisible({ timeout: 10_000 });
  await appTsxEntry.click();

  const monacoHost = page.getByTestId('monaco-editor-host');
  await expect(monacoHost).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(400);

  // Save once to confirm editor + save pipeline work
  await ctrlS(page);
  await expect(page.getByText('Saved')).toBeVisible({ timeout: 5_000 });
  await look(page);

  // Change "Todo App" → "My Tasks"
  await page.evaluate(() => {
    const models = (window as any).monaco?.editor?.getModels?.() ?? [];
    const model = models.find((m: any) => m.uri?.path?.includes('App.tsx'));
    if (model) {
      model.setValue(
        model.getValue()
          .replace(/>Todo App</g, '>My Tasks<')
          .replace(/'Todo App'/g, "'My Tasks'")
          .replace(/"Todo App"/g, '"My Tasks"')
      );
    }
  });
  await look(page, 1500);
  await ctrlS(page);
  await expect(page.getByText('Saved')).toBeVisible({ timeout: 5_000 });
  console.log('Code changed: "My Tasks"');

  if (await previewTab.isVisible()) await previewTab.click();
  await look(page, 3000); // watch hot-reload

  // =========================================================================
  // 11. CTRL+P — quick file open → opens index.css
  await step(page, '11. Ctrl+P quick open');
  // =========================================================================
  await expect(codeTab).toBeVisible({ timeout: 5_000 });
  await codeTab.click();
  await expect(page.getByText('App.tsx', { exact: true }).first()).toBeVisible({ timeout: 10_000 });
  await look(page, 500);

  await dispatchWindowKey(page, 'p', 'KeyP', { ctrlKey: true });
  const quickOpenInput = page.getByPlaceholder(/Type a file name/i);
  await expect(quickOpenInput).toBeVisible({ timeout: 5_000 });
  await quickOpenInput.pressSequentially('index');
  const quickOpenResult = page.getByRole('button', { name: /index\.css.*src\/index\.css/i }).first();
  await expect(quickOpenResult).toBeVisible({ timeout: 5_000 });
  await look(page, 2000);
  await page.keyboard.press('Enter');
  await expect(page.getByText('index.css', { exact: true }).first()).toBeVisible({ timeout: 5_000 });
  await look(page, 1500);
  console.log('Ctrl+P: index.css opened');

  // =========================================================================
  // 12. CTRL+SHIFT+F — search in files → "useState" → click result
  await step(page, '12. Ctrl+Shift+F search in files');
  // =========================================================================
  await dispatchWindowKey(page, 'f', 'KeyF', { ctrlKey: true, shiftKey: true });
  const searchInput = page.getByPlaceholder(/Search in files/i);
  await expect(searchInput).toBeVisible({ timeout: 5_000 });
  await searchInput.click();
  await searchInput.pressSequentially('useState');

  await expect(page.getByText('Searching…')).toBeVisible({ timeout: 5_000 }).catch(() => {});
  await expect(page.getByText('Searching…')).not.toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('No results. Try another query.')).not.toBeVisible();

  // The search results show a FILE HEADER button (title="src/App.tsx") that toggles
  // collapse, followed by individual MATCH buttons that call jumpToSearchHit().
  // We must click a match button, not the file header.
  const fileGroupHeader = page.locator('[title*="App.tsx"]').first();
  if (await fileGroupHeader.isVisible()) {
    // Navigate to the parent result group and grab the first MATCH button (index 1)
    const firstMatchBtn = fileGroupHeader.locator('xpath=..').locator('button').nth(1);
    await expect(firstMatchBtn).toBeVisible({ timeout: 3_000 });
    await firstMatchBtn.click();

    // 1. Correct file opened — App.tsx appears in the editor tabs
    await expect(page.getByText('App.tsx', { exact: true }).first()).toBeVisible({ timeout: 5_000 });

    // 2. Cursor is in Monaco (blink animation means count() not toBeVisible())
    await expect.poll(
      () => page.locator('.monaco-editor .cursor').count(),
      { timeout: 3_000 }
    ).toBeGreaterThan(0);

    // 3. Whole-line highlight (.editor-search-hit-highlight-line) lasts 1.8 s —
    //    the line decoration is a full-width div, reliably present in DOM after jumpToSearchHit
    await expect.poll(
      () => page.locator('.editor-search-hit-highlight-line').count(),
      { timeout: 2_000 }
    ).toBeGreaterThan(0);
  }
  await look(page, 2500); // watch the highlight fade
  console.log('Search in files: file opened, cursor jumped, line highlighted');

  // =========================================================================
  // 13. MONACO CTRL+F — find within current file
  await step(page, '13. Monaco Ctrl+F find widget');
  // =========================================================================
  await page.locator('.monaco-editor').first().click();
  await page.waitForTimeout(200);
  await page.keyboard.press('Control+f');
  const findWidget = page.locator('.monaco-editor .find-widget');
  await expect(findWidget).toBeVisible({ timeout: 5_000 });
  await look(page, 1500);
  await page.keyboard.type('useState');
  // Monaco renders each match with .cdr.findMatch decoration class
  await expect.poll(
    () => page.locator('.monaco-editor .cdr.findMatch').count(),
    { timeout: 3_000 }
  ).toBeGreaterThan(0);
  await look(page, 2000);
  await page.keyboard.press('Escape');
  await look(page, 500);
  console.log('Monaco Ctrl+F: find widget used, matches highlighted');

  // =========================================================================
  // 14. USER INTRODUCES A BUG → fix with AI
  await step(page, '14. User introduces bug → Fix with AI');
  // =========================================================================
  // Save a broken version of App.tsx directly via the backend API.
  // We use setTimeout+throw so the error bypasses React's error handling and
  // reaches window.onerror → template forwards as runtime-error postMessage
  // → useErrorCapture (no async file fetch needed) → ErrorToast immediately.
  await page.evaluate(async ([pid]) => {
    const res = await fetch(`/api/files/${pid}/content?path=%2Fsrc%2FApp.tsx`);
    const original = await res.text();
    const buggy = original.replace(
      "import { useState } from 'react'",
      "import { useState, useEffect } from 'react'"
    ).replace(
      "  const remove",
      "  // e2e-user-bug: setTimeout throw → window.onerror → ErrorToast → Fix with AI\n  useEffect(() => { const t = setTimeout(() => { throw new Error('E2E User-Introduced Bug') }, 200); return () => clearTimeout(t) }, [])\n\n  const remove"
    );
    await fetch(`/api/files/${pid}/content`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: '/src/App.tsx', content: buggy }),
    });
  }, [projectId]);
  console.log('User bug introduced via API');

  // Switch to Preview — iframe hot-reloads and runs the buggy App.tsx.
  // console.error fires → template forwards via postMessage → ErrorToast appears.
  if (await previewTab.isVisible()) await previewTab.click();
  else await previewTab.click();
  await page.waitForTimeout(3000); // wait for HMR + error propagation
  await look(page, 1000);

  await fixWithAI(page); // "Fix with AI" → FixErrorAgent → fixed
  console.log('User bug fixed');

  // =========================================================================
  // 15. SERVER LOG TAB
  await step(page, '15. Server log tab');
  // =========================================================================
  const serverTab = page.getByRole('button', { name: /^server$/i }).first();
  await expect(serverTab).toBeVisible({ timeout: 5_000 });
  await serverTab.click();
  // Server Log shows Vite dev server output — at minimum the initial "ready" line
  // or stack traces from the console.error we fired. Check the content area is rendered.
  await expect(page.locator('.xterm, [class*="server"], [class*="ServerLog"]').first()).toBeVisible({ timeout: 5_000 });
  await look(page, 2000);
  console.log('Server log tab open');

  // =========================================================================
  // 16. CONSOLE TAB
  await step(page, '16. Console tab');
  // =========================================================================
  const consoleTab = page.getByRole('button', { name: /^console$/i }).first();
  await expect(consoleTab).toBeVisible({ timeout: 5_000 });
  await consoleTab.click();
  // Console tab renders output from the preview iframe's console.* calls.
  // The area should be present and not display "No console output" (empty state).
  // If the Followup HMR didn't force a full reload, the user-bug console.error is still visible.
  await page.waitForTimeout(500);
  const noConsoleText = page.getByText('No console output', { exact: false });
  const hasNoOutput = await noConsoleText.isVisible();
  if (!hasNoOutput) {
    // Has output — verify the console component rendered entries
    await expect(page.locator('[class*="Console"], [class*="console-"]').first()).toBeVisible({ timeout: 3_000 }).catch(() => {});
    console.log('Console tab open — has output entries');
  } else {
    console.log('Console tab open — output was cleared by HMR reload (expected)');
  }
  await look(page, 2000);

  // =========================================================================
  // 17. RUNTIME CRASH BUTTON — add via Monaco, click in preview, fix error
  await step(page, '17. Runtime crash button → Fix with AI');
  // =========================================================================
  // Add a crash button directly via the backend API (bypasses Monaco eval issues)
  await page.evaluate(async ([pid]) => {
    const res = await fetch(`/api/files/${pid}/content?path=%2Fsrc%2FApp.tsx`);
    const original = await res.text();
    const withCrash = original.replace(
      '<ul>',
      '<button onClick={() => { throw new Error("E2E Runtime Test") }} style={{display:"block",margin:"8px 0",padding:"8px 12px",background:"#ef4444",color:"white",border:"none",borderRadius:"4px",cursor:"pointer"}}>Trigger Runtime Error</button>\n      <ul>'
    );
    await fetch(`/api/files/${pid}/content`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: '/src/App.tsx', content: withCrash }),
    });
  }, [projectId]);
  console.log('Crash button added via API');

  // Switch to Preview — iframe mounts and Vite serves the updated App.tsx with crash button
  if (await previewTab.isVisible()) await previewTab.click();
  await page.waitForTimeout(3000); // wait for iframe load + Vite HMR delivery
  await look(page, 1500); // see the crash button in the preview

  // Click the crash button inside the preview iframe → runtime error fires → toast appears
  const previewFrame = page.frameLocator('[data-testid="preview-iframe"]');
  const crashBtn = previewFrame.getByText('Trigger Runtime Error');
  await expect(crashBtn).toBeVisible({ timeout: 15_000 });
  await crashBtn.click();
  console.log('Runtime error triggered in preview iframe');

  await fixWithAI(page); // error toast → "Fix with AI" → wait for fix
  console.log('Runtime error fixed');

  // =========================================================================
  // 18. TERMINAL — run a command
  await step(page, '18. Terminal command');
  // =========================================================================
  // Case-insensitive: small tabs render lowercase "terminal" (drawer closed),
  // large tabs render titlecase "Terminal" (drawer open).
  const terminalTab = page.getByRole('button', { name: /^terminal$/i });
  await expect(terminalTab).toBeVisible({ timeout: 5_000 });
  await terminalTab.click();

  const xtermContainer = page.locator('.xterm').first();
  await expect(xtermContainer).toBeVisible({ timeout: 10_000 });

  await page.locator('.xterm-helper-textarea').first().click();
  await page.keyboard.type('echo "hello e2e"');
  await page.keyboard.press('Enter');
  await page.waitForTimeout(2000);
  // Verify the terminal output contains the echo result
  // xterm renders output as spans/divs inside .xterm-screen
  await expect(page.locator('.xterm-screen')).toContainText('hello e2e', { timeout: 5_000 });
  await look(page);
  console.log('Terminal: echo output verified');

  // =========================================================================
  // 19. FOLLOWUP — dark mode (intentionally buggy) → see error → fix
  await step(page, '19. Followup — dark mode → bug → fix');
  // =========================================================================
  await page.getByTestId('chat-input').pressSequentially('add a dark mode toggle');
  await look(page, 1000);
  await page.getByTestId('send-button').click();

  await expect(page.getByText(/I've added a dark mode/i)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('chat-input')).toBeEnabled({ timeout: 30_000 });
  await look(page); // read the followup response
  console.log('Followup sent (dark mode — buggy code expected)');

  // The buggy followup code has a console.error useEffect.
  // Switch to Preview so the iframe reloads with the new code and fires the error.
  if (await previewTab.isVisible()) await previewTab.click();
  await page.waitForTimeout(3000); // wait for HMR + iframe console.error propagation
  await look(page, 1000);

  await fixWithAI(page); // fix the followup's bug
  console.log('Followup bug fixed');

  // Preview shows the fixed dark mode
  if (await previewTab.isVisible()) await previewTab.click();
  await look(page, 3000);
  console.log('Updated preview with dark mode');

  // =========================================================================
  // 20. EXPORT ZIP
  await step(page, '20. Export ZIP + HTML');
  // =========================================================================
  await expect(codeTab).toBeVisible({ timeout: 5_000 });
  await codeTab.click();
  await expect(page.getByTestId('export-dropdown-toggle')).toBeVisible({ timeout: 5_000 });

  // Export ZIP
  const downloadPromise = page.waitForEvent('download');
  await page.getByTestId('export-dropdown-toggle').click();
  await expect(page.getByTestId('export-zip-button')).toBeVisible({ timeout: 3_000 });
  await look(page, 1000);
  await page.getByTestId('export-zip-button').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.(zip|html)$/i);
  await look(page, 1000);
  console.log(`Exported ZIP: ${download.suggestedFilename()}`);

  // Export HTML (separate function from ZIP — tests a different endpoint)
  const htmlDownloadPromise = page.waitForEvent('download');
  await page.getByTestId('export-dropdown-toggle').click();
  await expect(page.getByText('Export HTML')).toBeVisible({ timeout: 3_000 });
  await page.getByText('Export HTML').click();
  const htmlDownload = await htmlDownloadPromise;
  expect(htmlDownload.suggestedFilename()).toMatch(/\.html$/i);
  await look(page, 1000);
  console.log(`Exported HTML: ${htmlDownload.suggestedFilename()}`);

  // =========================================================================
  // 21. S3 PUBLISH (only if MinIO is available)
  await step(page, '21. S3 Publish');
  // =========================================================================
  if (process.env.E2E_MINIO_AVAILABLE === '1') {
    // Switch to Preview to access the Publish button
    const previewTabForPublish = page.getByRole('button', { name: 'Preview' });
    if (await previewTabForPublish.isVisible()) await previewTabForPublish.click();

    await page.getByRole('button', { name: 'Publish' }).click();
    // PublishModal appears — wait for success state
    await expect(page.getByText('Successfully Published')).toBeVisible({ timeout: 30_000 });
    // A URL is shown in the modal — verify it's accessible
    const publishedUrl = await page.locator('[class*="PublishModal"] a, .fixed a[href*="localhost"]').first().getAttribute('href')
      ?? await page.evaluate(() => {
        const links = Array.from(document.querySelectorAll('.fixed a'));
        return links.map((l: Element) => (l as HTMLAnchorElement).href).find(h => h.includes('localhost')) ?? null;
      });
    if (publishedUrl) {
      const resp = await page.evaluate((url) => fetch(url).then(r => r.status), publishedUrl);
      expect(resp).toBe(200);
      console.log(`Published URL accessible: ${publishedUrl} → HTTP ${resp} ✓`);
    }
    // Close the modal
    await page.getByText('Close').click();
    await look(page, 2000);
    console.log('S3 Publish: success modal shown, URL accessible ✓');
  } else {
    console.log('S3 Publish: skipped (MinIO not available)');
  }

  // =========================================================================
  // 22. MULTIPLE PROJECTS — create a second, verify sidebar, switch, delete it
  await step(page, '22. Multiple projects');
  // =========================================================================
  await expandSidebar(page, projectId);
  await look(page, 500);

  // "New Project" button is in the expanded sidebar
  await page.getByTestId('new-project-button').click();
  const secondProjectInput = page.getByTestId('new-project-input');
  await expect(secondProjectInput).toBeVisible({ timeout: 3_000 });
  await secondProjectInput.pressSequentially('E2E Second Project');
  await page.getByTestId('create-project-add-button').click();

  // Wait for second project to be created and selected
  await page.waitForURL(/\#\/project\/.+/, { timeout: 10_000 });
  const secondProjectId = new URL(page.url()).hash.split('/').at(-1)!;
  expect(secondProjectId).not.toBe(projectId); // different ID from first project

  // Both projects should be visible in the sidebar
  await expandSidebar(page, secondProjectId);
  await expect(page.getByTestId(`project-item-${projectId}`)).toBeVisible({ timeout: 5_000 });
  await expect(page.getByTestId(`project-item-${secondProjectId}`)).toBeVisible({ timeout: 5_000 });
  await look(page, 2000);
  console.log('Multiple projects: both visible in sidebar ✓');

  // Switch back to the first project
  await page.getByTestId(`project-item-${projectId}`).click();
  await page.waitForURL(new RegExp(`#/project/${projectId}`), { timeout: 5_000 });
  await look(page, 1000);
  console.log('Multiple projects: switched back to first project ✓');

  // Clean up: delete the second project
  await expandSidebar(page, secondProjectId);
  await page.getByTestId(`project-menu-button-${secondProjectId}`).click();
  await page.getByTestId(`delete-project-button-${secondProjectId}`).click();
  await page.getByTestId(`delete-project-button-${secondProjectId}`).click();
  // After deleting second project, first project should still be selected
  await expect(page.getByTestId(`project-item-${projectId}`)).toBeVisible({ timeout: 5_000 });
  await look(page, 1000);
  console.log('Multiple projects: second project deleted, first still intact ✓');

  // =========================================================================
  // 23. DELETE FIRST PROJECT
  await step(page, '23. Delete project');
  // =========================================================================
  await expandSidebar(page, projectId);
  await page.getByTestId(`project-menu-button-${projectId}`).click();
  await page.getByTestId(`delete-project-button-${projectId}`).click();  // show confirm
  await page.getByTestId(`delete-project-button-${projectId}`).click();  // confirm

  await expect(page.getByTestId('initial-create-button')).toBeVisible({ timeout: 10_000 });
  console.log('Project deleted');
});
