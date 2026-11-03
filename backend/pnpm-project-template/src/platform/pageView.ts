import { fetchWithAuth } from '../api/client';

type PageViewSource = 'preview' | 'production';

// Previews are served at /api/preview/<project id>/proxy/ (or /preview/<project id>/),
// published apps at /shared/<handle>/.
const PREVIEW_PATH = /^(?:\/api)?\/preview\/([^/]+)\//;
const PUBLISHED_PATH = /^\/shared\/([^/]+)/;

let sent = false;

function resolvePageView(pathname: string): { source: PageViewSource; ref: string } | null {
  const preview = PREVIEW_PATH.exec(pathname);
  // Only previews opened in their own tab count: the builder's preview iframe reloads on every edit.
  if (preview) return window.self === window.top ? { source: 'preview', ref: decodeURIComponent(preview[1]) } : null;
  const published = PUBLISHED_PATH.exec(pathname);
  if (published) return { source: 'production', ref: decodeURIComponent(published[1]) };
  return null;
}

/** Records one view per page load. Never throws: tracking must not affect the app. */
export function trackPageView(): void {
  if (sent) return;
  sent = true;
  try {
    const view = resolvePageView(window.location.pathname);
    if (!view) return;
    fetchWithAuth(
      '/api/page-views',
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(view) },
      false,
    ).catch(() => {});
  } catch {
    // ignore
  }
}
