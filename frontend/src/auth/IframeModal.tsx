import { useEffect, useRef, useCallback } from 'react';
import { authConfig } from './config';
import { credentialsStore } from './storage';
import { listenForIframeCredentials } from './iframeAuth';

type Props = {
  onSuccess: () => void;
  onError: (msg: string) => void;
  onCancel: () => void;
};

export function IframeModal({ onSuccess, onError, onCancel }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const controller = new AbortController();
    abortRef.current = controller;

    listenForIframeCredentials(iframe, authConfig, controller.signal)
      .then((creds) => {
        credentialsStore.save(creds);
        onSuccess();
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        onError(err instanceof Error ? err.message : 'Sign in failed');
      });

    return () => {
      controller.abort();
    };
  }, [onSuccess, onError]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        abortRef.current?.abort();
        onCancel();
      }
    },
    [onCancel],
  );

  const handleClose = useCallback(() => {
    abortRef.current?.abort();
    onCancel();
  }, [onCancel]);

  return (
    <div
      onClick={handleBackdropClick}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
      }}
    >
      <div
        style={{
          position: 'relative',
          width: 520,
          height: 720,
          maxWidth: '95vw',
          maxHeight: '90vh',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 25px 60px rgba(0,0,0,0.4)',
        }}
      >
        <button
          onClick={handleClose}
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            zIndex: 1,
            background: 'rgba(0,0,0,0.3)',
            color: '#fff',
            border: 'none',
            borderRadius: '50%',
            width: 28,
            height: 28,
            cursor: 'pointer',
            fontSize: 14,
            lineHeight: '1',
          }}
        >
          &#x2715;
        </button>
        <iframe
          ref={iframeRef}
          src={authConfig.providerUrl}
          style={{ width: '100%', height: '100%', border: 'none' }}
        />
      </div>
    </div>
  );
}
