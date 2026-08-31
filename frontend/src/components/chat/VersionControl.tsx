import { useTranslation } from 'react-i18next';
import { History, Eye, CheckCircle } from 'lucide-react';
import { useVersionStore, formatVersionLabel } from '../../stores/version';
import { LOCK_MESSAGES, useWorkspaceLock } from '../../stores/workspaceLock';
import { ActionButton } from '../ui/action-button';
import { RestoreVersionButton } from '../version/RestoreVersionButton';

type Props = {
  commit_sha: string;
};

export function VersionControl({ commit_sha }: Props) {
  const { t } = useTranslation();
  const versionLabel = useVersionStore((s) => formatVersionLabel(s.versions, commit_sha));
  const isLatestVersion = useVersionStore((s) => s.versions.at(-1) === commit_sha);
  const isPreviewing = useVersionStore((s) => s.previewingVersion === commit_sha);
  const previewVersionAction = useVersionStore((s) => s.previewVersion);
  const exitPreview = useVersionStore((s) => s.exitPreview);
  const { agentBusy, canWrite } = useWorkspaceLock();

  let previewTitle = t('version.previewTooltip');
  if (isPreviewing) previewTitle = t('version.exitPreviewTooltip');
  if (agentBusy) previewTitle = t(LOCK_MESSAGES.run_active);

  if (isLatestVersion) {
    return (
      <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-muted-foreground/60 select-none">
        <CheckCircle size={11} className="text-success/70" />
        <span>{t('version.currentVersion')} ({versionLabel})</span>
      </div>
    );
  }

  if (!canWrite) {
    return (
      <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-muted-foreground/60 select-none">
        <History size={11} className="text-muted-foreground/50 shrink-0" />
        <span>{versionLabel}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
      <History size={11} className="text-muted-foreground/50 shrink-0" />
      <span className="text-[11px] text-muted-foreground/60 select-none">{versionLabel}</span>
      <ActionButton
        title={previewTitle}
        className="h-5 px-2 text-[11px] gap-1"
        disabled={agentBusy}
        onClick={isPreviewing ? exitPreview : () => previewVersionAction(commit_sha)}
      >
        <Eye size={10} />
        {isPreviewing ? t('version.exitPreview') : t('version.preview')}
      </ActionButton>
      {isPreviewing && (
        <RestoreVersionButton
          commit_sha={commit_sha}
          versionLabel={versionLabel}
          className="h-5 px-2 text-[11px] gap-1"
        />
      )}
    </div>
  );
}
