import { useEffect, useRef, useCallback, useState } from 'react';
import Editor, { type Monaco } from '@monaco-editor/react';
import { Download, FileCode } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml } from '../../services/api';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';

const FILE_TREE_MIN = 120;
const FILE_TREE_MAX = 400;

let monacoTypesInitialized = false;

export function EditorPanel() {
  const { openFiles, activeFilePath, updateFileContent, saveFile, loadFileTree } = useFilesStore();
  const sessionId = useSessionStore((s) => s.sessionId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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
      scss: 'scss',
      less: 'less',
      md: 'markdown',
      py: 'python',
      yaml: 'yaml',
      yml: 'yaml',
      toml: 'toml',
      sh: 'shell',
      bash: 'shell',
      svg: 'xml',
    };

    return langMap[ext ?? ''] ?? 'plaintext';
  };

  const handleEditorMount = useCallback((monaco: Monaco) => {
    if (monacoTypesInitialized) return;
    monacoTypesInitialized = true;

    const tsDefaults = monaco.languages.typescript.typescriptDefaults;
    const jsDefaults = monaco.languages.typescript.javascriptDefaults;

    const sharedCompilerOptions: Parameters<typeof tsDefaults.setCompilerOptions>[0] = {
      target: monaco.languages.typescript.ScriptTarget.ESNext,
      module: monaco.languages.typescript.ModuleKind.ESNext,
      moduleResolution: monaco.languages.typescript.ModuleResolutionKind.NodeJs,
      jsx: monaco.languages.typescript.JsxEmit.ReactJSX,
      allowJs: true,
      allowNonTsExtensions: true,
      esModuleInterop: true,
      strict: true,
      skipLibCheck: true,
      noEmit: true,
      baseUrl: 'file:///',
    };

    tsDefaults.setCompilerOptions(sharedCompilerOptions);
    jsDefaults.setCompilerOptions(sharedCompilerOptions);

    tsDefaults.setDiagnosticsOptions({
      noSemanticValidation: false,
      noSyntaxValidation: false,
    });

    jsDefaults.setDiagnosticsOptions({
      noSemanticValidation: false,
      noSyntaxValidation: false,
    });

    tsDefaults.setEagerModelSync(true);
    jsDefaults.setEagerModelSync(true);

    const reactTypes = `
declare module 'react' {
  export function useState<T>(initial: T | (() => T)): [T, (v: T | ((prev: T) => T)) => void];
  export function useEffect(effect: () => void | (() => void), deps?: any[]): void;
  export function useRef<T>(initial: T): { current: T };
  export function useCallback<T extends (...args: any[]) => any>(fn: T, deps: any[]): T;
  export function useMemo<T>(fn: () => T, deps: any[]): T;
  export const StrictMode: any;
  export type FC<P = {}> = (props: P) => any;
  const React: any;
  export default React;
}

declare module 'react-dom/client' {
  export function createRoot(container: Element): { render(element: any): void };
}

declare module 'react/jsx-runtime' {
  export const Fragment: any;
  export function jsx(type: any, props: any, key?: any): any;
  export function jsxs(type: any, props: any, key?: any): any;
}

declare namespace JSX {
  interface IntrinsicElements {
    [tag: string]: any;
  }
  type Element = any;
}
`;

    tsDefaults.addExtraLib(reactTypes, 'file:///node_modules/@types/react/index.d.ts');
    jsDefaults.addExtraLib(reactTypes, 'file:///node_modules/@types/react/index.d.ts');
  }, []);

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
              language={getLanguage(activeFilePath)}
              path={activeFilePath}
              value={activeContent}
              onChange={handleEditorChange}
              beforeMount={handleEditorMount}
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