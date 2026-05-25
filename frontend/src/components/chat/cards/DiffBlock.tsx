import { useState } from 'react';
import { FileText, ChevronDown, ChevronRight } from 'lucide-react';
import type { FileDiff } from '../../../types';

export function DiffBlock({ fileDiff }: { fileDiff: FileDiff }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const lines = fileDiff.diff.split('\n');
  let additions = 0;
  let deletions = 0;
  for (const line of lines) {
    if (line.startsWith('+') && !line.startsWith('+++')) additions++;
    else if (line.startsWith('-') && !line.startsWith('---')) deletions++;
  }

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 px-2.5 py-1.5 bg-background cursor-pointer text-xs"
      >
        {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <FileText size={12} className="text-primary shrink-0" />
        <span className="font-mono flex-1">{fileDiff.path}</span>
        <span className="flex gap-1.5 text-[11px] shrink-0">
          {additions > 0 && <span className="text-diff-add">+{additions}</span>}
          {deletions > 0 && <span className="text-diff-remove">-{deletions}</span>}
        </span>
      </div>
      {isExpanded && (
        <div className="overflow-auto max-h-[300px] text-[11px] font-mono leading-normal">
          {lines.map((line, i) => {
            if (i === lines.length - 1 && line === '') return null;
            let bgClass = '';
            let textClass = 'text-muted-foreground';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              bgClass = 'bg-diff-add-bg';
              textClass = 'text-diff-add';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              bgClass = 'bg-diff-remove-bg';
              textClass = 'text-diff-remove';
            } else if (line.startsWith('@@')) {
              textClass = 'text-primary';
            }
            return (
              <div key={i} className={`px-2.5 whitespace-pre min-h-[18px] ${bgClass} ${textClass}`}>
                {line}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
