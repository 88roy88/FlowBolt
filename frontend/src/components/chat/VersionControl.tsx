import { useTranslation } from 'react-i18next';
import { History, Eye, CheckCircle } from 'lucide-react';
import { useVersionStore, formatVersionLabel } from '../../stores/version';
import { useChatStore } from '../../stores/chat';
import { isAgentAlive } from '../../stores/chatAgentState';
import { useSessionStore } from '../../stores/session';
import { WRITE_ROLES } from '../../types';
import { Button } from '../ui/button';
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
  const agentBusy = useChatStore(isAgentAlive);
  const projectRole = useSessionStore((s) => s.currentProject?.role);
  const canWrite = !projectRole || WRITE_ROLES.has(projectRole);

  let previewTitle = t('version.previewTooltip', 'View version without restoring');
  if (isPreviewing) previewTitle = t('version.exitPreviewTooltip', 'Back to latest');
  if (agentBusy) previewTitle = t('version.busyTooltip', 'Unavailable while the AI works');

  if (isLatestVersion) {
    return (
      <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-muted-foreground/60 select-none">
        <CheckCircle size={11} className="text-success/70" />
        <span>{t('version.currentVersion', 'Current version')} ({versionLabel})</span>
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
      <span className="inline-flex" title={previewTitle}>
        <Button
          variant="outline"
          size="sm"
          className="h-5 px-2 text-[11px] gap-1"
          disabled={agentBusy}
          onClick={isPreviewing ? exitPreview : () => previewVersionAction(commit_sha)}
        >
          <Eye size={10} />
          {isPreviewing ? t('version.exitPreview', 'Exit preview') : t('version.preview', 'Preview')}
        </Button>
      </span>
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
