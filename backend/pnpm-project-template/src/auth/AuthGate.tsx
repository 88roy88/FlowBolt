import { useEffect, useState } from 'react';
import { authSession, PopupBlockedError } from './session';
import { authConfig, isProviderConfigured } from './config';
import { IframeModal } from './IframeModal';
import type { SessionBootstrapResult } from './session';

type AuthState = 'loading' | 'ready' | 'needs_sign_in' | 'signing_in' | 'error';

export function AuthGate({ children }: { children: React.ReactNode }) {
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

  // Watch for token being cleared (e.g. by refreshAfter401 in iframe mode)
  useEffect(() => {
    if (state !== 'ready') return;
    function onCleared() {
      setState('needs_sign_in');
    }
    window.addEventListener('auth:credentials-cleared', onCleared);
    return () => window.removeEventListener('auth:credentials-cleared', onCleared);
  }, [state]);

  const handleSignIn = async () => {
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
  };

  if (state === 'loading') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div style={{ textAlign: 'center', color: '#888' }}>Loading...</div>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '12px' }}>
        <p style={{ color: '#e55', fontWeight: 600 }}>Authentication Error</p>
        <p style={{ color: '#888', fontSize: '14px' }}>{errorMsg}</p>
        <button
          onClick={() => { setState('loading'); window.location.reload(); }}
          style={{ padding: '8px 20px', background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (state === 'needs_sign_in' || state === 'signing_in') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '12px' }}>
        <p style={{ color: '#888' }}>Sign in to continue</p>
        {errorMsg && <p style={{ color: '#e55', fontSize: '14px' }}>{errorMsg}</p>}
        <button
          onClick={handleSignIn}
          style={{ padding: '10px 28px', background: '#2bbcc4', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '16px', fontWeight: 600 }}
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
