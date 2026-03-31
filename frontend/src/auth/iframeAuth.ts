import type { AuthConfig } from './config';
import type { AuthCredentials } from './types';
import { extractCredentials, isCredentialsMessage } from './types';

const MODAL_ID = 'sso-auth-modal';

function buildModal(iframeSrc: string): { backdrop: HTMLElement; iframe: HTMLIFrameElement } {
  const backdrop = document.createElement('div');
  backdrop.id = MODAL_ID;
  Object.assign(backdrop.style, {
    position: 'fixed',
    inset: '0',
    background: 'rgba(0,0,0,0.6)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: '9999',
  });

  const container = document.createElement('div');
  Object.assign(container.style, {
    position: 'relative',
    width: '520px',
    height: '720px',
    maxWidth: '95vw',
    maxHeight: '90vh',
    borderRadius: '12px',
    overflow: 'hidden',
    boxShadow: '0 25px 60px rgba(0,0,0,0.4)',
  });

  const closeBtn = document.createElement('button');
  closeBtn.textContent = '✕';
  Object.assign(closeBtn.style, {
    position: 'absolute',
    top: '8px',
    right: '8px',
    zIndex: '1',
    background: 'rgba(0,0,0,0.3)',
    color: '#fff',
    border: 'none',
    borderRadius: '50%',
    width: '28px',
    height: '28px',
    cursor: 'pointer',
    fontSize: '14px',
    lineHeight: '1',
  });

  const iframe = document.createElement('iframe');
  iframe.src = iframeSrc;
  Object.assign(iframe.style, {
    width: '100%',
    height: '100%',
    border: 'none',
  });

  container.appendChild(closeBtn);
  container.appendChild(iframe);
  backdrop.appendChild(container);

  return { backdrop, iframe };
}

export class IframeAuthenticator {
  constructor(private readonly config: AuthConfig) {}

  async acquireCredentials(): Promise<AuthCredentials> {
    if (!this.config.providerUrl) {
      throw new Error(
        'Authentication provider URL is not configured. Set VITE_AUTH_PROVIDER_URL in your .env file.',
      );
    }

    return new Promise<AuthCredentials>((resolve, reject) => {
      const { backdrop, iframe } = buildModal(this.config.providerUrl);
      const targetOrigin = this.config.postMessageTarget;

      const cleanup = () => {
        window.removeEventListener('message', onMessage);
        clearTimeout(timeoutTimer);
        backdrop.remove();
      };

      const finishOk = (creds: AuthCredentials) => {
        cleanup();
        resolve(creds);
      };

      const finishErr = (err: Error) => {
        cleanup();
        reject(err);
      };

      const onMessage = (event: MessageEvent) => {
        if (event.source !== iframe.contentWindow) return;
        if (!isCredentialsMessage(event.data)) return;
        const creds = extractCredentials(event.data as Record<string, unknown>);
        if (!creds) {
          finishErr(new Error('Login response did not include a valid auth_token'));
          return;
        }
        finishOk(creds);
      };

      const timeoutTimer = setTimeout(() => {
        finishErr(new Error('Login timed out. Please try again.'));
      }, this.config.popupTimeoutMs);

      // Close button
      const closeBtn = backdrop.querySelector('button')!;
      closeBtn.addEventListener('click', () => {
        finishErr(new Error('Login cancelled'));
      });

      // Click outside to cancel
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) finishErr(new Error('Login cancelled'));
      });

      window.addEventListener('message', onMessage);
      document.body.appendChild(backdrop);

      // Poll the iframe for credentials (same as popup approach)
      const requestPayload = { type: 'requestCredentials', doesTokenHaveExpirationDate: true };
      iframe.addEventListener('load', () => {
        const poll = setInterval(() => {
          if (!document.getElementById(MODAL_ID)) {
            clearInterval(poll);
            return;
          }
          try {
            iframe.contentWindow?.postMessage(requestPayload, targetOrigin);
          } catch {
            /* cross-origin not ready yet */
          }
        }, this.config.pollIntervalMs);
      });
    });
  }
}
