import type { Project } from '../types';

export function getVisibleProjects(
  projects: Project[],
  projectSearch: { results: Project[] } | null,
  currentProject: Project | null,
): Project[] {
  if (projectSearch) return projectSearch.results;
  if (!currentProject || projects.some((p) => p.id === currentProject.id)) return projects;
  // Pin the open project when not in search results
  return [currentProject, ...projects];
}
