import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import Editor, { loader, type OnMount } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

loader.config({ monaco });
import { Check, Loader2 } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml } from '../../services/api';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';
import { FILE_TREE_MIN, FILE_TREE_MAX } from './editorConstants';
import { toMonacoUri } from './editorFilePaths';
import { getEditorLanguageForPath } from './editorLanguage';
import { EditorSidebarHeader } from './EditorSidebarHeader';
import { EditorSearchPanel } from './EditorSearchPanel';
import { EditorQuickOpenOverlay } from './EditorQuickOpenOverlay';
import { EDITOR_MONACO_OPTIONS } from './monacoEditorOptions';
import { useEditorPanelTheme } from './useEditorPanelTheme';
import { useEditorPanelSave } from './useEditorPanelSave';
import { useEditorPendingReveal } from './useEditorPendingReveal';
import { useMonacoProjectModels } from './useMonacoProjectModels';
import { useEditorPanelSearch } from './useEditorPanelSearch';
import { useEditorPanelQuickOpen } from './useEditorPanelQuickOpen';
import { createEditorPanelMonacoOnMount } from './editorPanelMonacoOnMount';

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
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const importNavigationDisposableRef = useRef<{ dispose(): void } | null>(null);
  const [fileTreeWidth, setFileTreeWidth] = useState(180);
  const [leftTab, setLeftTab] = useState<'files' | 'search'>('files');

  const { monacoRef, indexedFilesRef, handleBeforeMount } = useMonacoProjectModels(
    projectId,
    fileTree,
    openFiles
  );

  const editorTheme = useEditorPanelTheme();
  const { saveStatus, handleEditorChange } = useEditorPanelSave(activeFilePath, updateFileContent, saveFile);

  useEditorPendingReveal(
    editorRef,
    pendingRevealLine,
    pendingRevealColumn,
    revealVersion,
    activeFilePath,
    clearPendingReveal
  );

  const {
    searchInputRef,
    searchQuery,
    setSearchQuery,
    searchBusy,
    searchResults,
    searchError,
    collapsedSearchFiles,
    searchCaseSensitive,
    setSearchCaseSensitive,
    performSearch,
    toggleSearchFileCollapsed,
    jumpToSearchHit,
  } = useEditorPanelSearch(projectId, openFile, editorRef, monacoRef);

  const {
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
  } = useEditorPanelQuickOpen(fileTree, openFile, searchInputRef, setLeftTab);

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((w: number) => Math.min(FILE_TREE_MAX, Math.max(FILE_TREE_MIN, w + delta)));
  }, []);

  useEffect(() => {
    if (projectId) {
      loadFileTree();
    }
  }, [projectId, loadFileTree]);

  const handleMonacoEditorMount = useMemo(
    () =>
      createEditorPanelMonacoOnMount({
        editorRef,
        monacoRef,
        importNavigationDisposableRef,
        quickOpenInputRef,
        indexedFilesRef,
        openFile,
        setQuickOpenVisible,
        setQuickOpenQuery,
        setQuickOpenSelectedIndex,
      }),
    [monacoRef, openFile, quickOpenInputRef, setQuickOpenQuery, setQuickOpenSelectedIndex, setQuickOpenVisible]
  );

  const activeContent = activeFilePath ? openFiles.get(activeFilePath) : undefined;

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
              beforeMount={handleBeforeMount}
              onMount={handleMonacoEditorMount}
              options={EDITOR_MONACO_OPTIONS}
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
