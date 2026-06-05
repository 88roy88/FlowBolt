import Cookies from 'js-cookie';
import { authConfig } from './config';
import type { AuthCredentials } from './types';

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

  ensureCookie(): void {
    if (Cookies.get(authConfig.cookieName)) return;
    const [creds, validToken] = [this.read(), this.getValidToken()];
    if (creds && validToken) setAuthCookie(creds)
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
