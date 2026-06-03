import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listenForIframeCredentials } from '../iframeAuth';
import type { AuthConfig } from '../config';

const UNIQUE_ID = 'https://issuer.example/claims/UniqueID';

const config: AuthConfig = {
  storageKey: 'Auth',
  cookieName: 'flow44_token',
  providerUrl: 'https://sso.example',
  postMessageTarget: '*',
  pollIntervalMs: 500,
  popupTimeoutMs: 300_000,
  useIframe: true,
};

let messageListener: ((e: { source: unknown; data: unknown }) => void) | undefined;

function installWindow() {
  messageListener = undefined;
  vi.stubGlobal('window', {
    addEventListener: vi.fn((type: string, cb: typeof messageListener) => {
      if (type === 'message') messageListener = cb;
    }),
    removeEventListener: vi.fn(),
  });
}

function makeIframe() {
  return {
    contentWindow: { postMessage: vi.fn() },
    addEventListener: vi.fn(),
  } as unknown as HTMLIFrameElement;
}

const validData = { message: 'delivercredentials', auth_token: 'tok', [UNIQUE_ID]: 'u', exp: 1 };

beforeEach(() => {
  vi.useFakeTimers();
  installWindow();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('listenForIframeCredentials', () => {
  it('resolves with credentials from the iframe contentWindow', async () => {
    const iframe = makeIframe();
    const promise = listenForIframeCredentials(iframe, config);
    messageListener!({ source: iframe.contentWindow, data: validData });
    await expect(promise).resolves.toEqual({ auth_token: 'tok', userId: 'u', exp: 1 });
  });

  it('ignores messages from a foreign source', async () => {
    const iframe = makeIframe();
    const promise = listenForIframeCredentials(iframe, config);
    messageListener!({ source: { other: true }, data: validData });
    messageListener!({ source: iframe.contentWindow, data: validData });
    await expect(promise).resolves.toMatchObject({ auth_token: 'tok' });
  });

  it('rejects when the message has no usable credentials', async () => {
    const iframe = makeIframe();
    const promise = listenForIframeCredentials(iframe, config);
    messageListener!({ source: iframe.contentWindow, data: { message: 'delivercredentials' } });
    await expect(promise).rejects.toThrow(/missing a valid auth_token/i);
  });

  it('rejects when the abort signal fires', async () => {
    const iframe = makeIframe();
    const controller = new AbortController();
    const promise = listenForIframeCredentials(iframe, config, controller.signal);
    controller.abort();
    await expect(promise).rejects.toThrow(/cancelled/i);
  });

  it('rejects on timeout', async () => {
    const iframe = makeIframe();
    const promise = listenForIframeCredentials(iframe, config);
    const expectation = expect(promise).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(config.popupTimeoutMs);
    await expectation;
  });
});
