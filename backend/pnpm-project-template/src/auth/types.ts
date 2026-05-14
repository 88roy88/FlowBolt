export type AuthCredentials = {
  auth_token: string;
  userId?: string;
  userName?: string;
  exp?: number;
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

export function extractCredentials(data: Record<string, unknown>): AuthCredentials | null {
  const token = data.auth_token;
  if (typeof token !== 'string' || !token.trim()) return null;

  const creds: AuthCredentials = { auth_token: token.trim() };

  const userId = findClaimBySuffix(data, '/UniqueID');
  if (userId) creds.userId = userId;

  const givenName = findClaimBySuffix(data, '/givenname');
  const surname = findClaimBySuffix(data, '/surname');
  const fullName = [givenName, surname].filter(Boolean).join(' ');
  if (fullName) creds.userName = fullName;

  if (typeof data.exp === 'number' && Number.isFinite(data.exp)) creds.exp = data.exp;

  return creds;
}
