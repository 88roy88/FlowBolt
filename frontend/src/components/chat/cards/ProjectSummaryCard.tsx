import { CheckCircle2 } from 'lucide-react';
import type { ProjectSummary } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { ProjectSummaryContent } from './ProjectSummaryContent';

export function ProjectSummaryCard({ summary }: { summary: ProjectSummary }) {
  return (
    <CardWrapper>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: 'var(--success)',
      }}>
        <CheckCircle2 size={12} />
        Project complete
      </div>
      <ProjectSummaryContent summary={summary} />
    </CardWrapper>
  );
}
