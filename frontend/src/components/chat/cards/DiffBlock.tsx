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
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: '6px',
      overflow: 'hidden',
    }}>
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 10px',
          background: 'var(--bg)',
          cursor: 'pointer',
          fontSize: '12px',
        }}
      >
        {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <FileText size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
        <span style={{ fontFamily: 'var(--font-mono)', flex: 1 }}>{fileDiff.path}</span>
        <span style={{ display: 'flex', gap: '6px', fontSize: '11px', flexShrink: 0 }}>
          {additions > 0 && <span style={{ color: 'var(--diff-add)' }}>+{additions}</span>}
          {deletions > 0 && <span style={{ color: 'var(--diff-remove)' }}>-{deletions}</span>}
        </span>
      </div>
      {isExpanded && (
        <div style={{
          overflow: 'auto',
          maxHeight: '300px',
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          lineHeight: '1.5',
        }}>
          {lines.map((line, i) => {
            if (i === lines.length - 1 && line === '') return null;
            let bg = 'transparent';
            let color = 'var(--text-dim)';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              bg = 'var(--diff-add-bg)';
              color = 'var(--diff-add)';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              bg = 'var(--diff-remove-bg)';
              color = 'var(--diff-remove)';
            } else if (line.startsWith('@@')) {
              color = 'var(--accent)';
            }
            return (
              <div
                key={i}
                style={{
                  padding: '0 10px',
                  background: bg,
                  color,
                  whiteSpace: 'pre',
                  minHeight: '18px',
                }}
              >
                {line}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
