import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import type { FileEntry } from '../../types';
import {
  normalizeProjectPath,
  scoreQuickOpenPath,
  flattenFileTreeEntries,
} from './editorFilePaths';

export function useEditorPanelQuickOpen(
  fileTree: FileEntry[],
  openFile: (path: string, line?: number, column?: number) => Promise<void>,
  searchInputRef: RefObject<HTMLInputElement | null>,
  setLeftTab: (tab: 'files' | 'search') => void
) {
  const [quickOpenVisible, setQuickOpenVisible] = useState(false);
  const [quickOpenQuery, setQuickOpenQuery] = useState('');
  const [quickOpenSelectedIndex, setQuickOpenSelectedIndex] = useState(0);
  const quickOpenInputRef = useRef<HTMLInputElement | null>(null);

  const projectFiles = useMemo(() => {
    return flattenFileTreeEntries(fileTree)
      .map((path: string) => normalizeProjectPath(path))
      .sort((a: string, b: string) => a.localeCompare(b));
  }, [fileTree]);

  const quickOpenResults = useMemo(() => {
    return projectFiles
      .map((path: string) => ({ path, score: scoreQuickOpenPath(path, quickOpenQuery) }))
      .filter((item: { path: string; score: number }) => item.score >= 0)
      .sort((a: { path: string; score: number }, b: { path: string; score: number }) => {
        if (b.score !== a.score) return b.score - a.score;
        return a.path.localeCompare(b.path);
      })
      .slice(0, 80)
      .map((item: { path: string; score: number }) => item.path);
  }, [projectFiles, quickOpenQuery]);

  const openQuickOpenFile = useCallback(
    (path: string) => {
      if (!path) return;
      void openFile(path);
      setQuickOpenVisible(false);
      setQuickOpenQuery('');
      setQuickOpenSelectedIndex(0);
    },
    [openFile]
  );

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => {
      const key = e.key?.toLowerCase?.() ?? '';
      const code = e.code ?? '';
      const ctrlOrMeta = e.ctrlKey || e.metaKey;

      if (ctrlOrMeta && (key === 'p' || code === 'KeyP')) {
        e.preventDefault();
        e.stopPropagation();
        setQuickOpenVisible(true);
        setQuickOpenQuery('');
        setQuickOpenSelectedIndex(0);
        setTimeout(() => quickOpenInputRef.current?.focus(), 0);
        return;
      }

      if (ctrlOrMeta && key === 'f' && e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        setLeftTab('search');
        setTimeout(() => searchInputRef.current?.focus(), 0);
        return;
      }

      if (quickOpenVisible && key === 'escape') {
        e.preventDefault();
        e.stopPropagation();
        setQuickOpenVisible(false);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [quickOpenVisible, searchInputRef, setLeftTab]);

  useEffect(() => {
    if (!quickOpenVisible) return;
    setTimeout(() => quickOpenInputRef.current?.focus(), 0);
  }, [quickOpenVisible]);

  useEffect(() => {
    setQuickOpenSelectedIndex((index: number) => {
      if (quickOpenResults.length === 0) return 0;
      if (index < 0) return 0;
      if (index >= quickOpenResults.length) return quickOpenResults.length - 1;
      return index;
    });
  }, [quickOpenResults]);

  const handleQuickOpenKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (quickOpenResults.length === 0) return;
        setQuickOpenSelectedIndex((i: number) => (i + 1) % quickOpenResults.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (quickOpenResults.length === 0) return;
        setQuickOpenSelectedIndex((i: number) => (i - 1 + quickOpenResults.length) % quickOpenResults.length);
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const selected = quickOpenResults[quickOpenSelectedIndex];
        if (selected) openQuickOpenFile(selected);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setQuickOpenVisible(false);
      }
    },
    [quickOpenResults, quickOpenSelectedIndex, openQuickOpenFile]
  );

  return {
    quickOpenVisible,
    setQuickOpenVisible,
    quickOpenQuery,
    setQuickOpenQuery,
    quickOpenSelectedIndex,
    setQuickOpenSelectedIndex,
    quickOpenInputRef,
    quickOpenResults,
    openQuickOpenFile,
    handleQuickOpenKeyDown,
  };
}
