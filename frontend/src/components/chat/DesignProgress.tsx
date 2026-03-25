import { Loader2, CheckCircle2 } from 'lucide-react';
import { CardWrapper } from './cards/CardWrapper';

export function DesignProgress({ designProgress }: { designProgress: { architecture: string | null; ux: string | null } }) {
  return (
    <CardWrapper>
      <div className="text-[13px] font-medium mb-2.5">Designing...</div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2 text-[13px]">
          {designProgress.architecture ? (
            <CheckCircle2 size={14} className="text-success" />
          ) : (
            <Loader2 size={14} className="text-primary animate-spin" />
          )}
          <span>Architecture</span>
        </div>
        <div className="flex items-center gap-2 text-[13px]">
          {designProgress.ux ? (
            <CheckCircle2 size={14} className="text-success" />
          ) : (
            <Loader2 size={14} className="text-primary animate-spin" />
          )}
          <span>UI/UX</span>
        </div>
      </div>
    </CardWrapper>
  );
}
