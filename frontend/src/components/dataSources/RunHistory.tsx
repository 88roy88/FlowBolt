import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Copy, History, X } from 'lucide-react';
import { logger } from '../../services/logger';
import { useDataSourceActivityStore, type DataSourceCall } from '../../stores/dataSourceActivity';
import type { ParamLabel, ProjectDataSource } from '../../types';
import { describeParams, formatBody } from '../../utils/dataSourceParams';
import { cn } from '@/lib/utils';
import { Button } from '../ui/button';

const RESULT_TEXT: Record<DataSourceCall['result'], string> = {
  running: 'text-primary',
  ok: 'text-success',
  error: 'text-destructive',
  aborted: 'text-muted-foreground',
};

const FEEDBACK_MS = 2000;

function CopyButton({ dataSourceId, body, cut }: { dataSourceId: string; body: string; cut: boolean }) {
  const { t } = useTranslation();
  const [outcome, setOutcome] = useState<'copied' | 'copyFailed' | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = async () => {
    let next: 'copied' | 'copyFailed' = 'copied';
    try {
      // Throws on a page without HTTPS, where there is no clipboard.
      await navigator.clipboard.writeText(formatBody(body));
      // Never the params themselves.
      logger.info('data_source_params_copied', { data_source_id: dataSourceId });
    } catch {
      next = 'copyFailed';
    }
    setOutcome(next);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setOutcome(null), FEEDBACK_MS);
  };

  const label = t(`dataSources.${outcome ?? 'copy'}`);
  const Icon = outcome === 'copied' ? Check : outcome === 'copyFailed' ? X : Copy;

  return (
    // A disabled button shows no tooltip, so the reason goes on the wrapper.
    <span title={cut ? t('dataSources.copyCut') : label} className="inline-flex shrink-0">
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={copy}
        disabled={cut}
        aria-label={label}
        className={cn(
          'h-5 w-5 text-muted-foreground hover:text-foreground',
          outcome === 'copyFailed' && 'text-destructive',
        )}
      >
        <Icon size={12} />
      </Button>
      <span aria-live="polite" className="sr-only">{outcome && label}</span>
    </span>
  );
}

function Run({ dataSourceId, call, labels }: { dataSourceId: string; call: DataSourceCall; labels: ParamLabel[] }) {
  const { t } = useTranslation();
  const params = describeParams(call.params, labels);

  return (
    <li data-testid="data-source-run" className="border-b border-border/60 px-3 py-1.5 text-[11px]">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">
          {new Date(call.startedAt).toLocaleTimeString([], { hour12: false })}
        </span>
        <span className={RESULT_TEXT[call.result]}>{t(`dataSources.result.${call.result}`)}</span>
        <span className="ms-auto">
          {call.params && <CopyButton dataSourceId={dataSourceId} body={call.params} cut={call.paramsCut} />}
        </span>
      </div>
      {'raw' in params ? (
        <div dir="ltr" className="font-mono text-start break-all">{params.raw}</div>
      ) : params.entries.length === 0 ? (
        <div className="text-muted-foreground">{t('dataSources.noParams')}</div>
      ) : (
        <dl className="grid grid-cols-[minmax(0,max-content)_minmax(0,1fr)] gap-x-3">
          {params.entries.map((entry) => (
            <div key={entry.path} className="contents">
              <dt title={entry.path} className="max-w-40 break-words text-muted-foreground">
                <bdi>{entry.label}</bdi>
                {entry.ambiguous && <span dir="ltr" className="block text-[10px] opacity-70">{entry.path}</span>}
              </dt>
              <dd dir="ltr" className="font-mono text-start text-foreground break-all">{entry.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

export function RunHistory({ dataSource }: { dataSource: ProjectDataSource | null }) {
  const { t } = useTranslation();
  const calls = useDataSourceActivityStore((s) => (dataSource ? s.byId[dataSource.data_source_id]?.recent : undefined));

  if (!dataSource) {
    return (
      <section
        data-testid="data-source-history"
        className="flex h-full flex-col items-center justify-center gap-1.5 px-3 text-center text-[12px] text-muted-foreground"
      >
        <History size={18} className="opacity-60" />
        <p>{t('dataSources.selectForRuns')}</p>
      </section>
    );
  }

  return (
    <section data-testid="data-source-history" className="flex h-full flex-col">
      <h3 className="shrink-0 truncate border-b border-border px-3 py-1 text-[11px] text-muted-foreground">
        <span className="font-medium text-foreground">{t('dataSources.recentRuns')}</span>
        {' · '}
        <bdi>{dataSource.name}</bdi>
      </h3>
      {calls?.length ? (
        <ul className="min-h-0 flex-1 overflow-auto">
          {calls.map((call) => (
            <Run key={call.id} dataSourceId={dataSource.data_source_id} call={call} labels={dataSource.params} />
          ))}
        </ul>
      ) : (
        <p className="flex flex-1 items-center justify-center px-3 text-center text-[12px] text-muted-foreground">
          {t('dataSources.noCalls')}
        </p>
      )}
    </section>
  );
}
