import { CheckCircle2 } from 'lucide-react';
import type { ProjectSummary } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { ProjectSummaryContent } from './ProjectSummaryContent';

export function ProjectSummaryCard({ summary }: { summary: ProjectSummary }) {
  return (
    <CardWrapper>
      <div className="flex items-center gap-1.5 mb-2 text-xs text-success">
        <CheckCircle2 size={12} />
        Project complete
      </div>
      <ProjectSummaryContent summary={summary} />
    </CardWrapper>
  );
}
