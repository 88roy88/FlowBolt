import Cookies from 'js-cookie';
import { authConfig } from './config';
import type { AuthCredentials } from './types';
import { credentialsFromToken } from './types';

function setAuthCookie(credentials: AuthCredentials): void {
  Cookies.set(authConfig.cookieName, credentials.auth_token, {
    expires: new Date(credentials.exp * 1000),
    secure: typeof window !== 'undefined' && window.location.protocol === 'https:',
    sameSite: 'strict',
  });
}

function clearAuthCookie(): void {
  Cookies.remove(authConfig.cookieName);
}

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

const EXPIRY_MARGIN_MS = 5_000;

function isExpired(creds: AuthCredentials): boolean {
  return creds.exp * 1000 - EXPIRY_MARGIN_MS <= Date.now();
}

function readOrClearCredentials(): AuthCredentials | null {
  const creds = credentialsStore.read();
  if (!creds?.auth_token?.trim()) return null;
  if (isExpired(creds)) {
    credentialsStore.clear();
    return null;
  }
  return creds;
}

export const credentialsStore = {
  read(): AuthCredentials | null {
    if (typeof window === 'undefined') return null;
    try {
      const raw = window.localStorage.getItem(authConfig.storageKey);
      if (raw) {
        const parsed = parseStoredCredentials(raw);
        if (parsed?.auth_token) return parsed;
      }

      const cookieToken = Cookies.get(authConfig.cookieName);
      if (cookieToken) {
        const creds = credentialsFromToken(cookieToken);
        if (creds && !isExpired(creds)) {
          window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds));
          return creds;
        }
      }

      return null;
    } catch {
      return null;
    }
  },

  save(credentials: AuthCredentials): void {
    try {
      window.localStorage.setItem(authConfig.storageKey, JSON.stringify(credentials));
      setAuthCookie(credentials);
    } catch {
      throw new Error('Failed to persist auth credentials');
    }
  },

  clear(): void {
    try {
      window.localStorage.removeItem(authConfig.storageKey);
      clearAuthCookie();
      window.dispatchEvent(new Event('auth:credentials-cleared'));
    } catch {
      /* ignore */
    }
  },

  ensureCookie(): void {
    const creds = readOrClearCredentials();
    if (creds) setAuthCookie(creds);
  },

  getValidToken(): string | undefined {
    try {
      const creds = readOrClearCredentials();
      if (!creds) return undefined;
      setAuthCookie(creds);
      return creds.auth_token.trim();
    } catch {
      return undefined;
    }
  },
};
