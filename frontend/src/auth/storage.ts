/**
 * Credentials storage in localStorage.
 *
 * Stores the full AuthCredentials JSON blob. Only auth_token is used for requests.
 */

import { authConfig } from './config';
import type { AuthCredentials } from './types';

/** Legacy token key from older builds - migrated once into authConfig.storageKey */
const LEGACY_TOKEN_KEY = 'flowbolt.dataSourceApiToken';

function parseStoredCredentials(raw: string): AuthCredentials | null {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return null;
    const token = (parsed as AuthCredentials).auth_token;
    return typeof token === 'string' && token.trim() ? (parsed as AuthCredentials) : null;
  } catch {
    return null;
  }
}

function parseExpiryTimestamp(creds: AuthCredentials): number | null {
  for (const key of ['expiresAt', 'expiration', 'tokenExpiry']) {
    const val = (creds as Record<string, unknown>)[key];
    if (typeof val === 'string' && val.trim()) {
      const ms = Date.parse(val.trim());
      return Number.isFinite(ms) ? ms : null;
    }
  }
  return null;
}

function migrateLegacyToken(): AuthCredentials | null {
  if (typeof window === 'undefined') return null;
  try {
    const legacy = window.localStorage.getItem(LEGACY_TOKEN_KEY)?.trim();
    if (!legacy) return null;

    const creds: AuthCredentials = { auth_token: legacy };
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds));
    window.localStorage.removeItem(LEGACY_TOKEN_KEY);
    return creds;
  } catch {
    return null;
  }
}

export const credentialsStore = {
  /** Read stored credentials from localStorage */
  read(): AuthCredentials | null {
    if (typeof window === 'undefined') return null;
    try {
      const raw = window.localStorage.getItem(authConfig.storageKey);
      if (raw) {
        const parsed = parseStoredCredentials(raw);
        if (parsed?.auth_token) return parsed;
      }
      return migrateLegacyToken();
    } catch {
      return null;
    }
  },

  /** Save credentials to localStorage */
  save(credentials: AuthCredentials): void {
    try {
      window.localStorage.setItem(authConfig.storageKey, JSON.stringify(credentials));
      try {
        window.localStorage.removeItem(LEGACY_TOKEN_KEY);
      } catch {
        /* ignore */
      }
    } catch {
      throw new Error('Failed to persist auth credentials');
    }
  },

  /** Clear stored credentials */
  clear(): void {
    try {
      window.localStorage.removeItem(authConfig.storageKey);
      window.localStorage.removeItem(LEGACY_TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },

  /**
   * Get the access token if valid (not expired).
   *
   * This is the only value sent to the backend via Authorization header.
   */
  getValidToken(): string | undefined {
    if (typeof window === 'undefined') return undefined;
    try {
      const creds = this.read();
      const token = creds?.auth_token?.trim();
      if (!token) return undefined;

      const expiry = creds ? parseExpiryTimestamp(creds) : null;
      if (expiry !== null && Date.now() >= expiry) return undefined;

      return token;
    } catch {
      return undefined;
    }
  },
};
