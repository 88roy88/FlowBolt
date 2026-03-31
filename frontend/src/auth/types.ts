/**
 * Authentication credentials from external auth provider (SSO/SAML).
 *
 * Delivered via postMessage from the popup window.
 */
export type AuthCredentials = {
  /** Access token sent to backend via Authorization header */
  auth_token: string;
  /** Optional user identifier */
  userId?: string;
  /** Optional user display name */
  userName?: string;
  /** Optional ISO-8601 expiration timestamp */
  expiresAt?: string;
  /** Additional vendor-specific fields are preserved */
  [key: string]: unknown;
};

/**
 * Check if a postMessage payload is a credentials delivery message.
 *
 * Supports both `message` and `type` fields for compatibility with different SSO providers.
 */
export function isCredentialsMessage(data: unknown): data is Record<string, unknown> {
  if (!data || typeof data !== 'object') return false;
  const msg = data as Record<string, unknown>;
  const tag = msg.message ?? msg.type;
  return typeof tag === 'string' && tag.toLowerCase() === 'delivercredentials';
}

/**
 * Extract auth credentials from a postMessage payload.
 *
 * Returns null if the payload doesn't contain a valid auth_token.
 */
export function extractCredentials(data: Record<string, unknown>): AuthCredentials | null {
  const token = data.auth_token;
  if (typeof token !== 'string' || !token.trim()) return null;

  const creds: AuthCredentials = { auth_token: token.trim() };
  if (typeof data.userId === 'string') creds.userId = data.userId;
  if (typeof data.userName === 'string') creds.userName = data.userName;

  // Support multiple expiry field names
  for (const key of ['expiresAt', 'expiration', 'tokenExpiry']) {
    const val = data[key];
    if (typeof val === 'string' && val.trim()) {
      creds.expiresAt = val.trim();
      break;
    }
  }

  return creds;
}
