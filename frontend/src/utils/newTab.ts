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
 * Handlers that open `href` in a new tab on middle click, the way a link would.
 * Spread onto any clickable element that navigates without being an <a>.
 */
export function middleClickOpens(href: string) {
  return {
    // Stops the browser's autoscroll from starting on middle mouse down
    onMouseDown: (e: MouseEvent) => {
      if (e.button === 1) e.preventDefault();
    },
    onAuxClick: (e: MouseEvent) => {
      if (e.button !== 1) return;
      e.preventDefault();
      e.stopPropagation();
      window.open(href, '_blank', 'noopener');
    },
  };
}
