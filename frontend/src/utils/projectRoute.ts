import type { Project } from '../types';
import { clearProjectCaches } from './projectCache';

export function getProjectIdFromHash(hash = window.location.hash): string | null {
  const match = hash.match(/^#\/project\/([^/?#]+)$/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function isKnownProjectId(projectId: string, projects: Project[]): boolean {
  return projects.some((p) => p.id === projectId);
}

/** Navigate to app home (pathname only). Drops an invalid #/project/... hash. */
export function goToAppHome(): void {
  clearProjectCaches();
  if (!getProjectIdFromHash()) return;
  const home = `${window.location.pathname}${window.location.search}`;
  window.location.replace(home);
}

export type RouteSyncInput = {
  hashProjectId: string | null;
  projects: Project[];
  loading: boolean;
  currentProjectId: string | null;
};

export type RouteSyncAction =
  | { type: 'redirect_home' }
  | { type: 'select_project'; project: Project }
  | { type: 'show_empty_state' }
  | { type: 'none' };

/** Pure routing decision used by App.tsx. */
export function resolveRouteAction(input: RouteSyncInput): RouteSyncAction {
  const { hashProjectId, projects, loading, currentProjectId } = input;

  if (hashProjectId && projects.length > 0 && !isKnownProjectId(hashProjectId, projects)) {
    return { type: 'redirect_home' };
  }

  if (loading) return { type: 'none' };

  if (projects.length === 0) {
    if (hashProjectId) return { type: 'redirect_home' };
    return { type: 'show_empty_state' };
  }

  if (hashProjectId) {
    const match = projects.find((p) => p.id === hashProjectId);
    if (match && match.id !== currentProjectId) {
      return { type: 'select_project', project: match };
    }
    return { type: 'none' };
  }

  if (currentProjectId) return { type: 'none' };
  return { type: 'select_project', project: projects[0] };
}
