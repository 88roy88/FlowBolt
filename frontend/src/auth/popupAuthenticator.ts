import type { AuthRuntimeConfig } from './config';
import type { AuthCredentials } from './types';
import { extractAuthCredentials, isDeliverCredentialsMessage } from './types';

const POPUP_FEATURES = 'popup=yes,width=520,height=720,menubar=no,toolbar=no';

function normalizeRequestPayload(doesTokenHaveExpirationDate: boolean): Record<string, unknown> {
  return {
    type: 'requestCredentials',
    Type: 'RequestCredentials',
    doesTokenHaveExpirationDate,
  };
}

export class PopupBlockedError extends Error {
  constructor() {
    super('Login popup was blocked by the browser');
    this.name = 'PopupBlockedError';
  }
}

/**
 * External SAML / Viny-style login via popup + postMessage.
 * Call `acquireCredentials` only from a user gesture (e.g. click); otherwise the popup is usually blocked.
 */
export class PopupAuthenticator {
  constructor(private readonly config: AuthRuntimeConfig) {}

  async acquireCredentials(): Promise<AuthCredentials> {
    const url = this.config.providerUrl;
    if (!url) {
      throw new Error('Authentication provider URL is not configured (VITE_AUTH_PROVIDER_URL)');
    }

    const targetOrigin =
      this.config.postMessageTargetOrigin === '' ? '*' : this.config.postMessageTargetOrigin;

    const popup = globalThis.window.open(url, 'external_auth', POPUP_FEATURES);
    if (!popup) {
      throw new PopupBlockedError();
    }

    try {
      popup.focus();
    } catch {
      /* ignore */
    }

    const requestPayload = normalizeRequestPayload(true);

    return await new Promise<AuthCredentials>((resolve, reject) => {
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

      const finishErr = (err: Error) => {
        cleanup();
        reject(err);
      };

      const finishOk = (creds: AuthCredentials) => {
        cleanup();
        resolve(creds);
      };

      const pollTimer = globalThis.setInterval(() => {
        try {
          popup.postMessage(requestPayload, targetOrigin);
        } catch {
          /* closed / cross-origin */
        }
      }, this.config.pollIntervalMs);

      const closedTimer = globalThis.setInterval(() => {
        if (popup.closed) {
          finishErr(new Error('Login window was closed before authentication completed'));
        }
      }, 300);

      const timeoutTimer = globalThis.setTimeout(() => {
        finishErr(new Error('Login timed out'));
      }, this.config.popupTimeoutMs);

      const onMessage = (event: MessageEvent) => {
        if (event.source !== popup) return;
        if (!isDeliverCredentialsMessage(event.data)) return;
        const creds = extractAuthCredentials(event.data as Record<string, unknown>);
        if (!creds) {
          finishErr(new Error('Login response did not include a valid auth_token'));
          return;
        }
        finishOk(creds);
      };

      globalThis.window.addEventListener('message', onMessage);
      try {
        popup.postMessage(requestPayload, targetOrigin);
      } catch {
        /* popup may not be ready yet — polling covers this */
      }
    });
  }
}
