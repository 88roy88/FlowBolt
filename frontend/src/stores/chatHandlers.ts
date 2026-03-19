import type { WSMessage, Message, FollowUpStep, FileDiff } from '../types';
import { useFilesStore } from './files';
import { useSessionStore } from './session';

type GetState = () => import('./chat').ChatState;
type SetState = (
  partial: Partial<import('./chat').ChatState> | ((state: import('./chat').ChatState) => Partial<import('./chat').ChatState>),
) => void;

function generateId(): string {
  return crypto.randomUUID();
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
  filesStore.loadFileTree();
}

function handleText(msg: { content: string }, set: SetState) {
  set((state) => ({
    currentAssistantMessage: state.currentAssistantMessage + msg.content,
  }));
}

function handleError(msg: { message: string }, set: SetState, cleanup: () => void) {
  set({ error: msg.message, isStreaming: false, agentPhase: 'idle' });
  cleanup();
}

export function createFixErrorHandler(
  set: SetState,
  get: GetState,
  cleanup: () => void,
) {
  return (msg: WSMessage) => {
    switch (msg.type) {
      case 'phase':
        set({ agentPhase: msg.phase });
        break;

      case 'fix_step':
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
            timestamp: Date.now(),
            agentCard: { type: 'fix_progress', steps: [...state.fixSteps] },
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
          set({
            currentAssistantMessage: '',
            actions: [],
            isStreaming: false,
            agentPhase: 'idle',
          });
        }
        cleanup();
        useFilesStore.getState().loadFileTree();
        break;
      }
    }
  };
}

export function createSendMessageHandler(
  set: SetState,
  get: GetState,
  cleanup: () => void,
) {
  return (msg: WSMessage) => {
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

      case 'followup_diffs':
        set({ followUpDiffs: msg.diffs });
        break;

      case 'text':
        handleText(msg, set);
        break;

      case 'file':
        handleFileUpdate(msg, set);
        break;

      case 'shell_output':
        set((state) => ({
          actions: [
            ...state.actions,
            { type: 'shell', command: msg.command, output: msg.output },
          ],
        }));
        break;

      case 'cases_fetched':
        handleCasesFetched(msg, set);
        break;

      case 'package_fetched':
        handlePackageFetched(msg, set);
        break;

      case 'case_error':
      case 'package_error':
        console.warn(`Case error: ${msg.message}`);
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
    useFilesStore.getState().loadFileTree();
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

function handleCasesFetched(
  msg: { cases: { package_id: string; package_name: string; data_schema: string; relevant_fields?: string }[] },
  set: SetState,
) {
  const casesMsg: Message = {
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    agentCard: {
      type: 'cases_fetched',
      cases: msg.cases.map((c) => ({
        packageId: c.package_id,
        packageName: c.package_name,
        dataSchema: c.data_schema,
        relevantFields: c.relevant_fields,
      })),
    },
  };
  set((s) => ({ messages: [...s.messages, casesMsg] }));
}

function handlePackageFetched(
  msg: { package_id: string; package_name: string; data_schema: string; relevant_fields?: string },
  set: SetState,
) {
  const packageMsg: Message = {
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    agentCard: {
      type: 'cases_fetched',
      cases: [{
        packageId: msg.package_id,
        packageName: msg.package_name,
        dataSchema: msg.data_schema,
        relevantFields: msg.relevant_fields,
      }],
    },
  };
  set((s) => ({ messages: [...s.messages, packageMsg] }));
}

function handleActionComplete(set: SetState, get: GetState, cleanup: () => void) {
  const state = get();
  const newMessages: Message[] = [];

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
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: state.currentAssistantMessage,
      actions: state.actions.length > 0 ? [...state.actions] : undefined,
      timestamp: Date.now(),
    });
  }

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

  // Add project summary card after task progress
  if (state.projectSummary) {
    newMessages.push({
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      agentCard: { type: 'project_summary', summary: state.projectSummary },
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
    projectSummary: null,
  }));
  cleanup();
  useFilesStore.getState().loadFileTree();
}
