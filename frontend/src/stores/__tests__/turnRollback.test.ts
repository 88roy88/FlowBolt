import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../chat';
import { useErrorStore } from '../errors';
import { handleVersionMessage, useVersionStore } from '../version';
import type { WSMessage } from '../../types';

vi.mock('../files', () => ({
  useFilesStore: {
    getState: () => ({
      openFiles: new Map(),
      updateFileContent: vi.fn(),
      loadFileTree: vi.fn(),
      refreshOpenFiles: vi.fn(),
      saveVersion: 0,
    }),
  },
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1', currentProject: { id: 'proj-1' } }),
  },
}));

vi.mock('../agentAlivePoll', () => ({
  startAgentAlivePolling: vi.fn(),
  stopAgentAlivePolling: vi.fn(),
}));

vi.mock('../../utils/notifications', () => ({ requestPermissionIfNeeded: vi.fn() }));

vi.mock('../../services/api', () => ({
  fetchModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchAgentEvents: vi.fn(),
  updateProjectModel: vi.fn(() => Promise.resolve()),
}));

const socketSend = vi.fn();
vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({ send: socketSend, onMessage: vi.fn(), offMessage: vi.fn() }),
}));

function msg(data: Record<string, unknown>): WSMessage {
  return data as unknown as WSMessage;
}

describe('turn rollback boundary', () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isStreaming: false, agentAlive: null });
    useVersionStore.setState({ pendingDirtyOp: null, previewingVersion: null });
    useErrorStore.setState({ errors: [] });
    socketSend.mockClear();
  });

  it.each([
    {
      code: 'dirty_workspace',
      message: 'You have unsaved edits',
      files: ['src/App.tsx'],
      pendingDirtyOp: { op: 'send', files: ['src/App.tsx'] },
    },
    {
      code: 'run_active',
      message: "Can't edit while the AI is working",
      files: [],
      pendingDirtyOp: null,
    },
    {
      code: 'previewing',
      message: 'Restore this version before editing',
      files: [],
      pendingDirtyOp: null,
    },
  ])('withdraws an optimistic turn refused with $code', ({ code, message, files, pendingDirtyOp }) => {
    useChatStore.getState().sendMessage('add a button');
    expect(useChatStore.getState().messages).toHaveLength(1);

    handleVersionMessage(
      msg({ type: 'version_error', code, message, files }),
    );

    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().agentAlive).toBe(false);
    expect(useChatStore.getState().isStreaming).toBe(false);
    expect(useVersionStore.getState().pendingDirtyOp).toEqual(
      pendingDirtyOp ? expect.objectContaining(pendingDirtyOp) : null,
    );
  });

  it('keeps the turn after the first phase commits it', () => {
    useChatStore.getState().sendMessage('add a button');
    handleVersionMessage(msg({ type: 'phase', phase: 'planning' }));

    handleVersionMessage(
      msg({ type: 'version_error', code: 'run_active', message: "Can't edit while the AI is working", files: [] }),
    );

    expect(useChatStore.getState().messages.map((message) => message.content)).toEqual(['add a button']);
    expect(useErrorStore.getState().errors.map((error) => error.message)).toEqual([
      "Can't edit while the AI is working",
    ]);
  });
});
