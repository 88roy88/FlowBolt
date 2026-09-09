import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({ send: vi.fn(), onMessage: vi.fn(), offMessage: vi.fn() }),
}));

vi.mock('../../services/api', () => ({
  fetchModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchAgentEvents: vi.fn(),
  updateProjectModel: vi.fn(),
}));

vi.mock('../../utils/notifications', () => ({ requestPermissionIfNeeded: vi.fn() }));

vi.mock('../agentAlivePoll', () => ({
  startAgentAlivePolling: vi.fn(),
  stopAgentAlivePolling: vi.fn(),
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1', currentProject: { id: 'proj-1' } }),
  },
}));

import { useChatStore } from '../chat';

describe('chatStore interviewMode', () => {
  beforeEach(() => {
    useChatStore.setState({ interviewMode: 'interview', messages: [] });
  });

  it('keeps the selected mode while the project stays open', () => {
    useChatStore.getState().setInterviewMode('build');
    useChatStore.getState().sendMessage('build me a todo app');
    expect(useChatStore.getState().interviewMode).toBe('build');
  });

  it('resets the mode when the project is cleared', () => {
    useChatStore.getState().setInterviewMode('build');
    useChatStore.getState().clearMessages();
    expect(useChatStore.getState().interviewMode).toBe('interview');
  });
});
