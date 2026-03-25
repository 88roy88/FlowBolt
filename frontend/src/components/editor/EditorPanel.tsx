import { useEffect, useRef, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Editor, { loader, type OnMount } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

// Use local monaco-editor instead of CDN
loader.config({ monaco });
import { Download, FileCode, Check, Loader2 } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml } from '../../services/api';
import { setupMonacoTypeScript, getLanguageForPath } from '../../utils/monacoSetup';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';

const FILE_TREE_MIN = 120;
const FILE_TREE_MAX = 400;

export function EditorPanel() {
  const { t } = useTranslation();
  const { openFiles, activeFilePath, updateFileContent, saveFile, loadFileTree, pendingRevealLine, pendingRevealColumn, revealVersion, clearPendingReveal } = useFilesStore();
  const projectId = useSessionStore((s) => s.projectId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [fileTreeWidth, setFileTreeWidth] = useState(180);
  const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((w) => Math.min(FILE_TREE_MAX, Math.max(FILE_TREE_MIN, w + delta)));
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

  // Reveal line/column when navigating from console or error toast
  useEffect(() => {
    if (!pendingRevealLine) return;
    const line = pendingRevealLine;
    const col = pendingRevealColumn ?? 1;
    clearPendingReveal();

    function tryReveal(attempts: number) {
      const editor = editorRef.current;
      if (editor) {
        editor.revealLineInCenter(line);
        editor.setPosition({ lineNumber: line, column: col });
        editor.focus();
      } else if (attempts > 0) {
        setTimeout(() => tryReveal(attempts - 1), 150);
      }
    }
    // Delay to allow Monaco to mount/switch file
    setTimeout(() => tryReveal(3), 100);
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

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (!activeFilePath || value === undefined) return;
    updateFileContent(activeFilePath, value);

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = setTimeout(() => {
      doSave(activeFilePath);
    }, 1000);
  }, [activeFilePath, updateFileContent, doSave]);

  // Cleanup save timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  // Cmd+S / Ctrl+S to save immediately
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
          overflow: 'auto',
          background: 'var(--surface)',
          flexShrink: 0,
        }}
      >
        <div className="flex items-center justify-between px-3 py-[7px] border-b border-border">
          <span className="text-[13px] font-semibold tracking-tight">{t('editor.files')}</span>

          <div className="flex gap-1">
            <button
              title={t('editor.exportZip')}
              disabled={!projectId}
              onClick={() => projectId && downloadZip(projectId)}
              className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
                projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
              }`}
            >
              <Download size={13} />
            </button>

            <button
              title={t('editor.exportHtml')}
              disabled={!projectId}
              onClick={() => projectId && downloadSingleHtml(projectId)}
              className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
                projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
              }`}
            >
              <FileCode size={13} />
            </button>
          </div>
        </div>

        <FileTree />
      </div>

      <Resizer direction="horizontal" onDrag={handleFileTreeResize} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="flex items-center">
          <div className="flex-1 min-w-0">
            <FileTabs />
          </div>
          {saveStatus !== 'idle' && (
            <div className="flex items-center gap-1 px-3 text-[11px] text-muted-foreground shrink-0">
              {saveStatus === 'saving' ? (
                <><Loader2 size={10} className="animate-spin" /> {t('editor.saving')}</>
              ) : (
                <><Check size={10} className="text-green-400" /> {t('editor.saved')}</>
              )}
            </div>
          )}
        </div>

        {activeFilePath && activeContent !== undefined ? (
          <div style={{ flex: 1, overflow: 'hidden' }} dir="ltr">
            <Editor
              theme={editorTheme}
              language={getLanguageForPath(activeFilePath)}
              path={activeFilePath}
              value={activeContent}
              onChange={handleEditorChange}
              beforeMount={setupMonacoTypeScript}
              onMount={(editor) => {
                editorRef.current = editor;
                const { pendingRevealLine: line, pendingRevealColumn: col, clearPendingReveal: clear } = useFilesStore.getState();
                if (line) {
                  setTimeout(() => {
                    editor.revealLineInCenter(line);
                    editor.setPosition({ lineNumber: line, column: col ?? 1 });
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
      </div>
    </div>
  );
}
