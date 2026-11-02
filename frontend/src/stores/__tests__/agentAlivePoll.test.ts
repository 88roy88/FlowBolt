import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';

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
import { startAgentAlivePolling, stopAgentAlivePolling, handleChatConnectionLost } from '../agentAlivePoll';

const initial = useChatStore.getState();
const questions = [{ id: 'q-1', header: 'Who', question: 'Who?', options: [], multi_select: false }];

describe('agent alive poll with the interview card', () => {
  beforeEach(() => {
    useChatStore.setState({ ...initial, agentPhase: 'awaiting_interview', interviewQuestions: questions });
  });

  afterEach(() => {
    stopAgentAlivePolling();
    vi.useRealTimers();
  });

  it('keeps the questions when a poll lands mid-turn and the next one sees the agent gone', async () => {
    vi.useFakeTimers();
    alive.mockResolvedValueOnce({ alive: true, phase: 'awaiting_interview' });
    alive.mockResolvedValueOnce({ alive: false, phase: 'idle' });

    startAgentAlivePolling('p');
    await vi.advanceTimersByTimeAsync(20000);

    expect(useChatStore.getState()).toMatchObject({ interviewQuestions: questions, agentPhase: 'awaiting_interview' });
  });

  it('keeps the questions when the socket drops', () => {
    useChatStore.setState({ isStreaming: true });

    handleChatConnectionLost();

    expect(useChatStore.getState().interviewQuestions).toEqual(questions);
  });
});
