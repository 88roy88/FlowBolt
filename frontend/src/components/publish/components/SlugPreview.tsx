import { ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SHARED_PREFIX } from '../../../stores/publish';

export function SlugPreview({ slugValue, dimmed = false }: { slugValue: string; dimmed?: boolean }) {
  return (
    <div className={cn(
      'flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-xs text-muted-foreground font-mono',
      dimmed && 'opacity-50',
    )}>
      <ExternalLink size={12} className="shrink-0" />
      <span className="truncate">{window.location.origin}{SHARED_PREFIX}{slugValue}</span>
    </div>
  );
}
