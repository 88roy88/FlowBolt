import { useTranslation } from 'react-i18next';
import { History, X } from 'lucide-react';
import { useVersionStore, formatVersionLabel } from '../../stores/version';
import { Button } from '../ui/button';
import { RestoreVersionButton } from '../version/RestoreVersionButton';

export function PreviewVersionBanner() {
  const { t } = useTranslation();
  const previewingVersion = useVersionStore((s) => s.previewingVersion);
  const versions = useVersionStore((s) => s.versions);
  const exitPreview = useVersionStore((s) => s.exitPreview);

  if (!previewingVersion) return null;

  const versionLabel = formatVersionLabel(versions, previewingVersion);

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-warning/10 border-b border-warning/30 shrink-0 text-[13px]">
      <History size={14} className="text-warning shrink-0" />
      <span className="text-warning font-medium flex-1">
        {t('version.previewingBanner', 'Previewing {{version}}', { version: versionLabel })}
      </span>
      <Button
        variant="outline"
        size="sm"
        className="h-6 px-2 text-[11px] gap-1 border-warning/40 text-warning hover:bg-warning/10"
        onClick={exitPreview}
      >
        <X size={10} />
        {t('version.returnToLatest', 'Return to latest')}
      </Button>
      <RestoreVersionButton
        commit_sha={previewingVersion}
        versionLabel={versionLabel}
        className="h-6 px-2 text-[11px] gap-1 border-warning/40 text-warning hover:bg-warning/10"
      />
    </div>
  );
}
