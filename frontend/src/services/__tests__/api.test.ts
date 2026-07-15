import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../auth', () => ({
  authSession: {
    ensureFreshToken: vi.fn(),
    refreshCredentials: vi.fn(),
    hasValidSession: vi.fn(),
  },
}));

import { fetchProjects, searchAdUsers, searchAdGroups } from '../api';
import { authSession } from '../../auth';

function response(status: number, body = ''): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
  } as unknown as Response;
}

function jsonResponse(status: number, data: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as unknown as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', fetchMock);
  vi.mocked(authSession.ensureFreshToken).mockResolvedValue('tok');
  vi.mocked(authSession.refreshCredentials).mockResolvedValue(undefined);
  vi.mocked(authSession.hasValidSession).mockReturnValue(true);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function authHeader(callIndex = 0): string | null {
  const init = fetchMock.mock.calls[callIndex][1] as RequestInit;
  return new Headers(init.headers).get('Authorization');
}

describe('fetchWithAuth (via fetchProjects)', () => {
  it('attaches a Bearer token to the request', async () => {
    fetchMock.mockResolvedValue(response(200, '[]'));
    await fetchProjects();
    expect(authHeader()).toBe('Bearer tok');
  });

  it('does not double-prefix a token that already starts with Bearer', async () => {
    vi.mocked(authSession.ensureFreshToken).mockResolvedValue('Bearer abc');
    fetchMock.mockResolvedValue(response(200, '[]'));
    await fetchProjects();
    expect(authHeader()).toBe('Bearer abc');
  });

  it('retries once after a 401 and returns the retried result', async () => {
    fetchMock
      .mockResolvedValueOnce(response(401, 'unauthorized'))
      .mockResolvedValueOnce(response(200, '[{"id":"p1"}]'));

    const projects = await fetchProjects();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(authSession.refreshCredentials).toHaveBeenCalledOnce();
    expect(projects).toEqual([{ id: 'p1' }]);
  });

  it('throws without retrying the request body when the refresh yields no session', async () => {
    fetchMock.mockResolvedValueOnce(response(401, 'unauthorized'));
    vi.mocked(authSession.hasValidSession).mockReturnValue(false);

    await expect(fetchProjects()).rejects.toThrow(/authentication required/i);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('does not retry more than once when the second response is also 401', async () => {
    fetchMock
      .mockResolvedValueOnce(response(401, 'first'))
      .mockResolvedValueOnce(response(401, 'second'));

    await expect(fetchProjects()).rejects.toThrow(/API error 401/);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('ADAPI search', () => {
  it('requests the backend users endpoint with an encoded query and a Bearer token', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ cn: 'djenkins' }]));

    const users = await searchAdUsers('a b');

    expect(fetchMock.mock.calls[0][0]).toBe('/api/adapi/users?q=a%20b');
    // Proxied through the backend, so it carries auth like any other request.
    expect(authHeader()).toBe('Bearer tok');
    expect(users).toEqual([{ cn: 'djenkins' }]);
  });

  it('requests the backend groups endpoint with an encoded query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ cn: 'Legal' }]));

    await searchAdGroups('le');

    expect(fetchMock.mock.calls[0][0]).toBe('/api/adapi/groups?q=le');
  });

  it('throws on a non-ok response', async () => {
    fetchMock.mockResolvedValue(response(502, 'ADAPI service unavailable'));
    await expect(searchAdUsers('dje')).rejects.toThrow(/API error 502/);
  });
});
