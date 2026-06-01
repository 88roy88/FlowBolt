import { ExternalLink } from 'lucide-react';
import { SHARED_PREFIX } from '../../../stores/publish';

export function SlugPreview({ slugValue }: { slugValue: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-xs text-muted-foreground font-mono">
      <ExternalLink size={12} className="shrink-0" />
      <span className="truncate">{window.location.origin}{SHARED_PREFIX}{slugValue}</span>
    </div>
  );
}
