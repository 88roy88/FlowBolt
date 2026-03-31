/**
 * Popup-based SSO authenticator.
 *
 * Opens a popup window and polls for credentials via postMessage.
 * MUST be called from a user gesture (click) to avoid popup blockers.
 */

import type { AuthConfig } from './config';
import type { AuthCredentials } from './types';
import { extractCredentials, isCredentialsMessage } from './types';

const POPUP_FEATURES = 'popup=yes,width=520,height=720,menubar=no,toolbar=no';

export class PopupBlockedError extends Error {
  constructor() {
    super('Login popup was blocked by the browser. Please allow popups and try again.');
    this.name = 'PopupBlockedError';
  }
}

export class PopupAuthenticator {
  constructor(private readonly config: AuthConfig) {}

  /**
   * Acquire credentials via popup + postMessage flow.
   *
   * MUST be called from a user gesture (e.g., button click) or popup will be blocked.
   */
  async acquireCredentials(): Promise<AuthCredentials> {
    if (!this.config.providerUrl) {
      throw new Error(
        'Authentication provider URL is not configured. Set VITE_AUTH_PROVIDER_URL in your .env file.',
      );
    }

    const popup = globalThis.window.open(this.config.providerUrl, 'sso_auth', POPUP_FEATURES);
    if (!popup) {
      throw new PopupBlockedError();
    }

    try {
      popup.focus();
    } catch {
      /* ignore */
    }

    return await this.waitForCredentials(popup);
  }

  private async waitForCredentials(popup: Window): Promise<AuthCredentials> {
    const requestPayload = {
      type: 'requestCredentials',
      doesTokenHaveExpirationDate: true,
    };

    return new Promise<AuthCredentials>((resolve, reject) => {
      let settled = false;

      const cleanup = () => {
        if (settled) return;
        settled = true;
        globalThis.clearInterval(pollTimer);
        globalThis.clearInterval(closedTimer);
        globalThis.clearTimeout(timeoutTimer);
        globalThis.window.removeEventListener('message', onMessage);
        try {
          popup.close();
        } catch {
          /* ignore */
        }
      };

      const finishError = (err: Error) => {
        cleanup();
        reject(err);
      };

      const finishSuccess = (creds: AuthCredentials) => {
        cleanup();
        resolve(creds);
      };

      // Poll: send credential request to popup
      const pollTimer = globalThis.setInterval(() => {
        try {
          popup.postMessage(requestPayload, this.config.postMessageTarget);
        } catch {
          /* popup closed or cross-origin */
        }
      }, this.config.pollIntervalMs);

      // Check if popup was closed by user
      const closedTimer = globalThis.setInterval(() => {
        if (popup.closed) {
          finishError(new Error('Login window was closed before authentication completed'));
        }
      }, 300);

      // Timeout
      const timeoutTimer = globalThis.setTimeout(() => {
        finishError(new Error('Login timed out. Please try again.'));
      }, this.config.popupTimeoutMs);

      // Listen for credentials from popup
      const onMessage = (event: MessageEvent) => {
        if (event.source !== popup) return;
        if (!isCredentialsMessage(event.data)) return;

        const creds = extractCredentials(event.data as Record<string, unknown>);
        if (!creds) {
          finishError(new Error('Login response did not include a valid auth_token'));
          return;
        }

        finishSuccess(creds);
      };

      globalThis.window.addEventListener('message', onMessage);

      // Send initial request
      try {
        popup.postMessage(requestPayload, this.config.postMessageTarget);
      } catch {
        /* popup may not be ready yet - polling will handle this */
      }
    });
  }
}
