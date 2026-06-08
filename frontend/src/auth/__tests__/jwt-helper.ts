import { UnsecuredJWT } from 'jose';

const CLAIM_PREFIX = 'https://issuer.example/v1/claims/';

export function fakeJwt(
  overrides: {
    userId?: string;
    exp?: number;
    givenName?: string;
    surname?: string;
  } = {},
): string {
  const exp = overrides.exp ?? Math.floor(Date.now() / 1000) + 3600;
  const builder = new UnsecuredJWT({
    [CLAIM_PREFIX + 'UniqueID']: overrides.userId ?? 'user-42',
    ...(overrides.givenName && { [CLAIM_PREFIX + 'givenname']: overrides.givenName }),
    ...(overrides.surname && { [CLAIM_PREFIX + 'surname']: overrides.surname }),
  }).setExpirationTime(exp);

  return builder.encode();
}
