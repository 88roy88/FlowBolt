import type { AgentPhase, CapitalChars } from '../types';
import type { ChatState } from './chat';

export const AGENT_PHASE = {
  IDLE: 'idle',
  FETCHING_DATA_SOURCES: 'fetching_data_sources',
  DESIGNING: 'designing',
  PLANNING: 'planning',
  AWAITING_APPROVAL: 'awaiting_approval',
  EXECUTING: 'executing',
  FIXING: 'fixing',
  EXPLORING: 'exploring',
  COMPLETE: 'complete',
} as const satisfies Record<CapitalChars<AgentPhase>, AgentPhase>;

/** Agent is paused until the user accepts or modifies the work plan. */
export const PLAN_AWAITING_AGENT_PHASES: readonly AgentPhase[] = [
  AGENT_PHASE.AWAITING_APPROVAL,
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
  AGENT_PHASE.FETCHING_DATA_SOURCES,
  AGENT_PHASE.DESIGNING,
  AGENT_PHASE.PLANNING,
  AGENT_PHASE.EXECUTING,
  AGENT_PHASE.FIXING,
  AGENT_PHASE.EXPLORING,
];

export const TRANSIENT_RESET: Partial<ChatState> = {
  isStreaming: false,
  agentPhase: AGENT_PHASE.IDLE,
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
