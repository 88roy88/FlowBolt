import { afterEach, describe, it, expect, vi } from 'vitest';

const alive = vi.fn();
vi.mock('../../services/api', () => ({
  fetchAgentAlive: (...a: unknown[]) => alive(...a),
  fetchModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchAgentEvents: vi.fn(),
  updateProjectModel: vi.fn(),
}));
vi.mock('../session', () => ({
  useSessionStore: { getState: () => ({ projectId: 'p', currentProject: { id: 'p' } }) },
}));

import { useChatStore } from '../chat';
import { startAgentAlivePolling, handleChatConnectionLost } from '../agentAlivePoll';
import { createSendMessageHandler } from '../chatHandlers';

const questions = [{ id: 'q-1', header: 'Who', question: 'Who?', options: [], multi_select: false }];

function showQuestions() {
  const handle = createSendMessageHandler(useChatStore.setState, useChatStore.getState, () => {});
  handle({ type: 'phase', phase: 'awaiting_interview' });
  handle({ type: 'interview_questions', questions });
}

describe('agent alive poll with the interview card', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('keeps the questions when a poll lands mid-turn and the next one sees the agent gone', async () => {
    vi.useFakeTimers();
    showQuestions();
    alive.mockResolvedValueOnce({ alive: true, phase: 'awaiting_interview' });
    alive.mockResolvedValueOnce({ alive: false, phase: 'idle' });

    startAgentAlivePolling('p');
    await vi.advanceTimersByTimeAsync(20000);

    const state = useChatStore.getState();
    expect(state.interviewQuestions).not.toBeNull();
    expect(state.agentPhase).toBe('awaiting_interview');
  });

  it('keeps the questions when the socket drops', () => {
    showQuestions();
    useChatStore.setState({ isStreaming: true });

    handleChatConnectionLost();

    expect(useChatStore.getState().interviewQuestions).not.toBeNull();
  });
});
