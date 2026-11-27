import { useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, Loader2, RefreshCw, Trash2, WandSparkles } from 'lucide-react';
import { useDataSourceActivityStore, type DataSourceCall } from '../../stores/dataSourceActivity';
import type { ProjectDataSource } from '../../types';
import { paramLines } from '../../utils/dataSourceParams';
import { aiMenuAnchorName } from '../../utils/dataSourceMenu';
import { cn } from '@/lib/utils';
import { Button } from '../ui/button';
import { FlowLogo } from '../ui/flow-logo';

const RESULT_TEXT: Record<DataSourceCall['result'], string> = {
  running: 'text-primary',
  ok: 'text-success',
  error: 'text-destructive',
  aborted: 'text-muted-foreground',
};

function RecentCalls({ calls }: { calls: DataSourceCall[] }) {
  const { t } = useTranslation();
  if (calls.length === 0) {
    return <div className="border-t border-border px-3 py-2 text-[11px] text-muted-foreground">{t('dataSources.noCalls')}</div>;
  }
  return (
    <ul className="space-y-1.5 border-t border-border px-3 py-2">
      {calls.map((call) => {
        const lines = paramLines(call.params);
        return (
          <li key={call.id} className="text-[11px]">
            <div className="flex gap-2">
              <span className="text-muted-foreground">
                {new Date(call.startedAt).toLocaleTimeString([], { hour12: false })}
              </span>
              <span className={RESULT_TEXT[call.result]}>{t(`dataSources.result.${call.result}`)}</span>
            </div>
            {lines.length === 0 ? (
              <div className="text-muted-foreground">{t('dataSources.noParams')}</div>
            ) : (
              <div dir="ltr" className="font-mono text-start break-all">
                {lines.map((line, i) => <div key={i}>{line}</div>)}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

interface DataSourceRowProps {
  dataSource: ProjectDataSource;
  canWrite: boolean;
  /** The package's date when it's newer than the data source's module, otherwise null. */
  updatedDate: string | null;
  /** Why syncing is unavailable right now, or null when it is available. */
  syncBlockedReason: string | null;
  onSync: () => void;
  /** Why removing is unavailable right now, or null when it is available. */
  removeBlockedReason: string | null;
  aiMenuId: string;
  onOpenAiMenu: (event: React.MouseEvent) => void;
  onRemove: () => void;
}

export function DataSourceRow({
  dataSource, canWrite, updatedDate, syncBlockedReason, onSync, removeBlockedReason, aiMenuId, onOpenAiMenu, onRemove,
}: DataSourceRowProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const activity = useDataSourceActivityStore((s) => s.byId[dataSource.data_source_id]);
  const count = activity?.count ?? 0;
  const running = !!activity?.running.length;
  const failed = activity?.lastResult === 'error';

  const syncTooltip = () => {
    if (updatedDate) return t('dataSources.updateTooltip', { date: formatDate(updatedDate) });
    return t(dataSource.package_updated_date ? 'dataSources.resyncNoUpdate' : 'dataSources.resyncUnknown');
  };

  return (
    <li
      data-testid="data-source-row"
      className="relative shrink-0 overflow-hidden rounded-lg border border-border bg-surface transition-colors hover:border-primary/40"
    >
      {/* Re-keyed on each call, so even one too quick to show as running is noticed. */}
      {count > 0 && <div key={count} aria-hidden className="data-source-flash pointer-events-none absolute inset-0" />}
      <div className="relative flex items-center gap-2 px-2.5 py-2">
        <button
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          title={t('dataSources.showCalls')}
          className="flex flex-1 min-w-0 items-center gap-2.5 text-start"
        >
          <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <FlowLogo size={15} />
            {/* The status sits on the corner of the icon. */}
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
              {/* Outside the truncated name, so a long one never hides the ID. */}
              <span className="shrink-0 text-[11px] text-muted-foreground" dir="ltr">
                ({dataSource.data_source_id})
              </span>
              <ChevronRight
                size={12}
                className={cn('shrink-0 text-muted-foreground transition-transform', expanded ? 'rotate-90' : 'rtl:rotate-180')}
              />
            </span>
            <span className={cn('truncate text-[11px]', failed && !running ? 'text-destructive' : 'text-muted-foreground')}>
              {updatedDate && <span className="text-primary">{`${t('dataSources.packageUpdated')} · `}</span>}
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
                // A notification dot.
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
      {expanded && <RecentCalls calls={activity?.recent ?? []} />}
    </li>
  );
}
