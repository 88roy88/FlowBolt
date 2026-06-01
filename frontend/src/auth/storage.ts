import { authConfig } from './config';
import type { AuthCredentials } from './types';

const COOKIE_NAME = 'flow44_token';
const COOKIE_BASE = 'Path=/; SameSite=Strict';

function setAuthCookie(token: string): void {
  if (typeof document === 'undefined') return;
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `${COOKIE_NAME}=${token}; ${COOKIE_BASE}${secure}`;
}

function clearAuthCookie(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${COOKIE_NAME}=; ${COOKIE_BASE}; Max-Age=0`;
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

function parseExpiryTimestamp(creds: AuthCredentials): number | null {
  const val = (creds as Record<string, unknown>).exp;
  return typeof val === 'number' && Number.isFinite(val) ? val * 1000 : null;
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
      setAuthCookie(credentials.auth_token);
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

      const expiry = creds ? parseExpiryTimestamp(creds) : null;
      if (expiry !== null && Date.now() >= expiry) return undefined;

      return token;
    } catch {
      return undefined;
    }
  },
};
