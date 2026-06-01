import { authConfig } from '../auth/config';

// List of users who see "FlowBase" instead of "Flow44"
const SPECIAL_USERS = ['666royz', "dev-user"];

function getUserIdFromJwt(token: string): string | undefined {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return undefined;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    return typeof payload.sub === 'string' ? payload.sub : undefined;
  } catch {
    return undefined;
  }
}

export function isSpecialUser(): boolean {
  try {
    const stored = window.localStorage?.getItem(authConfig.storageKey);
    if (!stored) return false;

    const creds = JSON.parse(stored);
    const userId = creds?.userId ?? getUserIdFromJwt(creds?.auth_token ?? '');

    return typeof userId === 'string' && SPECIAL_USERS.includes(userId);
  } catch {
    return false;
  }
}

/**
 * Get the app suffix ("44" or "Base" for special users)
 */
export function getAppSuffix(): string {
  return isSpecialUser() ? 'Base' : '44';
}

/**
 * Get the app name ("Flow44" or "FlowBase" for special users)
 */
export function getAppName(): string {
  return isSpecialUser() ? 'FlowBase' : 'Flow44';
}
