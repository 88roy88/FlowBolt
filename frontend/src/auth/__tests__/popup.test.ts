import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { PopupAuthenticator, PopupBlockedError } from '../popup';
import type { AuthConfig } from '../config';

const UNIQUE_ID = 'https://issuer.example/claims/UniqueID';

const config: AuthConfig = {
  storageKey: 'Auth',
  cookieName: 'flow44_token',
  providerUrl: 'https://sso.example',
  postMessageTarget: '*',
  pollIntervalMs: 500,
  popupTimeoutMs: 300_000,
  useIframe: false,
};

let messageListener: ((e: { source: unknown; data: unknown }) => void) | undefined;

function makePopup() {
  return { closed: false, focus: vi.fn(), close: vi.fn(), postMessage: vi.fn() };
}

function installWindow() {
  messageListener = undefined;
  vi.stubGlobal('window', {
    open: vi.fn(),
    addEventListener: vi.fn((type: string, cb: typeof messageListener) => {
      if (type === 'message') messageListener = cb;
    }),
    removeEventListener: vi.fn(),
  });
}

const validMessage = (popup: unknown) => ({
  source: popup,
  data: { message: 'delivercredentials', auth_token: 'tok', [UNIQUE_ID]: 'u', exp: 1 },
});

beforeEach(() => {
  vi.useFakeTimers();
  installWindow();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('PopupAuthenticator.acquireCredentials', () => {
  it('throws when the provider URL is not configured', async () => {
    const auth = new PopupAuthenticator({ ...config, providerUrl: '' });
    await expect(auth.acquireCredentials()).rejects.toThrow(/provider url is not configured/i);
  });

  it('throws PopupBlockedError when the popup cannot open', async () => {
    vi.mocked(window.open).mockReturnValue(null);
    await expect(new PopupAuthenticator(config).acquireCredentials()).rejects.toBeInstanceOf(
      PopupBlockedError,
    );
  });

  it('throws PopupBlockedError when focus is blocked', async () => {
    const popup = makePopup();
    popup.focus.mockImplementation(() => { throw new Error('blocked'); });
    vi.mocked(window.open).mockReturnValue(popup as unknown as Window);
    await expect(new PopupAuthenticator(config).acquireCredentials()).rejects.toBeInstanceOf(
      PopupBlockedError,
    );
  });

  it('resolves with credentials when the popup delivers a valid message', async () => {
    const popup = makePopup();
    vi.mocked(window.open).mockReturnValue(popup as unknown as Window);

    const promise = new PopupAuthenticator(config).acquireCredentials();
    messageListener!(validMessage(popup));

    await expect(promise).resolves.toEqual({ auth_token: 'tok', userId: 'u', exp: 1 });
    expect(popup.close).toHaveBeenCalled();
  });

  it('rejects when the delivered message has no usable credentials', async () => {
    const popup = makePopup();
    vi.mocked(window.open).mockReturnValue(popup as unknown as Window);

    const promise = new PopupAuthenticator(config).acquireCredentials();
    messageListener!({ source: popup, data: { message: 'delivercredentials' } });

    await expect(promise).rejects.toThrow(/missing a valid auth_token/i);
  });

  it('ignores messages from a different source', async () => {
    const popup = makePopup();
    vi.mocked(window.open).mockReturnValue(popup as unknown as Window);

    const promise = new PopupAuthenticator(config).acquireCredentials();
    messageListener!(validMessage({ not: 'the popup' }));
    // Still pending — deliver from the real popup to settle it.
    messageListener!(validMessage(popup));

    await expect(promise).resolves.toMatchObject({ auth_token: 'tok' });
  });

  it('rejects when the user closes the popup', async () => {
    const popup = makePopup();
    vi.mocked(window.open).mockReturnValue(popup as unknown as Window);

    const promise = new PopupAuthenticator(config).acquireCredentials();
    const expectation = expect(promise).rejects.toThrow(/closed before authentication/i);
    popup.closed = true;
    await vi.advanceTimersByTimeAsync(300);
    await expectation;
  });

  it('rejects on timeout', async () => {
    const popup = makePopup();
    vi.mocked(window.open).mockReturnValue(popup as unknown as Window);

    const promise = new PopupAuthenticator(config).acquireCredentials();
    const expectation = expect(promise).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(config.popupTimeoutMs);
    await expectation;
  });
});
