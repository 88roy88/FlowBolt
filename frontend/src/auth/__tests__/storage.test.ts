import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { credentialsStore } from '../storage';
import { authConfig } from '../config';
import type { AuthCredentials } from '../types';
import { fakeJwt } from './jwt-helper';

// ---------------------------------------------------------------------------
// Lightweight DOM fakes (Vitest runs in the `node` environment — no jsdom).
// ---------------------------------------------------------------------------

function makeLocalStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    _store: store,
  };
}

let cookieWrites: string[] = [];

function installDom(protocol = 'http:') {
  const localStorage = makeLocalStorage();
  cookieWrites = [];
  const win = {
    localStorage,
    location: { protocol },
    dispatchEvent: vi.fn(),
  };
  vi.stubGlobal('window', win);
  vi.stubGlobal('localStorage', localStorage);
  vi.stubGlobal('document', {
    get cookie() {
      return cookieWrites.join('; ');
    },
    set cookie(value: string) {
      cookieWrites.push(value);
    },
  });
  return win;
}

function currentCookieToken(): string | undefined {
  const prefix = `${authConfig.cookieName}=`;
  const last = cookieWrites.filter((w) => w.startsWith(prefix)).at(-1);
  const value = last?.slice(prefix.length).split(';')[0];
  return value ? decodeURIComponent(value) : undefined;
}

function storedToken(): string | undefined {
  const raw = window.localStorage.getItem(authConfig.storageKey);
  return raw ? (JSON.parse(raw) as AuthCredentials).auth_token : undefined;
}

const future = Math.floor(Date.now() / 1000) + 3600;
const past = Math.floor(Date.now() / 1000) - 3600;

const VALID_TOKEN = fakeJwt({ userId: 'user-42', exp: future });

function creds(overrides: Partial<AuthCredentials> = {}): AuthCredentials {
  return { auth_token: VALID_TOKEN, userId: 'user-42', exp: future, ...overrides };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('credentialsStore.save', () => {
  beforeEach(() => installDom());

  it('writes the credentials JSON to localStorage under the configured key', () => {
    credentialsStore.save(creds());
    const raw = window.localStorage.getItem(authConfig.storageKey);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!).auth_token).toBe(VALID_TOKEN);
  });

  it('writes a cookie carrying the token with an expiry derived from exp', () => {
    credentialsStore.save(creds());
    const cookie = cookieWrites.at(-1)!;
    expect(cookie).toContain(`${authConfig.cookieName}=${encodeURIComponent(VALID_TOKEN)}`);
    expect(cookie).toContain('expires=');
    expect(cookie).not.toContain('secure'); // http: in this fake
  });

  it('marks the cookie secure on https', () => {
    installDom('https:');
    credentialsStore.save(creds());
    expect(cookieWrites.at(-1)!).toContain('secure');
  });
});

describe('credentialsStore.read', () => {
  beforeEach(() => installDom());

  it('returns the stored credentials from localStorage', () => {
    credentialsStore.save(creds());
    expect(credentialsStore.read()?.auth_token).toBe(VALID_TOKEN);
  });

  it('falls back to cookie when localStorage is empty', () => {
    const token = fakeJwt({ userId: 'cookie-user', exp: future });
    cookieWrites.push(`${authConfig.cookieName}=${token}`);
    const result = credentialsStore.read();
    expect(result?.userId).toBe('cookie-user');
    expect(result?.auth_token).toBe(token);
  });

  it('returns null for invalid JSON in localStorage', () => {
    window.localStorage.setItem(authConfig.storageKey, '{not json');
    expect(credentialsStore.read()).toBeNull();
  });

  it('returns null when the stored value lacks an auth_token', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify({ userId: 'u' }));
    expect(credentialsStore.read()).toBeNull();
  });

  it('returns null when nothing is stored', () => {
    expect(credentialsStore.read()).toBeNull();
  });
});

describe('credentialsStore.getValidToken', () => {
  beforeEach(() => installDom());

  it('returns the token for an unexpired credential', () => {
    credentialsStore.save(creds());
    expect(credentialsStore.getValidToken()).toBe(VALID_TOKEN);
  });

  it('returns undefined and clears for an expired credential', () => {
    const expiredToken = fakeJwt({ userId: 'user-42', exp: past });
    credentialsStore.save(creds({ auth_token: expiredToken, exp: past }));
    expect(credentialsStore.getValidToken()).toBeUndefined();
    expect(window.localStorage.getItem(authConfig.storageKey)).toBeNull();
  });

  it('ensures the cookie is set when returning a valid token', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds()));
    expect(cookieWrites).toHaveLength(0);
    credentialsStore.getValidToken();
    expect(cookieWrites.length).toBeGreaterThan(0);
  });

  it('returns undefined when nothing is stored', () => {
    expect(credentialsStore.getValidToken()).toBeUndefined();
  });
});

describe('credentialsStore.ensureCookie', () => {
  beforeEach(() => installDom());

  it('re-writes the cookie when a valid credential is in localStorage but no cookie was written', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds()));
    expect(cookieWrites).toHaveLength(0);

    credentialsStore.ensureCookie();

    expect(cookieWrites.at(-1)!).toContain(`${authConfig.cookieName}=`);
  });

  it('clears the dead session instead of planting a cookie when the credential is expired', () => {
    const win = installDom();
    const expiredToken = fakeJwt({ userId: 'user-42', exp: past });
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds({ auth_token: expiredToken, exp: past })));

    credentialsStore.ensureCookie();

    expect(window.localStorage.getItem(authConfig.storageKey)).toBeNull();
    expect(cookieWrites.every((w) => w.startsWith(`${authConfig.cookieName}=;`))).toBe(true);
    expect(win.dispatchEvent).toHaveBeenCalledOnce();
  });

  it('is a no-op when nothing is stored', () => {
    credentialsStore.ensureCookie();
    expect(cookieWrites).toHaveLength(0);
  });

  it('re-writes the cookie when one is already present, so a stale token cannot survive', () => {
    credentialsStore.save(creds());
    const writesBefore = cookieWrites.length;
    credentialsStore.ensureCookie();
    expect(cookieWrites.length).toBeGreaterThan(writesBefore);
  });

  it('plants no cookie for a token that expires inside the expiry margin', () => {
    const soon = Math.floor(Date.now() / 1000) + 2;
    window.localStorage.setItem(
      authConfig.storageKey,
      JSON.stringify(creds({ auth_token: fakeJwt({ userId: 'user-42', exp: soon }), exp: soon })),
    );
    credentialsStore.ensureCookie();
    expect(cookieWrites.every((w) => w.startsWith(`${authConfig.cookieName}=;`))).toBe(true);
  });

  it('still plants a cookie for a token that outlives the expiry margin', () => {
    const later = Math.floor(Date.now() / 1000) + 30;
    window.localStorage.setItem(
      authConfig.storageKey,
      JSON.stringify(creds({ auth_token: fakeJwt({ userId: 'user-42', exp: later }), exp: later })),
    );
    credentialsStore.ensureCookie();
    expect(currentCookieToken()).toBeDefined();
  });
});

describe('cookie / localStorage sync', () => {
  beforeEach(() => installDom());

  it('heals a stale cookie so it matches the stored credentials', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds()));
    cookieWrites.push(`${authConfig.cookieName}=stale-token-from-an-older-session`);

    credentialsStore.ensureCookie();

    expect(currentCookieToken()).toBe(VALID_TOKEN);
    expect(storedToken()).toBe(VALID_TOKEN);
  });

  it('hydrates localStorage from the cookie when only the cookie survives', () => {
    const token = fakeJwt({ userId: 'cookie-user', exp: future });
    cookieWrites.push(`${authConfig.cookieName}=${token}`);

    credentialsStore.read();

    expect(storedToken()).toBe(token);
    expect(currentCookieToken()).toBe(token);
  });

  it('leaves neither store holding a token after clear', () => {
    credentialsStore.save(creds());
    credentialsStore.clear();

    expect(storedToken()).toBeUndefined();
    expect(currentCookieToken()).toBeUndefined();
  });
});

describe('credentialsStore.clear', () => {
  beforeEach(() => installDom());

  it('removes the stored credential, expires the cookie, and dispatches an event', () => {
    const win = installDom();
    credentialsStore.save(creds());
    credentialsStore.clear();

    expect(window.localStorage.getItem(authConfig.storageKey)).toBeNull();
    expect(cookieWrites.at(-1)!.startsWith(`${authConfig.cookieName}=;`)).toBe(true);
    expect(cookieWrites.at(-1)!).toContain('expires=');
    expect(win.dispatchEvent).toHaveBeenCalledOnce();
    const event = win.dispatchEvent.mock.calls[0][0] as Event;
    expect(event.type).toBe('auth:credentials-cleared');
  });
});

describe('SSR guards (no window)', () => {
  beforeEach(() => {
    vi.stubGlobal('window', undefined);
  });

  it('read returns null', () => {
    expect(credentialsStore.read()).toBeNull();
  });

  it('getValidToken returns undefined', () => {
    expect(credentialsStore.getValidToken()).toBeUndefined();
  });
});
