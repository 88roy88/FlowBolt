import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../chat';
import type { WSMessage } from '../../types';

let currentProjectId = 'proj-1';
vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: currentProjectId, currentProject: { id: currentProjectId } }),
  },
}));

vi.mock('../agentAlivePoll', () => ({
  startAgentAlivePolling: vi.fn(),
  stopAgentAlivePolling: vi.fn(),
}));

vi.mock('../../services/api', () => ({
  fetchModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchAgentEvents: vi.fn(),
  updateProjectModel: vi.fn(() => Promise.resolve()),
}));

const logInfo = vi.fn();
vi.mock('../../services/logger', () => ({
  logger: { info: (...args: unknown[]) => logInfo(...args) },
}));

const handlers = new Set<(msg: WSMessage) => void>();
const socketSend = vi.fn();
vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({
    send: socketSend,
    onMessage: (handler: (msg: WSMessage) => void) => handlers.add(handler),
    offMessage: (handler: (msg: WSMessage) => void) => handlers.delete(handler),
  }),
}));

function deliver(data: Record<string, unknown>) {
  for (const handler of [...handlers]) handler(data as unknown as WSMessage);
}

function loggedOutcomes() {
  return logInfo.mock.calls.map(([event, props]) => [event, props.outcome]);
}

describe('abortTurn', () => {
  beforeEach(() => {
    currentProjectId = 'proj-1';
    handlers.clear();
    socketSend.mockClear();
    logInfo.mockClear();
    useChatStore.setState({ aborting: false });
  });

  it('sends the abort and logs it as aborted once the server confirms', () => {
    useChatStore.getState().abortTurn();

    expect(socketSend).toHaveBeenCalledWith({ type: 'abort' });
    deliver({ type: 'text', content: 'still working' });
    deliver({ type: 'turn_aborted' });
    deliver({ type: 'action_complete' });

    expect(loggedOutcomes()).toEqual([['response_aborted', 'aborted']]);
    expect(handlers.size).toBe(0);
  });

  it('logs too_late when the turn ends before the abort reaches it', () => {
    useChatStore.getState().abortTurn();
    deliver({ type: 'action_complete' });

    expect(loggedOutcomes()).toEqual([['response_aborted', 'too_late']]);
    expect(handlers.size).toBe(0);
  });

  it('drops the pending outcome when the user switches to another project', () => {
    useChatStore.getState().abortTurn();
    currentProjectId = 'proj-2';
    deliver({ type: 'turn_aborted' });

    expect(logInfo).not.toHaveBeenCalled();
    expect(handlers.size).toBe(0);
  });
});
