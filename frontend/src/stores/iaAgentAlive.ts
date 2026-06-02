import { fetchIaAgentAlive } from '../services/api';
import type { AgentPhase } from '../types';
import {
  ACTIVE_AGENT_PHASES,
  getTransientReset,
  isAgentWorking,
  isAwaitingPlanApproval,
  isKnownAgentPhase,
} from './chatAgentState';
import { useChatStore } from './chat';

const POLL_FAST_MS = 2500;
const POLL_SLOW_MS = 10000;

let pollTimeout: ReturnType<typeof setTimeout> | null = null;
let pollProjectId: string | null = null;

function hasInProgressUi(state: ReturnType<typeof useChatStore.getState>): boolean {
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

  // Do not resurrect "working" UI while an error is shown or after a failed run.
  if (state.error) {
    if (!alive && hasInProgressUi(state) && !awaiting) {
      useChatStore.setState({ ...getTransientReset(), error: state.error });
    }
    return;
  }

  if (alive && !working) {
    const updates: { isStreaming: boolean; agentPhase?: AgentPhase; agentAlive: boolean } = {
      isStreaming: true,
      agentAlive: true,
    };
    if (isKnownAgentPhase(phase) && ACTIVE_AGENT_PHASES.includes(phase)) {
      updates.agentPhase = phase;
    }
    useChatStore.setState(updates);
    return;
  }

  if (!alive && (working || hasInProgressUi(state)) && !awaiting) {
    useChatStore.setState({ ...getTransientReset(), agentAlivePhase: phase ?? 'idle' });
  }
}

function scheduleNextPoll(): void {
  if (!pollProjectId) return;
  const delay = isAgentWorking(useChatStore.getState()) ? POLL_FAST_MS : POLL_SLOW_MS;
  pollTimeout = setTimeout(() => {
    void pollOnce();
  }, delay);
}

async function pollOnce(): Promise<void> {
  const projectId = pollProjectId;
  if (!projectId) return;

  try {
    const { alive, phase } = await fetchIaAgentAlive(projectId);
    if (pollProjectId !== projectId) return;

    useChatStore.setState({ agentAlive: alive, agentAlivePhase: phase });
    reconcileAlive(alive, phase);
  } catch (err) {
    console.error('Failed to fetch agent alive status:', err);
  }

  scheduleNextPoll();
}

export function startAgentAlivePolling(projectId: string): void {
  stopAgentAlivePolling();
  pollProjectId = projectId;
  useChatStore.setState({ agentAlive: null, agentAlivePhase: null });
  void pollOnce();
}

export function stopAgentAlivePolling(): void {
  if (pollTimeout !== null) {
    clearTimeout(pollTimeout);
    pollTimeout = null;
  }
  pollProjectId = null;
  useChatStore.setState({ agentAlive: null, agentAlivePhase: null });
}
