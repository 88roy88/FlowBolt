/** Keys written by the app that relate to projects (not auth/theme). */
const PROJECT_CACHE_PREFIXES = ['project-has-messages:', 'editor-tabs:'] as const;
const HAS_PROJECTS_KEY = 'has-projects';

export function hasProjectsCache(): boolean {
  try {
    return localStorage.getItem(HAS_PROJECTS_KEY) === 'true';
  } catch {
    return false;
  }
}

export function setHasProjectsCache(hasProjects: boolean): void {
  try {
    localStorage.setItem(HAS_PROJECTS_KEY, hasProjects ? 'true' : 'false');
  } catch {
    /* ignore quota / private mode */
  }
}

/** Remove all project-related entries from localStorage. */
export function clearProjectCaches(): void {
  try {
    localStorage.removeItem(HAS_PROJECTS_KEY);
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key) continue;
      if (PROJECT_CACHE_PREFIXES.some((prefix) => key.startsWith(prefix))) {
        keysToRemove.push(key);
      }
    }
    for (const key of keysToRemove) {
      localStorage.removeItem(key);
    }
  } catch {
    /* ignore quota / private mode */
  }
}
