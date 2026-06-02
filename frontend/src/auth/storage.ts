import { authConfig } from './config';
import type { AuthCredentials } from './types';

const COOKIE_BASE = 'Path=/; SameSite=Strict';

function setAuthCookie(credentials: AuthCredentials): void {
  if (typeof document === 'undefined') return;
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  const expires = new Date(credentials.exp * 1000).toUTCString();
  document.cookie = `${authConfig.cookieName}=${credentials.auth_token}; ${COOKIE_BASE}${secure}; Expires=${expires}`;
}

function clearAuthCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${authConfig.cookieName}=; ${COOKIE_BASE}; Max-Age=0`;
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

export const credentialsStore = {
  read(): AuthCredentials | null {
    if (typeof window === 'undefined') return null;
    try {
      const raw = window.localStorage.getItem(authConfig.storageKey);
      if (raw) {
        const parsed = parseStoredCredentials(raw);
        if (parsed?.auth_token) return parsed;
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

  getValidToken(): string | undefined {
    if (typeof window === 'undefined') return undefined;
    try {
      const creds = this.read();
      const token = creds?.auth_token?.trim();
      if (!token) return undefined;

      if (creds && creds.exp * 1000 <= Date.now()) return undefined;

      return token;
    } catch {
      return undefined;
    }
  },
};
