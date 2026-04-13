import { authConfig, isProviderConfigured } from './config';
import { credentialsStore } from './storage';
import { PopupAuthenticator, PopupBlockedError } from './popup';

export { PopupBlockedError };

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

  /** Sign in via popup. For iframe sign-in, use <IframeModal> directly. */
  async signIn(): Promise<void> {
    const creds = await new PopupAuthenticator(authConfig).acquireCredentials();
    credentialsStore.save(creds);
  },

  async refreshAfter401(): Promise<void> {
    if (authConfig.useIframe) {
      // Iframe refresh must be driven by the React layer — clear token so
      // the UI shows the sign-in state again.
      credentialsStore.clear();
      return;
    }
    const creds = await new PopupAuthenticator(authConfig).acquireCredentials();
    credentialsStore.save(creds);
  },

  signOut(): void {
    credentialsStore.clear();
  },

  hasValidSession(): boolean {
    return Boolean(credentialsStore.getValidToken());
  },
};
