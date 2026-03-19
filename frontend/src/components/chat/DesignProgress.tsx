import { Loader2, CheckCircle2 } from 'lucide-react';
import { CardWrapper } from './cards/CardWrapper';

export function DesignProgress({ designProgress }: { designProgress: { architecture: string | null; ux: string | null } }) {
  return (
    <CardWrapper>
      <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '10px' }}>
        Designing...
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          {designProgress.architecture ? (
            <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
          ) : (
            <Loader2 size={14} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
          )}
          <span>Architecture</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          {designProgress.ux ? (
            <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
          ) : (
            <Loader2 size={14} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
          )}
          <span>UI/UX</span>
        </div>
      </div>
    </CardWrapper>
  );
}
