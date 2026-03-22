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
import type { WSMessage, PlanOverview, ProjectSummary } from '../../types';

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
      sessionId: 'proj-1',
      updateProjectSummary: vi.fn(),
    }),
  },
}));

// ---------- Test helpers ----------

const MOCK_PLAN_OVERVIEW: PlanOverview = {
  summary: 'A todo app',
  features: [{ title: 'Add todos', description: 'User can add items' }],
  decisions: [{ id: 'd1', title: 'State management', chosen: 'useState', alternatives: ['useReducer'] }],
};

const MOCK_PROJECT_SUMMARY: ProjectSummary = {
  summary: 'A todo app with add/remove',
  tech_stack: ['React', 'TypeScript'],
  features: ['Add todos', 'Remove todos'],
  file_overview: { 'src/App.tsx': 'Main component' },
};

const INITIAL_STATE: ChatState = {
  messages: [],
  isStreaming: false,
  currentAssistantMessage: '',
  actions: [],
  agentPhase: 'idle',
  designProgress: { architecture: null, ux: null },
  planOverview: null,
  executionTasks: [],
  error: null,
  fixSteps: [],
  followUpSteps: [],
  followUpDiffs: [],
  projectSummary: null,
  models: [],
  selectedModel: null,
  selectedDataSources: [],
  historyLoaded: true,
  sendMessage: vi.fn() as unknown as ChatState['sendMessage'],
  sendFixError: vi.fn() as unknown as ChatState['sendFixError'],
  respondToPlan: vi.fn() as unknown as ChatState['respondToPlan'],
  addMessage: vi.fn() as unknown as ChatState['addMessage'],
  loadHistory: vi.fn() as unknown as ChatState['loadHistory'],
  clearMessages: vi.fn() as unknown as ChatState['clearMessages'],
  clearError: vi.fn() as unknown as ChatState['clearError'],
  setStreaming: vi.fn() as unknown as ChatState['setStreaming'],
  setSelectedModel: vi.fn() as unknown as ChatState['setSelectedModel'],
  addDataSource: vi.fn() as unknown as ChatState['addDataSource'],
  removeDataSource: vi.fn() as unknown as ChatState['removeDataSource'],
  clearDataSources: vi.fn() as unknown as ChatState['clearDataSources'],
  loadModels: vi.fn() as unknown as ChatState['loadModels'],
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

/** Cast to WSMessage without TS complaining about partial shapes. */
function msg(data: Record<string, unknown>): WSMessage {
  return data as unknown as WSMessage;
}

// ---------- Tests ----------

describe('createSendMessageHandler — build flow', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;
  let cleanup: () => void;

  beforeEach(() => {
    store = createTestStore();
    cleanup = vi.fn();
    setReplayMode(false);
    handler = createSendMessageHandler(store.set, store.get, cleanup);
  });

  it('full build flow produces correct messages and state', () => {
    // 1. User message arrives (from replay)
    handler(msg({ type: 'user_message', content: 'Build a todo app' }));
    expect(store.state().messages).toHaveLength(1);
    expect(store.state().messages[0].role).toBe('user');
    expect(store.state().messages[0].content).toBe('Build a todo app');

    // 2. Design phase
    handler(msg({ type: 'phase', phase: 'designing' }));
    expect(store.state().agentPhase).toBe('designing');

    handler(msg({ type: 'design_progress', stream: 'architecture', content: 'complete' }));
    handler(msg({ type: 'design_progress', stream: 'ux', content: 'complete' }));
    expect(store.state().designProgress).toEqual({ architecture: 'complete', ux: 'complete' });

    // 3. Phase → planning (should create design_complete card)
    handler(msg({ type: 'phase', phase: 'planning' }));
    expect(store.state().agentPhase).toBe('planning');
    expect(store.state().messages).toHaveLength(2);
    expect(store.state().messages[1].agentCard?.type).toBe('design_complete');

    // 4. Plan overview
    handler(msg({ type: 'plan_overview', overview: MOCK_PLAN_OVERVIEW }));
    expect(store.state().planOverview).toEqual(MOCK_PLAN_OVERVIEW);
    expect(store.state().isStreaming).toBe(false);

    // 5. Plan accepted
    handler(msg({ type: 'plan_accepted', overview: MOCK_PLAN_OVERVIEW }));
    expect(store.state().planOverview).toBeNull();
    expect(store.state().messages).toHaveLength(3);
    expect(store.state().messages[2].agentCard?.type).toBe('plan_overview');

    // 6. Execution
    handler(msg({ type: 'phase', phase: 'executing' }));
    expect(store.state().isStreaming).toBe(true);

    handler(msg({ type: 'task_list', tasks: [{ id: 't1', title: 'Types', status: 'pending' }] }));
    expect(store.state().executionTasks).toHaveLength(1);

    handler(msg({ type: 'task_update', taskId: 't1', status: 'running' }));
    expect(store.state().executionTasks[0].status).toBe('running');

    handler(msg({ type: 'task_update', taskId: 't1', status: 'completed' }));
    expect(store.state().executionTasks[0].status).toBe('completed');

    // 7. Completion
    handler(msg({ type: 'action_complete' }));
    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().isStreaming).toBe(false);
    expect(store.state().executionTasks).toHaveLength(0);
    expect(cleanup).toHaveBeenCalledOnce();

    const taskProgressMsg = store.state().messages.find(m => m.agentCard?.type === 'task_progress');
    expect(taskProgressMsg).toBeDefined();
  });

  it('streaming text accumulates and finalizes on action_complete', () => {
    handler(msg({ type: 'text', content: 'Hello ' }));
    handler(msg({ type: 'text', content: 'world' }));
    expect(store.state().currentAssistantMessage).toBe('Hello world');

    handler(msg({ type: 'action_complete' }));
    expect(store.state().currentAssistantMessage).toBe('');
    const result = store.state().messages.find(m => m.role === 'assistant' && m.content === 'Hello world');
    expect(result).toBeDefined();
  });

  it('plan_rejected resets state to idle', () => {
    handler(msg({ type: 'phase', phase: 'planning' }));
    handler(msg({ type: 'plan_rejected', overview: MOCK_PLAN_OVERVIEW }));

    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().isStreaming).toBe(false);
    expect(store.state().planOverview).toBeNull();
    expect(store.state().executionTasks).toHaveLength(0);
  });

  it('error event sets error and cleans up', () => {
    handler(msg({ type: 'phase', phase: 'executing' }));
    handler(msg({ type: 'error', message: 'LLM failed' }));

    expect(store.state().error).toBe('LLM failed');
    expect(store.state().isStreaming).toBe(false);
    expect(store.state().agentPhase).toBe('idle');
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it('data_sources_fetched creates a card with data source info', () => {
    handler(msg({
      type: 'data_sources_fetched',
      data_sources: [{
        data_source_id: '42',
        data_source_name: 'Sales Data',
        data_schema: '{ revenue: number }',
        relevant_fields: 'revenue, date',
      }],
    }));

    const found = store.state().messages.find(m => m.agentCard?.type === 'data_sources_fetched');
    expect(found).toBeDefined();
    const card = found!.agentCard as { type: 'data_sources_fetched'; dataSources: { dataSourceName: string }[] };
    expect(card.dataSources).toHaveLength(1);
    expect(card.dataSources[0].dataSourceName).toBe('Sales Data');
  });

  it('user_message with data_sources attaches them', () => {
    handler(msg({
      type: 'user_message',
      content: 'Show me the data',
      data_sources: [{ id: 1, name: 'Sales' }],
    }));

    const result = store.state().messages[0];
    expect(result.role).toBe('user');
    expect(result.dataSources).toEqual([{ id: 1, name: 'Sales' }]);
  });

  it('unknown event type does not crash', () => {
    expect(() => {
      handler(msg({ type: 'totally_unknown_event' }));
    }).not.toThrow();
  });
});

describe('createSendMessageHandler — followup flow', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;

  beforeEach(() => {
    store = createTestStore();
    setReplayMode(false);
    handler = createSendMessageHandler(store.set, store.get, vi.fn() as unknown as () => void);
  });

  it('followup steps track running → completed', () => {
    handler(msg({
      type: 'followup_step', tool: 'grep',
      args: { pattern: 'useState' }, status: 'running', iteration: 1,
    }));
    expect(store.state().followUpSteps).toHaveLength(1);
    expect(store.state().followUpSteps[0].status).toBe('running');

    handler(msg({
      type: 'followup_step', tool: 'grep',
      args: { pattern: 'useState' }, status: 'completed',
      result_preview: '3 matches found', iteration: 1,
    }));
    expect(store.state().followUpSteps[0].status).toBe('completed');
    expect(store.state().followUpSteps[0].resultPreview).toBe('3 matches found');
  });

  it('action_complete with followup steps creates followup_progress card', () => {
    handler(msg({ type: 'followup_step', tool: 'read_file', args: {}, status: 'running', iteration: 1 }));
    handler(msg({ type: 'followup_step', tool: 'read_file', args: {}, status: 'completed', iteration: 1 }));
    handler(msg({ type: 'text', content: 'I found the issue.' }));
    handler(msg({ type: 'action_complete' }));

    const found = store.state().messages.find(m => m.agentCard?.type === 'followup_progress');
    expect(found).toBeDefined();
    const card = found!.agentCard as { type: 'followup_progress'; steps: unknown[]; answer?: string };
    expect(card.steps).toHaveLength(1);
    expect(card.answer).toBe('I found the issue.');
  });
});

describe('createSendMessageHandler — replay mode', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;

  beforeEach(() => {
    store = createTestStore();
    handler = createSendMessageHandler(store.set, store.get, vi.fn() as unknown as () => void, { replay: true });
  });

  it('uses _ts timestamps instead of Date.now()', () => {
    handler(msg({ type: 'user_message', content: 'Hello', _ts: '2026-01-15T10:30:00.000Z' }));
    expect(store.state().messages[0].timestamp).toBe(new Date('2026-01-15T10:30:00.000Z').getTime());
  });

  it('replay mode skips adding cards to messages', () => {
    handler(msg({ type: 'phase', phase: 'designing', _ts: '2026-01-15T10:30:00Z' }));
    handler(msg({ type: 'design_progress', stream: 'architecture', content: 'complete' }));
    handler(msg({ type: 'design_progress', stream: 'ux', content: 'complete' }));
    handler(msg({ type: 'phase', phase: 'planning' }));

    const designCard = store.state().messages.find(m => m.agentCard?.type === 'design_complete');
    expect(designCard).toBeUndefined();
    expect(store.state().agentPhase).toBe('planning');
  });

  it('action_complete in replay does not add messages', () => {
    handler(msg({ type: 'text', content: 'Done!' }));
    handler(msg({ type: 'action_complete', _ts: '2026-01-15T10:31:00Z' }));

    expect(store.state().currentAssistantMessage).toBe('');
    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().messages).toHaveLength(0);
  });
});

describe('createFixErrorHandler', () => {
  let store: ReturnType<typeof createTestStore>;
  let handler: (msg: WSMessage) => void;
  let cleanup: () => void;

  beforeEach(() => {
    store = createTestStore();
    cleanup = vi.fn();
    setReplayMode(false);
    handler = createFixErrorHandler(store.set, store.get, cleanup);
  });

  it('tracks fix steps and creates fix_progress card on complete', () => {
    handler(msg({ type: 'phase', phase: 'fixing' }));
    expect(store.state().agentPhase).toBe('fixing');

    handler(msg({ type: 'fix_step', step: 'discover', status: 'running', message: 'Finding files...' }));
    expect(store.state().fixSteps).toHaveLength(1);
    expect(store.state().fixSteps[0].status).toBe('running');

    handler(msg({ type: 'fix_step', step: 'discover', status: 'completed', message: 'Found 2 files' }));
    expect(store.state().fixSteps).toHaveLength(1);
    expect(store.state().fixSteps[0].status).toBe('completed');

    handler(msg({ type: 'fix_step', step: 'generate', status: 'running', message: 'Generating fix...' }));
    expect(store.state().fixSteps).toHaveLength(2);

    handler(msg({ type: 'fix_step', step: 'generate', status: 'completed', message: 'Fix applied' }));

    handler(msg({ type: 'action_complete' }));
    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().fixSteps).toHaveLength(0);

    const found = store.state().messages.find(m => m.agentCard?.type === 'fix_progress');
    expect(found).toBeDefined();
    const card = found!.agentCard as { type: 'fix_progress'; steps: unknown[] };
    expect(card.steps).toHaveLength(2);
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it('fix error handler processes file updates', () => {
    handler(msg({ type: 'file', path: 'src/App.tsx', content: 'fixed code' }));
    expect(store.state().actions).toHaveLength(1);
    expect(store.state().actions[0].path).toBe('src/App.tsx');
  });

  it('action_complete without fix steps still cleans up', () => {
    handler(msg({ type: 'text', content: 'No issues found' }));
    handler(msg({ type: 'action_complete' }));

    expect(store.state().agentPhase).toBe('idle');
    expect(store.state().currentAssistantMessage).toBe('');
    expect(cleanup).toHaveBeenCalledOnce();
  });
});

describe('project summary handling', () => {
  it('project_summary is included in action_complete messages', () => {
    const store = createTestStore();
    setReplayMode(false);
    const handler = createSendMessageHandler(store.set, store.get, vi.fn() as unknown as () => void);

    handler(msg({ type: 'project_summary', summary: MOCK_PROJECT_SUMMARY }));
    expect(store.state().projectSummary).toBeDefined();

    handler(msg({ type: 'action_complete' }));

    const found = store.state().messages.find(m => m.agentCard?.type === 'project_summary');
    expect(found).toBeDefined();
    const card = found!.agentCard as { type: 'project_summary'; summary: ProjectSummary };
    expect(card.summary.summary).toBe('A todo app with add/remove');
    expect(store.state().projectSummary).toBeNull();
  });
});
