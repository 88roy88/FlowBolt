import { decodeJwt } from 'jose';

export type AuthCredentials = {
  auth_token: string;
  userId: string;
  userName?: string;
  exp: number;
  [key: string]: unknown;
};

export function isCredentialsMessage(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false;
  const msg = data as Record<string, unknown>;
  const tag = msg.message ?? msg.type;
  return typeof tag === 'string' && tag.toLowerCase() === 'delivercredentials';
}

// Real provider sends claims as URL-keyed entries (e.g. ".../UniqueID", ".../givenname").
// Suffix-match mirrors the backend's _find_unique_id pattern.
function findClaimBySuffix(data: Record<string, unknown>, suffix: string): string | undefined {
  for (const [key, val] of Object.entries(data)) {
    if (key.endsWith(suffix) && typeof val === 'string' && val.trim()) {
      return val.trim();
    }
  }
  return undefined;
}

function credentialsFromPayload(token: string, payload: Record<string, unknown>): AuthCredentials | null {
  const userId = findClaimBySuffix(payload, '/UniqueID');
  if (!userId) return null;

  if (typeof payload.exp !== 'number' || !Number.isFinite(payload.exp)) return null;

  const creds: AuthCredentials = { auth_token: token, userId, exp: payload.exp };

  const givenName = findClaimBySuffix(payload, '/givenname');
  const surname = findClaimBySuffix(payload, '/surname');
  const fullName = [givenName, surname].filter(Boolean).join(' ');
  if (fullName) creds.userName = fullName;

  return creds;
}

export function credentialsFromToken(token: string): AuthCredentials | null {
  try {
    // TODO: Add full JWT signature verification once JWKS endpoint is available
    const payload = decodeJwt(token) as Record<string, unknown>;
    return credentialsFromPayload(token, payload);
  } catch {
    return null;
  }
}

export function extractCredentials(data: Record<string, unknown>): AuthCredentials | null {
  const token = data.auth_token;
  if (typeof token !== 'string' || !token.trim()) return null;
  return credentialsFromToken(token.trim());
}
