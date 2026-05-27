export function normalizePath(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/\/$/, '');
  return normalized.startsWith('/') ? normalized : `/${normalized}`;
}

export function parentDirectory(path: string): string {
  const normalized = normalizePath(path);
  const idx = normalized.lastIndexOf('/');
  if (idx <= 0) return '/';
  return normalized.slice(0, idx);
}

export function joinPath(basePath: string, childName: string): string {
  const base = normalizePath(basePath);
  const trimmed = childName.trim().replace(/^\/+/, '').replace(/\/+$/, '');
  if (!trimmed) return base;
  return base === '/' ? `/${trimmed}` : `${base}/${trimmed}`;
}

export const ROOT_DROP_PATH = '/';
