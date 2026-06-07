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

  it('writes a cookie carrying the token with an expiry derived from exp', () => {
    credentialsStore.save(creds());
    const cookie = cookieWrites.at(-1)!;
    expect(cookie).toContain(`${authConfig.cookieName}=tok-123`);
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

describe('credentialsStore.ensureCookie', () => {
  beforeEach(() => installDom());

  it('re-writes the cookie when a valid credential is in localStorage but no cookie was written', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds()));
    expect(cookieWrites).toHaveLength(0);

    credentialsStore.ensureCookie();

    expect(cookieWrites.at(-1)!).toContain(`${authConfig.cookieName}=tok-123`);
  });

  it('is a no-op when the stored credential is expired', () => {
    window.localStorage.setItem(authConfig.storageKey, JSON.stringify(creds({ exp: past })));
    credentialsStore.ensureCookie();
    expect(cookieWrites).toHaveLength(0);
  });

  it('is a no-op when nothing is stored', () => {
    credentialsStore.ensureCookie();
    expect(cookieWrites).toHaveLength(0);
  });

  it('does not re-write the cookie when one is already present', () => {
    credentialsStore.save(creds());
    const writesBefore = cookieWrites.length;
    credentialsStore.ensureCookie();
    expect(cookieWrites).toHaveLength(writesBefore);
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
