import { describe, it, expect, vi, beforeEach } from 'vitest';
import { handleVersionMessage, useVersionStore } from '../version';
import { useChatStore } from '../chat';
import type { WSMessage } from '../../types';

vi.mock('../chat', () => {
  let state: Record<string, unknown> = { messages: [] };
  return {
    useChatStore: {
      getState: () => state,
      setState: (partial: unknown) => {
        const update = typeof partial === 'function' ? (partial as (s: unknown) => unknown)(state) : partial;
        state = { ...state, ...(update as Record<string, unknown>) };
      },
    },
  };
});

vi.mock('../files', () => ({
  useFilesStore: {
    getState: () => ({
      loadFileTree: vi.fn(),
      refreshOpenFiles: vi.fn(),
      saveVersion: 0,
    }),
    setState: vi.fn(),
  },
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1' }),
  },
}));

function msg(data: Record<string, unknown>): WSMessage {
  return data as unknown as WSMessage;
}

describe('version_restored handling', () => {
  beforeEach(() => {
    useVersionStore.setState({ versions: [], previewingVersion: null });
  });

  it('trims newer messages back to the restored version', () => {
    useVersionStore.setState({ versions: ['sha1', 'sha2'] });
    useChatStore.setState({
      messages: [
        { id: 'u1', role: 'user', content: 'first', timestamp: 1 },
        { id: 'a1', role: 'assistant', content: '', timestamp: 2, version: 'sha1' },
        { id: 'u2', role: 'user', content: 'second', timestamp: 3 },
        { id: 'a2', role: 'assistant', content: '', timestamp: 4, version: 'sha2' },
      ],
    });
    handleVersionMessage(msg({ type: 'version_restored', commit_sha: 'sha1' }));

    const messages = useChatStore.getState().messages;
    expect(messages.map((m) => m.id)).toEqual(['u1', 'a1']);
    expect(messages[1].version).toEqual('sha1');
    expect(useVersionStore.getState().versions).toEqual(['sha1']);
    expect(useVersionStore.getState().previewingVersion).toBeNull();
  });
});
