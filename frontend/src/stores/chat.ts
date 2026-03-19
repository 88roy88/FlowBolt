import { create } from 'zustand';
import type { Message, Action, WSMessage, AIModel, AgentPhase, AgentCard, PlanOverview, ExecutionTask, ProjectSummary, FixStep, FollowUpStep, FileDiff } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { fetchModels, fetchDefaultModel, fetchChatHistory, updateProjectModel } from '../services/api';
import { createFixErrorHandler, createSendMessageHandler } from './chatHandlers';

const CARD_PREFIX = '<!--agent-card:';
const CARD_SUFFIX = '-->';
const CASES_META_PREFIX = '<!--cases-meta:';
const CASES_META_SUFFIX = '-->';
const PACKAGE_META_PREFIX = '<!--package-meta:';
const PACKAGE_META_SUFFIX = '-->';

function parseAgentCard(content: string): { card: AgentCard; remainingContent: string } | undefined {
  const cardIdx = content.indexOf(CARD_PREFIX);
  if (cardIdx === -1) return undefined;
  const endIdx = content.indexOf(CARD_SUFFIX, cardIdx);
  if (endIdx === -1) return undefined;
  try {
    const json = content.slice(cardIdx + CARD_PREFIX.length, endIdx);
    const card = JSON.parse(json) as AgentCard;
    const textBefore = content.slice(0, cardIdx).trim();
    return { card, remainingContent: textBefore };
  } catch {
    return undefined;
  }
}

function parseCasesMeta(content: string): { cases: { id: number; name: string }[]; remainingContent: string } | undefined {
  const casesIdx = content.indexOf(CASES_META_PREFIX);
  if (casesIdx !== -1) {
    const endIdx = content.indexOf(CASES_META_SUFFIX, casesIdx);
    if (endIdx !== -1) {
      try {
        const json = content.slice(casesIdx + CASES_META_PREFIX.length, endIdx);
        const meta = JSON.parse(json) as { caseIds: number[]; caseNames: string[] };
        const cases = meta.caseIds.map((id: number, i: number) => ({ id, name: meta.caseNames[i] || `Case #${id}` }));
        const afterMeta = content.slice(endIdx + CASES_META_SUFFIX.length).trim();
        return { cases, remainingContent: afterMeta };
      } catch { /* fall through */ }
    }
  }

  const metaIdx = content.indexOf(PACKAGE_META_PREFIX);
  if (metaIdx !== -1) {
    const endIdx = content.indexOf(PACKAGE_META_SUFFIX, metaIdx);
    if (endIdx !== -1) {
      try {
        const json = content.slice(metaIdx + PACKAGE_META_PREFIX.length, endIdx);
        const meta = JSON.parse(json) as { packageId: number; packageName: string };
        const afterMeta = content.slice(endIdx + PACKAGE_META_SUFFIX.length).trim();
        return { cases: [{ id: meta.packageId, name: meta.packageName }], remainingContent: afterMeta };
      } catch { /* fall through */ }
    }
  }

  return undefined;
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
  executionTasks: ExecutionTask[];
  fixSteps: FixStep[];
  followUpSteps: FollowUpStep[];
  followUpDiffs: FileDiff[];
  designProgress: { architecture: string | null; ux: string | null };
  projectSummary: ProjectSummary | null;
  selectedCases: { id: number; name: string }[];
  sendMessage: (content: string) => void;
  sendFixError: (errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) => void;
  respondToPlan: (action: 'accept' | 'reject' | 'modify', feedback?: string) => void;
  addMessage: (message: Message) => void;
  loadHistory: (sessionId: string) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
  setStreaming: (streaming: boolean) => void;
  setSelectedModel: (model: string) => void;
  addCase: (pkg: { id: number; name: string }) => void;
  removeCase: (id: number) => void;
  clearCases: () => void;
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
  selectedCases: [],

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

    socket.send({
      type: 'fix_error',
      error_message: errorMessage,
      error_file: errorFile,
      error_line: errorLine,
      error_stack: errorStack,
      model: get().selectedModel || undefined,
    });
  },

  sendMessage(content: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const { selectedCases, selectedModel } = get();

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
      cases: selectedCases.length > 0 ? [...selectedCases] : undefined,
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
      ...(selectedCases.length > 0 && { caseIds: selectedCases.map((c) => c.id) }),
    });

    set({ selectedCases: [] });
  },

  respondToPlan(action: 'accept' | 'reject' | 'modify', feedback?: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const socket = getChatSocket(sessionId);
    socket.send({ type: 'plan_response', action, feedback });

    const state = get();

    if (action === 'accept') {
      const planMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        agentCard: { type: 'plan_overview', overview: state.planOverview!, accepted: true },
      };
      set((s) => ({
        messages: [...s.messages, planMsg],
        isStreaming: true,
        agentPhase: 'planning',
        planOverview: null,
      }));
    } else if (action === 'reject') {
      if (state.planOverview) {
        const planMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: '',
          timestamp: Date.now(),
          agentCard: { type: 'plan_overview', overview: state.planOverview, accepted: false },
        };
        set((s) => ({
          messages: [...s.messages, planMsg],
          agentPhase: 'idle',
          planOverview: null,
          executionTasks: [],
          isStreaming: false,
        }));
      } else {
        set({ agentPhase: 'idle', planOverview: null, executionTasks: [], isStreaming: false });
      }
    } else if (action === 'modify') {
      set({ isStreaming: true, agentPhase: 'planning' });
    }
  },

  addMessage(message: Message) {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  async loadHistory(sessionId: string) {
    try {
      const history = await fetchChatHistory(sessionId);
      const messages: Message[] = history.map((m) => {
        let content = m.content;
        let agentCard: AgentCard | undefined;
        let casesInfo: { id: number; name: string }[] | undefined;

        const cardParsed = parseAgentCard(content);
        if (cardParsed) {
          agentCard = cardParsed.card;
          content = cardParsed.remainingContent;
        }

        if (m.role === 'user') {
          const casesParsed = parseCasesMeta(content);
          if (casesParsed) {
            casesInfo = casesParsed.cases;
            content = casesParsed.remainingContent;
          }
        }

        return {
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content,
          timestamp: new Date(m.created_at).getTime(),
          agentCard,
          cases: casesInfo,
        };
      });
      set({ messages, ...RESET_STATE });
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  },

  clearMessages() {
    set({ messages: [], ...RESET_STATE });
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

  addCase(pkg: { id: number; name: string }) {
    set((state) => {
      if (state.selectedCases.some((c) => c.id === pkg.id)) return state;
      return { selectedCases: [...state.selectedCases, pkg] };
    });
  },

  removeCase(id: number) {
    set((state) => ({ selectedCases: state.selectedCases.filter((c) => c.id !== id) }));
  },

  clearCases() {
    set({ selectedCases: [] });
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
