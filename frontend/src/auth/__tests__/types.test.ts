import { describe, it, expect } from 'vitest';
import { extractCredentials, isCredentialsMessage } from '../types';

const CLAIM_PREFIX = 'https://issuer.example/v1/claims/';
const UNIQUE_ID = CLAIM_PREFIX + 'UniqueID';
const GIVEN_NAME = CLAIM_PREFIX + 'givenname';
const SURNAME = CLAIM_PREFIX + 'surname';

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
  it('lifts auth_token, URL-suffixed userId, and exp', () => {
    const creds = extractCredentials({
      auth_token: 'tok-123',
      [UNIQUE_ID]: 'user-42',
      exp: 1700000000,
    });
    expect(creds).toEqual({ auth_token: 'tok-123', userId: 'user-42', exp: 1700000000 });
  });

  it('composes userName from given name + surname', () => {
    const creds = extractCredentials({
      auth_token: 'tok',
      [UNIQUE_ID]: 'u',
      [GIVEN_NAME]: 'Ada',
      [SURNAME]: 'Lovelace',
      exp: 1,
    });
    expect(creds?.userName).toBe('Ada Lovelace');
  });

  it('uses a single name part when only one is present', () => {
    const creds = extractCredentials({
      auth_token: 'tok',
      [UNIQUE_ID]: 'u',
      [GIVEN_NAME]: 'Ada',
      exp: 1,
    });
    expect(creds?.userName).toBe('Ada');
  });

  it('trims the token and claim values', () => {
    const creds = extractCredentials({
      auth_token: '  tok  ',
      [UNIQUE_ID]: '  user-42  ',
      exp: 1,
    });
    expect(creds?.auth_token).toBe('tok');
    expect(creds?.userId).toBe('user-42');
  });

  it('rejects a missing or blank auth_token', () => {
    expect(extractCredentials({ [UNIQUE_ID]: 'u', exp: 1 })).toBeNull();
    expect(extractCredentials({ auth_token: '   ', [UNIQUE_ID]: 'u', exp: 1 })).toBeNull();
    expect(extractCredentials({ auth_token: 42, [UNIQUE_ID]: 'u', exp: 1 })).toBeNull();
  });

  it('rejects a missing userId claim', () => {
    expect(extractCredentials({ auth_token: 'tok', exp: 1 })).toBeNull();
  });

  it('rejects a missing or non-finite exp', () => {
    expect(extractCredentials({ auth_token: 'tok', [UNIQUE_ID]: 'u' })).toBeNull();
    expect(extractCredentials({ auth_token: 'tok', [UNIQUE_ID]: 'u', exp: 'soon' })).toBeNull();
    expect(extractCredentials({ auth_token: 'tok', [UNIQUE_ID]: 'u', exp: Infinity })).toBeNull();
  });
});
