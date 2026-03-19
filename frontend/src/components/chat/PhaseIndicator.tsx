import { Loader2, CheckCircle2 } from 'lucide-react';
import type { AgentPhase } from '../../types';

const PHASE_LABELS: Record<AgentPhase, string> = {
  idle: '',
  classifying: 'Analyzing your request...',
  fetching_cases: '',
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
    <div className="flex items-center gap-2 px-3.5 py-2 bg-surface border border-border rounded-lg text-[13px] text-muted-foreground">
      {phase !== 'complete' && phase !== 'awaiting_approval' && (
        <Loader2 size={14} className="animate-spin" />
      )}
      {phase === 'complete' && (
        <CheckCircle2 size={14} className="text-success" />
      )}
      {label}
    </div>
  );
}
