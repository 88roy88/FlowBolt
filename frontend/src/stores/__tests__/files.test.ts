import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFilesStore } from '../files';
import { queryClient } from '../../lib/queryClient';
import * as api from '../../services/api';
import type { FileEntry } from '../../types';

vi.mock('../../services/api', () => ({
  fetchFileTree: vi.fn(),
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1' }),
  },
}));

function file(name: string): FileEntry {
  return { name, path: `/${name}`, is_directory: false };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

describe('loadFileTree', () => {
  beforeEach(() => {
    queryClient.clear();
    vi.mocked(api.fetchFileTree).mockReset();
    useFilesStore.setState({
      loadedProjectId: null,
      fileTree: [],
      openFiles: new Map(),
      activeFilePath: null,
    });
  });

  it('a refresh started during an in-flight fetch never adopts the stale snapshot', async () => {
    const staleFetch = deferred<FileEntry[]>();
    const freshFetch = deferred<FileEntry[]>();
    vi.mocked(api.fetchFileTree)
      .mockReturnValueOnce(staleFetch.promise)
      .mockReturnValueOnce(freshFetch.promise);

    const freshTree = [file('old.ts'), file('new.ts')];

    const callA = useFilesStore.getState().loadFileTree();
    await vi.waitFor(() => expect(api.fetchFileTree).toHaveBeenCalledTimes(1));

    const callB = useFilesStore.getState().loadFileTree();
    await vi.waitFor(() => expect(api.fetchFileTree).toHaveBeenCalledTimes(2));

    staleFetch.resolve([file('old.ts')]);
    freshFetch.resolve(freshTree);
    await Promise.all([callA, callB]);

    expect(useFilesStore.getState().fileTree).toEqual(freshTree);
  });
});
