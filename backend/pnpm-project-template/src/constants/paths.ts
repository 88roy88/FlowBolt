/**
 * Preview/export URL helpers for sandbox apps.
 * Flow44 injects resolved bases (with project id) via `.env.local` — do not hardcode paths.
 */

function env(name: keyof ImportMetaEnv): string {
  const value = import.meta.env[name];
  if (!value) {
    throw new Error(`Missing ${name} — Flow44 injects this into the workspace env`);
  }
  return value;
}

/** Current project id from sandbox env */
export function projectId(): string {
  return env('VITE_PROJECT_ID');
}

/** Preview iframe URL base, e.g. `/api/preview/{id}/proxy/` */
export function previewBasePath(): string {
  return env('VITE_PREVIEW_BASE');
}

/** Published app URL base, e.g. `/api/export/{id}/published/` */
export function exportPublishedPath(): string {
  return env('VITE_EXPORT_BASE');
}
