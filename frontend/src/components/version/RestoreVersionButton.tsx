import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { useWorkspaceLock } from '../../stores/workspaceLock';
import { Button } from '../ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';

type Props = {
  commit_sha: string;
  versionLabel: string;
  className?: string;
};

export function RestoreVersionButton({ commit_sha, versionLabel, className }: Props) {
  const { t } = useTranslation();
  const restoreVersion = useVersionStore((s) => s.restoreVersion);
  const { agentBusy } = useWorkspaceLock();
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        title={agentBusy ? t('version.busyTooltip') : t('version.restoreTooltip')}
        className={className}
        aria-disabled={agentBusy}
        onClick={() => setOpen(true)}
      >
        <RotateCcw size={10} />
        {t('version.restoreHere')}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogClose onClose={() => setOpen(false)} />
          <DialogTitle>{t('version.restoreDialogTitle', { version: versionLabel })}</DialogTitle>
          <div className="text-sm text-muted-foreground mt-2 mb-4">
            {t('version.restoreDialogBody', { version: versionLabel })}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="warning"
              size="sm"
              onClick={() => {
                restoreVersion(commit_sha);
                setOpen(false);
              }}
            >
              <RotateCcw size={13} />
              {t('version.confirmRestore')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
