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

vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({ send: vi.fn() }),
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

describe('version_committed handling', () => {
  beforeEach(() => {
    useVersionStore.setState({ versions: [], previewingVersion: null });
    useChatStore.setState({ messages: [{ id: 'a1', role: 'assistant', content: 'done', timestamp: 1 }] });
  });

  it('stamps an AI version onto the last assistant message', () => {
    handleVersionMessage(msg({ type: 'version_committed', commit_sha: 'sha1', author: 'ai' }));

    const messages = useChatStore.getState().messages;
    expect(messages).toHaveLength(1);
    expect(messages[0].version).toEqual('sha1');
  });

  it('appends its own row for a user version instead of stamping the assistant message', () => {
    handleVersionMessage(
      msg({ type: 'version_committed', commit_sha: 'sha2', author: 'user', files: ['src/App.tsx'] }),
    );

    const messages = useChatStore.getState().messages;
    expect(messages).toHaveLength(2);
    expect(messages[0].version).toBeUndefined();
    expect(messages[1].version).toEqual('sha2');
    expect(messages[1].agentCard).toEqual({ type: 'user_edit', files: ['src/App.tsx'] });
  });

  it('treats a version with no author as AI, so existing history keeps working', () => {
    handleVersionMessage(msg({ type: 'version_committed', commit_sha: 'sha3' }));

    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().messages[0].version).toEqual('sha3');
  });
});

describe('version_error handling', () => {
  beforeEach(() => {
    useVersionStore.setState({ versions: [], previewingVersion: null, pendingDirtyOp: null });
    useChatStore.setState({ messages: [{ id: 'a1', role: 'assistant', content: 'done', timestamp: 1 }] });
  });

  it('opens the unsaved-edits dialog for the op that was refused', () => {
    useVersionStore.getState().previewVersion('sha1');
    handleVersionMessage(msg({ type: 'version_error', message: 'You have unsaved edits', code: 'dirty_workspace' }));

    expect(useVersionStore.getState().pendingDirtyOp).toEqual({ op: 'preview', commit_sha: 'sha1' });
  });

  it('leaves chat state untouched, so a version failure is not reported as a failed build', () => {
    handleVersionMessage(msg({ type: 'version_error', message: 'Version operation failed', code: 'failed' }));

    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useChatStore.getState().agentAlive).toBeUndefined();
    expect(useVersionStore.getState().pendingDirtyOp).toBeNull();
  });
});
