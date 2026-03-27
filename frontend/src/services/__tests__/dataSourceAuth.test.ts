// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest';
import { readDataSourceAuthorization } from '../dataSourceAuth';
import { authConfig } from '../../auth/config';

describe('readDataSourceAuthorization', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns the same string as stored auth_token (Authorization source)', () => {
    localStorage.setItem(authConfig.storageKey, JSON.stringify({ auth_token: 'bearer-source-only' }));
    expect(readDataSourceAuthorization()).toBe('bearer-source-only');
  });

  it('returns undefined when there is no valid token', () => {
    expect(readDataSourceAuthorization()).toBeUndefined();
  });
});
