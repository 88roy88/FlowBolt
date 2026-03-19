import { CheckCircle2, XCircle } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

export function DesignCompleteCard({ architecture, ux }: { architecture: boolean; ux: boolean }) {
  return (
    <CardWrapper>
      <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '6px' }}>
        Design complete
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {architecture ? (
            <CheckCircle2 size={13} style={{ color: 'var(--success)' }} />
          ) : (
            <XCircle size={13} style={{ color: 'var(--danger)' }} />
          )}
          <span>Architecture</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {ux ? (
            <CheckCircle2 size={13} style={{ color: 'var(--success)' }} />
          ) : (
            <XCircle size={13} style={{ color: 'var(--danger)' }} />
          )}
          <span>UI/UX</span>
        </div>
      </div>
    </CardWrapper>
  );
}
