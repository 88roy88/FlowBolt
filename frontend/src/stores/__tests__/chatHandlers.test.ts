/**
 * Tests for chatHandlers — the core event processing logic.
 *
 * These tests create a real Zustand-like state container, feed real event
 * sequences through the handlers, and assert the resulting state.
 * No React rendering, no browser — pure logic tests.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { createSendMessageHandler, createFixErrorHandler, setReplayMode } from '../chatHandlers';
import type { ChatState } from '../chat';
import type { WSMessage } from '../../types';

// Mock external stores — we don't want real file fetches or session lookups
vi.mock('../files', () => ({
  useFilesStore: {
    getState: () => ({
      openFiles: new Map(),
      updateFileContent: vi.fn(),
      loadFileTree: vi.fn(),
    }),
  },
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({
      currentProject: { id: 'proj-1' },
      sessionId: 'sess-1',
      updateProjectSummary: vi.fn(),
    }),
  },
}));

// ---------- Test harness ----------

const INITIAL_STATE: ChatState = {
  messages: [],
  isStreaming: false,
  historyLoaded: true,
  currentAssistantMessage: '',
  actions: [],
  agentPhase: 'idle',
  designProgress: {},
  planOverview: null,
  executionTasks: [],
  error: null,
  fixSteps: [],
  followUpSteps: [],
  followUpDiffs: [],
  projectSummary: null,
  // These are functions on the real store — we don't need them for handler tests
  sendMessage: vi.fn() as unknown as ChatState['sendMessage'],
  fixError: vi.fn() as unknown as ChatState['fixError'],
  loadHistory: vi.fn() as unknown as ChatState['loadHistory'],
  loadModels: vi.fn() as unknown as ChatState['loadModels'],
  setStreaming: vi.fn() as unknown as ChatState['setStreaming'],
  availableModels: [],
  selectedModel: null,
  setSelectedModel: vi.fn() as unknown as ChatState['setSelectedModel'],
};

/** Create a state container that behaves like Zustand's set/get. */
function createTestStore(initial: ChatState = { ...INITIAL_STATE }) {
  let state = { ...initial };
  const set = (partial: Partial<ChatState> | ((s: ChatState) => Partial<ChatState>)) => {
    const update = typeof partial === 'function' ? partial(state) : partial;
    state = { ...state, ...update };
  };
  const get = () => state;
  return { set, get, state: () => state };
}

/** Feed a sequence of events through a handler, with optional _ts timestamps. */
function feedEvents(
  handler: (msg: WSMessage) => void,
  events: (WSMessage & { _ts?: string })[],
) {
  for (const event of events) {
    handler(event as WSMessage);
  }
}

// ---------- Tests ----------

describe('createSendMessageHandler — build flow', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;
  let cleanup: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    store = createTestStore();
    cleanup = vi.fn();
    setReplayMode(false);
    handler = createSendMessageHandler(store.set, store.get, cleanup);
  });

  it('full build flow produces correct messages and state', () => {
    // 1. User message arrives (from replay)
    handler({ type: 'user_message', content: 'Build a todo app' } as WSMessage);
    expect(store.state().messages).toHaveLength(1);
    expect(store.state().messages[0].role).toBe('user');
    expect(store.state().messages[0].content).toBe('Build a todo app');

    // 2. Design phase
    handler({ type: 'phase', phase: 'designing' } as WSMessage);
    expect(store.state().agentPhase).toBe('designing');

    handler({ type: 'design_progress', stream: 'architecture', content: 'complete' } as WSMessage);
    handler({ type: 'design_progress', stream: 'ux', content: 'complete' } as WSMessage);
    expect(store.state().designProgress).toEqual({ architecture: 'complete', ux: 'complete' });

    // 3. Phase → planning (should create design_complete card)
    handler({ type: 'phase', phase: 'planning' } as WSMessage);
    expect(store.state().agentPhase).toBe('planning');
    expect(store.state().messages).toHaveLength(2); // user + design_complete
    expect(store.state().messages[1].agentCard?.type).toBe('design_complete');

    // 4. Plan overview
    const overview = {
      summary: 'A todo app',
      tasks: [{ id: 't1', title: 'Types', files: ['src/types.ts'], depends_on: [] }],
    };
    handler({ type: 'plan_overview', overview } as WSMessage);
    expect(store.state().planOverview).toEqual(overview);
    expect(store.state().isStreaming).toBe(false); // waiting for approval

    // 5. Plan accepted
    handler({ type: 'plan_accepted', overview } as WSMessage);
    expect(store.state().planOverview).toBeNull(); // cleared after acceptance
    expect(store.state().messages).toHaveLength(3); // + plan accepted card
    expect(store.state().messages[2].agentCard?.type).toBe('plan_overview');

    // 6. Execution
    handler({ type: 'phase', phase: 'executing' } as WSMessage);
    expect(store.state().isStreaming).toBe(true);

    handler({ type: 'task_list', tasks: [{ id: 't1', title: 'Types', status: 'pending' }] } as WSMessage);
    expect(store.state().executionTasks).toHaveLength(1);

    handler({ type: 'task_update', taskId: 't1', status: 'running' } as WSMessage);
    expect(store.state().executionTasks[0].status).toBe('running');

    handler({ type: 'task_update', taskId: 't1', status: 'completed' } as WSMessage);
    expect(store.state().executionTasks[0].status).toBe('completed');

    // 7. Completion
    handler({ type: 'action_complete' } as WSMessage);
    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().isStreaming).toBe(false);
    expect(store.state().executionTasks).toHaveLength(0); // cleared
    expect(cleanup).toHaveBeenCalledOnce();

    // Should have task_progress card in messages
    const taskProgressMsg = store.state().messages.find(m => m.agentCard?.type === 'task_progress');
    expect(taskProgressMsg).toBeDefined();
  });

  it('streaming text accumulates and finalizes on action_complete', () => {
    handler({ type: 'text', content: 'Hello ' } as WSMessage);
    handler({ type: 'text', content: 'world' } as WSMessage);
    expect(store.state().currentAssistantMessage).toBe('Hello world');

    handler({ type: 'action_complete' } as WSMessage);
    expect(store.state().currentAssistantMessage).toBe(''); // cleared
    // Should have created a message with the accumulated text
    const msg = store.state().messages.find(m => m.role === 'assistant' && m.content === 'Hello world');
    expect(msg).toBeDefined();
  });

  it('plan_rejected resets state to idle', () => {
    handler({ type: 'phase', phase: 'planning' } as WSMessage);
    const overview = { summary: 'Bad plan', tasks: [] };
    handler({ type: 'plan_rejected', overview } as WSMessage);

    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().isStreaming).toBe(false);
    expect(store.state().planOverview).toBeNull();
    expect(store.state().executionTasks).toHaveLength(0);
  });

  it('error event sets error and cleans up', () => {
    handler({ type: 'phase', phase: 'executing' } as WSMessage);
    handler({ type: 'error', message: 'LLM failed' } as WSMessage);

    expect(store.state().error).toBe('LLM failed');
    expect(store.state().isStreaming).toBe(false);
    expect(store.state().agentPhase).toBe('idle');
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it('cases_fetched creates a card with package data', () => {
    handler({
      type: 'cases_fetched',
      cases: [{
        package_id: '42',
        package_name: 'Sales Data',
        data_schema: '{ revenue: number }',
        relevant_fields: 'revenue, date',
      }],
    } as WSMessage);

    const msg = store.state().messages.find(m => m.agentCard?.type === 'cases_fetched');
    expect(msg).toBeDefined();
    expect(msg!.agentCard!.cases).toHaveLength(1);
    expect(msg!.agentCard!.cases[0].packageName).toBe('Sales Data');
  });

  it('user_message with cases attaches them', () => {
    handler({
      type: 'user_message',
      content: 'Show me the data',
      cases: [{ id: 1, name: 'Sales' }],
    } as WSMessage);

    const msg = store.state().messages[0];
    expect(msg.role).toBe('user');
    expect(msg.cases).toEqual([{ id: 1, name: 'Sales' }]);
  });

  it('unknown event type does not crash', () => {
    expect(() => {
      handler({ type: 'totally_unknown_event' } as unknown as WSMessage);
    }).not.toThrow();
  });
});

describe('createSendMessageHandler — followup flow', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;

  beforeEach(() => {
    store = createTestStore();
    setReplayMode(false);
    handler = createSendMessageHandler(store.set, store.get, vi.fn());
  });

  it('followup steps track running → completed', () => {
    handler({
      type: 'followup_step',
      tool: 'grep',
      args: { pattern: 'useState' },
      status: 'running',
      iteration: 1,
    } as WSMessage);
    expect(store.state().followUpSteps).toHaveLength(1);
    expect(store.state().followUpSteps[0].status).toBe('running');

    handler({
      type: 'followup_step',
      tool: 'grep',
      args: { pattern: 'useState' },
      status: 'completed',
      result_preview: '3 matches found',
      iteration: 1,
    } as WSMessage);
    expect(store.state().followUpSteps[0].status).toBe('completed');
    expect(store.state().followUpSteps[0].resultPreview).toBe('3 matches found');
  });

  it('action_complete with followup steps creates followup_progress card', () => {
    handler({ type: 'followup_step', tool: 'read_file', args: {}, status: 'running', iteration: 1 } as WSMessage);
    handler({ type: 'followup_step', tool: 'read_file', args: {}, status: 'completed', iteration: 1 } as WSMessage);
    handler({ type: 'text', content: 'I found the issue.' } as WSMessage);
    handler({ type: 'action_complete' } as WSMessage);

    const msg = store.state().messages.find(m => m.agentCard?.type === 'followup_progress');
    expect(msg).toBeDefined();
    expect(msg!.agentCard!.steps).toHaveLength(1);
    expect(msg!.agentCard!.answer).toBe('I found the issue.');
  });
});

describe('createSendMessageHandler — replay mode', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;

  beforeEach(() => {
    store = createTestStore();
    handler = createSendMessageHandler(store.set, store.get, vi.fn(), { replay: true });
  });

  it('uses _ts timestamps instead of Date.now()', () => {
    handler({
      type: 'user_message',
      content: 'Hello',
      _ts: '2026-01-15T10:30:00.000Z',
    } as WSMessage);

    expect(store.state().messages[0].timestamp).toBe(new Date('2026-01-15T10:30:00.000Z').getTime());
  });

  it('replay mode skips adding cards to messages', () => {
    handler({ type: 'phase', phase: 'designing', _ts: '2026-01-15T10:30:00Z' } as WSMessage);
    handler({ type: 'design_progress', stream: 'architecture', content: 'complete' } as WSMessage);
    handler({ type: 'design_progress', stream: 'ux', content: 'complete' } as WSMessage);
    handler({ type: 'phase', phase: 'planning' } as WSMessage);

    // In replay mode, design_complete card should NOT be added
    const designCard = store.state().messages.find(m => m.agentCard?.type === 'design_complete');
    expect(designCard).toBeUndefined();

    // But phase should still update
    expect(store.state().agentPhase).toBe('planning');
  });

  it('action_complete in replay does not add messages', () => {
    handler({ type: 'text', content: 'Done!' } as WSMessage);
    handler({
      type: 'action_complete',
      _ts: '2026-01-15T10:31:00Z',
    } as WSMessage);

    // State should be cleared
    expect(store.state().currentAssistantMessage).toBe('');
    expect(store.state().agentPhase).toBe('idle');
    // But no message should be added in replay mode
    expect(store.state().messages).toHaveLength(0);
  });
});

describe('createFixErrorHandler', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;
  let cleanup: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    store = createTestStore();
    cleanup = vi.fn();
    setReplayMode(false);
    handler = createFixErrorHandler(store.set, store.get, cleanup);
  });

  it('tracks fix steps and creates fix_progress card on complete', () => {
    handler({ type: 'phase', phase: 'fixing' } as WSMessage);
    expect(store.state().agentPhase).toBe('fixing');

    handler({ type: 'fix_step', step: 'discover', status: 'running', message: 'Finding files...' } as WSMessage);
    expect(store.state().fixSteps).toHaveLength(1);
    expect(store.state().fixSteps[0].status).toBe('running');

    handler({ type: 'fix_step', step: 'discover', status: 'completed', message: 'Found 2 files' } as WSMessage);
    expect(store.state().fixSteps).toHaveLength(1); // updated, not duplicated
    expect(store.state().fixSteps[0].status).toBe('completed');

    handler({ type: 'fix_step', step: 'generate', status: 'running', message: 'Generating fix...' } as WSMessage);
    expect(store.state().fixSteps).toHaveLength(2);

    handler({ type: 'fix_step', step: 'generate', status: 'completed', message: 'Fix applied' } as WSMessage);

    handler({ type: 'action_complete' } as WSMessage);
    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().fixSteps).toHaveLength(0); // cleared

    const msg = store.state().messages.find(m => m.agentCard?.type === 'fix_progress');
    expect(msg).toBeDefined();
    expect(msg!.agentCard!.steps).toHaveLength(2);
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it('fix error handler processes file updates', () => {
    handler({ type: 'file', path: 'src/App.tsx', content: 'fixed code' } as WSMessage);
    expect(store.state().actions).toHaveLength(1);
    expect(store.state().actions[0].path).toBe('src/App.tsx');
  });

  it('action_complete without fix steps still cleans up', () => {
    handler({ type: 'text', content: 'No issues found' } as WSMessage);
    handler({ type: 'action_complete' } as WSMessage);

    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().currentAssistantMessage).toBe('');
    expect(cleanup).toHaveBeenCalledOnce();
  });
});

describe('project summary handling', () => {
  it('project_summary is included in action_complete messages', () => {
    const store = createTestStore();
    setReplayMode(false);
    const handler = createSendMessageHandler(store.set, store.get, vi.fn());

    handler({
      type: 'project_summary',
      summary: { name: 'Todo App', description: 'A simple todo', techStack: ['React', 'TypeScript'] },
    } as WSMessage);
    expect(store.state().projectSummary).toBeDefined();

    handler({ type: 'action_complete' } as WSMessage);

    const summaryMsg = store.state().messages.find(m => m.agentCard?.type === 'project_summary');
    expect(summaryMsg).toBeDefined();
    expect(summaryMsg!.agentCard!.summary.name).toBe('Todo App');
    // Summary should be cleared after action_complete
    expect(store.state().projectSummary).toBeNull();
  });
});
