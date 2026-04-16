/**
 * Playwright route handlers that mock the backend REST API.
 *
 * The mock maintains a simple in-memory project list so tests can
 * start with an empty state, create projects, and delete them.
 */
import { type Page } from '@playwright/test';
import {
  MOCK_PROJECT,
  MOCK_PROJECT_WITH_SLUG,
  MOCK_FILE_TREE,
  MOCK_MODELS,
  CHAT_SEED_EVENTS,
  MOCK_FILE_CONTENTS,
} from './data';

function normalizeContentPathParam(encodedPath: string): string {
  const raw = decodeURIComponent(encodedPath);
  return raw.replace(/\\/g, '/').replace(/^\/+/, '');
}

export interface MockAPIOptions {
  /** Initial project list. Defaults to [MOCK_PROJECT]. Pass [] for empty state. */
  projects?: typeof MOCK_PROJECT[];
  /** Return a minimal chat event replay so the main layout shows Preview/Code (not empty project). */
  seedChatHistory?: boolean;
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
    const url = new URL(route.request().url());
    const pathParam = url.searchParams.get('path') ?? '';
    const key = normalizeContentPathParam(pathParam);
    const content = MOCK_FILE_CONTENTS[key] ?? `// e2e placeholder: ${key}\n`;
    return route.fulfill({ json: { path: pathParam || key, content } });
  });

  await page.route(`**/api/files/*/search`, async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 405, body: 'Method Not Allowed' });
    }
    let body: { query?: string } = {};
    try {
      body = route.request().postDataJSON() as { query?: string };
    } catch {
      /* ignore */
    }
    const q = (body.query ?? '').trim();
    const results =
      q.includes('E2E_TYPES_MARKER')
        ? [
            {
              path: '/src/types.ts',
              uri: 'file:///src/types.ts',
              hits: [{ line: 4, column: 1, preview: '// E2E_TYPES_MARKER' }],
            },
          ]
        : [];
    return route.fulfill({ json: { query: q, results } });
  });

  // --- Chat ---
  await page.route(`**/api/chat/*/history`, async (route) => {
    return route.fulfill({ json: [] });
  });

  await page.route(`**/api/chat/*/events`, async (route) => {
    const payload = options.seedChatHistory ? CHAT_SEED_EVENTS : [];
    return route.fulfill({ json: payload });
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
    return route.fulfill({ json: { port: 3001 } });
  });

  await page.route(`**/api/preview/*/proxy/**`, async (route) => {
    return route.fulfill({
      contentType: 'text/html',
      body: '<html><body><h1>Preview</h1></body></html>',
    });
  });

  // --- Publish & slug check ---
  await page.route('**/api/export/*/slug/check**', async (route) => {
    const url = new URL(route.request().url());
    const slug = url.searchParams.get('slug') ?? '';
    const projectId = url.pathname.split('/api/export/')[1]?.split('/slug/check')[0] ?? '';
    const taken = projects.some(
      (p) => 'published_slug' in p && p.published_slug === slug && p.id !== projectId
    );
    return route.fulfill({ json: { available: !taken } });
  });

  await page.route('**/api/export/*/publish', async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 405, body: 'Method Not Allowed' });
    }
    const url = route.request().url();
    const projectId = url.split('/api/export/')[1]?.split('/publish')[0] ?? '';
    let body: { slug?: string | null } = {};
    try { body = route.request().postDataJSON(); } catch { /* ignore */ }
    const slug = body.slug ?? undefined;

    const proj = projects.find((p) => p.id === projectId);
    if (proj && 'published_slug' in proj) {
      (proj as typeof MOCK_PROJECT).published_url = `https://s3.local/published/${projectId}.html`;
      (proj as typeof MOCK_PROJECT).published_slug = slug;
    }

    const publicPath = slug ? `/api/share/${slug}` : `/api/export/${projectId}/published`;
    return route.fulfill({ json: { url: publicPath, slug: slug ?? '' } });
  });

  // --- Data source search ---
  await page.route('**/api/data-source/search/**', async (route) => {
    return route.fulfill({ json: [] });
  });
}
