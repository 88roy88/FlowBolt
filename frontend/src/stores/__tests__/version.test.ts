import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { WSMessage } from '../../types';
import { useChatStore } from '../chat';
import { useErrorStore } from '../errors';
import { createSendMessageHandler } from '../chatHandlers';
import { handleVersionMessage, useVersionStore } from '../version';

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
  },
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1' }),
  },
}));

const socketSend = vi.fn();
vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({ send: socketSend }),
}));

function msg(data: Record<string, unknown>): WSMessage {
  return data as unknown as WSMessage;
}

describe('version store wire contracts', () => {
  beforeEach(() => {
    useVersionStore.getState().reset();
    useChatStore.setState({ messages: [], agentAlive: undefined });
    useErrorStore.setState({ errors: [] });
    socketSend.mockReset();
  });

  it('stamps AI versions and gives user edits their own version row', () => {
    useChatStore.setState({
      messages: [
        { id: 'a1', role: 'assistant', content: 'first', timestamp: 1 },
        { id: 'a2', role: 'assistant', content: 'second', timestamp: 2 },
      ],
    });

    const diffs = [{ path: 'src/App.tsx', diff: '--- a/src/App.tsx\n+++ b/src/App.tsx\n@@ -1 +1 @@\n-a\n+b', is_new: false }];
    const userEdit = msg({
      type: 'version_committed',
      commit_sha: 'sha-user',
      author: 'user',
      diffs,
      _ts: '2026-09-06T13:58:23.350895Z',
    });
    // Same order as loadHistory: the agent handler banks _ts before version.ts reads it back.
    const replayEvent = createSendMessageHandler(useChatStore.setState, useChatStore.getState, () => {});

    handleVersionMessage(msg({ type: 'version_committed', commit_sha: 'sha-ai', author: 'ai' }));
    handleVersionMessage(msg({ type: 'version_committed', commit_sha: 'sha-legacy' }));
    replayEvent(userEdit);
    handleVersionMessage(userEdit);

    const messages = useChatStore.getState().messages;
    expect(messages.map((message) => message.version)).toEqual([undefined, 'sha-legacy', 'sha-user']);
    expect(messages[2].role).toBe('user');
    expect(messages[2].agentCard).toEqual({ type: 'user_edit', diffs });
    expect(messages[2].timestamp).toBe(Date.parse('2026-09-06T13:58:23.350895Z'));
    expect(useVersionStore.getState().versions).toEqual(['sha-ai', 'sha-legacy', 'sha-user']);
  });

  it.each([
    {
      name: 'a prior version',
      target: 'sha1',
      versions: ['sha0', 'sha1', 'sha2'],
      expectedMessages: ['u1', 'a1'],
      expectedVersions: ['sha0', 'sha1'],
    },
    {
      name: 'v0',
      target: 'sha0',
      versions: ['sha0', 'sha1'],
      expectedMessages: [],
      expectedVersions: ['sha0'],
    },
  ])('trims messages and versions when restoring $name', ({ target, versions, expectedMessages, expectedVersions }) => {
    useVersionStore.setState({ versions, previewingVersion: 'sha1' });
    useChatStore.setState({
      messages: [
        { id: 'u1', role: 'user', content: 'first', timestamp: 1 },
        { id: 'a1', role: 'assistant', content: 'done', timestamp: 2, version: 'sha1' },
        { id: 'u2', role: 'user', content: 'second', timestamp: 3 },
        { id: 'a2', role: 'assistant', content: 'done', timestamp: 4, version: 'sha2' },
      ],
    });

    handleVersionMessage(msg({ type: 'version_restored', commit_sha: target }));

    expect(useChatStore.getState().messages.map((message) => message.id)).toEqual(expectedMessages);
    expect(useVersionStore.getState()).toMatchObject({
      versions: expectedVersions,
      previewingVersion: null,
    });
  });

  it('keeps the refused operation and server-owned dirty file list', () => {
    useVersionStore.getState().previewVersion('sha1');

    handleVersionMessage(
      msg({
        type: 'version_error',
        code: 'dirty_workspace',
        message: 'You have unsaved edits',
        files: ['src/App.tsx', 'src/index.css'],
      }),
    );

    expect(useVersionStore.getState().pendingDirtyOp).toEqual({
      op: 'preview',
      commit_sha: 'sha1',
      files: ['src/App.tsx', 'src/index.css'],
    });
  });

  it.each([
    ['save', 'save_version'],
    ['discard', 'discard_edits'],
  ] as const)('settles %s before retrying the refused operation', (resolution, settlementType) => {
    const sent: unknown[] = [];
    socketSend.mockImplementation((message: unknown) => sent.push(message));
    useVersionStore.getState().restoreVersion('sha1');
    handleVersionMessage(
      msg({ type: 'version_error', code: 'dirty_workspace', message: 'You have unsaved edits', files: [] }),
    );
    sent.length = 0;

    useVersionStore.getState().resolveDirtyOp(resolution);

    expect(sent).toEqual([
      { type: settlementType },
      { type: 'restore_version', commit_sha: 'sha1' },
    ]);
    expect(useVersionStore.getState().pendingDirtyOp).toBeNull();
  });

  it('cancels a refused operation without sending anything', () => {
    useVersionStore.getState().previewVersion('sha1');
    handleVersionMessage(
      msg({ type: 'version_error', code: 'dirty_workspace', message: 'You have unsaved edits', files: [] }),
    );
    socketSend.mockClear();

    useVersionStore.getState().dismissDirtyOp();

    expect(socketSend).not.toHaveBeenCalled();
    expect(useVersionStore.getState().pendingDirtyOp).toBeNull();
  });

  it('keeps preview state when a failed operation is followed by the correction frame', () => {
    useVersionStore.getState().previewVersion('sha1');
    handleVersionMessage(msg({ type: 'version_preview_active', commit_sha: 'sha1', is_latest: false }));

    handleVersionMessage(msg({ type: 'version_error', code: 'failed', message: 'Version operation failed' }));
    handleVersionMessage(msg({ type: 'version_preview_active', commit_sha: 'sha1', is_latest: false }));

    expect(useVersionStore.getState().previewingVersion).toBe('sha1');
    expect(useErrorStore.getState().errors.map((error) => error.message)).toEqual(['Version operation failed']);
    expect(useChatStore.getState().agentAlive).toBeUndefined();
  });

  it('replaces dirty files only when the server broadcasts workspace state', () => {
    handleVersionMessage(msg({ type: 'workspace_dirty', files: ['src/App.tsx'] }));
    expect(useVersionStore.getState().dirtyFiles).toEqual(['src/App.tsx']);

    useVersionStore.getState().discardEdits();
    expect(useVersionStore.getState().dirtyFiles).toEqual(['src/App.tsx']);

    handleVersionMessage(msg({ type: 'workspace_dirty', files: [] }));
    expect(useVersionStore.getState().dirtyFiles).toEqual([]);
  });
});
