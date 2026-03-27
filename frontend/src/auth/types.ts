/** Shape of credentials delivered by the external auth provider (postMessage). */
export type AuthCredentials = {
  auth_token: string;
  userId?: string;
  userName?: string;
  /**
   * Optional ISO-8601 instant when the token expires.
   * Additional vendor-specific keys are preserved when saving to storage.
   */
  expiresAt?: string;
  [key: string]: unknown;
};

/** Normalized credential delivery (supports `message` or `type` on the payload). */
export function isDeliverCredentialsMessage(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false;
  const m = data as Record<string, unknown>;
  const tag = m.message ?? m.type;
  return typeof tag === 'string' && tag.toLowerCase() === 'delivercredentials';
}

export function extractAuthCredentials(data: Record<string, unknown>): AuthCredentials | null {
  const token = data.auth_token;
  if (typeof token !== 'string' || !token.trim()) return null;

  const creds: AuthCredentials = { auth_token: token.trim() };
  if (typeof data.userId === 'string') creds.userId = data.userId;
  if (typeof data.userName === 'string') creds.userName = data.userName;
  const exp = pickExpiresField(data);
  if (exp.expiresAt) creds.expiresAt = exp.expiresAt;
  return creds;
}

function pickExpiresField(data: Record<string, unknown>): { expiresAt?: string } {
  for (const key of ['expiresAt', 'expiration', 'tokenExpiry'] as const) {
    const v = data[key];
    if (typeof v === 'string' && v.trim()) return { expiresAt: v.trim() };
  }
  return {};
}
