import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import type { Monaco, OnMount } from '@monaco-editor/react';
import { searchFiles, type SearchResult } from '../../services/api';
import { useFilesStore } from '../../stores/files';
import { normalizeProjectPath } from './editorFilePaths';
import { ensureEditorSearchHitHighlightStyles } from './searchHighlightStyles';

type StandaloneEditor = Parameters<OnMount>[0];

export function useEditorPanelSearch(
  projectId: string | null,
  openFile: (path: string, line?: number, column?: number) => Promise<void>,
  editorRef: MutableRefObject<StandaloneEditor | null>,
  monacoRef: MutableRefObject<Monaco | null>
) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [collapsedSearchFiles, setCollapsedSearchFiles] = useState<Set<string>>(new Set());
  const [searchCaseSensitive, setSearchCaseSensitive] = useState(false);
  const [searchWordMatch, setSearchWordMatch] = useState(false);
  const [searchUseRegex, setSearchUseRegex] = useState(false);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const searchRequestIdRef = useRef(0);
  const searchHighlightDecorationIdsRef = useRef<string[]>([]);
  const searchHighlightClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchDebounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    ensureEditorSearchHitHighlightStyles();
  }, []);

  const performSearch = useCallback(async () => {
    if (!projectId) return;
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }

    const requestId = ++searchRequestIdRef.current;
    setSearchBusy(true);
    setSearchResults([]);
    setSearchError(null);
    setCollapsedSearchFiles(new Set());

    try {
      const results = await searchFiles(projectId, query, {
        caseSensitive: searchCaseSensitive,
        wordMatch: searchWordMatch,
        useRegex: searchUseRegex,
        maxResults: 2000,
        maxHitsPerFile: 200,
      });
      if (searchRequestIdRef.current !== requestId) return;
      setSearchResults(results);
    } catch (err) {
      if (searchRequestIdRef.current !== requestId) return;
      const message = err instanceof Error ? err.message : 'Search failed';
      setSearchError(message);
    } finally {
      if (searchRequestIdRef.current === requestId) setSearchBusy(false);
    }
  }, [searchCaseSensitive, searchWordMatch, searchUseRegex, searchQuery, projectId]);

  // Auto-search with debounce when query changes
  useEffect(() => {
    // Clear previous timer
    if (searchDebounceTimerRef.current) {
      clearTimeout(searchDebounceTimerRef.current);
    }

    // Don't auto-search if query is empty
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }

    // Debounce: wait 500ms after user stops typing
    searchDebounceTimerRef.current = setTimeout(() => {
      void performSearch();
    }, 500);

    return () => {
      if (searchDebounceTimerRef.current) {
        clearTimeout(searchDebounceTimerRef.current);
      }
    };
  }, [searchQuery, searchCaseSensitive, searchWordMatch, searchUseRegex, projectId, performSearch]);

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
      const highlightLength = Math.max(1, searchQuery.trim().length);
      const normalizedTargetPath = normalizeProjectPath(path);

      const tryReveal = (attempt: number) => {
        const editor = editorRef.current;
        const m = monacoRef.current;
        const activePath = useFilesStore.getState().activeFilePath;
        const normalizedActivePath = activePath ? normalizeProjectPath(activePath) : '';
        const model = editor?.getModel();
        // Also verify Monaco's current model has switched to the target file, not just
        // the files-store activeFilePath. Without this, decorations land on the previous
        // model (e.g. index.css) before React re-renders the editor with the new path.
        const modelPath = model ? normalizeProjectPath(decodeURIComponent(model.uri.path)) : '';

        if (!editor || !m || !model || normalizedActivePath !== normalizedTargetPath || modelPath !== normalizedTargetPath) {
          if (attempt < 12) {
            setTimeout(() => tryReveal(attempt + 1), 40);
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
              options: {
                inlineClassName: 'editor-search-hit-highlight-inline',
                isWholeLine: false,
              },
            },
            {
              range: new m.Range(safeLine, 1, safeLine, lineMaxColumn),
              options: {
                className: 'editor-search-hit-highlight-line',
                isWholeLine: true,
              },
            },
          ]
        );

        if (searchHighlightClearTimerRef.current) {
          clearTimeout(searchHighlightClearTimerRef.current);
        }
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
    [openFile, searchQuery, editorRef, monacoRef]
  );

  return {
    searchInputRef,
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
    performSearch,
    toggleSearchFileCollapsed,
    jumpToSearchHit,
  };
}
