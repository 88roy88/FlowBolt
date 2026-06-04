import { describe, it, expect, vi, beforeEach } from 'vitest';

const { acquire } = vi.hoisted(() => ({ acquire: vi.fn() }));

vi.mock('../popup', () => ({
  PopupBlockedError: class PopupBlockedError extends Error {},
  PopupAuthenticator: vi.fn(function () { return { acquireCredentials: acquire }; }),
}));
vi.mock('../config', () => ({
  authConfig: { useIframe: false },
  isProviderConfigured: vi.fn(() => true),
}));
vi.mock('../storage', () => ({
  credentialsStore: {
    getValidToken: vi.fn(),
    save: vi.fn(),
    clear: vi.fn(),
  },
}));

import { authSession } from '../session';
import { credentialsStore } from '../storage';
import { authConfig, isProviderConfigured } from '../config';

const CREDS = { auth_token: 'new-tok', userId: 'u', exp: 999 };

beforeEach(() => {
  vi.clearAllMocks();
  (authConfig as { useIframe: boolean }).useIframe = false;
  vi.mocked(isProviderConfigured).mockReturnValue(true);
  acquire.mockResolvedValue(CREDS);
});

describe('bootstrap', () => {
  it('returns "ready" when a valid token exists', async () => {
    vi.mocked(credentialsStore.getValidToken).mockReturnValue('tok');
    await expect(authSession.bootstrap()).resolves.toBe('ready');
  });

  it('returns "needs_interactive_sign_in" when no token but provider is configured', async () => {
    vi.mocked(credentialsStore.getValidToken).mockReturnValue(undefined);
    await expect(authSession.bootstrap()).resolves.toBe('needs_interactive_sign_in');
  });

  it('throws when no token and provider is not configured', async () => {
    vi.mocked(credentialsStore.getValidToken).mockReturnValue(undefined);
    vi.mocked(isProviderConfigured).mockReturnValue(false);
    await expect(authSession.bootstrap()).rejects.toThrow(/not configured/i);
  });
});

describe('signIn (popup)', () => {
  it('acquires credentials via popup and saves them', async () => {
    await authSession.signIn();
    expect(acquire).toHaveBeenCalledOnce();
    expect(credentialsStore.save).toHaveBeenCalledWith(CREDS);
  });
});

describe('ensureFreshToken', () => {
  it('returns the cached token without refreshing', async () => {
    vi.mocked(credentialsStore.getValidToken).mockReturnValue('cached');
    await expect(authSession.ensureFreshToken()).resolves.toBe('cached');
    expect(acquire).not.toHaveBeenCalled();
  });

  it('refreshes when no cached token, then returns the fresh one', async () => {
    vi.mocked(credentialsStore.getValidToken)
      .mockReturnValueOnce(undefined) // initial check
      .mockReturnValue('new-tok'); // after refresh
    await expect(authSession.ensureFreshToken()).resolves.toBe('new-tok');
    expect(acquire).toHaveBeenCalledOnce();
    expect(credentialsStore.save).toHaveBeenCalledWith(CREDS);
  });
});

describe('refreshCredentials', () => {
  it('is single-flight: concurrent calls share one re-acquisition', async () => {
    let resolveAcquire!: (c: typeof CREDS) => void;
    acquire.mockReturnValue(new Promise((r) => { resolveAcquire = r; }));

    const p1 = authSession.refreshCredentials();
    const p2 = authSession.refreshCredentials();
    resolveAcquire(CREDS);
    await Promise.all([p1, p2]);

    expect(acquire).toHaveBeenCalledOnce();
  });

  it('in iframe mode clears credentials instead of acquiring', async () => {
    (authConfig as { useIframe: boolean }).useIframe = true;
    await authSession.refreshCredentials();
    expect(credentialsStore.clear).toHaveBeenCalledOnce();
    expect(acquire).not.toHaveBeenCalled();
  });
});

describe('signOut & hasValidSession', () => {
  it('signOut clears the stored credentials', () => {
    authSession.signOut();
    expect(credentialsStore.clear).toHaveBeenCalledOnce();
  });

  it('hasValidSession reflects the presence of a valid token', () => {
    vi.mocked(credentialsStore.getValidToken).mockReturnValue('tok');
    expect(authSession.hasValidSession()).toBe(true);
    vi.mocked(credentialsStore.getValidToken).mockReturnValue(undefined);
    expect(authSession.hasValidSession()).toBe(false);
  });
});
