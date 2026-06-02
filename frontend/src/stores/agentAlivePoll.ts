import { fetchAgentAlive } from '../services/api';
import {
  ACTIVE_AGENT_PHASES,
  getTransientReset,
  isAgentWorking,
  isAwaitingPlanApproval,
  isKnownAgentPhase,
} from './chatAgentState';
import { useChatStore } from './chat';

const POLL_MS = 2500;

let pollTimeout: ReturnType<typeof setTimeout> | null = null;
let pollProjectId: string | null = null;

export function handleChatConnectionLost(): void {
  const state = useChatStore.getState();
  if (isAgentWorking(state) && !isAwaitingPlanApproval(state)) {
    useChatStore.setState(getTransientReset());
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
      useChatStore.setState({ ...getTransientReset(), error: state.error });
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
    useChatStore.setState(getTransientReset());
  }
}

async function pollOnce(): Promise<void> {
  const projectId = pollProjectId;
  if (!projectId) return;

  try {
    const { alive, phase } = await fetchAgentAlive(projectId);
    if (pollProjectId !== projectId) return;

    useChatStore.setState({ agentAlive: alive });
    reconcileAlive(alive, phase);
  } catch (err) {
    console.error('Failed to fetch agent alive status:', err);
  }

  if (pollProjectId === projectId) {
    pollTimeout = setTimeout(() => {
      void pollOnce();
    }, POLL_MS);
  }
}

export function startAgentAlivePolling(projectId: string): void {
  stopAgentAlivePolling();
  pollProjectId = projectId;
  useChatStore.setState({ agentAlive: null });
  void pollOnce();
}

export function stopAgentAlivePolling(): void {
  if (pollTimeout !== null) {
    clearTimeout(pollTimeout);
    pollTimeout = null;
  }
  pollProjectId = null;
  useChatStore.setState({ agentAlive: null });
}
