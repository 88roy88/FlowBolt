import { useEffect, useCallback, useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import Editor, { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

loader.config({ monaco });
import { Check, Loader2 } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';
import { toMonacoUri, getEditorLanguageForPath } from './editorFilePaths';
import { FILE_TREE_MIN, FILE_TREE_MAX, EDITOR_MONACO_OPTIONS } from './editorConstants';
import { EditorSidebarHeader } from './EditorSidebarHeader';
import { EditorSearchPanel } from './EditorSearchPanel';
import { EditorQuickOpenOverlay } from './EditorQuickOpenOverlay';
import { useEditorPanelSave } from './useEditorPanelSave';
import { useEditorPendingReveal } from './useEditorPendingReveal';
import { useMonacoProjectModels } from './useMonacoProjectModels';
import { useEditorPanelSearch } from './useEditorPanelSearch';
import { useEditorPanelQuickOpen } from './useEditorPanelQuickOpen';

export function EditorPanel() {
  const { t } = useTranslation();
  const {
    fileTree,
    openFiles,
    activeFilePath,
    loadFileTree,
    pendingRevealLine,
    pendingRevealColumn,
    revealVersion,
    clearPendingReveal,
    openFile,
  } = useFilesStore();
  const projectId = useSessionStore((s) => s.projectId);
  const buildCompleted = useChatStore((s) => s.buildCompleted);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const aiFlowActive = isStreaming || agentPhase !== 'idle';
  const readOnlyUntilInitialBuildComplete = !buildCompleted;
  const editorReadOnly = readOnlyUntilInitialBuildComplete || aiFlowActive;
  const readOnlyMessage = readOnlyUntilInitialBuildComplete
    ? t('editor.readOnlyUntilFirstAiResponse')
    : t('editor.readOnlyWhileAiWorking');

  const [fileTreeWidth, setFileTreeWidth] = useState(180);
  const [leftTab, setLeftTab] = useState<'files' | 'search'>('files');
  const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark');
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const applyTheme = () => {
      setEditorTheme(document.documentElement.dataset.theme === 'light' ? 'light' : 'vs-dark');
    };
    applyTheme();
    const observer = new MutationObserver(applyTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  const { saveStatus, handleEditorChange } = useEditorPanelSave(activeFilePath, editorReadOnly);

  const {
    quickOpenVisible,
    setQuickOpenVisible,
    quickOpenQuery,
    setQuickOpenQuery,
    quickOpenSelectedIndex,
    setQuickOpenSelectedIndex,
    quickOpenInputRef,
    quickOpenResults,
    openQuickOpen,
    openQuickOpenFile,
    handleQuickOpenKeyDown,
  } = useEditorPanelQuickOpen(fileTree, openFile, searchInputRef, setLeftTab);

  const { handleBeforeMount, handleOnMount, monacoRef, editorRef } = useMonacoProjectModels(
    projectId,
    fileTree,
    openFile,
    openQuickOpen,
  );

  const {
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
  } = useEditorPanelSearch(projectId, openFile, editorRef, monacoRef);

  useEditorPendingReveal(
    editorRef,
    pendingRevealLine,
    pendingRevealColumn,
    revealVersion,
    activeFilePath,
    clearPendingReveal
  );

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((w: number) => Math.min(FILE_TREE_MAX, Math.max(FILE_TREE_MIN, w + delta)));
  }, []);

  useQuery({
    queryKey: ['file-tree', projectId],
    queryFn: () => loadFileTree(),
    enabled: !!projectId,
    staleTime: Infinity,
    gcTime: 0,
  });

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
          onShowFiles={() => {
            if (!projectId) return;
            setLeftTab('files');
          }}
          onShowSearch={() => {
            if (!projectId) return;
            setLeftTab('search');
            setTimeout(() => searchInputRef.current?.focus(), 0);
          }}
          searchResultCount={searchResults.reduce((sum, r) => sum + r.hits.length, 0)}
        />

        {leftTab === 'files' ? (
          <div style={{ flex: 1, overflow: 'auto' }}>
            <FileTree readOnly={editorReadOnly} readOnlyMessage={readOnlyMessage} />
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
            searchWordMatch={searchWordMatch}
            onSearchWordMatchChange={setSearchWordMatch}
            searchUseRegex={searchUseRegex}
            onSearchUseRegexChange={setSearchUseRegex}
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
                  <Check size={10} className="text-success" /> {t('editor.saved')}
                </>
              )}
            </div>
          )}
          {editorReadOnly && (
            <div className="px-3 text-[11px] text-muted-foreground shrink-0">
              {readOnlyMessage}
            </div>
          )}
        </div>

        {activeFilePath && activeContent !== undefined ? (
          <div data-testid="monaco-editor-host" style={{ flex: 1, overflow: 'hidden' }} dir="ltr">
            <Editor
              theme={editorTheme}
              language={getEditorLanguageForPath(activeFilePath)}
              path={toMonacoUri(activeFilePath)}
              value={activeContent}
              onChange={handleEditorChange}
              beforeMount={handleBeforeMount}
              onMount={handleOnMount}
              options={{ ...EDITOR_MONACO_OPTIONS, readOnly: editorReadOnly }}
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
