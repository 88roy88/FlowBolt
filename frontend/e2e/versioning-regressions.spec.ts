import { expect, type APIRequestContext, type BrowserContext, type Page } from '@playwright/test';
import { UnsecuredJWT } from 'jose';
import { AUTH_STORAGE_KEY, E2E_AUTH_TOKEN, test } from './fixtures';

declare const process: { env: Record<string, string | undefined> };

type Project = { id: string };
type VersionEvent = { type?: string; commit_sha?: string };

const authHeaders = (token = E2E_AUTH_TOKEN) => ({ Authorization: `Bearer ${token}` });

async function versionEvents(request: APIRequestContext, projectId: string): Promise<VersionEvent[]> {
  const response = await request.get(`/api/chat/${projectId}/events`, {
    headers: authHeaders(),
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as VersionEvent[];
}

async function fileContent(request: APIRequestContext, projectId: string): Promise<string> {
  const response = await request.get(`/api/files/${projectId}/file/content?path=${encodeURIComponent('/version.txt')}`, {
    headers: authHeaders(),
  });
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { content: string }).content;
}

async function sendVersionAction(page: Page, projectId: string, action: Record<string, unknown>, resultType: string) {
  await page.evaluate(
    ({ projectId: id, action: message, resultType: expected }) => new Promise<void>((resolve, reject) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/chat/${id}`);
      const timeout = window.setTimeout(() => {
        socket.close();
        reject(new Error(`Timed out waiting for ${expected}`));
      }, 15_000);

      socket.addEventListener('open', () => socket.send(JSON.stringify(message)));
      socket.addEventListener('message', (event) => {
        const payload = JSON.parse(String(event.data)) as { type?: string; message?: string };
        if (payload.type === expected) {
          window.clearTimeout(timeout);
          socket.close();
          resolve();
        } else if (payload.type === 'version_error' || payload.type === 'error') {
          window.clearTimeout(timeout);
          socket.close();
          reject(new Error(payload.message ?? payload.type));
        }
      });
      socket.addEventListener('error', () => {
        window.clearTimeout(timeout);
        reject(new Error('Version WebSocket failed'));
      });
    }),
    { projectId, action, resultType },
  );
}

async function expectViewerPreviewRejected(page: Page, projectId: string, commitSha: string) {
  const outcome = await page.evaluate(
    ({ projectId: id, commitSha: sha }) => new Promise<{ opened: boolean; closed: boolean; code: number | null }>((resolve) => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/chat/${id}`);
      let opened = false;
      const timeout = window.setTimeout(() => {
        socket.close();
        resolve({ opened, closed: false, code: null });
      }, 10_000);

      socket.addEventListener('open', () => {
        opened = true;
        socket.send(JSON.stringify({ type: 'preview_version', commit_sha: sha }));
      });
      socket.addEventListener('message', (event) => {
        const payload = JSON.parse(String(event.data)) as { type?: string };
        if (payload.type === 'version_preview_active') {
          window.clearTimeout(timeout);
          socket.close();
          resolve({ opened, closed: true, code: 1000 });
        }
      });
      socket.addEventListener('close', (event) => {
        window.clearTimeout(timeout);
        resolve({ opened, closed: true, code: event.code });
      });
      socket.addEventListener('error', () => {
        // Handshake rejection surfaces as error + close; wait for close for the code.
      });
    }),
    { projectId, commitSha },
  );

  expect(outcome.closed).toBe(true);
  expect(outcome.opened).toBe(false);
}

async function createSeededProject(request: APIRequestContext, page: Page): Promise<Project> {
  const response = await request.post('/api/projects', {
    headers: authHeaders(),
    data: { name: `Version regression ${Date.now()}` },
  });
  expect(response.ok()).toBe(true);
  const project = (await response.json()) as Project;

  await expect.poll(async () => {
    const tree = await request.get(`/api/files/${project.id}/tree`, { headers: authHeaders() });
    return tree.status();
  }, { timeout: 30_000 }).toBe(200);
  await expect.poll(async () => (await versionEvents(request, project.id))
    .filter((event) => event.type === 'version_committed').length, { timeout: 30_000 }).toBe(1);

  await page.goto(`/#/project/${project.id}`);
  await expect(page.getByPlaceholder(/what do you want to build/i)).toBeVisible({ timeout: 30_000 });

  for (const content of ['one', 'two']) {
    const write = await request.put(`/api/files/${project.id}/file/content`, {
      headers: authHeaders(),
      data: { path: '/version.txt', content },
    });
    expect(write.ok()).toBe(true);
    await sendVersionAction(page, project.id, { type: 'save_version' }, 'version_committed');
  }

  await expect(page.getByText('Current version (v2)', { exact: true })).toBeVisible({ timeout: 15_000 });
  return project;
}

async function openProject(page: Page, projectId: string) {
  await page.goto(`/#/project/${projectId}`);
  await expect(page.getByText('Current version (v2)', { exact: true })).toBeVisible({ timeout: 30_000 });
}

async function previewV1(page: Page) {
  await page.getByRole('button', { name: 'Preview', exact: true }).click();
  await expect(page.getByText('Previewing v1', { exact: true })).toBeVisible({ timeout: 15_000 });
}

async function installAuth(context: BrowserContext, token: string, userId: string) {
  await context.addCookies([{
    name: 'flow44_token',
    value: token,
    url: process.env.BACKEND_URL!,
  }]);
  await context.addInitScript(
    ({ storageKey, authToken, id }) => {
      localStorage.setItem(storageKey, JSON.stringify({
        auth_token: authToken,
        userId: id,
        exp: Math.floor(Date.now() / 1000) + 86400,
      }));
    },
    { storageKey: AUTH_STORAGE_KEY, authToken: token, id: userId },
  );
}

test.describe('real-backend versioning regressions', () => {
  test.skip(!process.env.BACKEND_URL, 'Requires the real-backend Playwright mode');

  test('a second tab joins preview and the banner survives selecting Code', async ({ page, context, request }) => {
    const project = await createSeededProject(request, page);
    try {
      await previewV1(page);
      expect(await fileContent(request, project.id)).toBe('one');

      const tabB = await context.newPage();
      await openProject(tabB, project.id);
      await expect(tabB.getByText('Previewing v1', { exact: true })).toBeVisible();
      expect(await fileContent(request, project.id)).toBe('one');

      await tabB.getByRole('button', { name: 'Code', exact: true }).click();
      await expect(tabB.getByText('Previewing v1', { exact: true })).toBeVisible();
    } finally {
      await request.delete(`/api/projects/${project.id}`, { headers: authHeaders() });
    }
  });

  test('a viewer sees version labels without controls and cannot move the workspace', async ({ page, browser, request }) => {
    const project = await createSeededProject(request, page);
    const viewerId = `version-viewer-${Date.now()}`;
    const viewerToken = new UnsecuredJWT({
      'https://issuer.example/v1/claims/UniqueID': viewerId,
    }).setExpirationTime('24h').encode();
    const viewerContext = await browser.newContext({ baseURL: process.env.BACKEND_URL });

    try {
      const addViewer = await request.post(`/api/projects/${project.id}/members`, {
        headers: authHeaders(),
        data: { user_id: viewerId, role: 'viewer' },
      });
      expect(addViewer.ok()).toBe(true);
      await installAuth(viewerContext, viewerToken, viewerId);

      const committed = (await versionEvents(request, project.id))
        .filter((event) => event.type === 'version_committed')
        .map((event) => event.commit_sha)
        .filter((sha): sha is string => Boolean(sha));
      const beforeVersions = committed;
      const v1Sha = committed[1];
      expect(v1Sha).toBeTruthy();

      const viewer = await viewerContext.newPage();
      await openProject(viewer, project.id);

      await expect(viewer.getByText('v1', { exact: true })).toBeVisible();
      await expect(viewer.getByText('Current version (v2)', { exact: true })).toBeVisible();
      await expect(viewer.getByRole('button', { name: /Preview|Restore here/ })).toHaveCount(0);

      await expectViewerPreviewRejected(viewer, project.id, v1Sha!);

      expect(await fileContent(request, project.id)).toBe('two');
      expect((await versionEvents(request, project.id))
        .filter((event) => event.type === 'version_committed')
        .map((event) => event.commit_sha)).toEqual(beforeVersions);
      await expect(page.getByText('Previewing v1', { exact: true })).toHaveCount(0);
      await expect(page.getByText('Current version (v2)', { exact: true })).toBeVisible();
    } finally {
      await viewerContext.close();
      await request.delete(`/api/projects/${project.id}`, { headers: authHeaders() });
    }
  });

  test('restore truncates another tab live and the state survives reload', async ({ page, context, request }) => {
    const project = await createSeededProject(request, page);
    try {
      const tabB = await context.newPage();
      await openProject(tabB, project.id);
      await expect(tabB.getByText(/You edited/)).toHaveCount(2);

      await previewV1(page);
      await expect(tabB.getByText('Previewing v1', { exact: true })).toBeVisible();
      await page.getByRole('button', { name: 'Restore here', exact: true }).click();
      await page.getByRole('button', { name: 'Yes, restore', exact: true }).click();

      await expect(tabB.getByText('Current version (v1)', { exact: true })).toBeVisible({ timeout: 15_000 });
      await expect(tabB.getByText(/You edited/)).toHaveCount(1);
      await expect(tabB.getByText(/v2/, { exact: true })).toHaveCount(0);

      const liveState = {
        editRows: await tabB.getByText(/You edited/).count(),
        currentLabel: await tabB.getByText(/Current version \(v\d+\)/).allTextContents(),
      };
      await tabB.reload();
      await expect(tabB.getByText('Current version (v1)', { exact: true })).toBeVisible({ timeout: 30_000 });
      expect({
        editRows: await tabB.getByText(/You edited/).count(),
        currentLabel: await tabB.getByText(/Current version \(v\d+\)/).allTextContents(),
      }).toEqual(liveState);
    } finally {
      await request.delete(`/api/projects/${project.id}`, { headers: authHeaders() });
    }
  });
});
