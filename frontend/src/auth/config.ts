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
  storageKey: string;
  providerUrl: string;
  postMessageTarget: string;
  pollIntervalMs: number;
  popupTimeoutMs: number;
};

function readConfig(): AuthConfig {
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
    postMessageTarget: explicitOrigin || derivedOrigin || '*',
    pollIntervalMs: envInt(import.meta.env.VITE_AUTH_POLL_INTERVAL_MS as string | undefined, 500),
    popupTimeoutMs: envInt(import.meta.env.VITE_AUTH_POPUP_TIMEOUT_MS as string | undefined, 300_000),
  };
}

export const authConfig = readConfig();

export function isProviderConfigured(): boolean {
  return Boolean(authConfig.providerUrl);
}
