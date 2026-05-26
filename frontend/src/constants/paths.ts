/** Must stay in sync with backend flow44.paths constants. */

export function previewBasePath(projectId: string): string {
  return `/api/preview/${projectId}/proxy/`;
}

export function exportPublishedPath(projectId: string): string {
  return `/api/export/${projectId}/published/`;
}
