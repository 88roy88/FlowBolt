import { describe, it, expect } from 'vitest';
import { isDeliverCredentialsMessage, extractAuthCredentials } from '../types';

describe('isDeliverCredentialsMessage', () => {
  it('accepts message tag (case-insensitive)', () => {
    expect(isDeliverCredentialsMessage({ message: 'DeliverCredentials' })).toBe(true);
    expect(isDeliverCredentialsMessage({ type: 'delivercredentials' })).toBe(true);
  });

  it('rejects non-objects and missing tag', () => {
    expect(isDeliverCredentialsMessage(null)).toBe(false);
    expect(isDeliverCredentialsMessage(undefined)).toBe(false);
    expect(isDeliverCredentialsMessage({})).toBe(false);
    expect(isDeliverCredentialsMessage({ message: 1 })).toBe(false);
  });
});

describe('extractAuthCredentials', () => {
  it('returns trimmed auth_token and optional profile fields', () => {
    const c = extractAuthCredentials({
      auth_token: '  tok  ',
      userId: 'u1',
      userName: 'Ada',
    });
    expect(c).toEqual({
      auth_token: 'tok',
      userId: 'u1',
      userName: 'Ada',
    });
  });

  it('maps expiresAt / expiration / tokenExpiry', () => {
    expect(extractAuthCredentials({ auth_token: 't', expiresAt: ' 2040-01-01T00:00:00Z ' })?.expiresAt).toBe(
      '2040-01-01T00:00:00Z',
    );
    expect(extractAuthCredentials({ auth_token: 't', expiration: '2039-12-31' })?.expiresAt).toBe('2039-12-31');
    expect(extractAuthCredentials({ auth_token: 't', tokenExpiry: '2041-06-01' })?.expiresAt).toBe('2041-06-01');
  });

  it('returns null when token missing or blank', () => {
    expect(extractAuthCredentials({})).toBeNull();
    expect(extractAuthCredentials({ auth_token: '' })).toBeNull();
    expect(extractAuthCredentials({ auth_token: '   ' })).toBeNull();
  });
});
