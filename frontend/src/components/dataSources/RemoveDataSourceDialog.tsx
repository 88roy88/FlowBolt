import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Sparkles } from 'lucide-react';
import * as api from '../../services/api';
import { logger } from '../../services/logger';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import type { DataSourceUsage, ProjectDataSource } from '../../types';
import { Button } from '../ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';

const KNOWN_REFUSALS = new Set(['dirty_workspace', 'run_active', 'previewing', 'busy', 'not_built']);

interface RemoveDataSourceDialogProps {
  projectId: string;
  dataSource: ProjectDataSource;
  onClose: () => void;
  onRemoved: () => void;
}

export function RemoveDataSourceDialog({ projectId, dataSource, onClose, onRemoved }: RemoveDataSourceDialogProps) {
  const { t } = useTranslation();
  const appendToDraft = useChatStore((s) => s.appendToDraft);
  /** Null while checking. */
  const [usages, setUsages] = useState<DataSourceUsage[] | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);
  const { data_source_id: id, name, module_path: path } = dataSource;

  useEffect(() => {
    let stale = false;
    api.fetchDataSourceUsages(projectId, id).then(
      (found) => { if (!stale) setUsages(found); },
      () => { if (!stale) setErrorKey('dataSources.errors.check'); },
    );
    return () => { stale = true; };
  }, [projectId, id]);

  const handleRemove = async () => {
    setRemoving(true);
    setErrorKey(null);
    try {
      await api.deleteProjectDataSource(projectId, id);
      const files = useFilesStore.getState();
      void files.loadFileTree();
      void files.refreshOpenFiles();
      onRemoved();
    } catch (err) {
      const detail = err instanceof api.ApiError
        ? (err.detail as { code?: string; usages?: DataSourceUsage[] } | undefined)
        : undefined;
      if (detail?.code === 'in_use' && detail.usages) setUsages(detail.usages);
      else if (detail?.code && KNOWN_REFUSALS.has(detail.code)) setErrorKey(`dataSources.errors.${detail.code}`);
      else setErrorKey('dataSources.errors.remove');
      setRemoving(false);
    }
  };

  const askAi = () => {
    logger.info('data_source_usage_removal_requested', { data_source_id: id, usage_count: usages?.length ?? 0 });
    const places = (usages ?? []).map((u) => `${u.file}:${u.line}`).join(', ');
    onClose();
    appendToDraft(t('dataSources.prompts.removeUsages', { name, path, places, interpolation: { escapeValue: false } }));
  };

  const inUse = usages !== null && usages.length > 0;

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !removing) onClose(); }}>
      <DialogContent className="w-[480px] max-w-[90vw] text-start">
        <DialogClose onClose={onClose} />
        <DialogTitle dir="auto">
          {t('dataSources.dialog.title', { name, interpolation: { escapeValue: false } })}
        </DialogTitle>

        {usages === null && !errorKey && (
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" />
            {t('dataSources.dialog.checking')}
          </p>
        )}
        {usages !== null && (
          <p className="mt-2 text-sm text-muted-foreground">
            {t(inUse ? 'dataSources.dialog.inUse' : 'dataSources.dialog.confirm')}
          </p>
        )}
        {inUse && (
          <ul className="mt-2 max-h-48 overflow-auto rounded-md border border-border bg-background px-3 py-1.5 font-mono text-[12px]">
            {usages.map((u) => (
              <li key={`${u.file}:${u.line}`} dir="ltr" className="text-start break-all">
                {u.file}:{u.line}
              </li>
            ))}
          </ul>
        )}
        {errorKey && <p role="alert" className="mt-2 text-xs text-destructive">{t(errorKey)}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={removing}>
            {t('common.cancel')}
          </Button>
          {/* Keyed, and absent while checking, so one button never fades into the other. */}
          {inUse && (
            <Button key="ask-ai" onClick={askAi}>
              <Sparkles size={14} />
              {t('dataSources.dialog.askAi')}
            </Button>
          )}
          {usages?.length === 0 && (
            <Button key="remove" variant="destructive" onClick={handleRemove} disabled={removing}>
              {removing && <Loader2 size={14} className="animate-spin" />}
              {t('dataSources.dialog.remove')}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
