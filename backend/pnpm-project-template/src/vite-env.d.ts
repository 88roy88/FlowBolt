/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PREVIEW_BASE: string;
  readonly VITE_EXPORT_BASE: string;
  readonly VITE_API_BASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
