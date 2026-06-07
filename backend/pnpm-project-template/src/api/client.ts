import { API_BASE } from '../config';
import { authSession } from '../auth';

export async function fetchWithAuth(path: string, options: RequestInit = {}, allowRetry = true): Promise<Response> {
  const token = await authSession.ensureFreshToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', token.startsWith('Bearer ') ? token : `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && allowRetry) {
    await authSession.refreshCredentials();
    if (!authSession.hasValidSession()) {
      throw new Error('API error 401: authentication required');
    }
    return fetchWithAuth(path, options, false);
  }
  return res;
}
