// @vitest-environment jsdom
/**
 * Sanity checks: JSON blob under storage key, only auth_token used for API auth,
 * expiry handling, legacy flat-key migration.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { credentialsStore } from '../credentialsStore';
import { authConfig } from '../config';

const LEGACY_KEY = 'flowbolt.dataSourceApiToken';

describe('credentialsStore', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('getValidAccessToken returns token when blob has auth_token but no expiry fields', () => {
    localStorage.setItem(
      authConfig.storageKey,
      JSON.stringify({
        auth_token: 'session-token',
        userId: 'uid',
        userName: 'Pat',
      }),
    );
    expect(credentialsStore.getValidAccessToken()).toBe('session-token');
  });

  it('getValidAccessToken is undefined when token missing or JSON invalid', () => {
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ userId: 'x' }));
    expect(credentialsStore.getValidAccessToken()).toBeUndefined();

    localStorage.setItem(authConfig.storageKey, 'not-json');
    expect(credentialsStore.getValidAccessToken()).toBeUndefined();
  });

  it('getValidAccessToken rejects expired sessions (expiresAt)', () => {
    const past = new Date(Date.now() - 60_000).toISOString();
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 't', expiresAt: past }));
    expect(credentialsStore.getValidAccessToken()).toBeUndefined();
  });

  it('getValidAccessToken accepts future expiry', () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 'ok', expiresAt: future }));
    expect(credentialsStore.getValidAccessToken()).toBe('ok');
  });

  it('getValidAccessToken reads expiration / tokenExpiry aliases', () => {
    const past = new Date(Date.now() - 60_000).toISOString();
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 't', expiration: past }));
    expect(credentialsStore.getValidAccessToken()).toBeUndefined();

    const future = new Date(Date.now() + 3600_000).toISOString();
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 'ok2', tokenExpiry: future }));
    expect(credentialsStore.getValidAccessToken()).toBe('ok2');
  });

  it('migrates legacy flat token key into JSON blob once', () => {
    localStorage.setItem(LEGACY_KEY, 'legacy-secret');
    expect(credentialsStore.read()?.auth_token).toBe('legacy-secret');
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
    expect(JSON.parse(localStorage.getItem(authConfig.storageKey)!).auth_token).toBe('legacy-secret');
  });

  it('save persists blob and removes legacy key', () => {
    localStorage.setItem(LEGACY_KEY, 'old');
    credentialsStore.save({ auth_token: 'new', userId: '1' });
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
    const parsed = JSON.parse(localStorage.getItem(authConfig.storageKey)!);
    expect(parsed.auth_token).toBe('new');
    expect(parsed.userId).toBe('1');
  });

  it('clear removes both storage keys', () => {
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 'x' }));
    localStorage.setItem(LEGACY_KEY, 'y');
    credentialsStore.clear();
    expect(localStorage.getItem(authConfig.storageKey)).toBeNull();
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it('getValidAccessToken works after legacy migration (blob has token only)', () => {
    localStorage.setItem(LEGACY_KEY, 'migrated-plain');
    expect(credentialsStore.getValidAccessToken()).toBe('migrated-plain');
  });
});
