import { Sparkles, FileText, Package } from 'lucide-react';
import type { ProjectSummary } from '../../../types';

export function ProjectSummaryContent({ summary }: { summary: ProjectSummary }) {
  return (
    <>
      <p style={{ marginBottom: '12px', lineHeight: '1.6' }}>{summary.summary}</p>

      {summary.tech_stack && summary.tech_stack.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '6px' }}>
            Tech Stack
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {summary.tech_stack.map((tech, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '3px 8px',
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: '5px',
                  fontSize: '11px',
                  color: 'var(--accent)',
                }}
              >
                <Package size={10} />
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.features && summary.features.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '6px' }}>
            Features
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {summary.features.map((feature, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                <Sparkles size={12} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary.file_overview && Object.keys(summary.file_overview).length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '6px' }}>
            Key Files
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {Object.entries(summary.file_overview).map(([file, description]) => (
              <div key={file} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px' }}>
                <FileText size={12} style={{ color: 'var(--text-dim)', flexShrink: 0, marginTop: '2px' }} />
                <span>
                  <strong style={{ color: 'var(--text)' }}>{file}</strong>
                  <span style={{ color: 'var(--text-dim)' }}> — {description}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
