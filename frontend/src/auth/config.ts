/**
 * Runtime authentication configuration from environment variables.
 */

function envBool(v: string | undefined, defaultValue: boolean): boolean {
  if (v === undefined || v === '') return defaultValue;
  return v === 'true' || v === '1';
}

function envInt(v: string | undefined, defaultValue: number): number {
  if (v === undefined || v === '') return defaultValue;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : defaultValue;
}

export type AuthConfig = {
  /** localStorage key for the JSON auth blob (default: "Auth") */
  storageKey: string;
  /** Full URL to open in the login popup (required for SSO) */
  providerUrl: string;
  /** postMessage targetOrigin - defaults to providerUrl origin, use "*" only if necessary */
  postMessageTarget: string;
  /** How often to poll the popup for credentials (ms) */
  pollIntervalMs: number;
  /** Popup timeout (ms) */
  popupTimeoutMs: number;
};

function readConfig(): AuthConfig {
  const providerUrl = (import.meta.env.VITE_AUTH_PROVIDER_URL as string | undefined)?.trim() ?? '';

  // Derive targetOrigin from providerUrl unless explicitly overridden
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
    postMessageTarget: explicitOrigin || derivedOrigin || '*',
    pollIntervalMs: envInt(import.meta.env.VITE_AUTH_POLL_INTERVAL_MS as string | undefined, 500),
    popupTimeoutMs: envInt(import.meta.env.VITE_AUTH_POPUP_TIMEOUT_MS as string | undefined, 300_000),
  };
}

export const authConfig = readConfig();

/** Check if auth provider URL is configured */
export function isProviderConfigured(): boolean {
  return Boolean(authConfig.providerUrl);
}
