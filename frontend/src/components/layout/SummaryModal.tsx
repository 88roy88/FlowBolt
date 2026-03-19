import { X } from 'lucide-react';
import type { ProjectSummary } from '../../types';
import { ProjectSummaryContent } from '../chat/cards/ProjectSummaryContent';

export function SummaryModal({ projectName, summary, onClose }: {
  projectName: string;
  summary: ProjectSummary;
  onClose: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          padding: '20px',
          maxWidth: '500px',
          maxHeight: '80vh',
          overflow: 'auto',
          position: 'relative',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '12px',
            right: '12px',
            padding: '4px',
            color: 'var(--text-dim)',
            borderRadius: '4px',
          }}
          title="Close"
        >
          <X size={18} />
        </button>

        <h3 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 600, paddingRight: '24px' }}>
          {projectName}
        </h3>

        <ProjectSummaryContent summary={summary} />
      </div>
    </div>
  );
}
