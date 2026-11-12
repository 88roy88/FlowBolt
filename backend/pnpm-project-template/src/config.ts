/** Base URL for backend API calls. Empty in dev (proxied), absolute in export. */
export const API_BASE = import.meta.env.VITE_API_BASE || '';

export const PROJECT_ID: string = import.meta.env.VITE_PROJECT_ID || '';
export const APP_MODE: string = import.meta.env.VITE_APP_MODE || '';
