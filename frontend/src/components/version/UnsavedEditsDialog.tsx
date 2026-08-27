import { useTranslation } from 'react-i18next';
import { Save } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { ConfirmDialog } from '../ui/confirm-dialog';

export function UnsavedEditsDialog() {
  const { t } = useTranslation();
  const pendingDirtyOp = useVersionStore((s) => s.pendingDirtyOp);
  const resolveDirtyOp = useVersionStore((s) => s.resolveDirtyOp);
  const dismissDirtyOp = useVersionStore((s) => s.dismissDirtyOp);

  const isRestore = pendingDirtyOp?.op === 'restore';

  return (
    <ConfirmDialog
      open={pendingDirtyOp !== null}
      onOpenChange={(open) => !open && dismissDirtyOp()}
      title={t('version.unsavedTitle', 'You have unsaved edits')}
      body={
        isRestore
          ? t('version.unsavedRestoreBody', 'Restoring will replace your current files. Save your edits as a version first, or discard them permanently.')
          : t('version.unsavedPreviewBody', 'Viewing an older version will replace your current files. Save your edits as a version first, or discard them permanently.')
      }
      confirmLabel={t('version.saveAndContinue', 'Save and continue')}
      confirmIcon={<Save size={13} />}
      onConfirm={() => resolveDirtyOp('save')}
      secondaryLabel={t('version.discardEdits', 'Discard my edits')}
      onSecondary={() => resolveDirtyOp('discard')}
    />
  );
}
