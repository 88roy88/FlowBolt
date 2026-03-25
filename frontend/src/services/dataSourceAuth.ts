/** Storage key for data-source authorization token in localStorage. */
export const DATA_SOURCE_API_TOKEN_STORAGE_KEY = 'flowbolt.dataSourceApiToken';

export function readDataSourceAuthorization(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  const raw = window.localStorage.getItem(DATA_SOURCE_API_TOKEN_STORAGE_KEY);
  const trimmed = raw?.trim();
  return trimmed || undefined;
}
