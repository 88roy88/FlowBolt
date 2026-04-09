import type { AuthConfig } from './config';
import type { AuthCredentials } from './types';
import { extractCredentials, isCredentialsMessage } from './types';

/**
 * Listen for credentials from an iframe via postMessage.
 * Pure logic — no DOM manipulation. The React component renders the iframe.
 */
export function listenForIframeCredentials(
  iframe: HTMLIFrameElement,
  config: AuthConfig,
  signal?: AbortSignal,
): Promise<AuthCredentials> {
  return new Promise<AuthCredentials>((resolve, reject) => {
    const requestPayload = { type: 'requestCredentials', doesTokenHaveExpirationDate: true };
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let timeoutTimer: ReturnType<typeof setTimeout> | undefined;

    const cleanup = () => {
      clearInterval(pollTimer);
      clearTimeout(timeoutTimer);
      window.removeEventListener('message', onMessage);
      signal?.removeEventListener('abort', onAbort);
    };

    const onMessage = (event: MessageEvent) => {
      if (event.source !== iframe.contentWindow) return;
      if (!isCredentialsMessage(event.data)) return;
      const creds = extractCredentials(event.data as Record<string, unknown>);
      if (!creds) {
        cleanup();
        reject(new Error('Login response did not include a valid auth_token'));
        return;
      }
      cleanup();
      resolve(creds);
    };

    const onAbort = () => {
      cleanup();
      reject(new Error('Login cancelled'));
    };

    window.addEventListener('message', onMessage);
    signal?.addEventListener('abort', onAbort);

    timeoutTimer = setTimeout(() => {
      cleanup();
      reject(new Error('Login timed out. Please try again.'));
    }, config.popupTimeoutMs);

    // Start polling after iframe loads
    iframe.addEventListener('load', () => {
      pollTimer = setInterval(() => {
        try {
          iframe.contentWindow?.postMessage(requestPayload, config.postMessageTarget);
        } catch {
          /* iframe not ready yet */
        }
      }, config.pollIntervalMs);
    });
  });
}
