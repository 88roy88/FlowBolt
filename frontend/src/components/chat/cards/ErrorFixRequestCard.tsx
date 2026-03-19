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
    <CardWrapper>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: '#f38ba8',
      }}>
        <AlertTriangle size={14} />
        Fix error request
      </div>

      {errorFile && (
        <div style={{ marginBottom: '8px', fontSize: '12px', color: 'var(--text-dim)' }}>
          <FileText size={12} style={{ display: 'inline', marginRight: '4px' }} />
          <strong>{errorFile}</strong>
          {errorLine && <span>:{errorLine}</span>}
        </div>
      )}

      <div
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: 'pointer',
          padding: '6px',
          marginBottom: isExpanded ? '8px' : '0',
          borderRadius: '6px',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
        }}
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span style={{ fontSize: '12px', fontWeight: 600 }}>Error details</span>
      </div>

      {isExpanded && (
        <div style={{
          padding: '8px',
          background: 'var(--bg)',
          borderRadius: '6px',
          fontSize: '12px',
          lineHeight: '1.5',
        }}>
          <div style={{ marginBottom: errorStack ? '8px' : '0' }}>
            <strong style={{ color: '#f38ba8' }}>Message:</strong>
            <div style={{ marginTop: '4px', color: 'var(--text)' }}>{errorMessage}</div>
          </div>

          {errorStack && (
            <div>
              <strong style={{ color: 'var(--text-dim)' }}>Stack trace:</strong>
              <pre style={{
                marginTop: '4px',
                padding: '8px',
                background: 'var(--surface)',
                borderRadius: '4px',
                fontSize: '11px',
                overflow: 'auto',
                maxHeight: '200px',
                fontFamily: 'monospace',
              }}>
                {errorStack}
              </pre>
            </div>
          )}
        </div>
      )}
    </CardWrapper>
  );
}
