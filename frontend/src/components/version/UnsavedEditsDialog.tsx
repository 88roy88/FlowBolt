import { useTranslation } from 'react-i18next';
import { Save } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { DirtyFileList } from './DirtyFileList';

export function UnsavedEditsDialog() {
  const { t } = useTranslation();
  const pendingDirtyOp = useVersionStore((s) => s.pendingDirtyOp);
  const resolveDirtyOp = useVersionStore((s) => s.resolveDirtyOp);
  const dismissDirtyOp = useVersionStore((s) => s.dismissDirtyOp);

  return (
    <ConfirmDialog
      open={pendingDirtyOp !== null}
      onOpenChange={(open) => !open && dismissDirtyOp()}
      title={t('version.unsavedTitle')}
      body={
        <>
          {t('version.unsavedBody')}
          <DirtyFileList files={pendingDirtyOp?.files ?? []} />
        </>
      }
      confirmLabel={t('version.saveAndContinue')}
      confirmIcon={<Save size={13} />}
      onConfirm={() => resolveDirtyOp('save')}
      secondaryLabel={t('version.discardEdits')}
      secondaryVariant="destructive"
      onSecondary={() => resolveDirtyOp('discard')}
    />
  );
}
