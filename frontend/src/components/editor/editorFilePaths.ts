import type { FileEntry } from '../../types';

export function toMonacoUri(path: string) {
  const normalized = path.replace(/\\/g, '/').replace(/^\/+/, '');
  return `file:///${normalized}`;
}

export function normalizeProjectPath(path: string) {
  return path.replace(/\\/g, '/').replace(/^\/+/, '');
}

function normalizeSegments(segments: string[]) {
  const out: string[] = [];
  for (const seg of segments) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      out.pop();
      continue;
    }
    out.push(seg);
  }
  return out;
}

export function resolveRelativeImportPath(fromPath: string, importPath: string, fileSet: Set<string>): string | null {
  if (!importPath.startsWith('.')) return null;

  const from = normalizeProjectPath(fromPath);
  const baseDir = from.includes('/') ? from.slice(0, from.lastIndexOf('/')) : '';
  const resolvedSegments = normalizeSegments([...baseDir.split('/'), ...importPath.split('/')]);
  const baseResolved = resolvedSegments.join('/');

  const candidates = [
    baseResolved,
    `${baseResolved}.ts`,
    `${baseResolved}.tsx`,
    `${baseResolved}.js`,
    `${baseResolved}.jsx`,
    `${baseResolved}.mjs`,
    `${baseResolved}.cjs`,
    `${baseResolved}.json`,
    `${baseResolved}.css`,
    `${baseResolved}.scss`,
    `${baseResolved}.sass`,
    `${baseResolved}.less`,
    `${baseResolved}.svg`,
    `${baseResolved}.png`,
    `${baseResolved}.jpg`,
    `${baseResolved}.jpeg`,
    `${baseResolved}.gif`,
    `${baseResolved}.webp`,
    `${baseResolved}/index.ts`,
    `${baseResolved}/index.tsx`,
    `${baseResolved}/index.js`,
    `${baseResolved}/index.jsx`,
  ];

  for (const candidate of candidates) {
    const normalized = normalizeProjectPath(candidate);
    if (fileSet.has(normalized)) return normalized;
  }

  return null;
}

export function findImportedModuleForSymbol(source: string, symbol: string): string | null {
  const defaultImportRegex = /import\s+([A-Za-z_$][\w$]*)\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of source.matchAll(defaultImportRegex)) {
    if (match[1] === symbol) return match[2] ?? null;
  }

  const namespaceImportRegex = /import\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of source.matchAll(namespaceImportRegex)) {
    if (match[1] === symbol) return match[2] ?? null;
  }

  const namedImportRegex = /import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of source.matchAll(namedImportRegex)) {
    const specifiers = (match[1] ?? '').split(',').map((part) => part.trim()).filter(Boolean);
    for (const specifier of specifiers) {
      const [imported, aliased] = specifier.split(/\s+as\s+/).map((s) => s.trim());
      const localName = aliased || imported;
      if (localName === symbol) return match[2] ?? null;
    }
  }

  return null;
}

export function getBaseName(path: string) {
  const normalized = normalizeProjectPath(path);
  const idx = normalized.lastIndexOf('/');
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
}

export function scoreQuickOpenPath(path: string, query: string): number {
  const normalizedPath = normalizeProjectPath(path).toLowerCase();
  const baseName = getBaseName(path).toLowerCase();
  const q = query.trim().toLowerCase();
  if (!q) return 1;

  const tokens = q.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return 1;
  if (tokens.some((token) => !normalizedPath.includes(token))) return -1;

  let score = 0;
  for (const token of tokens) {
    if (baseName === token) score += 150;
    else if (baseName.startsWith(token)) score += 90;
    else if (baseName.includes(token)) score += 45;
    else if (normalizedPath.includes(`/${token}`)) score += 25;
    else score += 10;
  }

  // Prefer shorter paths when relevance is equal.
  score -= normalizedPath.length * 0.01;
  return score;
}

export function flattenFileTreeEntries(entries: FileEntry[]): string[] {
  const out: string[] = [];
  const stack = [...entries];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    if (current.is_directory) {
      if (current.children?.length) stack.push(...current.children);
    } else {
      out.push(current.path);
    }
  }
  return out;
}
