import { useTranslation } from 'react-i18next';
import { History, X } from 'lucide-react';
import { useVersionStore, formatVersionLabel } from '../../stores/version';
import { useChatStore } from '../../stores/chat';
import { isAgentAlive } from '../../stores/chatAgentState';
import { useSessionStore } from '../../stores/session';
import { WRITE_ROLES } from '../../types';
import { Button } from '../ui/button';
import { RestoreVersionButton } from '../version/RestoreVersionButton';

export function PreviewVersionBanner() {
  const { t } = useTranslation();
  const previewingVersion = useVersionStore((s) => s.previewingVersion);
  const versions = useVersionStore((s) => s.versions);
  const exitPreview = useVersionStore((s) => s.exitPreview);
  const agentBusy = useChatStore(isAgentAlive);
  const projectRole = useSessionStore((s) => s.currentProject?.role);
  const canWrite = !projectRole || WRITE_ROLES.has(projectRole);

  if (!previewingVersion) return null;

  const versionLabel = formatVersionLabel(versions, previewingVersion);

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-warning/10 border-b border-warning/30 shrink-0 text-[13px]">
      <History size={14} className="text-warning shrink-0" />
      <span className="text-warning font-medium">
        {t('version.previewingBanner', 'Previewing {{version}}', { version: versionLabel })}
      </span>
      <span className="text-warning/70 flex-1 truncate">
        {t('version.previewingShared', 'Everyone viewing this project sees this version.')}
      </span>
      {canWrite && (
        <>
          <span
            className="inline-flex"
            title={
              agentBusy
                ? t('version.busyTooltip', 'Unavailable while the AI works')
                : t('version.exitPreviewTooltip', 'Back to latest')
            }
          >
            <Button
              variant="outline"
              size="sm"
              className="h-6 px-2 text-[11px] gap-1 border-warning/40 text-warning hover:bg-warning/10"
              disabled={agentBusy}
              onClick={exitPreview}
            >
              <X size={10} />
              {t('version.returnToLatest', 'Return to latest')}
            </Button>
          </span>
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
