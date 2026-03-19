import type { ProjectSummary } from '../../types';
import { ProjectSummaryContent } from '../chat/cards/ProjectSummaryContent';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';

export function SummaryModal({ projectName, summary, onClose }: {
  projectName: string;
  summary: ProjectSummary;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent>
        <DialogClose onClose={onClose} />
        <DialogTitle className="mb-4">{projectName}</DialogTitle>
        <ProjectSummaryContent summary={summary} />
      </DialogContent>
    </Dialog>
  );
}
