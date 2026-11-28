import type { CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, Trash2, WandSparkles } from 'lucide-react';
import { useDataSourceActivityStore } from '../../stores/dataSourceActivity';
import type { ProjectDataSource } from '../../types';
import { cn } from '@/lib/utils';
import { Button } from '../ui/button';
import { FlowLogo } from '../ui/flow-logo';

// eslint-disable-next-line react-refresh/only-export-components
export const aiMenuAnchorName = (id: string) => `--data-source-ai-${id.replace(/[^\w-]/g, '_')}`;

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

interface DataSourceRowProps {
  dataSource: ProjectDataSource;
  canWrite: boolean;
  selected: boolean;
  onSelect: () => void;
  /** The package's date when it's newer than the data source's module, otherwise null. */
  updatedDate: string | null;
  syncBlockedReason: string | null;
  onSync: () => void;
  removeBlockedReason: string | null;
  aiMenuId: string;
  onOpenAiMenu: (event: React.MouseEvent) => void;
  onRemove: () => void;
}

export function DataSourceRow({
  dataSource, canWrite, selected, onSelect, updatedDate, syncBlockedReason, onSync, removeBlockedReason, aiMenuId, onOpenAiMenu, onRemove,
}: DataSourceRowProps) {
  const { t } = useTranslation();
  const activity = useDataSourceActivityStore((s) => s.byId[dataSource.data_source_id]);
  const count = activity?.count ?? 0;
  const running = !!activity?.running.length;
  const failed = activity?.lastResult === 'error';

  const syncTooltip = () => {
    if (updatedDate) return t('dataSources.updateTooltip', { date: formatDate(updatedDate) });
    return t(dataSource.package_updated_date ? 'dataSources.resyncNoUpdate' : 'dataSources.resyncUnknown');
  };

  return (
    // Clicking anywhere on the card selects it; the button inside is what the keyboard reaches.
    <li
      data-testid="data-source-row"
      onClick={onSelect}
      className={cn(
        'relative shrink-0 cursor-pointer overflow-hidden rounded-lg border transition-colors',
        selected ? 'border-primary/60 bg-primary/5' : 'border-border bg-surface hover:border-primary/40',
      )}
    >
      {/* Re-keyed on each call, so even one too quick to show as running is noticed. */}
      {count > 0 && <div key={count} aria-hidden className="data-source-flash pointer-events-none absolute inset-0" />}
      <div className="relative flex items-center gap-2 px-2.5 py-2">
        <button
          aria-pressed={selected}
          title={t('dataSources.showCalls')}
          className="flex flex-1 min-w-0 items-center gap-2.5 text-start"
        >
          <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <FlowLogo size={15} />
            <span className="absolute -bottom-0.5 -end-0.5 flex h-3 w-3 items-center justify-center rounded-full bg-surface">
              {running ? (
                <Loader2 size={11} className="animate-spin text-primary" />
              ) : (
                <span
                  className={cn(
                    'h-2 w-2 rounded-full',
                    failed ? 'bg-destructive' : activity?.lastResult ? 'bg-success' : 'bg-muted-foreground/40',
                  )}
                />
              )}
            </span>
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="flex items-center gap-1">
              <span className="truncate text-[13px] font-medium text-foreground" dir="auto" title={dataSource.module_path}>
                {dataSource.name}
              </span>
              <span className="shrink-0 text-[11px] text-muted-foreground" dir="ltr">
                ({dataSource.data_source_id})
              </span>
            </span>
            <span className={cn('truncate text-[11px]', failed && !running ? 'text-destructive' : 'text-muted-foreground')}>
              {count === 0 ? t('dataSources.notRun') : (
                <>
                  {running && `${t('dataSources.running')} · `}
                  {t('dataSources.ran', { count })}
                  {failed && !running && ` · ${t('dataSources.result.error')}`}
                </>
              )}
            </span>
          </span>
        </button>
        {canWrite && (
          <span title={syncBlockedReason ?? syncTooltip()} className="inline-flex shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={onSync}
              disabled={syncBlockedReason !== null}
              className={cn(
                'relative h-6 gap-1 px-2 text-[12px]',
                updatedDate ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <RefreshCw size={12} />
              {t('dataSources.sync')}
              {updatedDate && (
                <span
                  data-testid="data-source-update-dot"
                  aria-hidden
                  className="absolute -top-0.5 -end-0.5 h-2 w-2 rounded-full bg-primary ring-2 ring-surface"
                />
              )}
            </Button>
          </span>
        )}
        {canWrite && (
          <Button
            variant="ghost"
            size="sm"
            popoverTarget={aiMenuId}
            onClick={onOpenAiMenu}
            title={t('dataSources.adjustTooltip')}
            style={{ anchorName: aiMenuAnchorName(dataSource.data_source_id) } as CSSProperties}
            className="h-6 shrink-0 gap-1 px-2 text-[12px] text-muted-foreground hover:text-foreground"
          >
            <WandSparkles size={12} />
            {t('dataSources.adjust')}
          </Button>
        )}
        {/* A disabled button shows no tooltip, so the reason goes on the wrapper. */}
        <span title={removeBlockedReason ?? t('dataSources.remove')} className="inline-flex shrink-0">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRemove}
            disabled={removeBlockedReason !== null}
            aria-label={t('dataSources.remove')}
            className="h-6 w-6 text-muted-foreground hover:text-destructive"
          >
            <Trash2 size={13} />
          </Button>
        </span>
      </div>
    </li>
  );
}
