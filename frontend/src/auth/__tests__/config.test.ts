import { describe, it, expect, vi, afterEach } from 'vitest';

// `authConfig` is computed once at module load, so each scenario re-imports the
// module after stubbing the relevant import.meta.env vars.
async function loadConfig(env: Record<string, string> = {}) {
  vi.resetModules();
  vi.unstubAllEnvs();
  for (const [k, v] of Object.entries(env)) vi.stubEnv(k, v);
  return import('../config');
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('authConfig defaults', () => {
  it('falls back to sane defaults when nothing is configured', async () => {
    const { authConfig, isProviderConfigured } = await loadConfig();
    expect(authConfig.storageKey).toBe('Auth');
    expect(authConfig.cookieName).toBe('flow44_token');
    expect(authConfig.providerUrl).toBe('');
    expect(authConfig.postMessageTarget).toBe('*');
    expect(authConfig.pollIntervalMs).toBe(500);
    expect(authConfig.popupTimeoutMs).toBe(300_000);
    expect(authConfig.useIframe).toBe(false);
    expect(isProviderConfigured()).toBe(false);
  });
});

describe('postMessage target resolution', () => {
  it('derives the origin from the provider URL', async () => {
    const { authConfig, isProviderConfigured } = await loadConfig({
      VITE_AUTH_PROVIDER_URL: 'https://sso.example.com/login?x=1',
    });
    expect(authConfig.providerUrl).toBe('https://sso.example.com/login?x=1');
    expect(authConfig.postMessageTarget).toBe('https://sso.example.com');
    expect(isProviderConfigured()).toBe(true);
  });

  it('prefers an explicit target over the derived origin', async () => {
    const { authConfig } = await loadConfig({
      VITE_AUTH_PROVIDER_URL: 'https://sso.example.com/login',
      VITE_AUTH_POST_MESSAGE_TARGET: 'https://override.example',
    });
    expect(authConfig.postMessageTarget).toBe('https://override.example');
  });

  it('falls back to "*" when the provider URL is unparseable', async () => {
    const { authConfig } = await loadConfig({ VITE_AUTH_PROVIDER_URL: 'not a url' });
    expect(authConfig.postMessageTarget).toBe('*');
  });
});

describe('envBool (useIframe)', () => {
  it.each([
    ['true', true],
    ['1', true],
    ['false', false],
    ['0', false],
    ['', false],
  ])('parses %j as %s', async (value, expected) => {
    const { authConfig } = await loadConfig({ VITE_AUTH_USE_IFRAME: value });
    expect(authConfig.useIframe).toBe(expected);
  });
});

describe('envInt (pollIntervalMs)', () => {
  it('uses a valid positive integer', async () => {
    const { authConfig } = await loadConfig({ VITE_AUTH_POLL_INTERVAL_MS: '1000' });
    expect(authConfig.pollIntervalMs).toBe(1000);
  });

  it.each(['0', '-5', 'abc', ''])('falls back to the default for %j', async (value) => {
    const { authConfig } = await loadConfig({ VITE_AUTH_POLL_INTERVAL_MS: value });
    expect(authConfig.pollIntervalMs).toBe(500);
  });
});

describe('custom storage/cookie keys', () => {
  it('honors overrides and trims them', async () => {
    const { authConfig } = await loadConfig({
      VITE_AUTH_STORAGE_KEY: '  MyKey  ',
      VITE_AUTH_COOKIE_NAME: '  my_cookie  ',
    });
    expect(authConfig.storageKey).toBe('MyKey');
    expect(authConfig.cookieName).toBe('my_cookie');
  });
});
