import { useTranslation } from 'react-i18next';
import { Save } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { Button } from '../ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';
import { DirtyFileList } from './DirtyFileList';

export function UnsavedEditsDialog() {
  const { t } = useTranslation();
  const pendingDirtyOp = useVersionStore((s) => s.pendingDirtyOp);
  const resolveDirtyOp = useVersionStore((s) => s.resolveDirtyOp);
  const dismissDirtyOp = useVersionStore((s) => s.dismissDirtyOp);

  return (
    <Dialog open={pendingDirtyOp !== null} onOpenChange={(open) => !open && dismissDirtyOp()}>
      <DialogContent>
        <DialogClose onClose={dismissDirtyOp} />
        <DialogTitle>{t('version.unsavedTitle')}</DialogTitle>
        <div className="text-sm text-muted-foreground mt-2 mb-4">
          {t('version.unsavedBody')}
          <DirtyFileList files={pendingDirtyOp?.files ?? []} />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={dismissDirtyOp}>
            {t('common.cancel')}
          </Button>
          <Button variant="destructive" size="sm" onClick={() => resolveDirtyOp('discard')}>
            {t('version.discardEdits')}
          </Button>
          <Button size="sm" onClick={() => resolveDirtyOp('save')}>
            <Save size={13} />
            {t('version.saveAndContinue')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
