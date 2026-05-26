/** Basename for react-router BrowserRouter — read from Flow44's <base href>. */
export function getRouterBasename(): string {
  if (typeof document === 'undefined') return '/';

  const href = document.querySelector('base')?.getAttribute('href');
  if (!href) return '/';

  try {
    const pathname = new URL(href, window.location.origin).pathname;
    const trimmed = pathname.replace(/\/$/, '');
    return trimmed || '/';
  } catch {
    return '/';
  }
}
