export type AuthCredentials = {
  auth_token: string;
  userId?: string;
  userName?: string;
  expiresAt?: string;
  [key: string]: unknown;
};

export function isCredentialsMessage(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false;
  const msg = data as Record<string, unknown>;
  const tag = msg.message ?? msg.type;
  return typeof tag === 'string' && tag.toLowerCase() === 'delivercredentials';
}

export function extractCredentials(data: Record<string, unknown>): AuthCredentials | null {
  const token = data.auth_token;
  if (typeof token !== 'string' || !token.trim()) return null;

  const creds: AuthCredentials = { auth_token: token.trim() };
  if (typeof data.userId === 'string') creds.userId = data.userId;
  if (typeof data.userName === 'string') creds.userName = data.userName;

  for (const key of ['expiresAt', 'expiration', 'tokenExpiry']) {
    const val = data[key];
    if (typeof val === 'string' && val.trim()) {
      creds.expiresAt = val.trim();
      break;
    }
  }

  return creds;
}
