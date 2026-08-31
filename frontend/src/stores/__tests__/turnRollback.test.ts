import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../chat';
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

describe('a refused turn leaves no trace', () => {
  beforeEach(() => {
    useChatStore.setState({ messages: [], isStreaming: false, agentAlive: null });
    useVersionStore.setState({ pendingDirtyOp: null, previewingVersion: null });
    socketSend.mockClear();
  });

  it('withdraws the optimistic message when the tree is dirty, and re-sends on save', () => {
    useChatStore.getState().sendMessage('add a button');
    expect(useChatStore.getState().messages).toHaveLength(1);

    handleVersionMessage(
      msg({ type: 'version_error', message: 'You have unsaved edits', code: 'dirty_workspace', files: ['src/App.tsx'] }),
    );

    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().agentAlive).toBe(false);
    expect(useVersionStore.getState().pendingDirtyOp).toMatchObject({ op: 'send', files: ['src/App.tsx'] });

    useVersionStore.getState().resolveDirtyOp('save');

    expect(useChatStore.getState().messages.map((m) => m.content)).toEqual(['add a button']);
    expect(socketSend).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'message', content: 'add a button' }));
  });

  it('withdraws it when an agent is already running', () => {
    useChatStore.getState().sendMessage('add a button');

    handleVersionMessage(msg({ type: 'error', message: 'An agent is already running' }));

    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it('keeps the turn once the agent reports a phase', () => {
    useChatStore.getState().sendMessage('add a button');
    handleVersionMessage(msg({ type: 'phase', phase: 'planning' }));

    handleVersionMessage(msg({ type: 'version_error', message: 'Version operation failed', code: 'failed' }));

    expect(useChatStore.getState().messages).toHaveLength(1);
  });
});
