import { useState } from 'react';
import { AlertTriangle, FileText, ChevronDown, ChevronRight } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

export function ErrorFixRequestCard({ errorMessage, errorFile, errorLine, errorStack }: {
  errorMessage: string;
  errorFile?: string;
  errorLine?: number;
  errorStack?: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <CardWrapper accent="destructive">
      <div className="flex items-center gap-1.5 mb-2 text-xs text-destructive">
        <AlertTriangle size={14} />
        Fix error request
      </div>

      {errorFile && (
        <div className="mb-2 text-xs text-muted-foreground">
          <FileText size={12} className="inline me-1" />
          <strong>{errorFile}</strong>
          {errorLine && <span>:{errorLine}</span>}
        </div>
      )}

      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className={`flex items-center gap-1.5 cursor-pointer p-1.5 rounded-md bg-background border border-border ${isExpanded ? 'mb-2' : ''}`}
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="text-xs font-semibold">Error details</span>
      </div>

      {isExpanded && (
        <div className="p-2 bg-background rounded-md text-xs leading-normal">
          <div className={errorStack ? 'mb-2' : ''}>
            <strong className="text-destructive">Message:</strong>
            <div className="mt-1">{errorMessage}</div>
          </div>

          {errorStack && (
            <div>
              <strong className="text-muted-foreground">Stack trace:</strong>
              <pre className="mt-1 p-2 bg-surface rounded text-[11px] overflow-auto max-h-[200px] font-mono">
                {errorStack}
              </pre>
            </div>
          )}
        </div>
      )}
    </CardWrapper>
  );
}
