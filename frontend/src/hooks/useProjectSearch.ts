import { useEffect, useState } from 'react';
import { useSessionStore } from '../stores/session';
import { useDebouncedValue } from './useDebounce';

const SEARCH_DEBOUNCE_MS = 250;

/** Project list with server-side search and paging, shared by the sidebar and the topbar switcher. */
export function useProjectSearch() {
  const projects = useSessionStore((s) => s.projects);
  const projectsCursor = useSessionStore((s) => s.projectsCursor);
  const projectSearch = useSessionStore((s) => s.projectSearch);
  const isLoadingMore = useSessionStore((s) => s.isLoadingMoreProjects);
  const searchProjects = useSessionStore((s) => s.searchProjects);
  const loadMoreProjects = useSessionStore((s) => s.loadMoreProjects);

  const [query, setQueryState] = useState('');
  const [failedSearch, setFailedSearch] = useState<string | null>(null);

  const canSearch = projects.length > 10 || projectsCursor !== null;
  const trimmed = canSearch ? query.trim() : '';
  const debounced = useDebouncedValue(trimmed, SEARCH_DEBOUNCE_MS);
  const searchTerm = trimmed ? debounced : '';

  useEffect(() => {
    searchProjects(searchTerm).catch((err) => {
      console.error('Project search failed:', err);
      setFailedSearch(searchTerm);
    });
  }, [searchTerm, searchProjects]);

  const isSearching = trimmed !== '' && trimmed !== projectSearch?.query && trimmed !== failedSearch;
  const visibleProjects = projectSearch?.results ?? projects;
  const hasMore = !isSearching && (projectSearch ? projectSearch.cursor : projectsCursor) !== null;

  return {
    query,
    setQuery: (value: string) => {
      setQueryState(value);
      setFailedSearch(null);
    },
    canSearch,
    isSearching,
    noMatches: projectSearch !== null && !isSearching && visibleProjects.length === 0,
    visibleProjects,
    hasMore,
    isLoadingMore,
    loadMore: () => loadMoreProjects().catch((err) => console.error('Failed to load more projects:', err)),
  };
}
