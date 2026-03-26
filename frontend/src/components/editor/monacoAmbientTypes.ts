/** Virtual URIs for Monaco extra libs (must match addExtraLib calls). */
export const MONACO_REACT_VITE_DTS_URI = 'file:///monaco/ambient/react-vite.d.ts';
export const MONACO_REACT_VITE_JS_DTS_URI = 'file:///monaco/ambient/react-vite.js.d.ts';

/**
 * Ambient type declarations injected into Monaco so that
 * imports inside generated files (like `vite.config.ts`) can be resolved
 * even though Monaco runs without full access to `node_modules`.
 */
export function getMonacoReactViteAmbientSource(): string {
  return `
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
}
