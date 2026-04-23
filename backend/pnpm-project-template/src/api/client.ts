import { API_BASE } from '../config';
import { credentialsStore, authSession } from '../auth';

export async function fetchWithAuth(path: string, body?: unknown): Promise<Response> {
  const url = `${API_BASE}${path}`;
  const token = credentialsStore.getValidToken();
  const options: RequestInit = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: token } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };
  const res = await fetch(url, options);
  if (res.status === 401) {
    await authSession.refreshAfter401();
    const retryToken = credentialsStore.getValidToken();
    const retry = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(retryToken ? { Authorization: retryToken } : {}),
      },
    });
    if (!retry.ok) throw new Error(`Request failed: ${retry.status}`);
    return retry;
  }
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res;
}
