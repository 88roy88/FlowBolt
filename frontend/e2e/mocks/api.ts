/**
 * Playwright route handlers that mock the backend REST API.
 *
 * The mock maintains a simple in-memory project list so tests can
 * start with an empty state, create projects, and delete them.
 */
import { type Page } from '@playwright/test';
import {
  MOCK_PROJECT, MOCK_FILE_TREE, MOCK_APP_TSX, MOCK_MODELS,
  SESSION_ID, PROJECT_ID,
} from './data';

export interface MockAPIOptions {
  /** Initial project list. Defaults to [MOCK_PROJECT]. Pass [] for empty state. */
  projects?: typeof MOCK_PROJECT[];
}

export async function setupMockAPI(page: Page, options: MockAPIOptions = {}) {
  const projects = options.projects ?? [MOCK_PROJECT];

  // --- Projects ---
  await page.route('**/api/projects', async (route) => {
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON();
      const newProject = {
        ...MOCK_PROJECT,
        id: `project-${Date.now()}`,
        name: body?.name ?? 'Untitled',
        session_id: `session-${Date.now()}`,
      };
      projects.push(newProject);
      return route.fulfill({ json: newProject });
    }
    // GET — list projects
    return route.fulfill({ json: [...projects] });
  });

  await page.route('**/api/projects/*', async (route) => {
    const url = route.request().url();

    // Skip sub-routes like /name, /model
    if (url.includes('/name') || url.includes('/model')) {
      return route.fulfill({ status: 200, json: {} });
    }

    if (route.request().method() === 'DELETE') {
      // Extract project ID from URL and remove from list
      const parts = url.split('/');
      const deletedId = parts[parts.length - 1];
      const idx = projects.findIndex(p => p.id === deletedId);
      if (idx >= 0) projects.splice(idx, 1);
      return route.fulfill({ status: 204, body: '' });
    }
    return route.fulfill({ json: projects[0] ?? MOCK_PROJECT });
  });

  // --- Files ---
  await page.route(`**/api/files/*/tree`, async (route) => {
    return route.fulfill({ json: MOCK_FILE_TREE });
  });

  await page.route(`**/api/files/*/content**`, async (route) => {
    if (route.request().method() === 'PUT') {
      return route.fulfill({ status: 200, json: {} });
    }
    return route.fulfill({ json: { path: 'src/App.tsx', content: MOCK_APP_TSX } });
  });

  // --- Chat ---
  await page.route(`**/api/chat/*/history`, async (route) => {
    return route.fulfill({ json: [] });
  });

  await page.route(`**/api/chat/*/events`, async (route) => {
    return route.fulfill({ json: [] });
  });

  // --- Models ---
  await page.route('**/api/models', async (route) => {
    return route.fulfill({ json: MOCK_MODELS });
  });

  await page.route('**/api/models/default', async (route) => {
    return route.fulfill({ json: { model: 'mock/test-model' } });
  });

  // --- Preview ---
  await page.route(`**/api/preview/*/port`, async (route) => {
    return route.fulfill({ json: { session_id: SESSION_ID, port: 3001 } });
  });

  await page.route(`**/api/preview/*/proxy/**`, async (route) => {
    return route.fulfill({
      contentType: 'text/html',
      body: '<html><body><h1>Preview</h1></body></html>',
    });
  });

  // --- Data source search ---
  await page.route('**/api/data-source/search/**', async (route) => {
    return route.fulfill({ json: [] });
  });
}
