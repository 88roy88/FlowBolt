import { CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AgentPhase } from '../../types';
import { AGENT_PHASE } from '../../stores/chatAgentState';

const PHASE_LABEL_KEYS: Partial<Record<AgentPhase, string>> = {
  [AGENT_PHASE.designing]: 'chat.phase.designingApplication',
  [AGENT_PHASE.planning]: 'chat.phase.buildingWorkPlan',
  [AGENT_PHASE.awaiting_approval]: 'chat.phase.reviewPlanBelow',
  [AGENT_PHASE.executing]: 'chat.phase.building',
  [AGENT_PHASE.fixing]: 'chat.phase.fixing',
  [AGENT_PHASE.exploring]: 'chat.phase.exploring',
  [AGENT_PHASE.complete]: 'chat.phase.done',
};

export function PhaseIndicator({ phase }: { phase: AgentPhase }) {
  const { t } = useTranslation();
  const labelKey = PHASE_LABEL_KEYS[phase];
  if (!labelKey) return null;
  const label = t(labelKey);

  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-surface border border-border rounded-lg text-[13px] text-muted-foreground animate-card-in">
      {phase === AGENT_PHASE.complete ? (
        <CheckCircle2 size={14} className="text-success" />
      ) : phase !== AGENT_PHASE.awaiting_approval ? (
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
