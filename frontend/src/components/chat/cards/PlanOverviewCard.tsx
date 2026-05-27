import { Check, Sparkles, ArrowRight } from 'lucide-react';
import type { PlanOverview } from '../../../types';
import { CardWrapper } from './CardWrapper';

export function PlanOverviewCard({ overview }: { overview: PlanOverview }) {
  return (
    <CardWrapper accent="primary">
      <div className="flex items-center gap-1.5 mb-2 text-xs text-success">
        <Check size={12} />
        Plan accepted
      </div>
      <p className="mb-2 leading-normal">{overview.summary}</p>
      {overview.features && overview.features.length > 0 && (
        <div className="flex flex-col gap-1 mb-2">
          {overview.features.map((f, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <Sparkles size={12} className="text-primary shrink-0 mt-0.5" />
              <span><strong>{f.title}</strong> — {f.description}</span>
            </div>
          ))}
        </div>
      )}
      {overview.decisions && overview.decisions.length > 0 && (
        <div className="flex flex-col gap-1">
          {overview.decisions.map((d) => (
            <div key={d.id} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ArrowRight size={10} className="shrink-0" />
              <span><strong>{d.title}:</strong> {d.chosen}</span>
            </div>
          ))}
        </div>
      )}
    </CardWrapper>
  );
}
