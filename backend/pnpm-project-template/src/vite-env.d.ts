/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Flow44 project id — injected by sandbox env */
  readonly VITE_PROJECT_ID: string;
  /** Full preview base incl. project id, e.g. `/api/preview/{id}/proxy/` */
  readonly VITE_PREVIEW_BASE: string;
  /** Full publish base incl. project id, e.g. `/api/export/{id}/published/` */
  readonly VITE_EXPORT_BASE: string;
  readonly VITE_API_BASE: string;
  /** App semver from package.json — injected at build time */
  readonly VITE_APP_VERSION: string;
  /** ISO timestamp — injected when Vite config loads */
  readonly VITE_BUILD_DATE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
