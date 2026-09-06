import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Pencil, Trash2 } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { useWorkspaceLock } from '../../stores/workspaceLock';
import { ActionButton } from '../ui/action-button';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { DirtyFileList } from './DirtyFileList';

export function UnsavedEditsRow() {
  const { t } = useTranslation();
  const dirtyFiles = useVersionStore((s) => s.dirtyFiles);
  const saveVersion = useVersionStore((s) => s.saveVersion);
  const discardEdits = useVersionStore((s) => s.discardEdits);
  const { code } = useWorkspaceLock();
  const [confirming, setConfirming] = useState(false);

  if (code !== null || !dirtyFiles.length) return null;

  return (
    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
      <Pencil size={11} className="text-primary/70 shrink-0" />
      <span className="text-[11px] text-muted-foreground/60 select-none">
        {t('version.unsavedRow', { count: dirtyFiles.length })}
      </span>

      <ActionButton
        variant="default"
        title={t('version.saveTooltip')}
        className="h-5 px-2 text-[11px] gap-1"
        onClick={saveVersion}
      >
        <Check size={10} />
        {t('version.saveAsVersion')}
      </ActionButton>

      <ActionButton
        title={t('version.discardTooltip')}
        className="h-5 w-5 p-0 hover:text-destructive hover:border-destructive/40"
        onClick={() => setConfirming(true)}
      >
        <Trash2 size={10} />
      </ActionButton>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={t('version.discardTitle')}
        body={
          <>
            {t('version.discardBody')}
            <DirtyFileList files={dirtyFiles} />
          </>
        }
        confirmLabel={t('version.discardEdits')}
        confirmVariant="destructive"
        confirmIcon={<Trash2 size={13} />}
        onConfirm={() => {
          discardEdits();
          setConfirming(false);
        }}
      />
    </div>
  );
}
