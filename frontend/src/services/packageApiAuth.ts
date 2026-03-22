/** Same key the host app uses for FLAPI / package-api tokens (mirrors production localStorage). */
export const PACKAGE_API_TOKEN_STORAGE_KEY = 'flowbolt.packageApiToken';

export function readPackageApiAuthorization(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  const raw = window.localStorage.getItem(PACKAGE_API_TOKEN_STORAGE_KEY);
  const trimmed = raw?.trim();
  return trimmed || undefined;
}
