import { useEffect, useRef, useCallback } from 'react';
import Editor, { type Monaco } from '@monaco-editor/react';
import { Download, FileCode } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml } from '../../services/api';
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
      tsx: 'typescriptreact',
      js: 'javascript',
      jsx: 'javascriptreact',
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
    // Configure TypeScript/JavaScript defaults for JSX support
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
    };

    tsDefaults.setCompilerOptions(sharedCompilerOptions);
    jsDefaults.setCompilerOptions(sharedCompilerOptions);

    // Enable validation
    tsDefaults.setDiagnosticsOptions({
      noSemanticValidation: false,
      noSyntaxValidation: false,
    });
    jsDefaults.setDiagnosticsOptions({
      noSemanticValidation: false,
      noSyntaxValidation: false,
    });

    // Add React type stub so JSX doesn't show errors
    const reactTypes = `
declare module 'react' {
  export function useState<T>(initial: T | (() => T)): [T, (v: T | ((prev: T) => T)) => void];
  export function useEffect(effect: () => void | (() => void), deps?: any[]): void;
  export function useRef<T>(initial: T): { current: T };
  export function useCallback<T extends (...args: any[]) => any>(fn: T, deps: any[]): T;
  export function useMemo<T>(fn: () => T, deps: any[]): T;
  export function useContext<T>(context: React.Context<T>): T;
  export function createContext<T>(defaultValue: T): React.Context<T>;
  export function memo<T>(component: T): T;
  export function forwardRef<T, P>(render: (props: P, ref: React.Ref<T>) => React.ReactElement | null): React.ForwardRefExoticComponent<P & React.RefAttributes<T>>;
  export type FC<P = {}> = (props: P) => React.ReactElement | null;
  export type ReactNode = React.ReactElement | string | number | boolean | null | undefined | Iterable<ReactNode>;
  export type ReactElement = any;
  export type Ref<T> = ((instance: T | null) => void) | { current: T | null } | null;
  export type RefAttributes<T> = { ref?: Ref<T> };
  export type ForwardRefExoticComponent<P> = React.FC<P>;
  export type Context<T> = { Provider: FC<{ value: T; children?: ReactNode }>; Consumer: FC<{ children: (value: T) => ReactNode }> };
  export type CSSProperties = Record<string, string | number>;
  export type ChangeEvent<T = Element> = { target: T & { value: string } };
  export type MouseEvent<T = Element> = { stopPropagation(): void; preventDefault(): void; target: T };
  export type KeyboardEvent<T = Element> = { key: string; stopPropagation(): void; preventDefault(): void };
  export type FormEvent<T = Element> = { stopPropagation(): void; preventDefault(): void };
  export default React;
  namespace React {}
}

declare module 'react-dom/client' {
  export function createRoot(container: Element): { render(element: any): void };
}

declare namespace JSX {
  interface IntrinsicElements { [tag: string]: any; }
  type Element = any;
}
`;
    tsDefaults.addExtraLib(reactTypes, 'file:///node_modules/@types/react/index.d.ts');
    jsDefaults.addExtraLib(reactTypes, 'file:///node_modules/@types/react/index.d.ts');
  }, []);

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
        }}>
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

      {/* Editor area */}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <FileTabs />
        {activeFilePath && activeContent !== undefined ? (
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <Editor
              theme="vs-dark"
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
