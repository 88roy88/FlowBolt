import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Pencil, Trash2 } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { useWorkspaceLock } from '../../stores/workspaceLock';
import { Button } from '../ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';
import { DirtyFileList } from './DirtyFileList';

export function UnsavedEditsRow() {
  const { t } = useTranslation();
  const dirtyFiles = useVersionStore((s) => s.dirtyFiles);
  const saveVersion = useVersionStore((s) => s.saveVersion);
  const discardEdits = useVersionStore((s) => s.discardEdits);
  const { lock } = useWorkspaceLock();
  const [confirming, setConfirming] = useState(false);

  if (lock !== null || !dirtyFiles.length) return null;

  return (
    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
      <Pencil size={11} className="text-primary/70 shrink-0" />
      <span className="text-[11px] text-muted-foreground/60 select-none">
        {t('version.unsavedRow', { count: dirtyFiles.length })}
      </span>

      <Button
        size="sm"
        title={t('version.saveTooltip')}
        className="h-5 px-2 text-[11px] gap-1"
        onClick={saveVersion}
      >
        <Check size={10} />
        {t('version.saveAsVersion')}
      </Button>

      <Button
        variant="outline"
        size="sm"
        title={t('version.discardTooltip')}
        className="h-5 w-5 p-0 hover:text-destructive hover:border-destructive/40"
        onClick={() => setConfirming(true)}
      >
        <Trash2 size={10} />
      </Button>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogClose onClose={() => setConfirming(false)} />
          <DialogTitle>{t('version.discardTitle')}</DialogTitle>
          <div className="text-sm text-muted-foreground mt-2 mb-4">
            {t('version.discardBody')}
            <DirtyFileList files={dirtyFiles} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                discardEdits();
                setConfirming(false);
              }}
            >
              <Trash2 size={13} />
              {t('version.discardEdits')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
