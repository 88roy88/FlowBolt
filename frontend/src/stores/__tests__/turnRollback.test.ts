import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../chat';
import { useErrorStore } from '../errors';
import { handleVersionMessage, useVersionStore } from '../version';
import type { Message, WSMessage } from '../../types';

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
    useChatStore.setState({ messages: [], isStreaming: false, agentAlive: null, draft: '' });
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
    expect(useChatStore.getState().draft).toBe('add a button');
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
    expect(useChatStore.getState().draft).toBe('');
    expect(useErrorStore.getState().errors.map((error) => error.message)).toEqual([
      "Can't edit while the AI is working",
    ]);
  });

  it('sends the client id with each message', () => {
    useChatStore.getState().sendMessage('add a button');

    const [message] = useChatStore.getState().messages;
    expect(message.editable).toBe(true);
    expect(socketSend).toHaveBeenCalledWith(expect.objectContaining({ type: 'message', message_id: message.id }));
  });
});

describe('rewinding a turn', () => {
  const history: Message[] = [
    { id: 'u1', role: 'user', content: 'build it', timestamp: 1, editable: true },
    { id: 'a1', role: 'assistant', content: 'built', timestamp: 2 },
    { id: 'u2', role: 'user', content: 'make it blue', timestamp: 3, editable: true },
    { id: 'a2', role: 'assistant', content: 'blue now', timestamp: 4 },
  ];

  beforeEach(() => {
    handleVersionMessage(msg({ type: 'phase', phase: 'idle' })); // commit any turn a previous test left pending
    useChatStore.setState({ messages: history, isStreaming: false, agentAlive: null, buildCompleted: true });
    useVersionStore.setState({ pendingDirtyOp: null, previewingVersion: null });
    useErrorStore.setState({ errors: [] });
    socketSend.mockClear();
  });

  it('cuts at the message and resends the edit under a new id', () => {
    useChatStore.getState().rewindTurn('u2', 'make it red');

    const messages = useChatStore.getState().messages;
    expect(messages.map((m) => m.content)).toEqual(['build it', 'built', 'make it red']);
    expect(messages[2].id).not.toBe('u2');
    expect(useChatStore.getState().buildCompleted).toBe(true);
    expect(socketSend).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'rewind', message_id: 'u2', new_message_id: messages[2].id, content: 'make it red' }),
    );
  });

  it('regenerates without content and reopens planning for the first prompt', () => {
    useChatStore.getState().rewindTurn('u1');

    expect(useChatStore.getState().messages.map((m) => m.content)).toEqual(['build it']);
    expect(useChatStore.getState().buildCompleted).toBe(false);
    expect(socketSend.mock.calls[0][0]).not.toHaveProperty('content');
  });

  it('restores the history when the rewind is refused', () => {
    useChatStore.getState().rewindTurn('u1', 'build something else');

    handleVersionMessage(
      msg({ type: 'version_error', code: 'run_active', message: "Can't edit while the AI is working", files: [] }),
    );

    expect(useChatStore.getState().messages).toEqual(history);
    expect(useChatStore.getState().buildCompleted).toBe(true);
    expect(useChatStore.getState().isStreaming).toBe(false);
  });
});
