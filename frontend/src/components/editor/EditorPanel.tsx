import { useEffect, useRef, useCallback, useState } from 'react';
import Editor, { type Monaco, type OnMount } from '@monaco-editor/react';
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

function defineMonacoThemes(monaco: Monaco) {
  monaco.editor.defineTheme('ai-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#111827',
      'editor.foreground': '#e5e7eb',
      'editorLineNumber.foreground': '#6b7280',
      'editorLineNumber.activeForeground': '#60a5fa',
      'editor.selectionBackground': '#60a5fa33',
      'editor.inactiveSelectionBackground': '#60a5fa22',
      'editor.lineHighlightBackground': '#1f293766',
      'editorIndentGuide.background': '#1f293780',
      'editorIndentGuide.activeBackground': '#60a5fa',
    },
  });

  monaco.editor.defineTheme('ai-light', {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#ffffff',
      'editor.foreground': '#111827',
      'editorLineNumber.foreground': '#9ca3af',
      'editorLineNumber.activeForeground': '#2563eb',
      'editor.selectionBackground': '#2563eb26',
      'editor.inactiveSelectionBackground': '#2563eb1a',
      'editor.lineHighlightBackground': '#e5e7eb66',
      'editorIndentGuide.background': '#e5e7eb80',
      'editorIndentGuide.activeBackground': '#2563eb',
    },
  });
}

export function EditorPanel() {
  const { openFiles, activeFilePath, updateFileContent, saveFile, loadFileTree, pendingRevealLine, pendingRevealColumn, clearPendingReveal } = useFilesStore();
  const sessionId = useSessionStore((s) => s.sessionId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [fileTreeWidth, setFileTreeWidth] = useState(180);
  const [editorTheme, setEditorTheme] = useState<'ai-dark' | 'ai-light'>('ai-dark');

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
      const mode = document.documentElement.dataset.theme === 'light' ? 'ai-light' : 'ai-dark';
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
    if (!monacoTypesInitialized) {
      monacoTypesInitialized = true;

      // Align Monaco themes with app surfaces
      defineMonacoThemes(monaco);
    }

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
  const React: any;
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
            padding: 'var(--space-md) var(--space-lg)',
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

          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
            <button
              title="Export ZIP"
              disabled={!sessionId}
              onClick={() => sessionId && downloadZip(sessionId)}
              style={{
                background: 'none',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: 'var(--space-sm) var(--space-md)',
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
                borderRadius: 'var(--radius-sm)',
                padding: 'var(--space-sm) var(--space-md)',
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

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: 'var(--surface)',
        }}
      >
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