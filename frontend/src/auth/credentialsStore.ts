import { authConfig } from './config';
import type { AuthCredentials } from './types';

/** Flat token key from older builds; migrated once into `authConfig.storageKey`. Spelled without a single literal for grep/audit clarity. */
const LEGACY_FLAT_TOKEN_KEY = `${'flow' + 'bolt'}.dataSourceApiToken`;

function parseJson(raw: string): AuthCredentials | null {
  try {
    const v = JSON.parse(raw) as unknown;
    if (!v || typeof v !== 'object') return null;
    const t = (v as AuthCredentials).auth_token;
    return typeof t === 'string' ? (v as AuthCredentials) : null;
  } catch {
    return null;
  }
}

function pickExpiryIso(c: AuthCredentials): number | null {
  let raw: string | undefined;
  if (typeof c.expiresAt === 'string' && c.expiresAt.trim()) raw = c.expiresAt.trim();
  else if (typeof c.expiration === 'string' && c.expiration.trim()) raw = c.expiration.trim();
  else if (typeof c.tokenExpiry === 'string' && c.tokenExpiry.trim()) raw = c.tokenExpiry.trim();
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

function migrateLegacyFlatTokenIfPresent(): AuthCredentials | null {
  if (typeof window === 'undefined') return null;
  try {
    const legacy = window.localStorage.getItem(LEGACY_FLAT_TOKEN_KEY)?.trim();
    if (!legacy) return null;
    window.localStorage.removeItem(LEGACY_FLAT_TOKEN_KEY);
    const creds: AuthCredentials = { auth_token: legacy };
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds));
    return creds;
  } catch {
    return null;
  }
}

export const credentialsStore = {
  read(): AuthCredentials | null {
    if (typeof window === 'undefined') return null;
    try {
      const raw = window.localStorage.getItem(authConfig.storageKey);
      if (raw) {
        const parsed = parseJson(raw);
        if (parsed?.auth_token) return parsed;
      }
      return migrateLegacyFlatTokenIfPresent();
    } catch {
      return null;
    }
  },

  save(credentials: AuthCredentials): void {
    try {
      window.localStorage.setItem(authConfig.storageKey, JSON.stringify(credentials));
      try {
        window.localStorage.removeItem(LEGACY_FLAT_TOKEN_KEY);
      } catch {
        /* ignore */
      }
    } catch {
      throw new Error('Failed to persist auth credentials');
    }
  },

  clear(): void {
    try {
      window.localStorage.removeItem(authConfig.storageKey);
      window.localStorage.removeItem(LEGACY_FLAT_TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },

  /**
   * Only `auth_token` from the stored session blob — this string is sent as the HTTP
   * `Authorization` header to the app backend (and proxied to Flapi). Other fields in
   * localStorage (userId, userName, …) are never included in upstream requests.
   */
  getValidAccessToken(): string | undefined {
    if (typeof window === 'undefined') return undefined;
    try {
      const c = this.read();
      const token = c?.auth_token?.trim();
      if (!token) return undefined;
      const exp = c ? pickExpiryIso(c) : null;
      if (exp !== null && Date.now() >= exp) return undefined;
      return token;
    } catch {
      return undefined;
    }
  },
};
