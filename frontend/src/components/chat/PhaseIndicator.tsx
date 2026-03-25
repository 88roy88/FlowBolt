import { CheckCircle2 } from 'lucide-react';
import type { AgentPhase } from '../../types';

const PHASE_LABELS: Record<AgentPhase, string> = {
  idle: '',
  classifying: 'Analyzing your request...',
  fetching_data_sources: '',
  designing: 'Designing the application...',
  planning: 'Building work plan...',
  awaiting_approval: 'Review the plan below',
  executing: 'Building...',
  fixing: 'Fixing error...',
  exploring: 'Exploring codebase...',
  complete: 'Done!',
};

export function PhaseIndicator({ phase }: { phase: AgentPhase }) {
  const label = PHASE_LABELS[phase];
  if (!label) return null;

  return (
    <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-surface border border-border rounded-lg text-[13px] text-muted-foreground animate-card-in">
      {phase === 'complete' ? (
        <CheckCircle2 size={14} className="text-success" />
      ) : phase !== 'awaiting_approval' ? (
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
