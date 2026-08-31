import { useTranslation } from 'react-i18next';
import { History, X } from 'lucide-react';
import { useVersionStore, formatVersionLabel } from '../../stores/version';
import { LOCK_MESSAGES, useWorkspaceLock } from '../../stores/workspaceLock';
import { ActionButton } from '../ui/action-button';
import { RestoreVersionButton } from '../version/RestoreVersionButton';

export function PreviewVersionBanner() {
  const { t } = useTranslation();
  const previewingVersion = useVersionStore((s) => s.previewingVersion);
  const versions = useVersionStore((s) => s.versions);
  const exitPreview = useVersionStore((s) => s.exitPreview);
  const { agentBusy, canWrite } = useWorkspaceLock();

  if (!previewingVersion) return null;

  const versionLabel = formatVersionLabel(versions, previewingVersion);

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-warning/10 border-b border-warning/30 shrink-0 text-[13px]">
      <History size={14} className="text-warning shrink-0" />
      <span className="text-warning font-medium">
        {t('version.previewingBanner', { version: versionLabel })}
      </span>
      <span className="text-warning/70 flex-1 truncate">
        {t('version.previewingShared')}
      </span>
      {canWrite && (
        <>
          <ActionButton
            title={agentBusy ? t(LOCK_MESSAGES.run_active) : t('version.exitPreviewTooltip')}
            className="h-6 px-2 text-[11px] gap-1 border-warning/40 text-warning hover:bg-warning/10"
            disabled={agentBusy}
            onClick={exitPreview}
          >
            <X size={10} />
            {t('version.returnToLatest')}
          </ActionButton>
          <RestoreVersionButton
            commit_sha={previewingVersion}
            versionLabel={versionLabel}
            className="h-6 px-2 text-[11px] gap-1 border-warning/40 text-warning hover:bg-warning/10"
          />
        </>
      )}
    </div>
  );
}
