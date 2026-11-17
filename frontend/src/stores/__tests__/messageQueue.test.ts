import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../chat';
import { handleVersionMessage, useVersionStore } from '../version';
import { AGENT_PHASE } from '../chatAgentState';
import type { InterviewQuestion, PlanOverview, SelectedElement, WSMessage } from '../../types';

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1', currentProject: { id: 'proj-1' } }),
  },
}));

vi.mock('../agentAlivePoll', () => ({
  startAgentAlivePolling: vi.fn(),
  stopAgentAlivePolling: vi.fn(),
}));

vi.mock('../../services/api', () => ({
  fetchModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchAgentEvents: vi.fn(() => Promise.resolve([])),
  fetchFileTree: vi.fn(() => Promise.resolve([])),
  updateProjectModel: vi.fn(() => Promise.resolve()),
}));

vi.mock('../../services/logger', () => ({ logger: { info: vi.fn() } }));

vi.mock('../../utils/notifications', () => ({
  requestPermissionIfNeeded: vi.fn(),
  notifyAgentNeedsAttention: vi.fn(),
  notifyBuildComplete: vi.fn(),
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
  const msg = data as unknown as WSMessage;
  handleVersionMessage(msg);
  for (const handler of [...handlers]) handler(msg);
}

// Every turn reports a phase once it has started, which confirms the send to version.ts.
function startRun(prompt: string) {
  useChatStore.getState().sendMessage(prompt);
  deliver({ type: 'phase', phase: AGENT_PHASE.exploring });
}

function sentPrompts() {
  return socketSend.mock.calls.map(([msg]) => msg).filter((msg) => msg.type === 'message').map((msg) => msg.content);
}

function queuedContents() {
  return useChatStore.getState().queuedMessages.map((m) => m.content);
}

const element = (id: string) => ({ id, tag: 'div' }) as unknown as SelectedElement;

describe('message queue', () => {
  beforeEach(() => {
    handlers.clear();
    socketSend.mockClear();
    useVersionStore.getState().reset();
    useChatStore.setState({
      messages: [],
      draft: '',
      error: null,
      aborting: false,
      queuedMessages: [],
      queueHeld: false,
      selectedDataSources: [],
      selectedElements: [],
      planOverview: null,
      interviewQuestions: null,
      agentPhase: AGENT_PHASE.idle,
    });
  });

  it('sends one queued message per released run, in order', () => {
    const chat = useChatStore.getState();
    chat.queueMessage('first');
    chat.queueMessage('second');
    expect(sentPrompts()).toEqual([]);

    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual(['first']);
    expect(queuedContents()).toEqual(['second']);

    deliver({ type: 'phase', phase: AGENT_PHASE.exploring });
    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual(['first', 'second']);
    expect(queuedContents()).toEqual([]);
  });

  it('waits for the run to be released, not for action_complete', () => {
    startRun('running');
    useChatStore.getState().queueMessage('next');

    deliver({ type: 'action_complete' });
    expect(sentPrompts()).toEqual(['running']);

    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual(['running', 'next']);
  });

  it('sends the attachments captured when the message was queued', () => {
    useChatStore.setState({ selectedDataSources: [{ id: 7, name: 'Sales' }], selectedElements: [element('e1')] });
    useChatStore.getState().queueMessage('with attachments');

    const state = useChatStore.getState();
    expect(state.selectedDataSources).toEqual([]);
    expect(state.selectedElements).toEqual([]);

    deliver({ type: 'run_released' });

    expect(socketSend).toHaveBeenCalledWith(expect.objectContaining({
      content: 'with attachments',
      dataSourceIds: [7],
      selectedElements: [{ tag: 'div' }],
    }));
  });

  it('leaves what the user is composing alone when a queued message sends', () => {
    useChatStore.getState().queueMessage('queued');
    useChatStore.setState({
      draft: 'still typing',
      selectedDataSources: [{ id: 7, name: 'Sales' }],
      selectedElements: [element('e1')],
    });

    deliver({ type: 'run_released' });

    const state = useChatStore.getState();
    expect(state.draft).toBe('still typing');
    expect(state.selectedDataSources).toEqual([{ id: 7, name: 'Sales' }]);
    expect(state.selectedElements).toEqual([element('e1')]);
  });

  it('holds the queue after a failed turn until the user sends it', () => {
    startRun('running');
    useChatStore.getState().queueMessage('next');

    deliver({ type: 'error', message: 'AI processing failed' });
    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual(['running']);
    expect(queuedContents()).toEqual(['next']);

    useChatStore.getState().sendQueued(useChatStore.getState().queuedMessages[0].id);
    expect(sentPrompts()).toEqual(['running', 'next']);
  });

  it('waits while a plan needs approval and resumes after the build', () => {
    useChatStore.getState().queueMessage('next');
    useChatStore.setState({ agentPhase: AGENT_PHASE.awaiting_approval, planOverview: {} as PlanOverview });

    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual([]);

    useChatStore.setState({ agentPhase: AGENT_PHASE.idle, planOverview: null });
    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual(['next']);
  });

  it('waits while an interview needs answers', () => {
    useChatStore.getState().queueMessage('next');
    useChatStore.setState({ agentPhase: AGENT_PHASE.awaiting_interview, interviewQuestions: [] as InterviewQuestion[] });

    deliver({ type: 'run_released' });
    expect(sentPrompts()).toEqual([]);
    expect(queuedContents()).toEqual(['next']);
  });

  it('holds the queue when Stop arrives too late to abort the turn', () => {
    startRun('running');
    useChatStore.getState().queueMessage('next');
    useChatStore.getState().abortTurn();

    deliver({ type: 'action_complete' });
    deliver({ type: 'run_released' });

    expect(sentPrompts()).toEqual(['running']);
    expect(queuedContents()).toEqual(['next']);
  });

  it('moves the queue back into the input when a turn is aborted', async () => {
    const chat = useChatStore.getState();
    useChatStore.setState({ selectedDataSources: [{ id: 7, name: 'Sales' }], selectedElements: [element('e1')] });
    chat.queueMessage('first');
    useChatStore.setState({ selectedDataSources: [{ id: 7, name: 'Sales' }], selectedElements: [element('e2')] });
    chat.queueMessage('second');
    useChatStore.setState({ draft: 'still typing' });
    chat.abortTurn();

    deliver({ type: 'turn_aborted' });
    await vi.waitFor(() => expect(useChatStore.getState().historyLoaded).toBe(true));

    const state = useChatStore.getState();
    expect(state.draft).toBe('first\n\nsecond\n\nstill typing');
    expect(state.selectedDataSources).toEqual([{ id: 7, name: 'Sales' }]);
    expect(state.selectedElements).toEqual([element('e1'), element('e2')]);
    expect(state.queuedMessages).toEqual([]);
    expect(state.queueHeld).toBe(false);
    expect(sentPrompts()).toEqual([]);
  });

  it('puts a refused message back at the front of the queue', () => {
    const chat = useChatStore.getState();
    chat.queueMessage('first');
    chat.queueMessage('second');
    deliver({ type: 'run_released' });

    deliver({ type: 'error', message: 'An agent is already running for this project' });

    expect(queuedContents()).toEqual(['first', 'second']);
    expect(useChatStore.getState().messages).toEqual([]);
  });

  it('sends a message once after the dirty-workspace dialog retries it', () => {
    useChatStore.getState().queueMessage('next');
    deliver({ type: 'run_released' });

    deliver({ type: 'version_error', message: 'Dirty', code: 'dirty_workspace', files: ['a.ts'] });
    expect(queuedContents()).toEqual(['next']);

    useVersionStore.getState().resolveDirtyOp('discard');

    expect(sentPrompts()).toEqual(['next', 'next']);
    expect(queuedContents()).toEqual([]);
    expect(useChatStore.getState().messages.map((m) => m.content)).toEqual(['next']);
  });
});
