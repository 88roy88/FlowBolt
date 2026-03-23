/** Storage keys for FLAPI authorization tokens in localStorage. */
export const FLAPI_API_TOKEN_STORAGE_KEY = 'flowbolt.flapiApiToken';

export function readFlapiApiAuthorization(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  const raw = window.localStorage.getItem(FLAPI_API_TOKEN_STORAGE_KEY);
  const trimmed = raw?.trim();
  return trimmed || undefined;
}
