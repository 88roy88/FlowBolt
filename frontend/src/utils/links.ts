import type { MouseEvent } from 'react';

/** Hash link to a project, the same URL the app navigates to when one is opened. */
export function projectHref(projectId: string): string {
  return `#/project/${projectId}`;
}

/** The app's URL without a project hash (opening it fresh behaves like the initial page load). */
export function appHref(): string {
  return window.location.pathname + window.location.search;
}

/**
 * Whether a click on a link should navigate in place. Modified clicks (new tab, new window, download)
 * are left to the browser; middle clicks never reach onClick.
 */
export function isPlainClick(e: MouseEvent): boolean {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
}
