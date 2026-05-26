/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PREVIEW_API_PREFIX: string;
  readonly VITE_PREVIEW_PROXY_SEGMENT: string;
  readonly VITE_EXPORT_API_PREFIX: string;
  readonly VITE_EXPORT_PUBLISHED_SEGMENT: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
