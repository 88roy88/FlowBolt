import { describe, it, expect } from 'vitest';
import { extractCredentials, isCredentialsMessage, credentialsFromToken } from '../types';
import { fakeJwt } from './jwt-helper';

describe('isCredentialsMessage', () => {
  it('matches on a message tag (case-insensitive)', () => {
    expect(isCredentialsMessage({ message: 'deliverCredentials' })).toBe(true);
    expect(isCredentialsMessage({ message: 'DELIVERCREDENTIALS' })).toBe(true);
  });

  it('matches on a type tag', () => {
    expect(isCredentialsMessage({ type: 'delivercredentials' })).toBe(true);
  });

  it('rejects other tags and non-objects', () => {
    expect(isCredentialsMessage({ type: 'requestCredentials' })).toBe(false);
    expect(isCredentialsMessage({})).toBe(false);
    expect(isCredentialsMessage(null)).toBe(false);
    expect(isCredentialsMessage('delivercredentials')).toBe(false);
  });
});

describe('extractCredentials', () => {
  it('decodes claims from the JWT payload', () => {
    const token = fakeJwt({ userId: 'user-42', exp: 1700000000 });
    const creds = extractCredentials({ auth_token: token });
    expect(creds).toMatchObject({ auth_token: token, userId: 'user-42', exp: 1700000000 });
  });

  it('composes userName from given name + surname in the JWT', () => {
    const token = fakeJwt({ userId: 'u', givenName: 'Ada', surname: 'Lovelace' });
    const creds = extractCredentials({ auth_token: token });
    expect(creds?.userName).toBe('Ada Lovelace');
  });

  it('uses a single name part when only one is present', () => {
    const token = fakeJwt({ userId: 'u', givenName: 'Ada' });
    const creds = extractCredentials({ auth_token: token });
    expect(creds?.userName).toBe('Ada');
  });

  it('ignores claims passed in the postMessage data (reads from JWT only)', () => {
    const token = fakeJwt({ userId: 'jwt-user', exp: 1700000000 });
    const creds = extractCredentials({
      auth_token: token,
      'https://issuer.example/v1/claims/UniqueID': 'postmessage-user',
      exp: 9999999999,
    });
    expect(creds?.userId).toBe('jwt-user');
    expect(creds?.exp).toBe(1700000000);
  });

  it('trims the token', () => {
    const token = fakeJwt({ userId: 'user-42' });
    const creds = extractCredentials({ auth_token: `  ${token}  ` });
    expect(creds?.auth_token).toBe(token);
  });

  it('rejects a missing or blank auth_token', () => {
    expect(extractCredentials({})).toBeNull();
    expect(extractCredentials({ auth_token: '   ' })).toBeNull();
    expect(extractCredentials({ auth_token: 42 })).toBeNull();
  });

  it('rejects an invalid (non-JWT) token', () => {
    expect(extractCredentials({ auth_token: 'not-a-jwt' })).toBeNull();
  });

  it('rejects a JWT without a UniqueID claim', () => {
    const token = fakeJwt({ userId: '' });
    expect(extractCredentials({ auth_token: token })).toBeNull();
  });
});

describe('credentialsFromToken', () => {
  it('decodes credentials from a valid JWT string', () => {
    const token = fakeJwt({ userId: 'u1', exp: 1700000000 });
    const creds = credentialsFromToken(token);
    expect(creds).toMatchObject({ auth_token: token, userId: 'u1', exp: 1700000000 });
  });

  it('returns null for an invalid token', () => {
    expect(credentialsFromToken('garbage')).toBeNull();
  });
});
