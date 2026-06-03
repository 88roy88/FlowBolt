import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { credentialsStore } from '../storage';
import { authConfig } from '../config';
import type { AuthCredentials } from '../types';

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

const future = Math.floor(Date.now() / 1000) + 3600;
const past = Math.floor(Date.now() / 1000) - 3600;

function creds(overrides: Partial<AuthCredentials> = {}): AuthCredentials {
  return { auth_token: 'tok-123', userId: 'user-42', exp: future, ...overrides };
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
    expect(JSON.parse(raw!).auth_token).toBe('tok-123');
  });

  it('writes a cookie carrying the token with an Expires derived from exp', () => {
    credentialsStore.save(creds());
    const cookie = cookieWrites.at(-1)!;
    expect(cookie).toContain(`${authConfig.cookieName}=tok-123`);
    expect(cookie).toContain('Expires=');
    expect(cookie).not.toContain('Secure'); // http: in this fake
  });

  it('marks the cookie Secure on https', () => {
    installDom('https:');
    credentialsStore.save(creds());
    expect(cookieWrites.at(-1)!).toContain('Secure');
  });
});

describe('credentialsStore.read', () => {
  beforeEach(() => installDom());

  it('returns the stored credentials', () => {
    credentialsStore.save(creds());
    expect(credentialsStore.read()?.auth_token).toBe('tok-123');
  });

  it('returns null for invalid JSON', () => {
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
    expect(credentialsStore.getValidToken()).toBe('tok-123');
  });

  it('returns undefined for an expired credential', () => {
    credentialsStore.save(creds({ exp: past }));
    expect(credentialsStore.getValidToken()).toBeUndefined();
  });

  it('treats a credential without an exp as valid', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 'tok' }));
    expect(credentialsStore.getValidToken()).toBe('tok');
  });

  it('returns undefined when nothing is stored', () => {
    expect(credentialsStore.getValidToken()).toBeUndefined();
  });
});

describe('credentialsStore.clear', () => {
  beforeEach(() => installDom());

  it('removes the stored credential, expires the cookie, and dispatches an event', () => {
    const win = installDom();
    credentialsStore.save(creds());
    credentialsStore.clear();

    expect(window.localStorage.getItem(authConfig.storageKey)).toBeNull();
    expect(cookieWrites.at(-1)!).toContain('Max-Age=0');
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
