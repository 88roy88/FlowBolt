import { useTranslation } from 'react-i18next';
import { Pencil } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

export function UserEditCard({ files }: { files: string[] }) {
  const { t } = useTranslation();
  const shown = files.slice(0, 3).join(', ');
  const label = files.length > 3
    ? t('version.youEditedMore', 'You edited {{files}} and {{count}} more', { files: shown, count: files.length - 3 })
    : t('version.youEdited', 'You edited {{files}}', { files: shown });

  return (
    <CardWrapper accent="primary">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Pencil size={13} className="text-primary/70 shrink-0" />
        <span className="truncate">{files.length ? label : t('version.youEditedFiles', 'You edited the project')}</span>
      </div>
    </CardWrapper>
  );
}
