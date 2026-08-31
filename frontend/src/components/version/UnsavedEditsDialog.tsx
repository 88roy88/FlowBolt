import { useTranslation } from 'react-i18next';
import { Save } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { ConfirmDialog } from '../ui/confirm-dialog';

export function UnsavedEditsDialog() {
  const { t } = useTranslation();
  const pendingDirtyOp = useVersionStore((s) => s.pendingDirtyOp);
  const resolveDirtyOp = useVersionStore((s) => s.resolveDirtyOp);
  const dismissDirtyOp = useVersionStore((s) => s.dismissDirtyOp);

  const files = pendingDirtyOp?.files ?? [];

  return (
    <ConfirmDialog
      open={pendingDirtyOp !== null}
      onOpenChange={(open) => !open && dismissDirtyOp()}
      title={t('version.unsavedTitle')}
      body={
        <>
          {t('version.unsavedBody')}
          {files.length > 0 && (
            <ul className="mt-2 max-h-32 overflow-y-auto font-mono text-xs opacity-80">
              {files.map((file) => (
                <li key={file}>{file}</li>
              ))}
            </ul>
          )}
        </>
      }
      confirmLabel={t('version.saveAndContinue')}
      confirmIcon={<Save size={13} />}
      onConfirm={() => resolveDirtyOp('save')}
      secondaryLabel={t('version.discardEdits')}
      onSecondary={() => resolveDirtyOp('discard')}
    />
  );
}
