import { credentialsStore } from './storage';

export type AuthUserDisplay = {
  userId?: string;
  userName?: string;
};

export function getAuthUserDisplay(): AuthUserDisplay | null {
  const creds = credentialsStore.read();
  if (!creds) return null;

  return {
    userId: creds.userId,
    userName: creds.userName,
  };
}

/** Prefer display name, then user id. */
export function formatAuthUserLabel(user: AuthUserDisplay): string | undefined {
  return user.userName || user.userId;
}
