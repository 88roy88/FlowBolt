import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import Editor, { type Monaco, type OnMount } from '@monaco-editor/react';
import { Download, FileCode, Search, Files } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml, fetchFileContent, searchFiles, type SearchResult } from '../../services/api';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';
import type { FileEntry } from '../../types';

const FILE_TREE_MIN = 120;
const FILE_TREE_MAX = 400;

let monacoTypesInitialized = false;
let monacoImportDefinitionProviderInitialized = false;

const toMonacoUri = (path: string) => {
  const normalized = path.replace(/\\/g, '/').replace(/^\/+/, '');
  return `file:///${normalized}`;
};

const normalizeProjectPath = (path: string) => path.replace(/\\/g, '/').replace(/^\/+/, '');

const normalizeSegments = (segments: string[]) => {
  const out: string[] = [];
  for (const seg of segments) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      out.pop();
      continue;
    }
    out.push(seg);
  }
  return out;
};

const resolveRelativeImportPath = (fromPath: string, importPath: string, fileSet: Set<string>): string | null => {
  if (!importPath.startsWith('.')) return null;

  const from = normalizeProjectPath(fromPath);
  const baseDir = from.includes('/') ? from.slice(0, from.lastIndexOf('/')) : '';
  const resolvedSegments = normalizeSegments([...baseDir.split('/'), ...importPath.split('/')]);
  const baseResolved = resolvedSegments.join('/');

  const candidates = [
    baseResolved,
    `${baseResolved}.ts`,
    `${baseResolved}.tsx`,
    `${baseResolved}.js`,
    `${baseResolved}.jsx`,
    `${baseResolved}.mjs`,
    `${baseResolved}.cjs`,
    `${baseResolved}.json`,
    `${baseResolved}.css`,
    `${baseResolved}.scss`,
    `${baseResolved}.sass`,
    `${baseResolved}.less`,
    `${baseResolved}.svg`,
    `${baseResolved}.png`,
    `${baseResolved}.jpg`,
    `${baseResolved}.jpeg`,
    `${baseResolved}.gif`,
    `${baseResolved}.webp`,
    `${baseResolved}/index.ts`,
    `${baseResolved}/index.tsx`,
    `${baseResolved}/index.js`,
    `${baseResolved}/index.jsx`,
  ];

  for (const candidate of candidates) {
    const normalized = normalizeProjectPath(candidate);
    if (fileSet.has(normalized)) return normalized;
  }

  return null;
};

const findImportedModuleForSymbol = (source: string, symbol: string): string | null => {
  const defaultImportRegex = /import\s+([A-Za-z_$][\w$]*)\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of source.matchAll(defaultImportRegex)) {
    if (match[1] === symbol) return match[2] ?? null;
  }

  const namespaceImportRegex = /import\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of source.matchAll(namespaceImportRegex)) {
    if (match[1] === symbol) return match[2] ?? null;
  }

  const namedImportRegex = /import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]/g;
  for (const match of source.matchAll(namedImportRegex)) {
    const specifiers = (match[1] ?? '').split(',').map((part) => part.trim()).filter(Boolean);
    for (const specifier of specifiers) {
      const [imported, aliased] = specifier.split(/\s+as\s+/).map((s) => s.trim());
      const localName = aliased || imported;
      if (localName === symbol) return match[2] ?? null;
    }
  }

  return null;
};

const getBaseName = (path: string) => {
  const normalized = normalizeProjectPath(path);
  const idx = normalized.lastIndexOf('/');
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
};

const scoreQuickOpenPath = (path: string, query: string): number => {
  const normalizedPath = normalizeProjectPath(path).toLowerCase();
  const baseName = getBaseName(path).toLowerCase();
  const q = query.trim().toLowerCase();
  if (!q) return 1;

  const tokens = q.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return 1;
  if (tokens.some((token) => !normalizedPath.includes(token))) return -1;

  let score = 0;
  for (const token of tokens) {
    if (baseName === token) score += 150;
    else if (baseName.startsWith(token)) score += 90;
    else if (baseName.includes(token)) score += 45;
    else if (normalizedPath.includes(`/${token}`)) score += 25;
    else score += 10;
  }

  // Prefer shorter paths when relevance is equal.
  score -= normalizedPath.length * 0.01;
  return score;
};

export function EditorPanel() {
  const {
    fileTree,
    openFiles,
    activeFilePath,
    updateFileContent,
    saveFile,
    loadFileTree,
    pendingRevealLine,
    pendingRevealColumn,
    clearPendingReveal,
    openFile,
  } = useFilesStore();
  const sessionId = useSessionStore((s) => s.projectId);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const importNavigationDisposableRef = useRef<{ dispose(): void } | null>(null);
  const [fileTreeWidth, setFileTreeWidth] = useState(180);
   const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark');

  const [leftTab, setLeftTab] = useState<'files' | 'search'>('files');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchCaseSensitive, setSearchCaseSensitive] = useState(false);
  const [quickOpenVisible, setQuickOpenVisible] = useState(false);
  const [quickOpenQuery, setQuickOpenQuery] = useState('');
  const [quickOpenSelectedIndex, setQuickOpenSelectedIndex] = useState(0);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const quickOpenInputRef = useRef<HTMLInputElement | null>(null);
  const searchRequestIdRef = useRef(0);
  const hydratedModelsRef = useRef<Set<string>>(new Set());
  const indexedFilesRef = useRef<Set<string>>(new Set());
  const openFilesRef = useRef(openFiles);

  useEffect(() => {
    openFilesRef.current = openFiles;
  }, [openFiles]);

  useEffect(() => {
    const monaco = monacoRef.current;
    if (!monaco) return;

    hydratedModelsRef.current.clear();
    indexedFilesRef.current.clear();

    for (const model of monaco.editor.getModels()) {
      const uri = model.uri.toString();

      if (
        uri === 'file:///monaco/ambient/react-vite.d.ts' ||
        uri === 'file:///monaco/ambient/react-vite.js.d.ts'
      ) {
        continue;
      }

      model.dispose();
    }
  }, [sessionId]);
  
  const flattenFiles = useCallback((entries: FileEntry[]): string[] => {
    const out: string[] = [];
    const stack = [...entries];
    while (stack.length > 0) {
      const current = stack.pop();
      if (!current) continue;
      if (current.is_directory) {
        if (current.children?.length) stack.push(...current.children);
      } else {
        out.push(current.path);
      }
    }
    return out;
  }, []);

  const handleFileTreeResize = useCallback((delta: number) => {
    setFileTreeWidth((w: number) => Math.min(FILE_TREE_MAX, Math.max(FILE_TREE_MIN, w + delta)));
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

  const projectFiles = useMemo(() => {
    return flattenFiles(fileTree)
      .map((path: string) => normalizeProjectPath(path))
      .sort((a: string, b: string) => a.localeCompare(b));
  }, [fileTree, flattenFiles]);

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
    const monaco = monacoRef.current;
    if (!monaco || !sessionId || fileTree.length === 0) return;
  
    let cancelled = false;
  
    const files = flattenFiles(fileTree)
      .map((p: string) => normalizeProjectPath(p))
      .filter((p: string) => /\.(ts|tsx|js|jsx|mjs|cjs|json|css|scss|sass|less)$/.test(p));

    // Ensure module paths exist in Monaco immediately to avoid transient
    // "Cannot find module" diagnostics while file contents are still loading.
    for (const path of files) {
      const uri = monaco.Uri.parse(toMonacoUri(path));
      if (monaco.editor.getModel(uri)) continue;
      monaco.editor.createModel('', getLanguage(path), uri);
    }
  
    const hydrateModels = async () => {
      const tasks = files.map(async (path: string) => {
        const uri = toMonacoUri(path);
        if (hydratedModelsRef.current.has(uri) || openFilesRef.current.has(path)) return;
  
        try {
          const content = await fetchFileContent(sessionId, path);
          if (cancelled) return;

          const model = monaco.editor.getModel(monaco.Uri.parse(uri));
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
  }, [sessionId, fileTree, flattenFiles]);
  
  useEffect(() => {
    indexedFilesRef.current = new Set(flattenFiles(fileTree).map((path: string) => normalizeProjectPath(path)));
  }, [fileTree, flattenFiles]);

  const performSearch = useCallback(async () => {
    if (!sessionId) return;
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults([]);
      return;
    }

    const requestId = ++searchRequestIdRef.current;
    setSearchBusy(true);
    setSearchResults([]);

    try {
      const results = await searchFiles(sessionId, query, {
        caseSensitive: searchCaseSensitive,
        maxResults: 2000,
        maxHitsPerFile: 200,
      });
      if (searchRequestIdRef.current !== requestId) return;
      setSearchResults(results);
    } finally {
      if (searchRequestIdRef.current === requestId) setSearchBusy(false);
    }
  }, [
    searchCaseSensitive,
    searchQuery,
    sessionId,
  ]);

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

  const handleEditorMount = useCallback((monaco: Monaco) => {
    try {
      monacoRef.current = monaco;
      const tsDefaults = monaco.languages.typescript.typescriptDefaults;
      const jsDefaults = monaco.languages.typescript.javascriptDefaults;

      const sharedCompilerOptions: Parameters<typeof tsDefaults.setCompilerOptions>[0] = {
        // Mirror frontend/tsconfig.app.json so Monaco diagnostics match the real build.
        target: monaco.languages.typescript.ScriptTarget.ES2020,
        module: monaco.languages.typescript.ModuleKind.ESNext,
        // Vite uses TS "bundler" module resolution (not NodeNext).
        moduleResolution: monaco.languages.typescript.ModuleResolutionKind.Bundler,
        jsx: monaco.languages.typescript.JsxEmit.ReactJSX,
        allowJs: true,
        allowNonTsExtensions: true,
        allowImportingTsExtensions: true,
        esModuleInterop: true,
        isolatedModules: true,
        resolveJsonModule: true,
        useDefineForClassFields: true,
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

      // Ambient type declarations injected into Monaco so that
      // imports inside generated files (like `vite.config.ts`) can be resolved
      // even though Monaco runs without full access to `node_modules`.
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

// Minimal Vite + plugin-react declarations for Monaco.
// Monaco runs TS in a virtual environment and cannot reliably resolve node_modules.
declare module 'vite' {
  export function defineConfig(config: any): any;
}

declare module '@vitejs/plugin-react' {
  const react: any;
  export default react;
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

// Minimal Vite-like asset module declarations.
// Without these, Monaco's TS worker will complain about imports like:
//   import reactLogo from '../assets/react.svg'
declare module '*.svg' {
  const src: string;
  export default src;
}
declare module '*.png' {
  const src: string;
  export default src;
}
declare module '*.css' {
  const src: string;
  export default src;
}
declare module '*.scss' {
  const src: string;
  export default src;
}
declare module '*.sass' {
  const src: string;
  export default src;
}
declare module '*.less' {
  const src: string;
  export default src;
}
declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}
declare module '*.module.scss' {
  const classes: Record<string, string>;
  export default classes;
}
declare module '*.module.sass' {
  const classes: Record<string, string>;
  export default classes;
}
declare module '*.module.less' {
  const classes: Record<string, string>;
  export default classes;
}
declare module '*.jpg' {
  const src: string;
  export default src;
}
declare module '*.jpeg' {
  const src: string;
  export default src;
}
declare module '*.gif' {
  const src: string;
  export default src;
}
declare module '*.webp' {
  const src: string;
  export default src;
}
`;

      if (!monacoTypesInitialized) {
        // Use stable but unique virtual file names for TS and JS workers.
        // This avoids cases where both workers share the same extraLib filename.
        tsDefaults.addExtraLib(reactTypes, 'file:///monaco/ambient/react-vite.d.ts');
        jsDefaults.addExtraLib(reactTypes, 'file:///monaco/ambient/react-vite.js.d.ts');
        monacoTypesInitialized = true;
      }

      if (!monacoImportDefinitionProviderInitialized) {
        const definitionProvider = {
          provideDefinition(model: Parameters<Monaco['editor']['createModel']>[0] extends never ? never : any, position: any) {
            const word = model.getWordAtPosition(position);
            if (!word?.word) return null;

            const importPath = findImportedModuleForSymbol(model.getValue(), word.word);
            if (!importPath) return null;

            const currentPath = normalizeProjectPath(decodeURIComponent(model.uri.path));
            const targetPath = resolveRelativeImportPath(currentPath, importPath, indexedFilesRef.current);
            if (!targetPath) return null;

            const uri = monaco.Uri.parse(toMonacoUri(targetPath));
            return {
              uri,
              range: new monaco.Range(1, 1, 1, 1),
            };
          },
        };

        monaco.languages.registerDefinitionProvider('typescript', definitionProvider);
        monaco.languages.registerDefinitionProvider('javascript', definitionProvider);
        monacoImportDefinitionProviderInitialized = true;
      }
    } catch (err) {
      console.error('Monaco types init failed, will retry on next mount:', err);
      monacoTypesInitialized = false;
      monacoImportDefinitionProviderInitialized = false;
    }
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
          display: 'flex',
          flexDirection: 'column',
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
          <span>{leftTab === 'files' ? 'Files' : 'Search'}</span>

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
              title="Files"
              disabled={!sessionId}
              onClick={() => {
                if (!sessionId) return;
                setLeftTab('files');
              }}
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
              <Files size={13} />
            </button>

            <button
              title="Search in files (Ctrl+Shift+F)"
              disabled={!sessionId}
              onClick={() => {
                if (!sessionId) return;
                setLeftTab('search');
                setTimeout(() => searchInputRef.current?.focus(), 0);
              }}
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
              <Search size={13} />
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

        {leftTab === 'files' ? (
          <div style={{ flex: 1, overflow: 'auto' }}>
            <FileTree />
          </div>
        ) : (
          <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 10, flex: 1, overflow: 'hidden' }}>
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') performSearch();
              }}
              placeholder="Search in files..."
              style={{
                width: '100%',
                background: 'var(--bg)',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '8px 10px',
                outline: 'none',
                fontSize: 13,
              }}
            />

            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                onClick={performSearch}
                disabled={searchBusy || !sessionId}
                style={{
                  padding: '7px 10px',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: 'var(--bg)',
                  cursor: searchBusy ? 'not-allowed' : 'pointer',
                  color: 'var(--text)',
                  opacity: searchBusy ? 0.6 : 1,
                  whiteSpace: 'nowrap',
                  fontSize: 12,
                }}
                title="Search"
              >
                {searchBusy ? 'Searching…' : 'Search'}
              </button>

              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, color: 'var(--text-dim)' }}>
                <input
                  type="checkbox"
                  checked={searchCaseSensitive}
                  onChange={(e) => setSearchCaseSensitive(e.target.checked)}
                />
                Case sensitive
              </label>

              <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-dim)' }}>
                {searchResults.length ? `${searchResults.reduce((a: number, r: SearchResult) => a + r.hits.length, 0)} matches` : ' '}
              </div>
            </div>

            <div style={{ flex: 1, overflow: 'auto', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
              {searchBusy ? (
                <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>Searching…</div>
              ) : searchResults.length === 0 ? (
                <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '8px 0' }}>
                  No results. Try another query.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {searchResults.map((r: SearchResult) => (
                    <div key={r.path} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-dim)', marginBottom: 8 }}>
                        {r.path} ({r.hits.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {r.hits.map((h: { line: number; column: number; preview: string }, idx: number) => (
                          <button
                            key={`${r.path}:${h.line}:${h.column}:${idx}`}
                            onClick={() => {
                              openFile(r.path, h.line, h.column);
                            }}
                            style={{
                              textAlign: 'left',
                              padding: '6px 8px',
                              borderRadius: 8,
                              border: '1px solid var(--border)',
                              background: 'var(--bg)',
                              cursor: 'pointer',
                              color: 'var(--text)',
                              fontSize: 13,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                            title="Jump to match"
                          >
                            {h.line}:{h.column} {h.preview}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <Resizer direction="horizontal" onDrag={handleFileTreeResize} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        <FileTabs />

        {activeFilePath && activeContent !== undefined ? (
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <Editor
              theme={editorTheme}
              language={getLanguage(activeFilePath)}
              path={activeFilePath ? toMonacoUri(activeFilePath) : undefined}
              value={activeContent}
              onChange={handleEditorChange}
              beforeMount={handleEditorMount}
              onMount={(editor: Parameters<OnMount>[0]) => {
                editorRef.current = editor;
                const monaco = monacoRef.current;
                if (monaco) {
                  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyP, () => {
                    setQuickOpenVisible(true);
                    setQuickOpenQuery('');
                    setQuickOpenSelectedIndex(0);
                    setTimeout(() => quickOpenInputRef.current?.focus(), 0);
                  });
                }
                importNavigationDisposableRef.current?.dispose();
                importNavigationDisposableRef.current = editor.onMouseDown((event: any) => {
                  const browserEvent = event?.event;
                  const isCtrlOrCmd = Boolean(browserEvent?.ctrlKey || browserEvent?.metaKey);
                  if (!isCtrlOrCmd) return;

                  const position = event?.target?.position;
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
            {sessionId ? 'Select a file to edit' : 'No project selected'}
          </div>
        )}

        {quickOpenVisible && (
          <div
            onMouseDown={() => setQuickOpenVisible(false)}
            style={{
              position: 'absolute',
              inset: 0,
              zIndex: 40,
              background: 'rgba(0, 0, 0, 0.15)',
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'center',
              paddingTop: 28,
            }}
          >
            <div
              onMouseDown={(e: any) => e.stopPropagation()}
              style={{
                width: 'min(700px, calc(100% - 40px))',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 10,
                boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
                overflow: 'hidden',
              }}
            >
              <input
                ref={quickOpenInputRef}
                value={quickOpenQuery}
                onChange={(e: any) => {
                  setQuickOpenQuery(e.target.value);
                  setQuickOpenSelectedIndex(0);
                }}
                onKeyDown={(e: any) => {
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
                }}
                placeholder="Type a file name (Ctrl+P)"
                style={{
                  width: '100%',
                  border: 'none',
                  borderBottom: '1px solid var(--border)',
                  outline: 'none',
                  background: 'var(--surface)',
                  color: 'var(--text)',
                  padding: '10px 12px',
                  fontSize: 14,
                }}
              />

              <div style={{ maxHeight: 320, overflow: 'auto' }}>
                {quickOpenResults.length === 0 ? (
                  <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 13 }}>
                    No matching files
                  </div>
                ) : (
                  quickOpenResults.map((path: string, idx: number) => {
                    const isSelected = idx === quickOpenSelectedIndex;
                    return (
                      <button
                        key={path}
                        onMouseEnter={() => setQuickOpenSelectedIndex(idx)}
                        onMouseDown={(e: any) => {
                          e.preventDefault();
                          openQuickOpenFile(path);
                        }}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          border: 'none',
                          borderBottom: '1px solid var(--border)',
                          background: isSelected ? 'var(--bg)' : 'transparent',
                          color: 'var(--text)',
                          padding: '8px 12px',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 2,
                        }}
                      >
                        <span style={{ fontSize: 13 }}>{getBaseName(path)}</span>
                        <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{path}</span>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}