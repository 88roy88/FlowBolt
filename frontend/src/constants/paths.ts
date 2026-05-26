/**
 * Preview/export URL builders.
 *
 * Path shape: `{VITE_PREVIEW_API_PREFIX}/{projectId}/{VITE_PREVIEW_PROXY_SEGMENT}/`
 * Set segment values in `.env.development` / `.env.production` (see `.env.example`).
 */

function env(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (!value) {
    throw new Error(`Missing ${name} — set it in frontend env (see .env.example)`);
  }
  return value;
}

export function previewBasePath(projectId: string): string {
  return `${env('VITE_PREVIEW_API_PREFIX')}/${projectId}/${env('VITE_PREVIEW_PROXY_SEGMENT')}/`;
}

export function exportPublishedPath(projectId: string): string {
  return `${env('VITE_EXPORT_API_PREFIX')}/${projectId}/${env('VITE_EXPORT_PUBLISHED_SEGMENT')}/`;
}
