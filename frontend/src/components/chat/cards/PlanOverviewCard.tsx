import { Check, X, Sparkles, ArrowRight } from 'lucide-react';
import type { PlanOverview } from '../../../types';
import { CardWrapper } from './CardWrapper';

export function PlanOverviewCard({ overview, accepted }: { overview: PlanOverview; accepted: boolean }) {
  return (
    <CardWrapper>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: accepted ? 'var(--success)' : 'var(--text-dim)',
      }}>
        {accepted ? <Check size={12} /> : <X size={12} />}
        {accepted ? 'Plan accepted' : 'Plan rejected'}
      </div>
      <p style={{ marginBottom: '8px', lineHeight: '1.5' }}>{overview.summary}</p>
      {overview.features && overview.features.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
          {overview.features.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
              <Sparkles size={12} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
              <span><strong>{f.title}</strong> — {f.description}</span>
            </div>
          ))}
        </div>
      )}
      {overview.decisions && overview.decisions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {overview.decisions.map((d) => (
            <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-dim)' }}>
              <ArrowRight size={10} style={{ flexShrink: 0 }} />
              <span><strong>{d.title}:</strong> {d.chosen}</span>
            </div>
          ))}
        </div>
      )}
    </CardWrapper>
  );
}
