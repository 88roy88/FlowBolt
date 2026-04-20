/**
 * Playwright route handlers that mock the backend REST API.
 *
 * The mock maintains a simple in-memory project list so tests can
 * start with an empty state, create projects, and delete them.
 */
import { type Page } from '@playwright/test';
import {
  MOCK_PROJECT,
  MOCK_FILE_TREE,
  MOCK_MODELS,
  CHAT_SEED_EVENTS,
  MOCK_FILE_CONTENTS,
} from './data';
import type { FileEntry } from '../../src/types';

function normalizeContentPathParam(encodedPath: string): string {
  const raw = decodeURIComponent(encodedPath);
  return raw.replace(/\\/g, '/').replace(/^\/+/, '');
}

function normalizeTreePath(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/\/$/, '');
  return normalized.startsWith('/') ? normalized : `/${normalized}`;
}

function toContentKey(path: string): string {
  return normalizeTreePath(path).replace(/^\/+/, '');
}

function splitSegments(path: string): string[] {
  return normalizeTreePath(path).split('/').filter(Boolean);
}

function cloneTree(entries: FileEntry[]): FileEntry[] {
  return entries.map((entry) => ({
    name: entry.name,
    path: entry.path,
    is_directory: entry.is_directory,
    children: entry.children ? cloneTree(entry.children) : undefined,
  }));
}

function sortTree(entries: FileEntry[]): void {
  entries.sort((a, b) => {
    if (a.is_directory !== b.is_directory) return a.is_directory ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  for (const entry of entries) {
    if (entry.children) sortTree(entry.children);
  }
}

function findEntryLocation(entries: FileEntry[], fullPath: string): { siblings: FileEntry[]; index: number; entry: FileEntry } | null {
  const segments = splitSegments(fullPath);
  if (segments.length === 0) return null;
  let siblings = entries;
  for (let i = 0; i < segments.length; i++) {
    const name = segments[i];
    const index = siblings.findIndex((entry) => entry.name === name);
    if (index < 0) return null;
    const entry = siblings[index];
    if (i === segments.length - 1) return { siblings, index, entry };
    if (!entry.is_directory) return null;
    siblings = entry.children ?? [];
  }
  return null;
}

function ensureDirectory(entries: FileEntry[], dirPath: string): FileEntry[] {
  const segments = splitSegments(dirPath);
  let siblings = entries;
  let currentPath = '';
  for (const segment of segments) {
    currentPath = `${currentPath}/${segment}`;
    let dir = siblings.find((entry) => entry.name === segment && entry.is_directory);
    if (!dir) {
      dir = {
        name: segment,
        path: currentPath,
        is_directory: true,
        children: [],
      };
      siblings.push(dir);
      sortTree(siblings);
    }
    if (!dir.children) dir.children = [];
    siblings = dir.children;
  }
  return siblings;
}

function getParentPath(fullPath: string): string {
  const normalized = normalizeTreePath(fullPath);
  const idx = normalized.lastIndexOf('/');
  if (idx <= 0) return '/';
  return normalized.slice(0, idx);
}

function applyPathPrefix(entry: FileEntry, oldPrefix: string, newPrefix: string): FileEntry {
  const updatedPath =
    entry.path === oldPrefix || entry.path.startsWith(`${oldPrefix}/`)
      ? `${newPrefix}${entry.path.slice(oldPrefix.length)}`
      : entry.path;
  return {
    ...entry,
    name: updatedPath.split('/').filter(Boolean).pop() ?? entry.name,
    path: updatedPath,
    children: entry.children?.map((child) => applyPathPrefix(child, oldPrefix, newPrefix)),
  };
}

export interface MockAPIOptions {
  /** Initial project list. Defaults to [MOCK_PROJECT]. Pass [] for empty state. */
  projects?: typeof MOCK_PROJECT[];
  /** Return a minimal chat event replay so the main layout shows Preview/Code (not empty project). */
  seedChatHistory?: boolean;
  /** Explicit chat replay events (overrides seedChatHistory when provided). */
  seedEvents?: Record<string, unknown>[];
  /** Simulate backend search tool failure for editor search. */
  searchUnavailable?: boolean;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export async function setupMockAPI(page: Page, options: MockAPIOptions = {}) {
  const projects = options.projects ?? [MOCK_PROJECT];
  const fileTree = cloneTree(MOCK_FILE_TREE);
  const fileContents = { ...MOCK_FILE_CONTENTS };

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
    return route.fulfill({ json: fileTree });
  });

  await page.route(`**/api/files/*/file/content**`, async (route) => {
    if (route.request().method() === 'PUT') {
      try {
        const body = route.request().postDataJSON() as { path?: string; content?: string };
        const key = toContentKey(body.path ?? '');
        fileContents[key] = body.content ?? '';
      } catch {
        /* ignore malformed payloads in mocks */
      }
      return route.fulfill({ status: 200, json: {} });
    }
    const url = new URL(route.request().url());
    const pathParam = url.searchParams.get('path') ?? '';
    const key = normalizeContentPathParam(pathParam);
    const content = fileContents[key] ?? `// e2e placeholder: ${key}\n`;
    return route.fulfill({ json: { path: pathParam || key, content } });
  });

  await page.route(`**/api/files/*/file/upload**`, async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());

    if (method !== 'POST') {
      return route.fulfill({ status: 405, body: 'Method Not Allowed' });
    }

    const fullPath = normalizeTreePath(url.searchParams.get('path') ?? '');
    if (findEntryLocation(fileTree, fullPath)) {
      return route.fulfill({ status: 409, json: { detail: 'Already exists' } });
    }
    const parentPath = getParentPath(fullPath);
    const siblings = ensureDirectory(fileTree, parentPath);
    const name = fullPath.split('/').filter(Boolean).pop() ?? fullPath;
    siblings.push({ name, path: fullPath, is_directory: false });
    sortTree(fileTree);

    const uploadedBytes = req.postDataBuffer()?.byteLength ?? 0;
    fileContents[toContentKey(fullPath)] = `// uploaded asset placeholder (${uploadedBytes} bytes)\n`;
    return route.fulfill({ status: 200, json: { status: 'ok', path: fullPath } });
  });

  await page.route(/\/api\/files\/[^/]+\/file(?:\?.*)?$/, async (route) => {
    const req = route.request();
    const method = req.method();
    const url = new URL(req.url());

    if (method === 'POST') {
      let body: { path?: string; content?: string } = {};
      try {
        body = req.postDataJSON() as { path?: string; content?: string };
      } catch {
        return route.fulfill({ status: 400, json: { detail: 'Invalid payload' } });
      }
      const fullPath = normalizeTreePath(body.path ?? '');
      if (findEntryLocation(fileTree, fullPath)) {
        return route.fulfill({ status: 409, json: { detail: 'Already exists' } });
      }

      const parentPath = getParentPath(fullPath);
      const siblings = ensureDirectory(fileTree, parentPath);
      const name = fullPath.split('/').filter(Boolean).pop() ?? fullPath;
      siblings.push({ name, path: fullPath, is_directory: false });
      sortTree(fileTree);
      fileContents[toContentKey(fullPath)] = body.content ?? '';
      return route.fulfill({ status: 200, json: { status: 'ok', path: fullPath } });
    }

    if (method === 'PATCH') {
      let body: { old_path?: string; new_path?: string } = {};
      try {
        body = req.postDataJSON() as { old_path?: string; new_path?: string };
      } catch {
        return route.fulfill({ status: 400, json: { detail: 'Invalid payload' } });
      }
      const oldPath = normalizeTreePath(body.old_path ?? '');
      const newPath = normalizeTreePath(body.new_path ?? '');
      const source = findEntryLocation(fileTree, oldPath);
      if (!source) return route.fulfill({ status: 404, json: { detail: 'Not found' } });
      if (findEntryLocation(fileTree, newPath)) {
        return route.fulfill({ status: 409, json: { detail: 'Destination already exists' } });
      }

      const [removed] = source.siblings.splice(source.index, 1);
      const renamed = applyPathPrefix(removed, oldPath, newPath);
      renamed.name = newPath.split('/').filter(Boolean).pop() ?? renamed.name;
      const destinationParent = ensureDirectory(fileTree, getParentPath(newPath));
      destinationParent.push(renamed);
      sortTree(fileTree);

      const oldKey = toContentKey(oldPath);
      const newKey = toContentKey(newPath);
      for (const key of Object.keys(fileContents)) {
        if (key === oldKey || key.startsWith(`${oldKey}/`)) {
          const suffix = key.slice(oldKey.length);
          fileContents[`${newKey}${suffix}`] = fileContents[key];
          delete fileContents[key];
        }
      }

      return route.fulfill({ status: 200, json: { status: 'ok', old_path: oldPath, new_path: newPath } });
    }

    if (method === 'DELETE') {
      const fullPath = normalizeTreePath(url.searchParams.get('path') ?? '');
      const target = findEntryLocation(fileTree, fullPath);
      if (!target) return route.fulfill({ status: 404, json: { detail: 'Not found' } });

      target.siblings.splice(target.index, 1);
      const prefix = toContentKey(fullPath);
      for (const key of Object.keys(fileContents)) {
        if (key === prefix || key.startsWith(`${prefix}/`)) {
          delete fileContents[key];
        }
      }
      return route.fulfill({ status: 200, json: { status: 'ok', path: fullPath } });
    }

    return route.fulfill({ status: 405, body: 'Method Not Allowed' });
  });

  await page.route(`**/api/files/*/search`, async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 405, body: 'Method Not Allowed' });
    }
    let body: { query?: string; case_sensitive?: boolean; word_match?: boolean; use_regex?: boolean } = {};
    try {
      body = route.request().postDataJSON() as {
        query?: string;
        case_sensitive?: boolean;
        word_match?: boolean;
        use_regex?: boolean;
      };
    } catch {
      /* ignore */
    }

    if (options.searchUnavailable) {
      return route.fulfill({ status: 503, json: { detail: 'ripgrep (rg) is required for search but was not found in PATH' } });
    }

    const q = (body.query ?? '').trim();
    const patternSource = body.use_regex ? q : escapeRegExp(q);
    const wrappedPattern = body.word_match ? `\\b${patternSource}\\b` : patternSource;
    const flags = body.case_sensitive ? 'g' : 'gi';
    let matcher: RegExp | null = null;
    try {
      matcher = q ? new RegExp(wrappedPattern, flags) : null;
    } catch {
      return route.fulfill({ status: 400, json: { detail: 'Invalid search pattern' } });
    }

    const results = Object.entries(fileContents).flatMap(([key, content]) => {
      if (!matcher) return [];
      const hits = content
        .split(/\r?\n/)
        .flatMap((line, index) => {
          const lineMatcher = new RegExp(matcher.source, matcher.flags);
          const match = lineMatcher.exec(line);
          if (!match) return [];
          return [{ line: index + 1, column: match.index + 1, preview: line }];
        });
      if (hits.length === 0) return [];
      const path = `/${key}`;
      return [{ path, uri: `file://${path}`, hits }];
    });
    return route.fulfill({ json: { query: q, results } });
  });

  // --- Chat ---
  await page.route(`**/api/chat/*/history`, async (route) => {
    return route.fulfill({ json: [] });
  });

  await page.route(`**/api/chat/*/events`, async (route) => {
    const payload = options.seedEvents ?? (options.seedChatHistory ? CHAT_SEED_EVENTS : []);
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

  // --- Data source search ---
  await page.route('**/api/data-source/search/**', async (route) => {
    return route.fulfill({ json: [] });
  });
}
