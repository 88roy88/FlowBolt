import { fetchAgentAlive } from '../services/api';
import { WRITE_ROLES } from '../types';
import {
  ACTIVE_AGENT_PHASES,
  getTransientReset,
  isAgentWorking,
  isAwaitingPlanApproval,
  isKnownAgentPhase,
} from './chatAgentState';
import { useChatStore } from './chat';
import { useSessionStore } from './session';

const POLL_MS = 10000;

export function handleChatConnectionLost(): void {
  const state = useChatStore.getState();
  if (isAgentWorking(state) && !isAwaitingPlanApproval(state)) {
    useChatStore.setState({ ...getTransientReset(), agentAlive: false });
  }
}

function hasBusyUi(state: ReturnType<typeof useChatStore.getState>): boolean {
  return (
    isAgentWorking(state) ||
    state.followUpSteps.length > 0 ||
    state.fixSteps.length > 0 ||
    state.currentAssistantMessage.length > 0 ||
    state.actions.length > 0
  );
}

function reconcileAlive(alive: boolean, phase: string | null): void {
  const state = useChatStore.getState();
  const working = isAgentWorking(state);
  const awaiting = isAwaitingPlanApproval(state);
  const busyUi = hasBusyUi(state);

  if (state.error) {
    if (!alive && busyUi && !awaiting) {
      useChatStore.setState({ ...getTransientReset(), agentAlive: false, error: state.error });
    }
    return;
  }

  if (alive && !working) {
    useChatStore.setState({
      isStreaming: true,
      agentAlive: true,
      ...(isKnownAgentPhase(phase) && ACTIVE_AGENT_PHASES.includes(phase) ? { agentPhase: phase } : {}),
    });
    return;
  }

  if (!alive && busyUi && !awaiting) {
    useChatStore.setState({ ...getTransientReset(), agentAlive: false });
  }
}

async function pollOnce(projectId: string, pollId: number): Promise<void> {
  try {
    const { alive, phase } = await fetchAgentAlive(projectId);
    if (useChatStore.getState().agentAlivePollId !== pollId) return;

    useChatStore.setState({ agentAlive: alive });
    reconcileAlive(alive, phase);
  } catch (err) {
    console.error('Failed to fetch agent alive status:', err);
  }

  if (useChatStore.getState().agentAlivePollId !== pollId) return;

  const { agentAlive } = useChatStore.getState();
  if (agentAlive !== false) {
    setTimeout(() => {
      void pollOnce(projectId, pollId);
    }, POLL_MS);
  }
}

export function startAgentAlivePolling(projectId: string): void {
  const currentProject = useSessionStore.getState().currentProject;
  const canWrite = !currentProject?.role || WRITE_ROLES.has(currentProject.role);
  if (!canWrite) return;

  const pollId = useChatStore.getState().agentAlivePollId + 1;
  useChatStore.setState({ agentAlive: null, agentAlivePollId: pollId });

  setTimeout(() => {
    void pollOnce(projectId, pollId);
  }, POLL_MS);
}

export function stopAgentAlivePolling(): void {
  useChatStore.setState((state) => ({
    agentAlive: null,
    agentAlivePollId: state.agentAlivePollId + 1,
  }));
}
