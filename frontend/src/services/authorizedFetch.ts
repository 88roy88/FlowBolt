import { authSession } from '../auth/authSession';
import { credentialsStore } from '../auth/credentialsStore';

function headersWithAuth(base: HeadersInit | undefined): Headers {
  const h = new Headers(base ?? undefined);
  const token = credentialsStore.getValidAccessToken();
  if (token) h.set('Authorization', token);
  return h;
}

/**
 * Same-origin API `fetch` with `Authorization` from the auth session and a single 401 re-login retry.
 */
export async function authorizedFetch(input: string, init?: RequestInit): Promise<Response> {
  const first = await fetch(input, {
    ...init,
    headers: headersWithAuth(init?.headers),
  });

  if (first.status !== 401) return first;

  try {
    await authSession.reauthenticateAfterUnauthorized();
  } catch {
    authSession.navigateToLoginFallback();
    return first;
  }

  const second = await fetch(input, {
    ...init,
    headers: headersWithAuth(init?.headers),
  });

  if (second.status === 401) {
    authSession.navigateToLoginFallback();
  }

  return second;
}
