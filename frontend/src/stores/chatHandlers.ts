import type { WSMessage, Message, FollowUpStep } from '../types';
import { useFilesStore } from './files';
import { useSessionStore } from './session';
import { requestPermissionIfNeeded, notifyBuildComplete } from '../utils/notifications';

type GetState = () => import('./chat').ChatState;
type SetState = (
  partial: Partial<import('./chat').ChatState> | ((state: import('./chat').ChatState) => Partial<import('./chat').ChatState>),
) => void;

let _skipMessages = false;

export function setReplayMode(replay: boolean) {
  _skipMessages = replay;
}

let _lastEventTs = 0;

function getTimestamp(msg?: { _ts?: string }): number {
  if (msg?._ts) {
    _lastEventTs = new Date(msg._ts).getTime();
    return _lastEventTs;
  }
  return _lastEventTs || Date.now();
}

function generateId(): string {
  return crypto.randomUUID();
}

function refreshFileTreeAfterAgentWrite() {
  if (_skipMessages) return;
  void useFilesStore.getState().loadFileTree();
}

function handleFileUpdate(msg: { path: string; content: string }, set: SetState) {
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
  // New files on disk (e.g. fix pass) — keep explorer in sync before action_complete.
  refreshFileTreeAfterAgentWrite();
}

function handleText(msg: { content: string }, set: SetState) {
  set((state) => ({
    currentAssistantMessage: state.currentAssistantMessage + msg.content,
  }));
}

function handleError(msg: { message: string }, set: SetState, cleanup: () => void) {
  set({ error: msg.message, isStreaming: false, agentPhase: 'idle' });
  if (!_skipMessages) {
    notifyBuildComplete(useSessionStore.getState().currentProject?.name, true);
  }
  cleanup();
}

function handleFixStep(msg: WSMessage & { type: 'fix_step' }, set: SetState) {
  set((state) => {
    const existingIdx = state.fixSteps.findIndex((s) => s.step === msg.step);
    if (existingIdx >= 0) {
      const updated = [...state.fixSteps];
      updated[existingIdx] = {
        id: updated[existingIdx].id,
        step: msg.step,
        status: msg.status,
        message: msg.message,
      };
      return { fixSteps: updated };
    }
    return {
      fixSteps: [
        ...state.fixSteps,
        { id: generateId(), step: msg.step, status: msg.status, message: msg.message },
      ],
    };
  });
}

function handleUserMessage(msg: WSMessage & { type: 'user_message' }, set: SetState) {
  const userMsg: Message = {
    id: generateId(),
    role: 'user',
    content: msg.content || '',
    timestamp: getTimestamp(),
  };
  if (msg.data_sources && msg.data_sources.length > 0) {
    userMsg.dataSources = msg.data_sources;
  }
  if (msg.error_fix_request) {
    userMsg.agentCard = { type: 'error_fix_request', ...msg.error_fix_request };
  }
  set((s) => ({ messages: [...s.messages, userMsg] }));
}

export function createFixErrorHandler(
  set: SetState,
  get: GetState,
  cleanup: () => void,
) {
  return (msg: WSMessage) => {
    getTimestamp(msg as { _ts?: string });
    switch (msg.type) {
      case 'phase':
        set({ agentPhase: msg.phase });
        break;

      case 'fix_step':
        handleFixStep(msg, set);
        break;

      case 'text':
        handleText(msg, set);
        break;

      case 'file':
        handleFileUpdate(msg, set);
        break;

      case 'error':
        handleError(msg, set, cleanup);
        break;

      case 'action_complete': {
        const state = get();
        if (state.fixSteps.length > 0) {
          const fixMessage: Message = {
            id: generateId(),
            role: 'assistant',
            content: state.currentAssistantMessage,
            timestamp: getTimestamp(),
            agentCard: { type: 'fix_progress', steps: [...state.fixSteps] },
          };
          set((s) => ({
            messages: [...s.messages, fixMessage],
            currentAssistantMessage: '',
            actions: [],
            fixSteps: [],
            isStreaming: false,
            agentPhase: 'idle',
            buildCompleted: true,
          }));
        } else {
          set({
            currentAssistantMessage: '',
            actions: [],
            isStreaming: false,
            agentPhase: 'idle',
            buildCompleted: true,
          });
        }
        if (!_skipMessages) {
          notifyBuildComplete(useSessionStore.getState().currentProject?.name);
        }
        cleanup();
        useFilesStore.getState().loadFileTree();
        useFilesStore.getState().refreshOpenFiles();
        break;
      }
    }
  };
}

export function createSendMessageHandler(
  set: SetState,
  get: GetState,
  cleanup: () => void,
  options?: { replay?: boolean },
) {
  _skipMessages = options?.replay ?? false;
  return (msg: WSMessage) => {
    getTimestamp(msg as { _ts?: string });
    switch (msg.type) {
      case 'phase':
        handlePhaseChange(msg, set, get);
        break;

      case 'design_progress':
        set((state) => ({
          designProgress: { ...state.designProgress, [msg.stream]: msg.content },
        }));
        break;

      case 'plan_overview':
        set({ planOverview: msg.overview, isStreaming: false });
        break;

      case 'plan_accepted': {
        const acceptedMsg: Message = {
          id: generateId(),
          role: 'assistant',
          content: '',
          timestamp: getTimestamp(),
          agentCard: { type: 'plan_overview', overview: msg.overview },
        };
        set((s) => ({
          messages: _skipMessages ? s.messages : [...s.messages, acceptedMsg],
          isStreaming: true,
          agentPhase: 'planning',
          planOverview: null,
        }));
        break;
      }


      case 'task_list':
        set({ executionTasks: msg.tasks });
        break;

      case 'task_update':
        handleTaskUpdate(msg, set);
        break;

      case 'project_summary':
        handleProjectSummary(msg, set);
        break;

      case 'followup_step':
        handleFollowUpStep(msg, set);
        break;

      case 'fix_step':
        handleFixStep(msg, set);
        break;

      case 'followup_diffs':
        set({ followUpDiffs: msg.diffs });
        break;

      case 'text':
        handleText(msg, set);
        break;

      case 'file':
        handleFileUpdate(msg, set);
        break;

      case 'data_sources_fetched':
        handleDataSourcesFetched(msg, set);
        break;

      case 'user_message':
        handleUserMessage(msg, set);
        break;

      case 'data_source_error':
        console.warn(`Data source error: ${msg.message}`);
        break;

      case 'error':
        handleError(msg, set, cleanup);
        break;

      case 'action_complete':
        handleActionComplete(set, get, cleanup);
        break;
    }
  };
}

function handlePhaseChange(
  msg: { phase: import('../types').AgentPhase },
  set: SetState,
  get: GetState,
) {
  const prevPhase = get().agentPhase;

  if (prevPhase === 'designing' && msg.phase === 'planning') {
    const dp = get().designProgress;
    const designMsg: Message = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: getTimestamp(),
      agentCard: {
        type: 'design_complete',
        architecture: dp.architecture === 'complete',
        ux: dp.ux === 'complete',
      },
    };
    if (!_skipMessages) set((s) => ({ messages: [...s.messages, designMsg] }));
  }

  set({ agentPhase: msg.phase });
  if (msg.phase === 'executing') {
    set({ isStreaming: true });
    requestPermissionIfNeeded();
  }
}

function handleTaskUpdate(
  msg: { taskId: string; status: string; file?: string },
  set: SetState,
) {
  set((state) => ({
    executionTasks: state.executionTasks.map((t) =>
      t.id === msg.taskId ? { ...t, status: msg.status as 'running' | 'completed' | 'failed' } : t
    ),
  }));
  if (msg.file) {
    const filesStore = useFilesStore.getState();
    if (filesStore.openFiles.has(msg.file)) {
      filesStore.refreshOpenFiles();
    }
  }
  // Task progress UI updates per task; refresh tree here so new files appear before the whole run ends.
  if (
    msg.status === 'completed' ||
    msg.status === 'failed' ||
    (msg.status === 'running' && msg.file)
  ) {
    refreshFileTreeAfterAgentWrite();
  }
}

function handleProjectSummary(
  msg: { summary: import('../types').ProjectSummary },
  set: SetState,
) {
  // Store summary but don't add card yet — action_complete will add it after task progress
  set({ projectSummary: msg.summary });
  const currentProject = useSessionStore.getState().currentProject;
  if (currentProject) {
    useSessionStore.getState().updateProjectSummary(
      currentProject.id,
      JSON.stringify(msg.summary),
    );
  }
}

function handleFollowUpStep(msg: WSMessage & { type: 'followup_step' }, set: SetState) {
  set((state) => {
    if (msg.status === 'running') {
      return {
        followUpSteps: [
          ...state.followUpSteps,
          {
            id: generateId(),
            tool: msg.tool as FollowUpStep['tool'],
            args: msg.args,
            status: 'running',
            iteration: msg.iteration,
          },
        ],
      };
    }
    const steps = [...state.followUpSteps];
    const idx = steps.findLastIndex(
      (s) => s.tool === msg.tool && s.iteration === msg.iteration && s.status === 'running',
    );
    if (idx >= 0) {
      steps[idx] = {
        ...steps[idx],
        status: msg.status as FollowUpStep['status'],
        resultPreview: msg.result_preview,
      };
    }
    return { followUpSteps: steps };
  });
}

function handleDataSourcesFetched(
  msg: { data_sources: { data_source_id: string; data_source_name: string; data_schema: string; relevant_fields?: string }[] },
  set: SetState,
) {
  const dsMsg: Message = {
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: getTimestamp(),
    agentCard: {
      type: 'data_sources_fetched',
      dataSources: msg.data_sources.map((ds) => ({
        dataSourceId: ds.data_source_id,
        dataSourceName: ds.data_source_name,
        dataSchema: ds.data_schema,
        relevantFields: ds.relevant_fields,
      })),
    },
  };
  if (!_skipMessages) set((s) => ({ messages: [...s.messages, dsMsg] }));
}

function handleActionComplete(set: SetState, get: GetState, cleanup: () => void) {
  const state = get();
  const newMessages: Message[] = [];

  if (state.fixSteps.length > 0) {
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: state.currentAssistantMessage,
      timestamp: getTimestamp(),
      agentCard: { type: 'fix_progress', steps: [...state.fixSteps] },
    });
  } else if (state.followUpSteps.length > 0) {
    const filesChanged = state.actions
      .filter((a) => a.type === 'file' && a.path)
      .map((a) => a.path!);
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: state.currentAssistantMessage,
      actions: state.actions.length > 0 ? [...state.actions] : undefined,
      timestamp: getTimestamp(),
      agentCard: {
        type: 'followup_progress',
        steps: [...state.followUpSteps],
        answer: state.currentAssistantMessage || undefined,
        filesChanged: filesChanged.length > 0 ? filesChanged : undefined,
        diffs: state.followUpDiffs.length > 0 ? [...state.followUpDiffs] : undefined,
      },
    });
  } else if (state.currentAssistantMessage) {
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: state.currentAssistantMessage,
      actions: state.actions.length > 0 ? [...state.actions] : undefined,
      timestamp: getTimestamp(),
    });
  }

  if (state.executionTasks.length > 0) {
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: '',
      actions: state.actions.length > 0 ? [...state.actions] : undefined,
      timestamp: getTimestamp(),
      agentCard: {
        type: 'task_progress',
        tasks: [...state.executionTasks],
      },
    });
  }

  // Add project summary card after task progress
  if (state.projectSummary) {
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: getTimestamp(),
      agentCard: { type: 'project_summary', summary: state.projectSummary },
    });
  }

  set((s) => ({
    messages: _skipMessages ? s.messages : [...s.messages, ...newMessages],
    currentAssistantMessage: '',
    actions: [],
    isStreaming: false,
    agentPhase: 'idle',
    planOverview: null,
    executionTasks: [],
    fixSteps: [],
    followUpSteps: [],
    followUpDiffs: [],
    projectSummary: null,
    buildCompleted: true,
  }));
  if (!_skipMessages) {
    notifyBuildComplete(useSessionStore.getState().currentProject?.name);
  }
  cleanup();
  useFilesStore.getState().loadFileTree();
  useFilesStore.getState().refreshOpenFiles();
}
