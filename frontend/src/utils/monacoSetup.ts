import type { Monaco } from '@monaco-editor/react';

let initialized = false;

export function setupMonacoTypeScript(monaco: Monaco) {
  if (initialized) return;
  initialized = true;

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

  tsDefaults.setDiagnosticsOptions({ noSemanticValidation: false, noSyntaxValidation: false });
  jsDefaults.setDiagnosticsOptions({ noSemanticValidation: false, noSyntaxValidation: false });

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
}

const LANG_MAP: Record<string, string> = {
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

export function getLanguageForPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  return LANG_MAP[ext] ?? 'plaintext';
}
