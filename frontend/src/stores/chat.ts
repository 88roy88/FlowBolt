import { create } from 'zustand';
import type { Message, SelectedElement, Action, WSMessage, AIModel, AgentPhase, PlanOverview, ExecutionTask, ProjectSummary, FixStep, FollowUpStep, FileDiff, InterviewQuestion, InterviewAnswer, InterviewMode } from '../types';
import { WRITE_ROLES } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { fetchModels, fetchDefaultModel, fetchAgentEvents, updateProjectModel } from '../services/api';
import { createFixErrorHandler, createSendMessageHandler, finalizeHistoryReplayState, setReplayMode } from './chatHandlers';
import { armTurn, handleVersionMessage, useVersionStore } from './version';
import { requestPermissionIfNeeded } from '../utils/notifications';
import { AGENT_PHASE, TERMINAL_EVENT_TYPES } from './chatAgentState';
import { startAgentAlivePolling, stopAgentAlivePolling } from './agentAlivePoll';
import { logger } from '../services/logger';

export interface QueuedMessage {
  id: string;
  content: string;
  dataSources: { id: number; name: string }[];
  selectedElements: SelectedElement[];
}

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
  interviewQuestions: InterviewQuestion[] | null;
  interviewMode: InterviewMode;
  executionTasks: ExecutionTask[];
  fixSteps: FixStep[];
  followUpSteps: FollowUpStep[];
  fileDiffs: FileDiff[];
  designProgress: { architecture: string | null; ux: string | null };
  projectSummary: ProjectSummary | null;
  selectedDataSources: { id: number; name: string }[];
  selectedElements: SelectedElement[];
  /** True after the project has completed at least one AI action cycle. */
  buildCompleted: boolean;
  /** Server-reported agent activity from GET /api/iaagent/{id}/alive */
  agentAlive: boolean | null;
  agentAlivePollId: number;
  aborting: boolean;
  queuedMessages: QueuedMessage[];
  /** Stops the queue from sending by itself: the user pressed Stop, even if the turn then finished anyway. */
  queueHeld: boolean;
  draft: string;
  setDraft: (draft: string) => void;
  sendMessage: (content: string, opts?: { keepDraft?: boolean }) => void;
  queueMessage: (content: string) => void;
  removeQueued: (id: string) => void;
  sendQueued: (id: string) => void;
  sendFixError: (errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) => void;
  rollbackTurn: (id: string) => void;
  abortTurn: () => void;
  reloadAfterAbort: (projectId: string) => Promise<void>;
  respondToPlan: (action: 'accept' | 'modify', feedback?: string) => void;
  respondToInterview: (action: 'submit' | 'skip', answers?: InterviewAnswer[]) => void;
  setInterviewMode: (mode: InterviewMode) => void;
  addMessage: (message: Message) => void;
  historyLoaded: boolean;
  loadHistory: (projectId: string, opts?: { keepInput?: boolean }) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
  setStreaming: (streaming: boolean) => void;
  setSelectedModel: (model: string) => void;
  addDataSource: (pkg: { id: number; name: string }) => void;
  removeDataSource: (id: number) => void;
  clearDataSources: () => void;
  addSelectedElement: (element: SelectedElement) => boolean;
  removeSelectedElement: (id: string) => void;
  clearSelectedElements: () => void;
  loadModels: () => Promise<void>;
}

export const MAX_SELECTED_ELEMENTS = 5;

function generateId(): string {
  return crypto.randomUUID();
}

let activeHandler: ((msg: WSMessage) => void) | null = null;
let activeProjectId: string | null = null;

function attachHandler(
  projectId: string,
  socket: ReturnType<typeof getChatSocket>,
  handler: (msg: WSMessage) => void,
) {
  if (activeHandler && activeProjectId === projectId) {
    socket.offMessage(activeHandler);
  }
  activeHandler = handler;
  activeProjectId = projectId;
  socket.onMessage(handler);
}

function detachHandler(socket: ReturnType<typeof getChatSocket>, handler: (msg: WSMessage) => void) {
  socket.offMessage(handler);
  activeHandler = null;
}

function logAbortOutcome(socket: ReturnType<typeof getChatSocket>, projectId: string) {
  const requestedAt = performance.now();
  const onMessage = (msg: WSMessage) => {
    if (useSessionStore.getState().projectId !== projectId) {
      socket.offMessage(onMessage);
      return;
    }
    const outcome =
      msg.type === 'turn_aborted' ? 'aborted' :
      (TERMINAL_EVENT_TYPES as readonly string[]).includes(msg.type) ? 'too_late' :
      null;
    if (!outcome) return;
    socket.offMessage(onMessage);
    logger.info('response_aborted', { outcome, elapsed_ms: Math.round(performance.now() - requestedAt) });
  };
  socket.onMessage(onMessage);
}

const RESET_STATE = {
  currentAssistantMessage: '',
  actions: [] as Action[],
  fixSteps: [] as FixStep[],
  followUpSteps: [] as FollowUpStep[],
  fileDiffs: [] as FileDiff[],
  error: null,
  agentPhase: AGENT_PHASE.idle,
  planOverview: null,
  interviewQuestions: null,
  executionTasks: [] as ExecutionTask[],
  aborting: false,
};

function rememberProjectModel(model: string | null) {
  const currentProject = useSessionStore.getState().currentProject;
  if (currentProject && model) {
    updateProjectModel(currentProject.id, model).catch(() => {});
  }
}

function sendTurn(
  projectId: string,
  content: string,
  { dataSources, selectedElements }: Pick<QueuedMessage, 'dataSources' | 'selectedElements'>,
  keepDraft?: boolean,
): string {
  const { setState: set, getState: get } = useChatStore;
  void requestPermissionIfNeeded();

  const { selectedModel } = get();

  const userMessage: Message = {
    id: generateId(),
    role: 'user',
    content,
    timestamp: Date.now(),
    dataSources: dataSources.length > 0 ? [...dataSources] : undefined,
    selectedElements: selectedElements.length > 0 ? [...selectedElements] : undefined,
  };

  set((state) => ({
    messages: [...state.messages, userMessage],
    isStreaming: true,
    agentAlive: true,
    queueHeld: false,
    ...(!keepDraft && { draft: '' }),
    ...RESET_STATE,
    designProgress: { architecture: null, ux: null },
  }));

  const socket = getChatSocket(projectId);
  const handler = createSendMessageHandler(set, get, () => detachHandler(socket, handler));
  attachHandler(projectId, socket, handler);
  startAgentAlivePolling(projectId);

  socket.send({
    type: 'message',
    content,
    mode: get().interviewMode,
    ...(selectedModel && { model: selectedModel }),
    ...(dataSources.length > 0 && { dataSourceIds: dataSources.map((c) => c.id) }),
    ...(selectedElements.length > 0 && { selectedElements: selectedElements.map(({ id: _id, ...e }) => e) }),
  });

  rememberProjectModel(selectedModel);

  return userMessage.id;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  historyLoaded: false,
  isStreaming: false,
  currentAssistantMessage: '',
  actions: [],
  error: null,
  models: [],
  selectedModel: null,
  agentPhase: AGENT_PHASE.idle,
  planOverview: null,
  interviewQuestions: null,
  interviewMode: 'interview',
  executionTasks: [],
  fixSteps: [],
  followUpSteps: [],
  fileDiffs: [],
  designProgress: { architecture: null, ux: null },
  projectSummary: null,
  selectedDataSources: [],
  selectedElements: [],
  buildCompleted: false,
  agentAlive: null,
  agentAlivePollId: 0,
  aborting: false,
  queuedMessages: [],
  queueHeld: false,
  draft: '',

  setDraft(draft: string) {
    set({ draft });
  },

  sendFixError(errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    void requestPermissionIfNeeded();

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
      agentAlive: true,
      ...RESET_STATE,
    }));

    const socket = getChatSocket(projectId);
    const handler = createFixErrorHandler(set, get, () => detachHandler(socket, handler));
    attachHandler(projectId, socket, handler);
    startAgentAlivePolling(projectId);

    const selectedModel = get().selectedModel;
    socket.send({
      type: 'fix_error',
      error_message: errorMessage,
      error_file: errorFile,
      error_line: errorLine,
      error_stack: errorStack,
      model: selectedModel || undefined,
    });

    rememberProjectModel(selectedModel);

    armTurn({
      run: () => get().sendFixError(errorMessage, errorFile, errorLine, errorStack),
      undo: () => get().rollbackTurn(userMessage.id),
    });
  },

  sendMessage(content: string, opts?: { keepDraft?: boolean }) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;

    const { selectedDataSources, selectedElements } = get();
    const messageId = sendTurn(projectId, content, { dataSources: selectedDataSources, selectedElements }, opts?.keepDraft);

    set({ selectedDataSources: [], selectedElements: [] });
    armTurn({
      run: () => get().sendMessage(content, opts),
      undo: () => {
        get().rollbackTurn(messageId);
        set({ selectedElements, ...((!opts?.keepDraft || !get().draft) && { draft: content }) });
      },
    });
  },

  queueMessage(content: string) {
    set((state) => ({
      queuedMessages: [...state.queuedMessages, {
        id: generateId(),
        content,
        dataSources: state.selectedDataSources,
        selectedElements: state.selectedElements,
      }],
      draft: '',
      selectedDataSources: [],
      selectedElements: [],
    }));
  },

  removeQueued(id: string) {
    set((state) => ({ queuedMessages: state.queuedMessages.filter((m) => m.id !== id) }));
  },

  sendQueued(id: string) {
    const projectId = useSessionStore.getState().projectId;
    const queued = get().queuedMessages.find((m) => m.id === id);
    if (!projectId || !queued) return;

    get().removeQueued(id);
    const messageId = sendTurn(projectId, queued.content, queued, true);
    armTurn({
      run: () => get().sendQueued(id),
      undo: () => {
        get().rollbackTurn(messageId);
        set((state) => ({ queuedMessages: [queued, ...state.queuedMessages] }));
      },
    });
  },

  rollbackTurn(id: string) {
    stopAgentAlivePolling();
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== id),
      isStreaming: false,
      agentAlive: false,
      ...RESET_STATE,
    }));
  },

  abortTurn() {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId || get().aborting) return;
    const socket = getChatSocket(projectId);
    logAbortOutcome(socket, projectId);
    socket.send({ type: 'abort' });
    set({ aborting: true, queueHeld: true });
  },

  reloadAfterAbort(projectId: string) {
    const { draft, queuedMessages, selectedDataSources, selectedElements } = get();
    const dataSources = [...queuedMessages.flatMap((m) => m.dataSources), ...selectedDataSources];
    set({
      draft: [...queuedMessages.map((m) => m.content), draft].filter(Boolean).join('\n\n'),
      selectedDataSources: dataSources.filter((c, i) => dataSources.findIndex((o) => o.id === c.id) === i),
      selectedElements: [...queuedMessages.flatMap((m) => m.selectedElements), ...selectedElements].slice(0, MAX_SELECTED_ELEMENTS),
      queuedMessages: [],
      queueHeld: false,
    });
    return get().loadHistory(projectId, { keepInput: true });
  },

  respondToPlan(action: 'accept' | 'modify', feedback?: string) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;

    const socket = getChatSocket(projectId);
    socket.send({ type: 'plan_response', action, feedback });

    // The backend will emit plan_accepted which the handler processes to add
    // the appropriate message and update state.
    // For 'modify', just show planning state while the plan is being rebuilt.
    if (action === 'modify') {
      set({ isStreaming: true, agentAlive: true, agentPhase: AGENT_PHASE.planning });
    }
    startAgentAlivePolling(projectId);
  },

  respondToInterview(action: 'submit' | 'skip', answers?: InterviewAnswer[]) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;

    const socket = getChatSocket(projectId);
    const handler = createSendMessageHandler(set, get, () => detachHandler(socket, handler));
    attachHandler(projectId, socket, handler);
    socket.send({ type: 'interview_response', action, answers });

    set({ isStreaming: true, agentAlive: true });
    startAgentAlivePolling(projectId);
  },

  setInterviewMode(mode: InterviewMode) {
    set({ interviewMode: mode });
  },

  addMessage(message: Message) {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  async loadHistory(projectId: string, opts?: { keepInput?: boolean }) {
    // Detach any existing handlers from the previous session
    if (activeProjectId && activeProjectId !== projectId) {
      stopAgentAlivePolling();
      const oldSocket = getChatSocket(activeProjectId);
      if (activeHandler) detachHandler(oldSocket, activeHandler);
      oldSocket.offMessage(handleVersionMessage);
      set({ queuedMessages: [], queueHeld: false });
    }

    try {
      // Reset state, then replay all events — events are the single source of truth
      // for both user messages and assistant messages/cards
      set({
        messages: [],
        isStreaming: false,
        historyLoaded: false,
        buildCompleted: false,
        agentAlive: null,
        ...(!opts?.keepInput && { draft: '', selectedElements: [] }),
        ...RESET_STATE,
      });
      useVersionStore.getState().reset();

      const currentProject = useSessionStore.getState().currentProject;
      const canWrite = !currentProject?.role || WRITE_ROLES.has(currentProject.role);

      let turnHandler: ((msg: WSMessage) => void) | null = null;

      if (canWrite) {
        const socket = getChatSocket(projectId);
        turnHandler = createSendMessageHandler(set, get, () => detachHandler(socket, turnHandler!));
        attachHandler(projectId, socket, turnHandler);
        socket.onMessage(handleVersionMessage);
      }

      // Kept separate: the turn handler detaches after each turn, the version handler stays for the session.
      const events = await fetchAgentEvents(projectId);
      const replayHandler = turnHandler ?? createSendMessageHandler(set, get, () => {});
      setReplayMode(true);
      try {
        for (const evt of events) {
          replayHandler(evt as WSMessage);
          handleVersionMessage(evt as WSMessage);
        }
      } finally {
        setReplayMode(false);
      }

      finalizeHistoryReplayState(set, get, events);

      set({ historyLoaded: true });
      startAgentAlivePolling(projectId);
    } catch (err) {
      console.error('Failed to load history:', err);
      set({ historyLoaded: true });
      startAgentAlivePolling(projectId);
    }
  },

  clearMessages() {
    stopAgentAlivePolling();
    set({
      messages: [],
      historyLoaded: false,
      buildCompleted: false,
      agentAlive: null,
      interviewMode: 'interview',
      selectedElements: [],
      queuedMessages: [],
      queueHeld: false,
      ...RESET_STATE,
    });
    useVersionStore.getState().reset();
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

  addSelectedElement(element: SelectedElement) {
    if (get().selectedElements.length >= MAX_SELECTED_ELEMENTS) return false;
    set((state) => ({ selectedElements: [...state.selectedElements, element] }));
    return true;
  },

  removeSelectedElement(id: string) {
    set((state) => ({ selectedElements: state.selectedElements.filter((e) => e.id !== id) }));
  },

  clearSelectedElements() {
    set({ selectedElements: [] });
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
