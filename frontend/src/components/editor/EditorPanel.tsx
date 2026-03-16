import { useEffect, useRef, useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';

export function EditorPanel() {
  const { openFiles, activeFilePath, updateFileContent, saveFile, loadFileTree } = useFilesStore();
  const sessionId = useSessionStore((s) => s.sessionId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (sessionId) {
      loadFileTree();
    }
  }, [sessionId, loadFileTree]);

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

  const getLanguage = (path: string): string => {
    const ext = path.split('.').pop()?.toLowerCase();
    const langMap: Record<string, string> = {
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      jsx: 'javascript',
      json: 'json',
      html: 'html',
      css: 'css',
      md: 'markdown',
      py: 'python',
      yaml: 'yaml',
      yml: 'yaml',
      toml: 'toml',
      sh: 'shell',
      bash: 'shell',
    };
    return langMap[ext ?? ''] ?? 'plaintext';
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '180px 1fr',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* File tree */}
      <div style={{
        borderRight: '1px solid var(--border)',
        overflow: 'auto',
        background: 'var(--surface)',
      }}>
        <div style={{
          padding: '10px 12px',
          fontSize: '12px',
          fontWeight: 600,
          color: 'var(--text-dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          borderBottom: '1px solid var(--border)',
        }}>
          Files
        </div>
        <FileTree />
      </div>

      {/* Editor area */}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <FileTabs />
        {activeFilePath && activeContent !== undefined ? (
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <Editor
              theme="vs-dark"
              language={getLanguage(activeFilePath)}
              value={activeContent}
              onChange={handleEditorChange}
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
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-dim)',
            fontSize: '14px',
          }}>
            {sessionId ? 'Select a file to edit' : 'No project selected'}
          </div>
        )}
      </div>
    </div>
  );
}
