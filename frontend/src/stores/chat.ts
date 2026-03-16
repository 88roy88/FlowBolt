import { create } from 'zustand';
import type { Message, Action, WSMessage, AIModel, AgentPhase, AgentCard, PlanOverview, ExecutionTask } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { useFilesStore } from './files';
import { fetchModels, fetchDefaultModel, fetchChatHistory } from '../services/api';

const CARD_PREFIX = '<!--agent-card:';
const CARD_SUFFIX = '-->';

function parseAgentCard(content: string): AgentCard | undefined {
  if (!content.startsWith(CARD_PREFIX)) return undefined;
  const endIdx = content.indexOf(CARD_SUFFIX);
  if (endIdx === -1) return undefined;
  try {
    const json = content.slice(CARD_PREFIX.length, endIdx);
    return JSON.parse(json) as AgentCard;
  } catch {
    return undefined;
  }
}

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentAssistantMessage: string;
  actions: Action[];
  error: string | null;
  models: AIModel[];
  selectedModel: string | null;
  // Agent state
  agentPhase: AgentPhase;
  planOverview: PlanOverview | null;
  executionTasks: ExecutionTask[];
  designProgress: { architecture: string | null; ux: string | null };
  // Actions
  sendMessage: (content: string) => void;
  respondToPlan: (action: 'accept' | 'reject' | 'modify', feedback?: string) => void;
  addMessage: (message: Message) => void;
  loadHistory: (sessionId: string) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
  setStreaming: (streaming: boolean) => void;
  setSelectedModel: (model: string) => void;
  loadModels: () => Promise<void>;
}

function generateId(): string {
  return crypto.randomUUID();
}

let activeHandler: ((msg: WSMessage) => void) | null = null;
let activeSessionId: string | null = null;

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
  designProgress: { architecture: null, ux: null },

  sendMessage(content: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      currentAssistantMessage: '',
      actions: [],
      error: null,
      agentPhase: 'idle',
      planOverview: null,
      executionTasks: [],
      designProgress: { architecture: null, ux: null },
    }));

    const socket = getChatSocket(sessionId);
    const assistantId = generateId();

    if (activeHandler && activeSessionId === sessionId) {
      socket.offMessage(activeHandler);
    }

    const handler = (msg: WSMessage) => {
      switch (msg.type) {
        case 'phase': {
          const prevPhase = get().agentPhase;

          // Bake design progress card when design phase completes
          if (prevPhase === 'designing' && msg.phase === 'planning') {
            const dp = get().designProgress;
            const designMsg: Message = {
              id: generateId(),
              role: 'assistant',
              content: '',
              timestamp: Date.now(),
              agentCard: {
                type: 'design_complete',
                architecture: dp.architecture === 'complete',
                ux: dp.ux === 'complete',
              },
            };
            set((s) => ({ messages: [...s.messages, designMsg] }));
          }

          set({ agentPhase: msg.phase });
          if (msg.phase === 'executing') {
            set({ isStreaming: true });
          }
          break;
        }
        case 'design_progress': {
          set((state) => ({
            designProgress: {
              ...state.designProgress,
              [msg.stream]: msg.content,
            },
          }));
          break;
        }
        case 'plan_overview': {
          set({
            planOverview: msg.overview,
            isStreaming: false,
          });
          break;
        }
        case 'task_list': {
          set({ executionTasks: msg.tasks });
          break;
        }
        case 'task_update': {
          set((state) => ({
            executionTasks: state.executionTasks.map((t) =>
              t.id === msg.taskId
                ? { ...t, status: msg.status }
                : t
            ),
          }));
          if (msg.file) {
            useFilesStore.getState().loadFileTree();
          }
          break;
        }
        case 'text': {
          set((state) => ({
            currentAssistantMessage: state.currentAssistantMessage + msg.content,
          }));
          break;
        }
        case 'file': {
          set((state) => ({
            actions: [
              ...state.actions,
              { type: 'file', path: msg.path, content: msg.content },
            ],
          }));
          const filesStore = useFilesStore.getState();
          if (filesStore.openFiles.has(msg.path)) {
            filesStore.updateFileContent(msg.path, msg.content);
          }
          filesStore.loadFileTree();
          break;
        }
        case 'shell_output': {
          set((state) => ({
            actions: [
              ...state.actions,
              { type: 'shell', command: msg.command, output: msg.output },
            ],
          }));
          break;
        }
        case 'error': {
          set({ error: msg.message, isStreaming: false, agentPhase: 'idle' });
          socket.offMessage(handler);
          activeHandler = null;
          break;
        }
        case 'action_complete': {
          const state = get();
          const newMessages: Message[] = [];

          // Save streaming text as a message (follow-up flow)
          if (state.currentAssistantMessage) {
            newMessages.push({
              id: generateId(),
              role: 'assistant',
              content: state.currentAssistantMessage,
              actions: state.actions.length > 0 ? [...state.actions] : undefined,
              timestamp: Date.now(),
            });
          }

          // Save task progress card as a message (agent flow)
          if (state.executionTasks.length > 0) {
            newMessages.push({
              id: generateId(),
              role: 'assistant',
              content: '',
              actions: state.actions.length > 0 ? [...state.actions] : undefined,
              timestamp: Date.now(),
              agentCard: {
                type: 'task_progress',
                tasks: [...state.executionTasks],
              },
            });
          }

          set((s) => ({
            messages: [...s.messages, ...newMessages],
            currentAssistantMessage: '',
            actions: [],
            isStreaming: false,
            agentPhase: 'idle',
            planOverview: null,
            executionTasks: [],
          }));
          socket.offMessage(handler);
          activeHandler = null;
          useFilesStore.getState().loadFileTree();
          break;
        }
      }
    };

    activeHandler = handler;
    activeSessionId = sessionId;
    socket.onMessage(handler);

    const { selectedModel } = get();
    const msg: WSMessage = selectedModel
      ? { type: 'message', content, model: selectedModel }
      : { type: 'message', content };
    socket.send(msg);
  },

  respondToPlan(action: 'accept' | 'reject' | 'modify', feedback?: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const socket = getChatSocket(sessionId);
    const msg: WSMessage = { type: 'plan_response', action, feedback };
    socket.send(msg);

    const state = get();

    if (action === 'accept') {
      // Bake the accepted plan into chat history
      const planMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        agentCard: {
          type: 'plan_overview',
          overview: state.planOverview!,
          accepted: true,
        },
      };
      set((s) => ({
        messages: [...s.messages, planMsg],
        isStreaming: true,
        agentPhase: 'planning',
        planOverview: null,
      }));
    } else if (action === 'reject') {
      // Bake the rejected plan into chat history
      if (state.planOverview) {
        const planMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: '',
          timestamp: Date.now(),
          agentCard: {
            type: 'plan_overview',
            overview: state.planOverview,
            accepted: false,
          },
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
        const card = parseAgentCard(m.content);
        return {
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: card ? '' : m.content,
          timestamp: new Date(m.created_at).getTime(),
          agentCard: card,
        };
      });
      set({ messages, currentAssistantMessage: '', actions: [], error: null, agentPhase: 'idle', planOverview: null, executionTasks: [] });
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  },

  clearMessages() {
    set({ messages: [], currentAssistantMessage: '', actions: [], error: null, agentPhase: 'idle', planOverview: null, executionTasks: [] });
  },

  clearError() {
    set({ error: null });
  },

  setStreaming(streaming: boolean) {
    set({ isStreaming: streaming });
  },

  setSelectedModel(model: string) {
    set({ selectedModel: model });
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
