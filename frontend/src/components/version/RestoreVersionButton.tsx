import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RotateCcw } from 'lucide-react';
import { useVersionStore } from '../../stores/version';
import { useWorkspaceLock } from '../../stores/workspaceLock';
import { ActionButton } from '../ui/action-button';
import { ConfirmDialog } from '../ui/confirm-dialog';

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
      <ActionButton
        title={agentBusy ? t('version.busyTooltip') : t('version.restoreTooltip')}
        className={className}
        disabled={agentBusy}
        onClick={() => setOpen(true)}
      >
        <RotateCcw size={10} />
        {t('version.restoreHere')}
      </ActionButton>

      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title={t('version.restoreDialogTitle', { version: versionLabel })}
        body={t('version.restoreDialogBody', { version: versionLabel })}
        confirmLabel={t('version.confirmRestore')}
        confirmVariant="warning"
        confirmIcon={<RotateCcw size={13} />}
        onConfirm={() => {
          restoreVersion(commit_sha);
          setOpen(false);
        }}
      />
    </>
  );
}
