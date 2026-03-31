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
  async bootstrap(): Promise<SessionBootstrapResult> {
    if (credentialsStore.getValidToken()) {
      return 'ready';
    }

    if (!isProviderConfigured()) {
      throw new Error(
        'Authentication is not configured. Set VITE_AUTH_PROVIDER_URL or provide credentials.',
      );
    }

    return 'needs_interactive_sign_in';
  },

  async signIn(): Promise<void> {
    const creds = await getAuthenticator().acquireCredentials();
    credentialsStore.save(creds);
  },

  async refreshAfter401(): Promise<void> {
    const creds = await getAuthenticator().acquireCredentials();
    credentialsStore.save(creds);
  },

  signOut(): void {
    credentialsStore.clear();
  },

  hasValidSession(): boolean {
    return Boolean(credentialsStore.getValidToken());
  },
};
