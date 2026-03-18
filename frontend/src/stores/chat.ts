import { create } from 'zustand';
import type { Message, Action, WSMessage, AIModel, AgentPhase, AgentCard, PlanOverview, ExecutionTask, ProjectSummary, FixStep, FollowUpStep, FileDiff } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { useFilesStore } from './files';
import { fetchModels, fetchDefaultModel, fetchChatHistory, updateProjectModel } from '../services/api';

const CARD_PREFIX = '<!--agent-card:';
const CARD_SUFFIX = '-->';
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

    // Extract text before the card (if any)
    const textBefore = content.slice(0, cardIdx).trim();

    return { card, remainingContent: textBefore };
  } catch {
    return undefined;
  }
}

function parsePackageMeta(content: string): { packageId: number; packageName: string; remainingContent: string } | undefined {
  const metaIdx = content.indexOf(PACKAGE_META_PREFIX);
  if (metaIdx === -1) return undefined;

  const endIdx = content.indexOf(PACKAGE_META_SUFFIX, metaIdx);
  if (endIdx === -1) return undefined;

  try {
    const json = content.slice(metaIdx + PACKAGE_META_PREFIX.length, endIdx);
    const meta = JSON.parse(json) as { type: string; packageId: number; packageName: string };

    // Extract text after the package meta (remove the comment line)
    const afterMeta = content.slice(endIdx + PACKAGE_META_SUFFIX.length).trim();

    return { packageId: meta.packageId, packageName: meta.packageName, remainingContent: afterMeta };
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
  fixSteps: FixStep[];
  followUpSteps: FollowUpStep[];
  followUpDiffs: FileDiff[];
  designProgress: { architecture: string | null; ux: string | null };
  projectSummary: ProjectSummary | null;
  // Package integration
  selectedPackage: { id: number; name: string } | null;
  // Actions
  sendMessage: (content: string) => void;
  sendFixError: (errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) => void;
  respondToPlan: (action: 'accept' | 'reject' | 'modify', feedback?: string) => void;
  addMessage: (message: Message) => void;
  loadHistory: (sessionId: string) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
  setStreaming: (streaming: boolean) => void;
  setSelectedModel: (model: string) => void;
  setSelectedPackage: (pkg: { id: number; name: string } | null) => void;
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
  fixSteps: [],
  followUpSteps: [],
  followUpDiffs: [],
  designProgress: { architecture: null, ux: null },
  projectSummary: null,
  selectedPackage: null,

  sendFixError(errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    // Create a user message with error fix request card
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: '',
      timestamp: Date.now(),
      agentCard: {
        type: 'error_fix_request',
        errorMessage,
        errorFile,
        errorLine,
        errorStack,
      },
    };

    // Set streaming state to show activity - clear any previous fix steps
    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      currentAssistantMessage: '',
      actions: [],
      error: null,
      agentPhase: 'idle',
      planOverview: null,
      executionTasks: [],
      fixSteps: [],  // Clear previous fix steps when starting a new fix
    }));

    const socket = getChatSocket(sessionId);

    if (activeHandler && activeSessionId === sessionId) {
      socket.offMessage(activeHandler);
    }

    const handler = (msg: WSMessage) => {
      switch (msg.type) {
        case 'phase': {
          set({ agentPhase: msg.phase });
          break;
        }
        case 'fix_step': {
          set((state) => {
            const existingStepIndex = state.fixSteps.findIndex((s) => s.step === msg.step);
            if (existingStepIndex >= 0) {
              // Update existing step
              const updatedSteps = [...state.fixSteps];
              updatedSteps[existingStepIndex] = {
                id: updatedSteps[existingStepIndex].id,
                step: msg.step,
                status: msg.status,
                message: msg.message,
              };
              return { fixSteps: updatedSteps };
            } else {
              // Add new step
              return {
                fixSteps: [
                  ...state.fixSteps,
                  {
                    id: generateId(),
                    step: msg.step,
                    status: msg.status,
                    message: msg.message,
                  },
                ],
              };
            }
          });
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
        case 'error': {
          set({ error: msg.message, isStreaming: false, agentPhase: 'idle' });
          socket.offMessage(handler);
          activeHandler = null;
          break;
        }
        case 'action_complete': {
          const state = get();

          // For fix progress, create a frontend message to keep card visible
          // Backend already saved to database, so on refresh we'll see that version
          if (state.fixSteps.length > 0) {
            const fixMessage: Message = {
              id: generateId(),
              role: 'assistant',
              content: state.currentAssistantMessage,
              timestamp: Date.now(),
              agentCard: {
                type: 'fix_progress',
                steps: [...state.fixSteps],
              },
            };
            set((s) => ({
              messages: [...s.messages, fixMessage],
              currentAssistantMessage: '',
              actions: [],
              fixSteps: [],
              isStreaming: false,
              agentPhase: 'idle',
            }));
          } else {
            // Old behavior for non-fix flows
            set({
              currentAssistantMessage: '',
              actions: [],
              isStreaming: false,
              agentPhase: 'idle',
            });
          }
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
    const msg: WSMessage = {
      type: 'fix_error',
      error_message: errorMessage,
      error_file: errorFile,
      error_line: errorLine,
      error_stack: errorStack,
      model: selectedModel || undefined,
    };
    socket.send(msg);
  },

  sendMessage(content: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const { selectedPackage, selectedModel } = get();

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
      package: selectedPackage ? { id: selectedPackage.id, name: selectedPackage.name } : null,
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
      followUpSteps: [],
      followUpDiffs: [],
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
        case 'project_summary': {
          set({ projectSummary: msg.summary });
          // Bake the summary into chat as a card
          const summaryMsg: Message = {
            id: generateId(),
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
            agentCard: { type: 'project_summary', summary: msg.summary },
          };
          set((s) => ({ messages: [...s.messages, summaryMsg] }));
          // Update projects store so Info icon appears without refresh
          const currentProject = useSessionStore.getState().currentProject;
          if (currentProject) {
            useSessionStore.getState().updateProjectSummary(
              currentProject.id,
              JSON.stringify(msg.summary)
            );
          }
          break;
        }
        case 'followup_step': {
          set((state) => {
            if (msg.status === 'running') {
              const stepId = generateId();
              return {
                followUpSteps: [
                  ...state.followUpSteps,
                  {
                    id: stepId,
                    tool: msg.tool as FollowUpStep['tool'],
                    args: msg.args,
                    status: 'running',
                    iteration: msg.iteration,
                  },
                ],
              };
            } else {
              // Update the last running step for this tool+iteration
              const steps = [...state.followUpSteps];
              const idx = steps.findLastIndex(
                (s) => s.tool === msg.tool && s.iteration === msg.iteration && s.status === 'running'
              );
              if (idx >= 0) {
                steps[idx] = {
                  ...steps[idx],
                  status: msg.status as FollowUpStep['status'],
                  resultPreview: msg.result_preview,
                };
              }
              return { followUpSteps: steps };
            }
          });
          break;
        }
        case 'followup_diffs': {
          set({ followUpDiffs: msg.diffs });
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
        case 'package_fetched': {
          // Create a message card for package fetched
          const packageMsg: Message = {
            id: generateId(),
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
            agentCard: {
              type: 'package_fetched',
              packageId: msg.package_id,
              packageName: msg.package_name,
              dataSchema: msg.data_schema,
              relevantFields: msg.relevant_fields,
            },
          };
          set((s) => ({ messages: [...s.messages, packageMsg] }));
          break;
        }
        case 'package_error': {
          // Package fetch failed - show error but don't block the flow
          console.warn(`Package error: ${msg.message}`);
          // Could optionally set a non-blocking warning message
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

          // Save follow-up progress card
          if (state.followUpSteps.length > 0) {
            const filesChanged = state.actions
              .filter((a) => a.type === 'file' && a.path)
              .map((a) => a.path!);
            newMessages.push({
              id: generateId(),
              role: 'assistant',
              content: state.currentAssistantMessage,
              actions: state.actions.length > 0 ? [...state.actions] : undefined,
              timestamp: Date.now(),
              agentCard: {
                type: 'followup_progress',
                steps: [...state.followUpSteps],
                answer: state.currentAssistantMessage || undefined,
                filesChanged: filesChanged.length > 0 ? filesChanged : undefined,
                diffs: state.followUpDiffs.length > 0 ? [...state.followUpDiffs] : undefined,
              },
            });
          } else if (state.currentAssistantMessage) {
            // Save streaming text as a message (follow-up flow)
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
            followUpSteps: [],
            followUpDiffs: [],
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

    const msg: WSMessage = {
      type: 'message',
      content,
      ...(selectedModel && { model: selectedModel }),
      ...(selectedPackage && { packageId: selectedPackage.id }),
    };
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
        let content = m.content;
        let agentCard: AgentCard | undefined;
        let packageInfo: { id: number; name: string } | null = null;

        // Parse agent card
        const cardParsed = parseAgentCard(content);
        if (cardParsed) {
          agentCard = cardParsed.card;
          content = cardParsed.remainingContent;
        }

        // Parse package metadata (for user messages)
        if (m.role === 'user') {
          const packageParsed = parsePackageMeta(content);
          if (packageParsed) {
            packageInfo = { id: packageParsed.packageId, name: packageParsed.packageName };
            content = packageParsed.remainingContent;
          }
        }

        return {
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content,
          timestamp: new Date(m.created_at).getTime(),
          agentCard,
          package: packageInfo,
        };
      });
      set({ messages, currentAssistantMessage: '', actions: [], fixSteps: [], followUpSteps: [], followUpDiffs: [], error: null, agentPhase: 'idle', planOverview: null, executionTasks: [] });
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  },

  clearMessages() {
    set({ messages: [], currentAssistantMessage: '', actions: [], fixSteps: [], followUpSteps: [], followUpDiffs: [], error: null, agentPhase: 'idle', planOverview: null, executionTasks: [] });
  },

  clearError() {
    set({ error: null });
  },

  setStreaming(streaming: boolean) {
    set({ isStreaming: streaming });
  },

  setSelectedModel(model: string) {
    set({ selectedModel: model });
    // Save the selected model to the project
    const currentProject = useSessionStore.getState().currentProject;
    if (currentProject) {
      updateProjectModel(currentProject.id, model).catch((err) => {
        console.error('Failed to save selected model:', err);
      });
    }
  },

  setSelectedPackage(pkg: { id: number; name: string } | null) {
    set({ selectedPackage: pkg });
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
