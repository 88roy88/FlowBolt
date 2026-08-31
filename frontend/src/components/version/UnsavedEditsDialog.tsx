import { useTranslation } from 'react-i18next';
import { Save } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { ConfirmDialog } from '../ui/confirm-dialog';

const BODY_KEYS = {
  restore: ['version.unsavedRestoreBody', 'Restoring will replace your current files. Save your edits as a version first, or discard them permanently.'],
  preview: ['version.unsavedPreviewBody', 'Viewing an older version will replace your current files. Save your edits as a version first, or discard them permanently.'],
  send: ['version.unsavedSendBody', 'The AI works from the latest version. Save your edits as a version first, or discard them permanently.'],
} as const;

export function UnsavedEditsDialog() {
  const { t } = useTranslation();
  const pendingDirtyOp = useVersionStore((s) => s.pendingDirtyOp);
  const resolveDirtyOp = useVersionStore((s) => s.resolveDirtyOp);
  const dismissDirtyOp = useVersionStore((s) => s.dismissDirtyOp);

  const [bodyKey, bodyFallback] = BODY_KEYS[pendingDirtyOp?.op ?? 'preview'];
  const files = pendingDirtyOp?.files ?? [];

  return (
    <ConfirmDialog
      open={pendingDirtyOp !== null}
      onOpenChange={(open) => !open && dismissDirtyOp()}
      title={t('version.unsavedTitle', 'You have unsaved edits')}
      body={
        <>
          {t(bodyKey, bodyFallback)}
          {files.length > 0 && (
            <ul className="mt-2 max-h-32 overflow-y-auto font-mono text-xs opacity-80">
              {files.map((file) => (
                <li key={file}>{file}</li>
              ))}
            </ul>
          )}
        </>
      }
      confirmLabel={t('version.saveAndContinue', 'Save and continue')}
      confirmIcon={<Save size={13} />}
      onConfirm={() => resolveDirtyOp('save')}
      secondaryLabel={t('version.discardEdits', 'Discard my edits')}
      onSecondary={() => resolveDirtyOp('discard')}
    />
  );
}
