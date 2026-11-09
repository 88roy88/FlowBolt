import { describe, it, expect, beforeEach, vi } from 'vitest';

const send = vi.hoisted(() => vi.fn());
vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({ send, onMessage: vi.fn(), offMessage: vi.fn() }),
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
import { fetchAgentEvents } from '../../services/api';

describe('chatStore interview', () => {
  beforeEach(() => {
    send.mockClear();
    useChatStore.setState({ interviewMode: 'interview', messages: [] });
  });

  it('sends the selected mode and keeps it while the project stays open', () => {
    useChatStore.getState().setInterviewMode('build');
    useChatStore.getState().sendMessage('build me a todo app');

    expect(send).toHaveBeenCalledWith(expect.objectContaining({ type: 'message', mode: 'build' }));
    expect(useChatStore.getState().interviewMode).toBe('build');
  });

  it('sends the interview answers', () => {
    const answers = [{ question_id: 'q-1', values: ['Me'] }];

    useChatStore.getState().respondToInterview('submit', answers);

    expect(send).toHaveBeenCalledWith({ type: 'interview_response', action: 'submit', answers });
  });

  it('keeps the selected mode across loadHistory', async () => {
    vi.mocked(fetchAgentEvents).mockResolvedValue([]);
    useChatStore.getState().setInterviewMode('build');
    await useChatStore.getState().loadHistory('proj-1');
    expect(useChatStore.getState().interviewMode).toBe('build');
  });

  it('resets the mode when the project is cleared', () => {
    useChatStore.getState().setInterviewMode('build');
    useChatStore.getState().clearMessages();
    expect(useChatStore.getState().interviewMode).toBe('interview');
  });
});
