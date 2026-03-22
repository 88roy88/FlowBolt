import { create } from 'zustand';
import type { Message, Action, WSMessage, AIModel, AgentPhase, PlanOverview, ExecutionTask, ProjectSummary, FixStep, FollowUpStep, FileDiff } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { fetchModels, fetchDefaultModel, fetchAgentEvents, updateProjectModel } from '../services/api';
import { createFixErrorHandler, createSendMessageHandler } from './chatHandlers';

export interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentAssistantMessage: string;
  actions: Action[];
  error: string | null;
  models: AIModel[];
  selectedModel: string | null;
  agentPhase: AgentPhase;
  planOverview: PlanOverview | null;
  executionTasks: ExecutionTask[];
  fixSteps: FixStep[];
  followUpSteps: FollowUpStep[];
  followUpDiffs: FileDiff[];
  designProgress: { architecture: string | null; ux: string | null };
  projectSummary: ProjectSummary | null;
  selectedDataSources: { id: number; name: string }[];
  sendMessage: (content: string) => void;
  sendFixError: (errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) => void;
  respondToPlan: (action: 'accept' | 'reject' | 'modify', feedback?: string) => void;
  addMessage: (message: Message) => void;
  historyLoaded: boolean;
  loadHistory: (sessionId: string) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
  setStreaming: (streaming: boolean) => void;
  setSelectedModel: (model: string) => void;
  addDataSource: (pkg: { id: number; name: string }) => void;
  removeDataSource: (id: number) => void;
  clearDataSources: () => void;
  loadModels: () => Promise<void>;
}

function generateId(): string {
  return crypto.randomUUID();
}

let activeHandler: ((msg: WSMessage) => void) | null = null;
let activeSessionId: string | null = null;

function attachHandler(
  sessionId: string,
  socket: ReturnType<typeof getChatSocket>,
  handler: (msg: WSMessage) => void,
) {
  if (activeHandler && activeSessionId === sessionId) {
    socket.offMessage(activeHandler);
  }
  activeHandler = handler;
  activeSessionId = sessionId;
  socket.onMessage(handler);
}

function detachHandler(socket: ReturnType<typeof getChatSocket>, handler: (msg: WSMessage) => void) {
  socket.offMessage(handler);
  activeHandler = null;
}

const RESET_STATE = {
  currentAssistantMessage: '',
  actions: [] as Action[],
  fixSteps: [] as FixStep[],
  followUpSteps: [] as FollowUpStep[],
  followUpDiffs: [] as FileDiff[],
  error: null,
  agentPhase: 'idle' as AgentPhase,
  planOverview: null,
  executionTasks: [] as ExecutionTask[],
};

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  historyLoaded: false,
  isStreaming: false,
  currentAssistantMessage: '',
  actions: [],
  error: null,
  models: [],
  selectedModel: null,
  agentPhase: 'idle',
  planOverview: null,
  executionTasks: [],
  fixSteps: [],
  followUpSteps: [],
  followUpDiffs: [],
  designProgress: { architecture: null, ux: null },
  projectSummary: null,
  selectedDataSources: [],

  sendFixError(errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: '',
      timestamp: Date.now(),
      agentCard: { type: 'error_fix_request', errorMessage, errorFile, errorLine, errorStack },
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      ...RESET_STATE,
    }));

    const socket = getChatSocket(sessionId);
    const handler = createFixErrorHandler(set, get, () => detachHandler(socket, handler));
    attachHandler(sessionId, socket, handler);

    const selectedModel = get().selectedModel;
    socket.send({
      type: 'fix_error',
      error_message: errorMessage,
      error_file: errorFile,
      error_line: errorLine,
      error_stack: errorStack,
      model: selectedModel || undefined,
    });

    const currentProject = useSessionStore.getState().currentProject;
    if (currentProject && selectedModel) {
      updateProjectModel(currentProject.id, selectedModel).catch(() => {});
    }
  },

  sendMessage(content: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const { selectedDataSources, selectedModel } = get();

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
      dataSources: selectedDataSources.length > 0 ? [...selectedDataSources] : undefined,
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      ...RESET_STATE,
      designProgress: { architecture: null, ux: null },
    }));

    const socket = getChatSocket(sessionId);
    const handler = createSendMessageHandler(set, get, () => detachHandler(socket, handler));
    attachHandler(sessionId, socket, handler);

    socket.send({
      type: 'message',
      content,
      ...(selectedModel && { model: selectedModel }),
      ...(selectedDataSources.length > 0 && { dataSourceIds: selectedDataSources.map((c) => c.id) }),
    });

    // Persist the model to the project so it's restored on next visit
    const currentProject = useSessionStore.getState().currentProject;
    if (currentProject && selectedModel) {
      updateProjectModel(currentProject.id, selectedModel).catch(() => {});
    }

    set({ selectedDataSources: [] });
  },

  respondToPlan(action: 'accept' | 'reject' | 'modify', feedback?: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const socket = getChatSocket(sessionId);
    socket.send({ type: 'plan_response', action, feedback });

    // The backend will emit plan_accepted/plan_rejected events which the
    // handler will process to add the appropriate message and update state.
    // For 'modify', just show planning state while the plan is being rebuilt.
    if (action === 'modify') {
      set({ isStreaming: true, agentPhase: 'planning' });
    }
  },

  addMessage(message: Message) {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  async loadHistory(sessionId: string) {
    // Detach any existing handler from the previous session
    if (activeHandler && activeSessionId && activeSessionId !== sessionId) {
      const oldSocket = getChatSocket(activeSessionId);
      detachHandler(oldSocket, activeHandler);
    }

    try {
      // Reset state, then replay all events — events are the single source of truth
      // for both user messages and assistant messages/cards
      set({ messages: [], isStreaming: false, historyLoaded: false, ...RESET_STATE });

      const socket = getChatSocket(sessionId);
      const handler = createSendMessageHandler(set, get, () => detachHandler(socket, handler));
      attachHandler(sessionId, socket, handler);

      const events = await fetchAgentEvents(sessionId);
      for (const evt of events) {
        handler(evt as import('../types').WSMessage);
      }

      set({ historyLoaded: true });
    } catch (err) {
      console.error('Failed to load history:', err);
      set({ historyLoaded: true });
    }
  },

  clearMessages() {
    set({ messages: [], historyLoaded: false, ...RESET_STATE });
  },

  clearError() {
    set({ error: null });
  },

  setStreaming(streaming: boolean) {
    set({ isStreaming: streaming });
  },

  setSelectedModel(model: string) {
    set({ selectedModel: model });
    const currentProject = useSessionStore.getState().currentProject;
    if (currentProject) {
      updateProjectModel(currentProject.id, model).catch((err) => {
        console.error('Failed to save selected model:', err);
      });
    }
  },

  addDataSource(pkg: { id: number; name: string }) {
    set((state) => {
      if (state.selectedDataSources.some((c) => c.id === pkg.id)) return state;
      return { selectedDataSources: [...state.selectedDataSources, pkg] };
    });
  },

  removeDataSource(id: number) {
    set((state) => ({ selectedDataSources: state.selectedDataSources.filter((c) => c.id !== id) }));
  },

  clearDataSources() {
    set({ selectedDataSources: [] });
  },

  async loadModels() {
    try {
      const [models, defaultModel] = await Promise.all([
        fetchModels(),
        fetchDefaultModel(),
      ]);
      const modelIds = new Set(models.map((m) => m.id));
      if (defaultModel && !modelIds.has(defaultModel)) {
        models.unshift({ id: defaultModel, name: defaultModel, provider: 'default' });
      }
      set((state) => ({
        models,
        selectedModel: state.selectedModel ?? defaultModel,
      }));
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  },
}));
