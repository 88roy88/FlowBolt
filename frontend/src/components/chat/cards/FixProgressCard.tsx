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

  const headerColor = failed > 0 ? 'var(--danger)' : (isLive && hasRunning) ? 'var(--accent)' : 'var(--success)';

  return (
    <CardWrapper>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '12px',
        fontSize: '13px',
        fontWeight: 500,
        color: headerColor,
      }}>
        {isLive && hasRunning ? (
          <>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
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
        <div style={{
          marginBottom: '12px',
          padding: '10px',
          background: 'var(--bg)',
          borderRadius: '6px',
          fontSize: '12px',
          lineHeight: '1.6',
          color: 'var(--text)',
        }}>
          {content}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {steps.map((step) => {
          const StepIcon = getStepIcon(step.step);
          return (
            <div
              key={step.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 8px',
                borderRadius: '6px',
                background: step.status === 'running' ? 'var(--running-bg)' : 'transparent',
                fontSize: '13px',
                transition: 'background 0.2s',
              }}
            >
              {step.status === 'running' ? (
                <Loader2 size={14} style={{ color: 'var(--accent)', flexShrink: 0, animation: 'spin 1s linear infinite' }} />
              ) : step.status === 'completed' ? (
                <StepIcon size={14} style={{ color: 'var(--success)', flexShrink: 0 }} />
              ) : (
                <XCircle size={14} style={{ color: 'var(--danger)', flexShrink: 0 }} />
              )}
              <span style={{ color: step.status === 'failed' ? 'var(--danger)' : 'var(--text)' }}>
                {step.message}
              </span>
            </div>
          );
        })}
      </div>
    </CardWrapper>
  );
}
