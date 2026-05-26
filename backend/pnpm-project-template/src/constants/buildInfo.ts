/**
 * Build metadata injected at compile time (vite.config.ts) and by Flow44 sandbox env.
 */

export type BuildEnvironment = 'prod' | 'dev';

export type BuildInfo = {
  environment: BuildEnvironment;
  version: string;
  buildDate: string;
  projectId: string | undefined;
  previewBase: string | undefined;
  exportBase: string | undefined;
  apiBase: string | undefined;
};

function optionalEnv(name: keyof ImportMetaEnv): string | undefined {
  const value = import.meta.env[name];
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

/** prod when built/served for publish; dev for Vite dev server */
export const BUILD_ENVIRONMENT: BuildEnvironment = import.meta.env.PROD ? 'prod' : 'dev';

export const APP_VERSION = import.meta.env.VITE_APP_VERSION || '0.0.0';

export const BUILD_DATE = import.meta.env.VITE_BUILD_DATE || '';

export const PROJECT_ID = optionalEnv('VITE_PROJECT_ID');

export const PREVIEW_BASE = optionalEnv('VITE_PREVIEW_BASE');

export const EXPORT_BASE = optionalEnv('VITE_EXPORT_BASE');

export const API_BASE = optionalEnv('VITE_API_BASE');

export function getBuildInfo(): BuildInfo {
  return {
    environment: BUILD_ENVIRONMENT,
    version: APP_VERSION,
    buildDate: BUILD_DATE,
    projectId: PROJECT_ID,
    previewBase: PREVIEW_BASE,
    exportBase: EXPORT_BASE,
    apiBase: API_BASE,
  };
}
