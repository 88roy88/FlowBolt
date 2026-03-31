/**
 * Auth session manager.
 *
 * Handles session bootstrap, interactive sign-in, and token refresh.
 */

import { authConfig, isProviderConfigured } from './config';
import { credentialsStore } from './storage';
import { PopupAuthenticator, PopupBlockedError } from './popup';

export { PopupBlockedError };

let authenticator: PopupAuthenticator | null = null;

function getAuthenticator(): PopupAuthenticator {
  if (!authenticator) {
    authenticator = new PopupAuthenticator(authConfig);
  }
  return authenticator;
}

export type SessionBootstrapResult = 'ready' | 'needs_interactive_sign_in';

export const authSession = {
  /**
   * Bootstrap session on app load.
   *
   * - If valid token exists in localStorage: returns 'ready'
   * - If no token and provider configured: returns 'needs_interactive_sign_in'
   * - If no token and no provider: throws error
   *
   * Never opens a popup (browsers block that outside user gesture).
   */
  async bootstrap(): Promise<SessionBootstrapResult> {
    // Check if we already have a valid token
    if (credentialsStore.getValidToken()) {
      return 'ready';
    }

    // No token - check if auth is configured
    if (!isProviderConfigured()) {
      throw new Error(
        'Authentication is not configured. Set VITE_AUTH_PROVIDER_URL or provide credentials.',
      );
    }

    return 'needs_interactive_sign_in';
  },

  /**
   * Interactive sign-in - opens popup for SSO.
   *
   * MUST be called from a user gesture (button click) or popup will be blocked.
   */
  async signIn(): Promise<void> {
    const creds = await getAuthenticator().acquireCredentials();
    credentialsStore.save(creds);
  },

  /**
   * Attempt to refresh credentials after 401.
   *
   * Opens popup (usually blocked unless in user gesture context).
   * Caller should handle PopupBlockedError and prompt user to sign in manually.
   */
  async refreshAfter401(): Promise<void> {
    const creds = await getAuthenticator().acquireCredentials();
    credentialsStore.save(creds);
  },

  /** Sign out - clear stored credentials */
  signOut(): void {
    credentialsStore.clear();
  },

  /** Check if user has a valid session */
  hasValidSession(): boolean {
    return Boolean(credentialsStore.getValidToken());
  },
};
