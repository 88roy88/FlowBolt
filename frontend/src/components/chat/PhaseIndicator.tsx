import { CheckCircle2 } from 'lucide-react';
import type { AgentPhase } from '../../types';
import { AGENT_PHASE } from '../../stores/chatAgentState';

const PHASE_LABELS: Partial<Record<AgentPhase, string>> = {
  [AGENT_PHASE.IDLE]: '',
  [AGENT_PHASE.FETCHING_DATA_SOURCES]: '',
  [AGENT_PHASE.DESIGNING]: 'Designing the application...',
  [AGENT_PHASE.PLANNING]: 'Building work plan...',
  [AGENT_PHASE.AWAITING_APPROVAL]: 'Review the plan below',
  [AGENT_PHASE.EXECUTING]: 'Building...',
  [AGENT_PHASE.FIXING]: 'Fixing error...',
  [AGENT_PHASE.EXPLORING]: 'Exploring codebase...',
  [AGENT_PHASE.COMPLETE]: 'Done!',
};

export function PhaseIndicator({ phase }: { phase: AgentPhase }) {
  const label = PHASE_LABELS[phase];
  if (!label) return null;

  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-surface border border-border rounded-lg text-[13px] text-muted-foreground animate-card-in">
      {phase === AGENT_PHASE.COMPLETE ? (
        <CheckCircle2 size={14} className="text-success" />
      ) : phase !== AGENT_PHASE.AWAITING_APPROVAL ? (
        <div className="flex items-center gap-1">
          <span className="pulse-dot" />
          <span className="pulse-dot" style={{ animationDelay: '200ms' }} />
          <span className="pulse-dot" style={{ animationDelay: '400ms' }} />
        </div>
      ) : null}
      {label}
    </div>
  );
}
