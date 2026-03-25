import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Editor, { loader, type Monaco, type OnMount } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

// Use local monaco-editor instead of CDN
loader.config({ monaco });
import { Check, Loader2 } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml, fetchFileContent, searchFiles, type SearchResult } from '../../services/api';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';
import { FILE_TREE_MIN, FILE_TREE_MAX } from './editorConstants';
import {
  toMonacoUri,
  normalizeProjectPath,
  resolveRelativeImportPath,
  findImportedModuleForSymbol,
  scoreQuickOpenPath,
  flattenFileTreeEntries,
} from './editorFilePaths';
import { getEditorLanguageForPath } from './editorLanguage';
import { installMonacoProjectTypes } from './monacoProjectSetup';
import { MONACO_REACT_VITE_DTS_URI, MONACO_REACT_VITE_JS_DTS_URI } from './monacoAmbientTypes';
import { ensureEditorSearchHitHighlightStyles } from './searchHighlightStyles';
import { EditorSidebarHeader } from './EditorSidebarHeader';
import { EditorSearchPanel } from './EditorSearchPanel';
import { EditorQuickOpenOverlay } from './EditorQuickOpenOverlay';

export function EditorPanel() {
  const { t } = useTranslation();
  const {
    fileTree,
    openFiles,
    activeFilePath,
    updateFileContent,
    saveFile,
    loadFileTree,
    pendingRevealLine,
    pendingRevealColumn,
    revealVersion,
    clearPendingReveal,
    openFile,
  } = useFilesStore();
  const projectId = useSessionStore((s) => s.projectId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const importNavigationDisposableRef = useRef<{ dispose(): void } | null>(null);
  const [fileTreeWidth, setFileTreeWidth] = useState(180);
  const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  const [leftTab, setLeftTab] = useState<'files' | 'search'>('files');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [collapsedSearchFiles, setCollapsedSearchFiles] = useState<Set<string>>(new Set());
  const [searchCaseSensitive, setSearchCaseSensitive] = useState(false);
  const [quickOpenVisible, setQuickOpenVisible] = useState(false);
  const [quickOpenQuery, setQuickOpenQuery] = useState('');
  const [quickOpenSelectedIndex, setQuickOpenSelectedIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const quickOpenInputRef = useRef<HTMLInputElement | null>(null);
  const searchRequestIdRef = useRef(0);
  const searchHighlightDecorationIdsRef = useRef<string[]>([]);
  const searchHighlightClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hydratedModelsRef = useRef<Set<string>>(new Set());
  const indexedFilesRef = useRef<Set<string>>(new Set());
  const openFilesRef = useRef(openFiles);

  useEffect(() => {
    openFilesRef.current = openFiles;
  }, [openFiles]);

  useEffect(() => {
    ensureEditorSearchHitHighlightStyles();
  }, []);

  useEffect(() => {
    const m = monacoRef.current;
    if (!m) return;

    hydratedModelsRef.current.clear();
    indexedFilesRef.current.clear();

    for (const model of m.editor.getModels()) {
      const uri = model.uri.toString();

      if (uri === MONACO_REACT_VITE_DTS_URI || uri === MONACO_REACT_VITE_JS_DTS_URI) {
        continue;
      }

      model.dispose();
    }
  }, [projectId]);

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((w: number) => Math.min(FILE_TREE_MAX, Math.max(FILE_TREE_MIN, w + delta)));
  }, []);

  useEffect(() => {
    if (projectId) {
      loadFileTree();
    }
  }, [projectId, loadFileTree]);

  // Sync Monaco theme with app light/dark theme
  useEffect(() => {
    const applyTheme = () => {
      const mode = document.documentElement.dataset.theme === 'light' ? 'light' : 'vs-dark';
      setEditorTheme(mode);
    };
    applyTheme();
    const observer = new MutationObserver(() => applyTheme());
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  // Reveal line/column when navigating from error toast
  useEffect(() => {
    if (!pendingRevealLine || !editorRef.current) return;
    const line = pendingRevealLine;
    const col = pendingRevealColumn ?? 1;
    // Small delay to let Monaco finish switching to the new file model
    const timer = setTimeout(() => {
      const editor = editorRef.current;
      if (!editor) return;
      const pos = { lineNumber: line, column: col };
      editor.setPosition(pos);
      editor.revealPositionInCenter(pos);
      editor.focus();
    }, 100);
    clearPendingReveal();
    return () => clearTimeout(timer);
  }, [pendingRevealLine, pendingRevealColumn, revealVersion, activeFilePath, clearPendingReveal]);

  const doSave = useCallback((path: string) => {
    setSaveStatus('saving');
    saveFile(path)
      .then(() => {
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 1500);
      })
      .catch(() => setSaveStatus('idle'));
  }, [saveFile]);

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (!activeFilePath || value === undefined) return;
      updateFileContent(activeFilePath, value);

      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      saveTimerRef.current = setTimeout(() => {
        doSave(activeFilePath);
      }, 1000);
    },
    [activeFilePath, updateFileContent, doSave]
  );

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    function onKeyDown(e: globalThis.KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        const path = useFilesStore.getState().activeFilePath;
        if (path) {
          if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
          doSave(path);
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [doSave]);

  const activeContent = activeFilePath ? openFiles.get(activeFilePath) : undefined;

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

  const openQuickOpenFile = useCallback((path: string) => {
    if (!path) return;
    void openFile(path);
    setQuickOpenVisible(false);
    setQuickOpenQuery('');
    setQuickOpenSelectedIndex(0);
  }, [openFile]);

  useEffect(() => {
    const m = monacoRef.current;
    if (!m || !projectId || fileTree.length === 0) return;

    let cancelled = false;

    const files = flattenFileTreeEntries(fileTree)
      .map((p: string) => normalizeProjectPath(p))
      .filter((p: string) => /\.(ts|tsx|js|jsx|mjs|cjs|json|css|scss|sass|less)$/.test(p));

    // Ensure module paths exist in Monaco immediately to avoid transient
    // "Cannot find module" diagnostics while file contents are still loading.
    for (const path of files) {
      const uri = m.Uri.parse(toMonacoUri(path));
      if (m.editor.getModel(uri)) continue;
      m.editor.createModel('', getEditorLanguageForPath(path), uri);
    }

    const hydrateModels = async () => {
      const tasks = files.map(async (path: string) => {
        const uri = toMonacoUri(path);
        if (hydratedModelsRef.current.has(uri) || openFilesRef.current.has(path)) return;

        try {
          const content = await fetchFileContent(projectId, path);
          if (cancelled) return;

          const model = m.editor.getModel(m.Uri.parse(uri));
          if (!model) return;
          if (model.getValue() !== content) {
            model.setValue(content);
          }
          hydratedModelsRef.current.add(uri);
        } catch {
          // ignore
        }
      });

      await Promise.allSettled(tasks);
    };

    void hydrateModels();

    return () => {
      cancelled = true;
    };
  }, [projectId, fileTree]);

  useEffect(() => {
    indexedFilesRef.current = new Set(flattenFileTreeEntries(fileTree).map((path: string) => normalizeProjectPath(path)));
  }, [fileTree]);

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
  }, [searchCaseSensitive, searchQuery, projectId]);

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

        if (!editor || !m || !model || normalizedActivePath !== normalizedTargetPath) {
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
    [openFile, searchQuery]
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
  }, [quickOpenVisible]);

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

  const handleEditorMount = useCallback((m: Monaco) => {
    monacoRef.current = m;
    installMonacoProjectTypes(m, () => indexedFilesRef.current);
  }, []);

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

  return (
    <div
      dir="ltr"
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          width: fileTreeWidth,
          minWidth: fileTreeWidth,
          borderRight: '1px solid var(--border)',
          overflow: 'auto',
          background: 'var(--surface)',
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <EditorSidebarHeader
          t={t}
          leftTab={leftTab}
          projectId={projectId}
          onExportZip={() => projectId && downloadZip(projectId)}
          onShowFiles={() => {
            if (!projectId) return;
            setLeftTab('files');
          }}
          onShowSearch={() => {
            if (!projectId) return;
            setLeftTab('search');
            setTimeout(() => searchInputRef.current?.focus(), 0);
          }}
          onExportHtml={() => projectId && downloadSingleHtml(projectId)}
        />

        {leftTab === 'files' ? (
          <div style={{ flex: 1, overflow: 'auto' }}>
            <FileTree />
          </div>
        ) : (
          <EditorSearchPanel
            t={t}
            searchInputRef={searchInputRef}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            onSearchKeyDown={(e) => {
              if (e.key === 'Enter') performSearch();
            }}
            performSearch={performSearch}
            searchBusy={searchBusy}
            projectId={projectId}
            searchCaseSensitive={searchCaseSensitive}
            onSearchCaseSensitiveChange={setSearchCaseSensitive}
            searchResults={searchResults}
            searchError={searchError}
            collapsedSearchFiles={collapsedSearchFiles}
            toggleSearchFileCollapsed={toggleSearchFileCollapsed}
            jumpToSearchHit={jumpToSearchHit}
          />
        )}
      </div>

      <Resizer direction="horizontal" onDrag={handleFileTreeResize} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        <div className="flex items-center shrink-0">
          <div className="flex-1 min-w-0">
            <FileTabs />
          </div>
          {saveStatus !== 'idle' && (
            <div className="flex items-center gap-1 px-3 text-[11px] text-muted-foreground shrink-0">
              {saveStatus === 'saving' ? (
                <>
                  <Loader2 size={10} className="animate-spin" /> {t('editor.saving')}
                </>
              ) : (
                <>
                  <Check size={10} className="text-green-400" /> {t('editor.saved')}
                </>
              )}
            </div>
          )}
        </div>

        {activeFilePath && activeContent !== undefined ? (
          <div data-testid="monaco-editor-host" style={{ flex: 1, overflow: 'hidden' }} dir="ltr">
            <Editor
              theme={editorTheme}
              language={getEditorLanguageForPath(activeFilePath)}
              path={activeFilePath ? toMonacoUri(activeFilePath) : undefined}
              value={activeContent}
              onChange={handleEditorChange}
              beforeMount={handleEditorMount}
              onMount={(editor: Parameters<OnMount>[0]) => {
                editorRef.current = editor;
                const m = monacoRef.current;
                if (m) {
                  editor.addCommand(m.KeyMod.CtrlCmd | m.KeyCode.KeyP, () => {
                    setQuickOpenVisible(true);
                    setQuickOpenQuery('');
                    setQuickOpenSelectedIndex(0);
                    setTimeout(() => quickOpenInputRef.current?.focus(), 0);
                  });
                }
                importNavigationDisposableRef.current?.dispose();
                importNavigationDisposableRef.current = editor.onMouseDown((event: any) => {
                  const browserEvent = event?.event as globalThis.MouseEvent | undefined;
                  const isCtrlOrCmd = Boolean(browserEvent?.ctrlKey || browserEvent?.metaKey);
                  if (!isCtrlOrCmd) return;

                  let position = event?.target?.position ?? null;
                  // Playwright (and sometimes the a11y textarea layer) yields a mouse target without a position;
                  // map client coordinates to editor position so Ctrl+click still works.
                  if (!position && browserEvent && typeof browserEvent.clientX === 'number') {
                    const hit = editor.getTargetAtClientPoint(browserEvent.clientX, browserEvent.clientY);
                    position = hit?.position ?? null;
                  }
                  if (!position) return;

                  const model = editor.getModel();
                  if (!model) return;

                  const lineText = model.getLineContent(position.lineNumber) ?? '';
                  if (!lineText.includes('import')) return;

                  const word = model.getWordAtPosition(position);
                  if (!word?.word) return;

                  const importPath = findImportedModuleForSymbol(model.getValue(), word.word);
                  if (!importPath) return;

                  const currentPath = normalizeProjectPath(decodeURIComponent(model.uri.path));
                  const targetPath = resolveRelativeImportPath(currentPath, importPath, indexedFilesRef.current);
                  if (!targetPath) return;

                  browserEvent?.preventDefault?.();
                  browserEvent?.stopPropagation?.();
                  void openFile(targetPath, 1, 1);
                });
                editor.onDidDispose(() => {
                  importNavigationDisposableRef.current?.dispose();
                  importNavigationDisposableRef.current = null;
                });
                const { pendingRevealLine: line, pendingRevealColumn: col, clearPendingReveal: clear } = useFilesStore.getState();
                if (line) {
                  setTimeout(() => {
                    const pos = { lineNumber: line, column: col ?? 1 };
                    editor.setPosition(pos);
                    editor.revealPositionInCenter(pos);
                    editor.focus();
                    clear();
                  }, 50);
                }
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: 'on',
                tabSize: 2,
                automaticLayout: true,
                definitionLinkOpensInPeek: false,
                gotoLocation: {
                  multipleDefinitions: 'goto',
                  multipleDeclarations: 'goto',
                  multipleImplementations: 'goto',
                  multipleReferences: 'peek',
                  multipleTypeDefinitions: 'goto',
                },
              }}
            />
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-dim)',
              fontSize: '14px',
            }}
          >
            {projectId ? t('editor.selectFileToEdit') : t('editor.noProjectSelected')}
          </div>
        )}

        {quickOpenVisible && (
          <EditorQuickOpenOverlay
            t={t}
            quickOpenInputRef={quickOpenInputRef}
            quickOpenQuery={quickOpenQuery}
            onQuickOpenQueryChange={setQuickOpenQuery}
            onQuickOpenKeyDown={handleQuickOpenKeyDown}
            quickOpenResults={quickOpenResults}
            quickOpenSelectedIndex={quickOpenSelectedIndex}
            onQuickOpenSelectedIndexChange={setQuickOpenSelectedIndex}
            onDismiss={() => setQuickOpenVisible(false)}
            openQuickOpenFile={openQuickOpenFile}
          />
        )}
      </div>
    </div>
  );
}
