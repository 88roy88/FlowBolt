import { useTranslation } from 'react-i18next';
import { Pencil } from 'lucide-react';
import type { FileDiff } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { FileRows } from './FilesChangedSection';

export function UserEditCard({ diffs }: { diffs?: FileDiff[] }) {
  const { t } = useTranslation();

  return (
    <CardWrapper className="w-full border-primary/30 bg-user-bubble px-2.5 py-2">
      <div className="flex items-center gap-1.5 mb-2 text-[11px] text-muted-foreground">
        <Pencil size={11} className="text-primary/70 shrink-0" />
        <span>{t('version.yourEdits', 'Your edits')}</span>
      </div>
      <FileRows diffs={diffs} />
    </CardWrapper>
  );
}
