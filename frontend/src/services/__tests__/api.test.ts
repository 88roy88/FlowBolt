import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../auth', () => ({
  authSession: {
    ensureFreshToken: vi.fn(),
    refreshCredentials: vi.fn(),
    hasValidSession: vi.fn(),
  },
}));

import { fetchProjects, searchAdUsers, searchAdGroups, enhancePrompt } from '../api';
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
      .mockResolvedValueOnce(response(200, '{"projects":[{"id":"p1"}],"next_cursor":null}'));

    const page = await fetchProjects();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(authSession.refreshCredentials).toHaveBeenCalledOnce();
    expect(page.projects).toEqual([{ id: 'p1' }]);
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

describe('Directory search', () => {
  it('requests the backend users endpoint with an encoded query and a Bearer token', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ cn: 'djenkins' }]));

    const users = await searchAdUsers('a b');

    expect(fetchMock.mock.calls[0][0]).toBe('/api/directory/users?q=a%20b');
    // Proxied through the backend, so it carries auth like any other request.
    expect(authHeader()).toBe('Bearer tok');
    expect(users).toEqual([{ cn: 'djenkins' }]);
  });

  it('requests the backend groups endpoint with an encoded query', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ cn: 'Legal' }]));

    await searchAdGroups('le');

    expect(fetchMock.mock.calls[0][0]).toBe('/api/directory/groups?q=le');
  });

  it('throws on a non-ok response', async () => {
    fetchMock.mockResolvedValue(response(502, 'Directory service unavailable'));
    await expect(searchAdUsers('dje')).rejects.toThrow(/API error 502/);
  });
});

describe('enhancePrompt', () => {
  it('posts the draft and returns the enhanced text', async () => {
    fetchMock.mockResolvedValue(response(200, '{"enhanced":"a fuller prompt"}'));

    const enhanced = await enhancePrompt('p1', {
      content: 'a todo app',
      model: 'some/model',
      dataSourceNames: ['Sales Postgres'],
      selectedElements: [{ id: 'e1', tag: 'button', selector: '#go', text: 'Go', classes: 'btn', html: '<button>', components: ['App'] }],
    });

    expect(enhanced).toBe('a fuller prompt');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/chat/enhance?project_id=p1');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({
      content: 'a todo app',
      model: 'some/model',
      data_source_names: ['Sales Postgres'],
      selected_elements: [{ tag: 'button', selector: '#go', text: 'Go', classes: 'btn', html: '<button>', components: ['App'] }],
    });
  });

  it('omits project_id when there is no project', async () => {
    fetchMock.mockResolvedValue(response(200, '{"enhanced":"x"}'));

    await enhancePrompt(null, { content: 'a todo app', model: null, dataSourceNames: [], selectedElements: [] });

    expect(fetchMock.mock.calls[0][0]).toBe('/api/chat/enhance');
  });
});
