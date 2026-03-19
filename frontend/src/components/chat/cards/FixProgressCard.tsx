import { Loader2, CheckCircle2, XCircle } from 'lucide-react';
import type { FixStep } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { getStepIcon } from './icons';

export function FixProgressCard({ steps, content, isLive }: {
  steps: FixStep[];
  content?: string;
  isLive?: boolean;
}) {
  const completed = steps.filter((s) => s.status === 'completed').length;
  const failed = steps.filter((s) => s.status === 'failed').length;
  const total = steps.length;
  const hasRunning = steps.some((s) => s.status === 'running');

  const headerColor = failed > 0 ? 'text-destructive' : (isLive && hasRunning) ? 'text-primary' : 'text-success';

  return (
    <CardWrapper accent={failed > 0 ? 'destructive' : 'success'}>
      <div className={`flex items-center gap-1.5 mb-3 text-[13px] font-medium ${headerColor}`}>
        {isLive && hasRunning ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            Fixing error...
          </>
        ) : failed > 0 ? (
          <>
            <XCircle size={14} />
            {isLive ? 'Error fix completed with issues' : `Fixed error with ${failed} validation failure${failed > 1 ? 's' : ''}`}
          </>
        ) : (
          <>
            <CheckCircle2 size={14} />
            {isLive ? 'Error fixed successfully!' : `Fixed error (${completed}/${total} steps)`}
          </>
        )}
      </div>

      {content && (
        <div className="mb-3 p-2.5 bg-background rounded-md text-xs leading-relaxed">
          {content}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        {steps.map((step) => {
          const StepIcon = getStepIcon(step.step);
          return (
            <div
              key={step.id}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors ${
                step.status === 'running' ? 'bg-running-bg' : ''
              }`}
            >
              {step.status === 'running' ? (
                <Loader2 size={14} className="text-primary shrink-0 animate-spin" />
              ) : step.status === 'completed' ? (
                <StepIcon size={14} className="text-success shrink-0" />
              ) : (
                <XCircle size={14} className="text-destructive shrink-0" />
              )}
              <span className={step.status === 'failed' ? 'text-destructive' : ''}>
                {step.message}
              </span>
            </div>
          );
        })}
      </div>
    </CardWrapper>
  );
}
