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
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '8px 14px',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      fontSize: '13px',
      color: 'var(--text-dim)',
    }}>
      {phase !== 'complete' && phase !== 'awaiting_approval' && (
        <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
      )}
      {phase === 'complete' && (
        <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
      )}
      {label}
    </div>
  );
}
