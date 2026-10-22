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

export async function fetchDataSource(path: string, body?: Record<string, unknown>): Promise<Response> {
  const options: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  };
  const res = await fetchWithAuth(path, options);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await readErrorDetail(res)}`);
  }
  return res;
}

async function readErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    // Non-JSON error body (e.g. a gateway HTML page)
  }
  return res.statusText || 'request failed';
}