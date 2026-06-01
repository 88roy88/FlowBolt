import { useEffect, useState, useCallback } from 'react';
import { authSession, PopupBlockedError } from './session';
import { authConfig, isProviderConfigured } from './config';
import { IframeModal } from './IframeModal';
import type { SessionBootstrapResult } from './session';

type AuthState = 'loading' | 'ready' | 'needs_sign_in' | 'signing_in' | 'error';

type Props = {
  children: React.ReactNode;
  /** Rendered during auth loading state */
  loader?: React.ReactNode;
};

export function AuthGate({ children, loader }: Props) {
  const [state, setState] = useState<AuthState>('loading');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isProviderConfigured()) {
      setState('ready');
      return;
    }
    let cancelled = false;
    authSession
      .bootstrap()
      .then((result: SessionBootstrapResult) => {
        if (!cancelled) setState(result === 'ready' ? 'ready' : 'needs_sign_in');
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState('error');
          setErrorMsg(err instanceof Error ? err.message : 'Authentication failed');
        }
      });
    return () => { cancelled = true; };
  }, []);

  // Watch for token being cleared (e.g. by refreshCredentials in iframe mode)
  useEffect(() => {
    if (state !== 'ready') return;
    function onCleared() {
      setState('needs_sign_in');
    }
    window.addEventListener('auth:credentials-cleared', onCleared);
    return () => window.removeEventListener('auth:credentials-cleared', onCleared);
  }, [state]);

  const handleSignIn = useCallback(async () => {
    if (authConfig.useIframe) {
      setErrorMsg(null);
      setState('signing_in');
      return;
    }
    try {
      setErrorMsg(null);
      await authSession.signIn();
      setState('ready');
    } catch (err) {
      if (err instanceof PopupBlockedError) {
        setErrorMsg('Popup was blocked. Please allow popups and try again.');
      } else {
        setErrorMsg(err instanceof Error ? err.message : 'Sign in failed');
      }
    }
  }, []);

  if (state === 'loading') {
    return <>{loader ?? null}</>;
  }

  if (state === 'error') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        gap: '16px',
      }}>
        <div style={{
          padding: '16px 24px',
          background: 'var(--surface)',
          border: '2px solid var(--danger)',
          borderRadius: '8px',
          maxWidth: '500px',
          textAlign: 'center',
        }}>
          <p style={{ color: 'var(--danger)', fontWeight: 600, marginBottom: '8px' }}>
            Authentication Error
          </p>
          <p style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
            {errorMsg || 'Failed to initialize authentication'}
          </p>
        </div>
      </div>
    );
  }

  if (state === 'needs_sign_in' || state === 'signing_in') {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        gap: '16px',
      }}>
        <p style={{ color: 'var(--text-dim)', marginBottom: '8px' }}>
          Sign in to continue
        </p>
        {errorMsg && (
          <div style={{
            padding: '12px 16px',
            background: 'var(--danger-dim)',
            border: '1px solid var(--danger)',
            borderRadius: '6px',
            maxWidth: '400px',
            textAlign: 'center',
            marginBottom: '8px',
          }}>
            <p style={{ color: 'var(--danger)', fontSize: '14px' }}>
              {errorMsg}
            </p>
          </div>
        )}
        <button
          onClick={handleSignIn}
          style={{
            padding: '10px 24px',
            background: 'var(--accent)',
            color: 'var(--bg)',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '16px',
            cursor: 'pointer',
          }}
        >
          Sign In
        </button>
        {state === 'signing_in' && (
          <IframeModal
            onSuccess={() => setState('ready')}
            onError={(msg) => { setErrorMsg(msg); setState('needs_sign_in'); }}
            onCancel={() => setState('needs_sign_in')}
          />
        )}
      </div>
    );
  }

  return <>{children}</>;
}
