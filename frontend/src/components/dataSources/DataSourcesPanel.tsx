import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { CirclePlus, Loader2 } from 'lucide-react';
import * as api from '../../services/api';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { useVersionStore } from '../../stores/version';
import { LOCK_MESSAGES, useWorkspaceLock } from '../../stores/workspaceLock';
import type { ProjectDataSource } from '../../types';
import { aiMenuAnchorName } from '../../utils/dataSourceMenu';
import { Button } from '../ui/button';
import { DataSourceRow } from './DataSourceRow';
import { RemoveDataSourceDialog } from './RemoveDataSourceDialog';

const UPDATES_STALE_MS = 5 * 60 * 1000;
const AI_MENU_ID = 'data-source-ai-menu';
const AI_ISSUES = ['notRunning', 'runningTooMuch', 'wrongParams'] as const;

interface Listing {
  projectId: string;
  /** Null when loading failed. */
  items: ProjectDataSource[] | null;
}

/** The project's list, loaded again whenever something may have changed which data source files exist. */
function useProjectDataSources(projectId: string | null) {
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const versionCount = useVersionStore((s) => s.versions.length);
  const previewingVersion = useVersionStore((s) => s.previewingVersion);
  const [listing, setListing] = useState<Listing | null>(null);
  const [reloads, setReloads] = useState(0);
  const reload = useCallback(() => setReloads((n) => n + 1), []);

  useEffect(() => {
    if (!projectId) return;
    let stale = false;
    api.fetchProjectDataSources(projectId).then(
      (items) => { if (!stale) setListing({ projectId, items }); },
      () => { if (!stale) setListing({ projectId, items: null }); },
    );
    return () => { stale = true; };
  }, [projectId, reloads, isStreaming, agentPhase, versionCount, previewingVersion]);

  // Never show the previous project's list while the new one loads.
  return { listing: listing?.projectId === projectId ? listing : null, reload };
}

/** When each outdated data source's package last changed, by id. Checked only while the panel is open. */
function useDataSourceUpdates(projectId: string | null, items: ProjectDataSource[] | null | undefined) {
  // Part of the key, so a sync or a restored version checks again; otherwise a result is reused for a while.
  const knownDates = (items ?? [])
    .filter((item) => item.package_updated_date)
    .map((item) => `${item.data_source_id}@${item.package_updated_date}`);
  const query = useQuery({
    queryKey: ['data-source-updates', projectId, knownDates],
    queryFn: () => api.fetchDataSourceUpdates(projectId!),
    enabled: !!projectId && knownDates.length > 0,
    staleTime: UPDATES_STALE_MS,
  });
  return new Map((query.data ?? []).map((update) => [update.data_source_id, update.updated_date]));
}

export function DataSourcesPanel() {
  const { t } = useTranslation();
  const projectId = useSessionStore((s) => s.projectId);
  const buildCompleted = useChatStore((s) => s.buildCompleted);
  const appendToDraft = useChatStore((s) => s.appendToDraft);
  const { lock, canWrite } = useWorkspaceLock();
  const { listing, reload } = useProjectDataSources(projectId);
  const updates = useDataSourceUpdates(projectId, listing?.items);
  const addDataSource = useChatStore((s) => s.addDataSource);
  const [removing, setRemoving] = useState<ProjectDataSource | null>(null);
  const [menuTarget, setMenuTarget] = useState<ProjectDataSource | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const removeBlockedReason = () => {
    if (!canWrite) return t('dataSources.disabled.readOnly');
    if (lock) return t(LOCK_MESSAGES[lock]);
    return buildCompleted ? null : t('dataSources.disabled.notBuilt');
  };

  const syncBlockedReason = buildCompleted ? null : t('dataSources.disabled.notBuilt');

  const sync = (dataSource: ProjectDataSource) => {
    appendToDraft(t('dataSources.prompts.sync', {
      name: dataSource.name,
      path: dataSource.module_path,
      interpolation: { escapeValue: false },
    }));
    // Attaching it is what makes the next run fetch the package again and regenerate its module.
    addDataSource({ id: Number(dataSource.data_source_id), name: dataSource.name });
  };

  const openAiMenu = (dataSource: ProjectDataSource) => (event: React.MouseEvent) => {
    // Clicking another row's button while the menu is open moves it instead of closing it.
    if (menuTarget !== dataSource && menuRef.current?.matches(':popover-open')) event.preventDefault();
    setMenuTarget(dataSource);
  };

  const askAi = (issue: (typeof AI_ISSUES)[number]) => {
    if (!menuTarget) return;
    menuRef.current?.hidePopover();
    appendToDraft(t(`dataSources.prompts.${issue}`, {
      name: menuTarget.name,
      path: menuTarget.module_path,
      interpolation: { escapeValue: false },
    }));
  };

  const body = () => {
    if (!listing) {
      return (
        <div className="flex h-full items-center justify-center">
          <Loader2 size={16} className="animate-spin text-muted-foreground" aria-label={t('common.loading')} />
        </div>
      );
    }
    if (!listing.items) {
      return (
        <div className="flex h-full items-center justify-center gap-2 text-[12px] text-muted-foreground">
          {t('dataSources.loadFailed')}
          <Button variant="outline" size="sm" onClick={reload}>{t('common.retry')}</Button>
        </div>
      );
    }
    if (listing.items.length === 0) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-1 px-3 text-center text-[12px] text-muted-foreground">
          <p className="font-medium text-foreground">{t('dataSources.empty')}</p>
          {canWrite && (
            <p data-testid="data-sources-add-hint">
              {/* The icon is the one on the chat input's button. */}
              <Trans
                i18nKey="dataSources.addHint"
                components={{ plus: <CirclePlus size={13} className="inline align-text-bottom text-primary" aria-label="+" /> }}
              />
            </p>
          )}
        </div>
      );
    }
    return (
      <ul className="flex flex-col gap-1.5 p-2">
        {listing.items.map((dataSource) => (
          <DataSourceRow
            key={dataSource.data_source_id}
            dataSource={dataSource}
            canWrite={canWrite}
            updatedDate={updates.get(dataSource.data_source_id) ?? null}
            syncBlockedReason={syncBlockedReason}
            onSync={() => sync(dataSource)}
            removeBlockedReason={removeBlockedReason()}
            aiMenuId={AI_MENU_ID}
            onOpenAiMenu={openAiMenu(dataSource)}
            onRemove={() => setRemoving(dataSource)}
          />
        ))}
      </ul>
    );
  };

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex-1 overflow-auto">{body()}</div>

      {/* A native popover, so the short drawer doesn't clip it. */}
      <div
        ref={menuRef}
        id={AI_MENU_ID}
        popover="auto"
        style={menuTarget
          ? ({ positionAnchor: aiMenuAnchorName(menuTarget.data_source_id) } as CSSProperties)
          : undefined}
        className="anchored-menu min-w-60 rounded-lg border border-border bg-popover py-1 shadow-[var(--shadow-lg)]"
      >
        {AI_ISSUES.map((issue) => (
          <button
            key={issue}
            onClick={() => askAi(issue)}
            className="block w-full px-3 py-1.5 text-start text-[13px] text-foreground transition-colors hover:bg-muted/50"
          >
            {t(`dataSources.issues.${issue}`)}
          </button>
        ))}
      </div>

      {removing && projectId && (
        <RemoveDataSourceDialog
          projectId={projectId}
          dataSource={removing}
          onClose={() => setRemoving(null)}
          onRemoved={() => { setRemoving(null); reload(); }}
        />
      )}
    </div>
  );
}
