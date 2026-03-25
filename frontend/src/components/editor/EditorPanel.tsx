import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Editor, { loader, type Monaco, type OnMount } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';

// Use local monaco-editor instead of CDN
loader.config({ monaco });
import { Download, FileCode, Search, Files, ChevronRight, Check, Loader2 } from 'lucide-react';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { downloadZip, downloadSingleHtml, fetchFileContent, searchFiles, type SearchResult } from '../../services/api';
import { Resizer } from '../layout/Resizer';
import { FileTree } from './FileTree';
import { FileTabs } from './FileTabs';
import type { FileEntry } from '../../types';

const FILE_TREE_MIN = 120;
const FILE_TREE_MAX = 400;

let monacoTypeLibDisposables: Array<{ dispose(): void }> = [];
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
    const styleId = 'editor-search-hit-highlight-style';
    if (document.getElementById(styleId)) return;
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .editor-search-hit-highlight-inline {
        background: rgba(255, 211, 77, 0.35);
        border-radius: 2px;
      }
      .editor-search-hit-highlight-line {
        background: rgba(255, 211, 77, 0.08);
      }
    `;
    document.head.appendChild(style);
  }, []);

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
  }, [projectId]);
  
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
    if (!monaco || !projectId || fileTree.length === 0) return;
  
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
          const content = await fetchFileContent(projectId, path);
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
  }, [projectId, fileTree, flattenFiles]);
  
  useEffect(() => {
    indexedFilesRef.current = new Set(flattenFiles(fileTree).map((path: string) => normalizeProjectPath(path)));
  }, [fileTree, flattenFiles]);

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
  }, [
    searchCaseSensitive,
    searchQuery,
    projectId,
  ]);

  const toggleSearchFileCollapsed = useCallback((path: string) => {
    setCollapsedSearchFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const jumpToSearchHit = useCallback((path: string, line: number, column: number) => {
    const highlightLength = Math.max(1, searchQuery.trim().length);
    const normalizedTargetPath = normalizeProjectPath(path);

    const tryReveal = (attempt: number) => {
      const editor = editorRef.current;
      const monaco = monacoRef.current;
      const activePath = useFilesStore.getState().activeFilePath;
      const normalizedActivePath = activePath ? normalizeProjectPath(activePath) : '';
      const model = editor?.getModel();

      if (!editor || !monaco || !model || normalizedActivePath !== normalizedTargetPath) {
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
      editor.setSelection(new monaco.Selection(safeLine, safeColumn, safeLine, endColumn));

      searchHighlightDecorationIdsRef.current = editor.deltaDecorations(
        searchHighlightDecorationIdsRef.current,
        [
          {
            range: new monaco.Range(safeLine, safeColumn, safeLine, endColumn),
            options: {
              inlineClassName: 'editor-search-hit-highlight-inline',
              isWholeLine: false,
            },
          },
          {
            range: new monaco.Range(safeLine, 1, safeLine, lineMaxColumn),
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
  }, [openFile, searchQuery]);

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
        // Monaco's TS worker is more stable with NodeJs resolution for virtual models.
        moduleResolution: monaco.languages.typescript.ModuleResolutionKind.NodeJs,
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
  export type ReactElement = any;
  export type ReactNode = ReactElement | string | number | boolean | null | undefined | Iterable<ReactNode>;
  export type Ref<T> = ((instance: T | null) => void) | { current: T | null } | null;
  export type RefObject<T> = { current: T | null };
  export type RefAttributes<T> = { ref?: Ref<T> };
  export type FC<P = {}> = (props: P & { children?: ReactNode }) => ReactElement | null;
  export type ForwardRefExoticComponent<P> = FC<P>;
  export type HTMLAttributes<T = Element> = Record<string, any>;
  export type ButtonHTMLAttributes<T = Element> = Record<string, any>;
  export type AnchorHTMLAttributes<T = Element> = Record<string, any>;
  export type Context<T> = { Provider: FC<{ value: T; children?: ReactNode }>; Consumer: FC<{ children: (value: T) => ReactNode }> };
  export type CSSProperties = Record<string, string | number>;
  export type SyntheticEvent<T = Element, E = Event> = {
    nativeEvent: E;
    target: EventTarget & T;
    currentTarget: EventTarget & T;
    stopPropagation(): void;
    preventDefault(): void;
  };
  export type ChangeEvent<T = Element> = SyntheticEvent<T> & { target: EventTarget & T & { value: string } };
  export type MouseEvent<T = Element, E = globalThis.MouseEvent> = SyntheticEvent<T, E>;
  export type KeyboardEvent<T = Element, E = globalThis.KeyboardEvent> = SyntheticEvent<T, E> & { key: string };
  export type DragEvent<T = Element, E = globalThis.DragEvent> = SyntheticEvent<T, E> & { dataTransfer: DataTransfer };
  export type FormEvent<T = Element> = SyntheticEvent<T>;

  export function useState<T>(initial: T | (() => T)): [T, (v: T | ((prev: T) => T)) => void];
  export function useEffect(effect: () => void | (() => void), deps?: any[]): void;
  export function useRef<T>(initial: T): { current: T };
  export function useCallback<T extends (...args: any[]) => any>(fn: T, deps: any[]): T;
  export function useMemo<T>(fn: () => T, deps: any[]): T;
  export function useContext<T>(context: Context<T>): T;
  export function createContext<T>(defaultValue: T): Context<T>;
  export function memo<T>(component: T): T;
  export function forwardRef<T, P>(render: (props: P, ref: Ref<T>) => ReactElement | null): ForwardRefExoticComponent<P & RefAttributes<T>>;
  export const StrictMode: any;

  const React: {
    StrictMode: any;
    useState: typeof useState;
    useEffect: typeof useEffect;
    useRef: typeof useRef;
    useCallback: typeof useCallback;
    useMemo: typeof useMemo;
    useContext: typeof useContext;
    createContext: typeof createContext;
    memo: typeof memo;
    forwardRef: typeof forwardRef;
  };

  namespace React {
    export type ReactElement = import('react').ReactElement;
    export type ReactNode = import('react').ReactNode;
    export type Ref<T> = import('react').Ref<T>;
    export type RefObject<T> = import('react').RefObject<T>;
    export type RefAttributes<T> = import('react').RefAttributes<T>;
    export type FC<P = {}> = import('react').FC<P>;
    export type ForwardRefExoticComponent<P> = import('react').ForwardRefExoticComponent<P>;
    export type HTMLAttributes<T = Element> = import('react').HTMLAttributes<T>;
    export type ButtonHTMLAttributes<T = Element> = import('react').ButtonHTMLAttributes<T>;
    export type AnchorHTMLAttributes<T = Element> = import('react').AnchorHTMLAttributes<T>;
    export type Context<T> = import('react').Context<T>;
    export type CSSProperties = import('react').CSSProperties;
    export type ChangeEvent<T = Element> = import('react').ChangeEvent<T>;
    export type MouseEvent<T = Element> = import('react').MouseEvent<T>;
    export type KeyboardEvent<T = Element> = import('react').KeyboardEvent<T>;
    export type DragEvent<T = Element> = import('react').DragEvent<T>;
    export type FormEvent<T = Element> = import('react').FormEvent<T>;
  }

  export default React;
}

declare module 'react-dom/client' {
  export function createRoot(container: Element): { render(element: any): void };
}

// Minimal Node + Vite declarations for Monaco.
// Monaco runs TS in a virtual environment and cannot reliably resolve node_modules.
declare const process: {
  cwd(): string;
  env: Record<string, string | undefined>;
};

declare module 'vite' {
  export interface ConfigEnv {
    command: 'build' | 'serve';
    mode: string;
    isSsrBuild?: boolean;
    isPreview?: boolean;
  }

  export interface UserConfig {
    base?: string;
    plugins?: any[];
    [key: string]: any;
  }

  export type UserConfigFn = (env: ConfigEnv) => UserConfig | Promise<UserConfig>;
  export type UserConfigExport = UserConfig | Promise<UserConfig> | UserConfigFn;

  export function defineConfig(config: UserConfigExport): UserConfigExport;
  export function loadEnv(mode: string, envDir: string, prefixes?: string | string[]): Record<string, string>;
}

declare module '@vitejs/plugin-react' {
  const react: any;
  export default react;
}

// Monaco fallback for relative module specifiers inside virtual projects.
// This suppresses false "Cannot find module './...'" diagnostics when files
// are present in the sandbox tree but TS worker resolution lags behind.
declare module './*' {
  const mod: any;
  export = mod;
}
declare module '../*' {
  const mod: any;
  export = mod;
}
declare module '../../*' {
  const mod: any;
  export = mod;
}
declare module '../../../*' {
  const mod: any;
  export = mod;
}

declare module 'react/jsx-runtime' {
  export const Fragment: any;
  export function jsx(type: any, props: any, key?: any): any;
  export function jsxs(type: any, props: any, key?: any): any;
}

interface ImportMetaEnv {
  readonly MODE: string;
  readonly BASE_URL: string;
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly SSR: boolean;
  readonly VITE_API_BASE?: string;
  readonly [key: string]: string | boolean | undefined;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
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

      // Refresh Monaco extra libs on each mount to avoid stale worker cache
      // holding old ambient declarations between project/editor reloads.
      for (const disposable of monacoTypeLibDisposables) {
        disposable.dispose();
      }
      monacoTypeLibDisposables = [
        tsDefaults.addExtraLib(reactTypes, 'file:///monaco/ambient/react-vite.d.ts'),
        jsDefaults.addExtraLib(reactTypes, 'file:///monaco/ambient/react-vite.js.d.ts'),
      ];

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
      for (const disposable of monacoTypeLibDisposables) {
        disposable.dispose();
      }
      monacoTypeLibDisposables = [];
      monacoImportDefinitionProviderInitialized = false;
    }
  }, []);

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
        <div className="flex items-center justify-between gap-2 px-3 py-[7px] border-b border-border shrink-0">
          <span className="text-[13px] font-semibold tracking-tight truncate min-w-0">
            {leftTab === 'files' ? t('editor.files') : t('editor.searchTab')}
          </span>

          <div className="flex gap-1 shrink-0">
            <button
              type="button"
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
              type="button"
              title={t('editor.files')}
              disabled={!projectId}
              onClick={() => {
                if (!projectId) return;
                setLeftTab('files');
              }}
              className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
                projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
              }`}
            >
              <Files size={13} />
            </button>

            <button
              type="button"
              title={t('editor.searchShortcutTitle')}
              disabled={!projectId}
              onClick={() => {
                if (!projectId) return;
                setLeftTab('search');
                setTimeout(() => searchInputRef.current?.focus(), 0);
              }}
              className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
                projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
              }`}
            >
              <Search size={13} />
            </button>

            <button
              type="button"
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
              placeholder={t('editor.searchInFilesPlaceholder')}
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
                disabled={searchBusy || !projectId}
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
                title={t('editor.runSearch')}
              >
                {searchBusy ? t('editor.searching') : t('editor.runSearch')}
              </button>

              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, color: 'var(--text-dim)' }}>
                <input
                  type="checkbox"
                  checked={searchCaseSensitive}
                  onChange={(e) => setSearchCaseSensitive(e.target.checked)}
                />
                {t('editor.caseSensitive')}
              </label>

              <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-dim)' }}>
                {searchResults.length
                  ? t('editor.matchesCount', {
                      count: searchResults.reduce((a: number, r: SearchResult) => a + r.hits.length, 0),
                    })
                  : ' '}
              </div>
            </div>

            <div style={{ flex: 1, overflow: 'auto', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
              {searchBusy ? (
                <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>{t('editor.searching')}</div>
              ) : searchError ? (
                <div style={{ color: 'var(--danger)', fontSize: 13, padding: '8px 0' }}>
                  {t('editor.searchFailedPrefix')}: {searchError}
                </div>
              ) : searchResults.length === 0 ? (
                <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '8px 0' }}>
                  {t('editor.noSearchResults')}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {searchResults.map((r: SearchResult) => (
                    <div key={r.path} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                      {(() => {
                        const isCollapsed = collapsedSearchFiles.has(r.path);
                        return (
                          <>
                            <button
                              onClick={() => toggleSearchFileCollapsed(r.path)}
                              style={{
                                width: '100%',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                fontSize: 12,
                                color: 'var(--text-dim)',
                                marginBottom: isCollapsed ? 0 : 8,
                                background: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                padding: 0,
                                textAlign: 'left',
                              }}
                              title={isCollapsed ? t('editor.showMatches') : t('editor.hideMatches')}
                            >
                              <ChevronRight
                                size={13}
                                style={{ transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)', transition: 'transform 120ms ease' }}
                              />
                              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {r.path} ({r.hits.length})
                              </span>
                            </button>
                            {!isCollapsed && (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                {r.hits.map((h: { line: number; column: number; preview: string }, idx: number) => (
                                  <button
                                    key={`${r.path}:${h.line}:${h.column}:${idx}`}
                                    onClick={() => {
                                      jumpToSearchHit(r.path, h.line, h.column);
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
                                    title={t('editor.jumpToMatch')}
                                  >
                                    {h.line}:{h.column} {h.preview}
                                  </button>
                                ))}
                              </div>
                            )}
                          </>
                        );
                      })()}
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
          <div style={{ flex: 1, overflow: 'hidden' }} dir="ltr">
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
            {projectId ? t('editor.selectFileToEdit') : t('editor.noProjectSelected')}
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
                placeholder={t('editor.quickOpenPlaceholder')}
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
                    {t('editor.noMatchingFiles')}
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