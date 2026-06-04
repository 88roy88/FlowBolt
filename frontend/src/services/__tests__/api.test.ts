import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../auth', () => ({
  authSession: {
    ensureFreshToken: vi.fn(),
    refreshCredentials: vi.fn(),
    hasValidSession: vi.fn(),
  },
}));

import { fetchProjects } from '../api';
import { authSession } from '../../auth';

function response(status: number, body = ''): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
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
