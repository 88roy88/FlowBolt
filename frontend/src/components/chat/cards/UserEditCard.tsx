import { useTranslation } from 'react-i18next';
import { Pencil, RefreshCw } from 'lucide-react';
import type { FileDiff, VersionAuthor } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { FileRows } from './FilesChangedSection';

const SYSTEM = { Icon: RefreshCw, label: 'version.platformUpdate', bubble: 'border-border bg-assistant-bubble' };
const USER = { Icon: Pencil, label: 'version.yourEdits', bubble: 'border-primary/30 bg-user-bubble' };

export function UserEditCard({ diffs, author }: { diffs?: FileDiff[]; author?: VersionAuthor }) {
  const { t } = useTranslation();
  const { Icon, label, bubble } = author === 'system' ? SYSTEM : USER;

  return (
    <CardWrapper className={`w-full px-2.5 py-2 ${bubble}`}>
      <div className="flex items-center gap-1.5 mb-2 text-[11px] text-muted-foreground">
        <Icon size={11} className="text-primary/70 shrink-0" />
        <span>{t(label)}</span>
      </div>
      <FileRows diffs={diffs} />
    </CardWrapper>
  );
}
