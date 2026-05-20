import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Monaco, OnMount } from '@monaco-editor/react';
import { searchFiles } from '../../services/api';
import { useFilesStore } from '../../stores/files';
import { normalizeProjectPath } from './editorFilePaths';
import { useDebounce } from '../../utils/useDebounce';

type StandaloneEditor = Parameters<OnMount>[0];

export function useEditorPanelSearch(
  projectId: string | null,
  openFile: (path: string, line?: number, column?: number) => Promise<void>,
  editorRef: MutableRefObject<StandaloneEditor | null>,
  monacoRef: MutableRefObject<Monaco | null>
) {
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsedSearchFiles, setCollapsedSearchFiles] = useState<Set<string>>(new Set());
  const [searchCaseSensitive, setSearchCaseSensitive] = useState(false);
  const [searchWordMatch, setSearchWordMatch] = useState(false);
  const [searchUseRegex, setSearchUseRegex] = useState(false);
  const searchHighlightDecorationIdsRef = useRef<string[]>([]);
  const searchHighlightClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const revealRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedQuery = useDebounce(searchQuery, 500);

  const { data: searchResults = [], isFetching: searchBusy, error, refetch } = useQuery({
    queryKey: ['search', projectId, debouncedQuery, searchCaseSensitive, searchWordMatch, searchUseRegex],
    queryFn: () => searchFiles(projectId!, debouncedQuery, {
      caseSensitive: searchCaseSensitive,
      wordMatch: searchWordMatch,
      useRegex: searchUseRegex,
      maxResults: 2000,
      maxHitsPerFile: 200,
    }),
    enabled: !!projectId && !!debouncedQuery.trim(),
    staleTime: 30_000,
    gcTime: 60_000,
    retry: false,
  });

  const searchError = error instanceof Error ? error.message : null;

  useEffect(() => {
    setCollapsedSearchFiles(new Set());
  }, [debouncedQuery]);

  const toggleSearchFileCollapsed = useCallback((path: string) => {
    setCollapsedSearchFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const jumpToSearchHit = useCallback(
    (path: string, line: number, column: number) => {
      const highlightLength = Math.max(1, debouncedQuery.trim().length);
      const normalizedTargetPath = normalizeProjectPath(path);

      if (revealRetryTimerRef.current) clearTimeout(revealRetryTimerRef.current);

      const tryReveal = (attempt: number) => {
        const editor = editorRef.current;
        const m = monacoRef.current;
        const activePath = useFilesStore.getState().activeFilePath;
        const normalizedActivePath = activePath ? normalizeProjectPath(activePath) : '';
        const model = editor?.getModel();

        if (!editor || !m || !model || normalizedActivePath !== normalizedTargetPath) {
          if (attempt < 12) {
            revealRetryTimerRef.current = setTimeout(() => tryReveal(attempt + 1), 40);
          }
          return;
        }

        const maxLine = model.getLineCount();
        const safeLine = Math.max(1, Math.min(line, maxLine));
        const lineMaxColumn = model.getLineMaxColumn(safeLine);
        const safeColumn = Math.max(1, Math.min(column, lineMaxColumn));
        const endColumn = Math.max(safeColumn + 1, Math.min(lineMaxColumn, safeColumn + highlightLength));

        const pos = { lineNumber: safeLine, column: safeColumn };
        editor.setPosition(pos);
        editor.revealPositionInCenter(pos);
        editor.focus();
        editor.setSelection(new m.Selection(safeLine, safeColumn, safeLine, endColumn));

        searchHighlightDecorationIdsRef.current = editor.deltaDecorations(
          searchHighlightDecorationIdsRef.current,
          [
            {
              range: new m.Range(safeLine, safeColumn, safeLine, endColumn),
              options: { inlineClassName: 'editor-search-hit-highlight-inline', isWholeLine: false },
            },
            {
              range: new m.Range(safeLine, 1, safeLine, lineMaxColumn),
              options: { className: 'editor-search-hit-highlight-line', isWholeLine: true },
            },
          ]
        );

        if (searchHighlightClearTimerRef.current) clearTimeout(searchHighlightClearTimerRef.current);
        searchHighlightClearTimerRef.current = setTimeout(() => {
          const activeEditor = editorRef.current;
          if (!activeEditor) return;
          searchHighlightDecorationIdsRef.current = activeEditor.deltaDecorations(
            searchHighlightDecorationIdsRef.current,
            []
          );
        }, 1800);
      };

      void openFile(path, line, column);
      tryReveal(0);
    },
    [openFile, debouncedQuery, editorRef, monacoRef]
  );

  return {
    searchQuery,
    setSearchQuery,
    searchBusy,
    searchResults,
    searchError,
    collapsedSearchFiles,
    searchCaseSensitive,
    setSearchCaseSensitive,
    searchWordMatch,
    setSearchWordMatch,
    searchUseRegex,
    setSearchUseRegex,
    performSearch: refetch,
    toggleSearchFileCollapsed,
    jumpToSearchHit,
  };
}
