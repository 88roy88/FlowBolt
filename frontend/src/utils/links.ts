import type { MouseEvent } from 'react';

export function projectHref(projectId: string): string {
  return `#/project/${projectId}`;
}

export function appHref(): string {
  return window.location.pathname + window.location.search;
}

export function isPlainClick(e: MouseEvent): boolean {
  return e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
}
