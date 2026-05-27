// PLATFORM SYSTEM FILE.
// Required for preview/export/publish base-path support.
// Do not remove or rewrite during normal app generation.

/** Basename for react-router — derived from Vite `base` via import.meta.env.BASE_URL. */
export function getRouterBasename(): string {
  const base = import.meta.env.BASE_URL || '/';
  const normalized = base.replace(/\/+$/, '');
  return normalized || '/';
}
