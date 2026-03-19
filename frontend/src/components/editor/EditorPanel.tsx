import { useEffect, useRef, useCallback, useState } from 'react';
import Editor, { type OnMount } from '@monaco-editor/react';
import { Download, FileCode } from 'lucide-react';
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
  const { openFiles, activeFilePath, updateFileContent, saveFile, loadFileTree, pendingRevealLine, pendingRevealColumn, clearPendingReveal } = useFilesStore();
  const sessionId = useSessionStore((s) => s.sessionId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [fileTreeWidth, setFileTreeWidth] = useState(180);
  const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark');

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((w) => Math.min(FILE_TREE_MAX, Math.max(FILE_TREE_MIN, w + delta)));
  }, []);

  useEffect(() => {
    if (sessionId) {
      loadFileTree();
    }
  }, [sessionId, loadFileTree]);

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
    const timer = setTimeout(() => {
      const editor = editorRef.current;
      if (!editor) return;
      editor.revealLineInCenter(line);
      editor.setPosition({ lineNumber: line, column: col });
      editor.focus();
    }, 100);
    clearPendingReveal();
    return () => clearTimeout(timer);
  }, [pendingRevealLine, pendingRevealColumn, activeFilePath, clearPendingReveal]);

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (!activeFilePath || value === undefined) return;
    updateFileContent(activeFilePath, value);

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = setTimeout(() => {
      saveFile(activeFilePath);
    }, 1000);
  }, [activeFilePath, updateFileContent, saveFile]);

  const activeContent = activeFilePath ? openFiles.get(activeFilePath) : undefined;

  return (
    <div
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
        }}
      >
        <div
          style={{
            padding: '6px 12px',
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>Files</span>

          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              title="Export ZIP"
              disabled={!sessionId}
              onClick={() => sessionId && downloadZip(sessionId)}
              style={{
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                padding: '3px 5px',
                cursor: sessionId ? 'pointer' : 'not-allowed',
                color: sessionId ? 'var(--text)' : 'var(--text-dim)',
                display: 'flex',
                alignItems: 'center',
                opacity: sessionId ? 1 : 0.4,
              }}
            >
              <Download size={13} />
            </button>

            <button
              title="Export HTML"
              disabled={!sessionId}
              onClick={() => sessionId && downloadSingleHtml(sessionId)}
              style={{
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                padding: '3px 5px',
                cursor: sessionId ? 'pointer' : 'not-allowed',
                color: sessionId ? 'var(--text)' : 'var(--text-dim)',
                display: 'flex',
                alignItems: 'center',
                opacity: sessionId ? 1 : 0.4,
              }}
            >
              <FileCode size={13} />
            </button>
          </div>
        </div>

        <FileTree />
      </div>

      <Resizer direction="horizontal" onDrag={handleFileTreeResize} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <FileTabs />

        {activeFilePath && activeContent !== undefined ? (
          <div style={{ flex: 1, overflow: 'hidden' }}>
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
            {sessionId ? 'Select a file to edit' : 'No project selected'}
          </div>
        )}
      </div>
    </div>
  );
}
