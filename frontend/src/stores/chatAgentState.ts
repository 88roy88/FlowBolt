import type { AgentPhase, AgentPhaseConstMap } from '../types';
import type { ChatState } from './chat';

/** Every `AgentPhase` as an identity key/value pair; mismatched values fail type-check. */
export const AGENT_PHASE = {
  idle: 'idle',
  fetching_data_sources: 'fetching_data_sources',
  designing: 'designing',
  planning: 'planning',
  awaiting_approval: 'awaiting_approval',
  executing: 'executing',
  fixing: 'fixing',
  exploring: 'exploring',
  complete: 'complete',
} as const satisfies AgentPhaseConstMap;

export type AgentPhaseMap = typeof AGENT_PHASE;

/** Agent is paused until the user accepts or modifies the work plan. */
export const PLAN_AWAITING_AGENT_PHASES: readonly AgentPhase[] = [
  AGENT_PHASE.awaiting_approval,
];

/** WS events that end an in-flight run while the user must review the plan. */
export const PLAN_AWAITING_AGENT_EVENT_TYPES = ['plan_overview'] as const;

export const TERMINAL_EVENT_TYPES = [
  'action_complete',
  'error',
  'plan_rejected',
  ...PLAN_AWAITING_AGENT_EVENT_TYPES,
] as const;

export const ACTIVE_AGENT_PHASES: AgentPhase[] = [
  AGENT_PHASE.fetching_data_sources,
  AGENT_PHASE.designing,
  AGENT_PHASE.planning,
  AGENT_PHASE.executing,
  AGENT_PHASE.fixing,
  AGENT_PHASE.exploring,
];

export const TRANSIENT_RESET: Partial<ChatState> = {
  isStreaming: false,
  agentPhase: AGENT_PHASE.idle,
  currentAssistantMessage: '',
  actions: [],
  followUpSteps: [],
  followUpDiffs: [],
  fixSteps: [],
  executionTasks: [],
  designProgress: { architecture: null, ux: null },
};

export type AgentActivityState = Pick<ChatState, 'isStreaming' | 'agentPhase'>;
export type AwaitingPlanState = Pick<ChatState, 'agentPhase' | 'planOverview'>;

export function isHistoryRunComplete(events: Array<{ type?: string }>): boolean {
  if (events.length === 0) return true;
  const lastType = events[events.length - 1].type;
  if (!lastType) return true;
  return (TERMINAL_EVENT_TYPES as readonly string[]).includes(lastType);
}

export function isAwaitingPlanApproval(state: AwaitingPlanState): boolean {
  return (
    PLAN_AWAITING_AGENT_PHASES.includes(state.agentPhase) &&
    state.planOverview != null
  );
}

export function isAgentWorking(state: AgentActivityState): boolean {
  return state.isStreaming || ACTIVE_AGENT_PHASES.includes(state.agentPhase);
}

export function shouldResetOnConnectionLost(state: AgentActivityState & AwaitingPlanState): boolean {
  return isAgentWorking(state) && !isAwaitingPlanApproval(state);
}

export function getTransientReset(): Partial<ChatState> {
  return { ...TRANSIENT_RESET };
}

export const selectIsAwaitingPlanApproval = (state: ChatState) => isAwaitingPlanApproval(state);
export const selectIsAgentWorking = (state: ChatState) => isAgentWorking(state);
