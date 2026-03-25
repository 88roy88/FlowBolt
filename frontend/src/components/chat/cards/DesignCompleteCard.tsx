import { CheckCircle2, XCircle } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

export function DesignCompleteCard({ architecture, ux }: { architecture: boolean; ux: boolean }) {
  return (
    <CardWrapper>
      <div className="text-xs text-muted-foreground mb-1.5">Design complete</div>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          {architecture ? <CheckCircle2 size={13} className="text-success" /> : <XCircle size={13} className="text-destructive" />}
          <span>Architecture</span>
        </div>
        <div className="flex items-center gap-1.5">
          {ux ? <CheckCircle2 size={13} className="text-success" /> : <XCircle size={13} className="text-destructive" />}
          <span>UI/UX</span>
        </div>
      </div>
    </CardWrapper>
  );
}
