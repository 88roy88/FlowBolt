import { create } from 'zustand';
import type { ChatAttachment, Message, SelectedElement, Action, WSMessage, AIModel, AgentPhase, PlanOverview, ExecutionTask, ProjectSummary, FixStep, FollowUpStep, FileDiff } from '../types';
import { WRITE_ROLES } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { fetchModels, fetchDefaultModel, fetchAgentEvents, updateProjectModel, uploadAttachment } from '../services/api';
import { attachmentKind, MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS, prepareImage, type AttachmentKind } from '../utils/attachments';
// The bare singleton: '../i18n' initialises it at startup but touches localStorage on import.
import i18n from 'i18next';
import { createFixErrorHandler, createSendMessageHandler, finalizeHistoryReplayState, setReplayMode } from './chatHandlers';
import { armTurn, handleVersionMessage, useVersionStore } from './version';
import { requestPermissionIfNeeded } from '../utils/notifications';
import { AGENT_PHASE } from './chatAgentState';
import { startAgentAlivePolling, stopAgentAlivePolling } from './agentAlivePoll';

export interface PendingAttachment {
  localId: string;
  name: string;
  kind: AttachmentKind;
  previewUrl: string | null;
  status: 'uploading' | 'ready' | 'failed';
  progress: number;
  upload?: ChatAttachment;
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
  fileDiffs: FileDiff[];
  designProgress: { architecture: string | null; ux: string | null };
  projectSummary: ProjectSummary | null;
  selectedDataSources: { id: number; name: string }[];
  selectedElements: SelectedElement[];
  pendingAttachments: PendingAttachment[];
  /** True after the project has completed at least one AI action cycle. */
  buildCompleted: boolean;
  /** Server-reported agent activity from GET /api/iaagent/{id}/alive */
  agentAlive: boolean | null;
  agentAlivePollId: number;
  draft: string;
  setDraft: (draft: string) => void;
  sendMessage: (content: string, opts?: { keepDraft?: boolean }) => void;
  sendFixError: (errorMessage: string, errorFile?: string, errorLine?: number, errorStack?: string) => void;
  rollbackTurn: (id: string) => void;
  respondToPlan: (action: 'accept' | 'modify', feedback?: string) => void;
  addMessage: (message: Message) => void;
  historyLoaded: boolean;
  loadHistory: (projectId: string) => Promise<void>;
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
  addAttachments: (files: File[]) => void;
  removeAttachment: (localId: string) => void;
  loadModels: () => Promise<void>;
}

export const MAX_SELECTED_ELEMENTS = 5;

class AttachmentTooLarge extends Error {}

function currentModel(state: Pick<ChatState, 'models' | 'selectedModel'>): AIModel | undefined {
  return state.models.find((m) => m.id === state.selectedModel) ?? state.models[0];
}

function dropAttachments(attachments: PendingAttachment[]): [] {
  for (const a of attachments) if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
  return [];
}

async function uploadPending(
  projectId: string,
  file: File,
  pending: PendingAttachment,
  update: (patch: Partial<PendingAttachment>) => void,
): Promise<void> {
  try {
    const prepared = pending.kind === 'image' ? await prepareImage(file) : { blob: file, width: undefined, height: undefined };
    if (prepared.blob.size > MAX_ATTACHMENT_BYTES) {
      throw new AttachmentTooLarge(i18n.t('chat.attachment.tooLarge', { name: file.name, mb: MAX_ATTACHMENT_BYTES / (1024 * 1024) }));
    }
    const upload = await uploadAttachment(projectId, prepared.blob, {
      name: file.name,
      width: prepared.width,
      height: prepared.height,
      onProgress: (progress) => update({ progress }),
    });
    update({ status: 'ready', progress: 1, upload });
  } catch (err) {
    update({ status: 'failed' });
    throw err;
  }
}

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

const RESET_STATE = {
  currentAssistantMessage: '',
  actions: [] as Action[],
  fixSteps: [] as FixStep[],
  followUpSteps: [] as FollowUpStep[],
  fileDiffs: [] as FileDiff[],
  error: null,
  agentPhase: AGENT_PHASE.idle,
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
  agentPhase: AGENT_PHASE.idle,
  planOverview: null,
  executionTasks: [],
  fixSteps: [],
  followUpSteps: [],
  fileDiffs: [],
  designProgress: { architecture: null, ux: null },
  projectSummary: null,
  selectedDataSources: [],
  selectedElements: [],
  pendingAttachments: [],
  buildCompleted: false,
  agentAlive: null,
  agentAlivePollId: 0,
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

    const currentProject = useSessionStore.getState().currentProject;
    if (currentProject && selectedModel) {
      updateProjectModel(currentProject.id, selectedModel).catch(() => {});
    }

    armTurn({
      run: () => get().sendFixError(errorMessage, errorFile, errorLine, errorStack),
      undo: () => get().rollbackTurn(userMessage.id),
    });
  },

  sendMessage(content: string, opts?: { keepDraft?: boolean }) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    void requestPermissionIfNeeded();

    const { selectedDataSources, selectedElements, selectedModel, pendingAttachments } = get();
    const attachments = pendingAttachments.flatMap((a) => (a.upload ? [a.upload] : []));

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
      dataSources: selectedDataSources.length > 0 ? [...selectedDataSources] : undefined,
      selectedElements: selectedElements.length > 0 ? [...selectedElements] : undefined,
      attachments: attachments.length > 0 ? attachments : undefined,
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      agentAlive: true,
      ...(!opts?.keepDraft && { draft: '' }),
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
      ...(selectedModel && { model: selectedModel }),
      ...(selectedDataSources.length > 0 && { dataSourceIds: selectedDataSources.map((c) => c.id) }),
      ...(selectedElements.length > 0 && { selectedElements: selectedElements.map(({ id: _id, ...e }) => e) }),
      ...(attachments.length > 0 && { attachmentIds: attachments.map((a) => a.id) }),
    });

    // Persist the model to the project so it's restored on next visit
    const currentProject = useSessionStore.getState().currentProject;
    if (currentProject && selectedModel) {
      updateProjectModel(currentProject.id, selectedModel).catch(() => {});
    }

    set({ selectedDataSources: [], selectedElements: [], pendingAttachments: [] });
    armTurn({
      run: () => get().sendMessage(content, opts),
      undo: () => {
        get().rollbackTurn(userMessage.id);
        set({
          selectedElements,
          pendingAttachments,
          ...((!opts?.keepDraft || !get().draft) && { draft: content }),
        });
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

  addMessage(message: Message) {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  async loadHistory(projectId: string) {
    // Detach any existing handlers from the previous session
    if (activeProjectId && activeProjectId !== projectId) {
      stopAgentAlivePolling();
      const oldSocket = getChatSocket(activeProjectId);
      if (activeHandler) detachHandler(oldSocket, activeHandler);
      oldSocket.offMessage(handleVersionMessage);
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
        draft: '',
        selectedElements: [],
        pendingAttachments: dropAttachments(get().pendingAttachments),
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
      selectedElements: [],
      pendingAttachments: dropAttachments(get().pendingAttachments),
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

  addAttachments(files: File[]) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const room = MAX_ATTACHMENTS - get().pendingAttachments.length;
    if (files.length > room) set({ error: i18n.t('chat.attachment.tooMany', { max: MAX_ATTACHMENTS }) });
    const imagesAllowed = currentModel(get())?.supports_vision !== false;

    for (const file of files.slice(0, Math.max(room, 0))) {
      const kind = attachmentKind(file.type, file.name);
      if (!kind) {
        set({ error: i18n.t('chat.attachment.unsupported', { name: file.name }) });
        continue;
      }
      if (kind === 'image' && !imagesAllowed) {
        set({ error: i18n.t('chat.attachment.noVision') });
        continue;
      }
      const pending: PendingAttachment = {
        localId: generateId(),
        name: file.name,
        kind,
        previewUrl: kind === 'image' ? URL.createObjectURL(file) : null,
        status: 'uploading',
        progress: 0,
      };
      set((state) => ({ pendingAttachments: [...state.pendingAttachments, pending] }));
      void uploadPending(projectId, file, pending, (patch) => {
        set((state) => ({
          pendingAttachments: state.pendingAttachments.map((a) => (a.localId === pending.localId ? { ...a, ...patch } : a)),
        }));
      }).catch((err: unknown) => {
        set({ error: err instanceof AttachmentTooLarge ? err.message : i18n.t('chat.attachment.failed', { name: file.name }) });
      });
    }
  },

  removeAttachment(localId: string) {
    const removed = get().pendingAttachments.filter((a) => a.localId === localId);
    dropAttachments(removed);
    set((state) => ({ pendingAttachments: state.pendingAttachments.filter((a) => a.localId !== localId) }));
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
