function envBool(v: string | undefined, defaultValue: boolean): boolean {
  if (v === undefined || v === '') return defaultValue;
  return v === 'true' || v === '1';
}

function envInt(v: string | undefined, defaultValue: number): number {
  if (v === undefined || v === '') return defaultValue;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : defaultValue;
}

export type AuthRuntimeConfig = {
  /** localStorage key for the JSON auth blob (default `Auth`). */
  storageKey: string;
  /** Full URL opened in the login popup when not using the mock authenticator. */
  providerUrl: string;
  /**
   * Target origin for postMessage to the popup. Defaults to the origin of `providerUrl`.
   * Use `*` only if the provider cannot be restricted to a single origin.
   */
  postMessageTargetOrigin: string;
  pollIntervalMs: number;
  popupTimeoutMs: number;
  useMock: string;
  mockAuthToken: string;
  mockUserId: string;
  mockUserName: string;
  /** Navigated when interactive login fails or repeated 401 after refresh. */
  loginFallbackUrl: string;
};

function readConfig(): AuthRuntimeConfig {
  const providerUrl = (import.meta.env.VITE_AUTH_PROVIDER_URL as string | undefined)?.trim() ?? '';
  const derivedOrigin = (() => {
    try {
      return providerUrl ? new URL(providerUrl).origin : '';
    } catch {
      return '';
    }
  })();
  const explicitOrigin = (import.meta.env.VITE_AUTH_POST_MESSAGE_TARGET as string | undefined)?.trim();

  return {
    storageKey: (import.meta.env.VITE_AUTH_STORAGE_KEY as string | undefined)?.trim() || 'Auth',
    providerUrl,
    postMessageTargetOrigin: explicitOrigin || derivedOrigin || '*',
    pollIntervalMs: envInt(import.meta.env.VITE_AUTH_POLL_INTERVAL_MS as string | undefined, 500),
    popupTimeoutMs: envInt(import.meta.env.VITE_AUTH_POPUP_TIMEOUT_MS as string | undefined, 300_000),
    useMock: (import.meta.env.VITE_AUTH_MOCK as string | undefined)?.trim() ?? '',
    mockAuthToken: (import.meta.env.VITE_AUTH_MOCK_TOKEN as string | undefined)?.trim() || 'mock-auth-token',
    mockUserId: (import.meta.env.VITE_AUTH_MOCK_USER_ID as string | undefined)?.trim() || 'mock-user',
    mockUserName: (import.meta.env.VITE_AUTH_MOCK_USER_NAME as string | undefined)?.trim() || 'Mock User',
    loginFallbackUrl: (import.meta.env.VITE_AUTH_LOGIN_FALLBACK_URL as string | undefined)?.trim() || '/',
  };
}

export const authConfig = readConfig();

export function isAuthMockMode(): boolean {
  return envBool(authConfig.useMock, false);
}

export function isAuthProviderConfigured(): boolean {
  return Boolean(authConfig.providerUrl);
}
