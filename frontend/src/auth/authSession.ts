import type { AuthRuntimeConfig } from './config';
import { authConfig, isAuthMockMode, isAuthProviderConfigured } from './config';
import { credentialsStore } from './credentialsStore';
import type { UserAuthenticator } from './authenticator';
import { MockAuthenticator } from './mockAuthenticator';
import { PopupAuthenticator } from './popupAuthenticator';

export { PopupBlockedError } from './popupAuthenticator';

function createAuthenticator(cfg: AuthRuntimeConfig): UserAuthenticator {
  if (isAuthMockMode()) return new MockAuthenticator(cfg);
  return new PopupAuthenticator(cfg);
}

let cachedAuthenticator: UserAuthenticator | null = null;

function getAuthenticator(): UserAuthenticator {
  if (!cachedAuthenticator) cachedAuthenticator = createAuthenticator(authConfig);
  return cachedAuthenticator;
}

async function persistCredentialsFromAuthenticator(): Promise<void> {
  const creds = await getAuthenticator().acquireCredentials();
  credentialsStore.save(creds);
}

export type AuthBootstrapResult = 'ready' | 'needs_interactive_sign_in';

export const authSession = {
  /**
   * Passive bootstrap: restore session / apply mock. Never opens a popup (browsers block that outside a click).
   * When external SSO is configured and there is no token yet, returns `needs_interactive_sign_in` — call `signInInteractive` from a button handler next.
   */
  async ensureInitialSession(): Promise<AuthBootstrapResult> {
    if (credentialsStore.getValidAccessToken()) return 'ready';

    if (isAuthMockMode()) {
      await persistCredentialsFromAuthenticator();
      return 'ready';
    }
    if (!isAuthProviderConfigured()) {
      throw new Error(
        'Authentication is not configured: set VITE_AUTH_PROVIDER_URL, seed session storage, or enable VITE_AUTH_MOCK=true',
      );
    }
    return 'needs_interactive_sign_in';
  },

  /** Must run inside a user gesture (click) so the SSO window is allowed. */
  async signInInteractive(): Promise<void> {
    await persistCredentialsFromAuthenticator();
  },

  /**
   * After HTTP 401 — tries a new popup (often blocked without user gesture).
   * On `PopupBlockedError`, callers should redirect or prompt the user to sign in again.
   */
  async reauthenticateAfterUnauthorized(): Promise<void> {
    await persistCredentialsFromAuthenticator();
  },

  navigateToLoginFallback(): void {
    try {
      globalThis.window.location.assign(authConfig.loginFallbackUrl);
    } catch {
      /* ignore */
    }
  },
};
