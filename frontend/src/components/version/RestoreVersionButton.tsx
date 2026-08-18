import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { useChatStore } from '../../stores/chat';
import { isAgentAlive } from '../../stores/chatAgentState';
import { Button } from '../ui/button';
import { ConfirmDialog } from '../ui/confirm-dialog';

type Props = {
  commit_sha: string;
  versionLabel: string;
  className?: string;
};

export function RestoreVersionButton({ commit_sha, versionLabel, className }: Props) {
  const { t } = useTranslation();
  const restoreVersion = useVersionStore((s) => s.restoreVersion);
  const agentBusy = useChatStore(isAgentAlive);
  const [open, setOpen] = useState(false);

  return (
    <>
      <span
        className="inline-flex"
        title={
          agentBusy
            ? t('version.busyTooltip', 'Unavailable while the AI works')
            : t('version.restoreTooltip', 'Discard newer versions')
        }
      >
        <Button variant="outline" size="sm" className={className} disabled={agentBusy} onClick={() => setOpen(true)}>
          <RotateCcw size={10} />
          {t('version.restoreHere', 'Restore here')}
        </Button>
      </span>

      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t('version.restoreDialogTitle', 'Restore version {{version}}?', { version: versionLabel })}
        body={t(
          'version.restoreDialogBody',
          'This will discard all versions after {{version}}. They can be recovered by support. This action cannot be undone.',
          { version: versionLabel },
        )}
        confirmLabel={t('version.confirmRestore', 'Yes, restore')}
        confirmClassName="bg-warning text-background hover:bg-warning/90"
        confirmIcon={<RotateCcw size={13} />}
        onConfirm={() => {
          void restoreVersion(commit_sha);
          setOpen(false);
        }}
      />
    </>
  );
}
