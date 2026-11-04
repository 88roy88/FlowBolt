import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { useConsoleStore } from '../../stores/console';
import { usePublishStore } from '../../stores/publish';
import { PUBLISH_ROLES } from '../../types';
import { RefreshCw, ExternalLink, Globe } from 'lucide-react';
import { Button } from '../ui/button';
import { AppTitle } from './AppTitle';
import { credentialsStore } from '../../auth';
import { useDebouncedCallback } from '../../hooks/useDebounce';
import { TOOLBAR_SOURCE } from '../../hooks/usePreviewToolbarBridge';
import { logger } from '../../services/logger';
import { formatPreviewRoute } from '../../utils/previewRoute';

type PreviewLoadTrigger = 'manual_refresh' | 'auto_on_code_change';

export function Preview() {
  const { t } = useTranslation();
  const projectId = useSessionStore((s) => s.projectId);
  const currentProject = useSessionStore((s) => s.currentProject);
  const saveVersion = useFilesStore((s) => s.saveVersion);
  
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [route, setRoute] = useState('/');
  const [appTitle, setAppTitle] = useState<string | null>(null);

  const routeLabel = formatPreviewRoute(route);
  const isHome = routeLabel === '/';

  const isPublished = !!currentProject?.published_url;
  const liveUrl = currentProject?.published_url
    ? `/shared/${currentProject.published_url}`
    : null;

  useEffect(() => {
    if (!projectId) {
      setPreviewUrl(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setRoute('/');
    setAppTitle(null);
    credentialsStore.ensureCookie();
    setPreviewUrl(`/api/preview/${projectId}/proxy/`);
  }, [projectId]);

  // Only the iframe's page counts: tabs opened from the preview report theirs here too.
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      const data = event.data;
      if (event.origin !== window.location.origin) return;
      if (event.source !== iframeRef.current?.contentWindow) return;
      if (data?.source !== TOOLBAR_SOURCE) return;
      if (data.type === 'route-changed' && typeof data.route === 'string') setRoute(data.route);
      if (data.type === 'title-changed' && typeof data.title === 'string') setAppTitle(data.title);
    }

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  const clearConsole = useConsoleStore((s) => s.clear);

  const pendingLoadRef = useRef<{ trigger: PreviewLoadTrigger; startedAt: number } | null>(null);

  const reloadPreview = useCallback((trigger: PreviewLoadTrigger) => {
    const frame = iframeRef.current?.contentWindow;
    if (!frame) return;
    console.debug(`[Preview] refresh — trigger: ${trigger}`);
    clearConsole();
    setLoading(true);
    pendingLoadRef.current = { trigger, startedAt: performance.now() };
    frame.location.reload();
  }, [clearConsole]);

  const saveVersionRef = useRef(saveVersion);
  const debouncedRefresh = useDebouncedCallback(() => {
    reloadPreview('auto_on_code_change');
  }, 2000, { maxWait: 8000 });
  useEffect(() => {
    if (saveVersion === saveVersionRef.current) return;
    saveVersionRef.current = saveVersion;
    debouncedRefresh();
  }, [saveVersion, debouncedRefresh]);

  const handleRefresh = () => reloadPreview('manual_refresh');

  const handleFrameLoad = () => {
    setLoading(false);
    const pending = pendingLoadRef.current;
    if (!pending) return;
    pendingLoadRef.current = null;
    logger.info('preview_loaded', {
      load_time_ms: Math.round(performance.now() - pending.startedAt),
      trigger: pending.trigger,
    });
  };

  const handlePublish = useCallback(() => {
    if (projectId) {
      usePublishStore.getState().open(projectId, currentProject?.published_url);
    }
  }, [projectId, currentProject]);

  if (!projectId) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        {t('preview.noPreviewAvailable')}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="grid grid-cols-[1fr_minmax(0,24rem)_1fr] items-center gap-2 px-3 py-1.5 bg-surface border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="rounded-full" onClick={handleRefresh} title={t('preview.refreshPreview')}>
            <RefreshCw size={14} className={`text-primary/70 ${loading ? 'animate-spin' : ''}`} />
            {t('preview.refresh')}
          </Button>
          {previewUrl && (
            <Button
              variant="outline"
              size="sm"
              className="rounded-full"
              onClick={() => { credentialsStore.ensureCookie(); window.open(`${previewUrl}${route.slice(1)}`, '_blank'); }}
              title={t('preview.openInNewTab')}
            >
              <ExternalLink size={14} className="text-primary/70" />
              {t('preview.open')}
            </Button>
          )}
        </div>

        {/* Route bar */}
        <div className="flex items-center justify-center gap-2 min-w-0 h-7 px-3 rounded-full bg-muted/70 border border-border/60 text-xs">
          <AppTitle title={appTitle} onChange={setAppTitle} />
          {!isHome && (
            <span dir="ltr" className="min-w-0 truncate text-muted-foreground" title={routeLabel} data-testid="preview-path">
              {routeLabel}
            </span>
          )}
        </div>

        {/* Publish Actions */}
        <div className="flex items-center justify-end gap-1.5">
          {isPublished && liveUrl ? (
            <Button
              variant="outline"
              size="sm"
              className="rounded-full"
              onClick={() => window.open(liveUrl, '_blank')}
              title={t('preview.viewPublishedApp')}
            >
              <ExternalLink size={14} className="text-primary/70" />
              {t('preview.viewLive')}
            </Button>
          ) : null}
          {(!currentProject?.role || PUBLISH_ROLES.has(currentProject.role)) && (
            <Button
              variant="default"
              size="sm"
              className="rounded-full"
              disabled={!projectId}
              onClick={handlePublish}
              title={isPublished ? t('preview.republish') : t('preview.publish')}
            >
              <Globe size={14} />
              {isPublished ? t('preview.republish') : t('preview.publish')}
            </Button>
          )}
        </div>
      </div>

      {/* iframe */}
      {previewUrl ? (
        <div className="relative flex-1">
          <iframe
            ref={iframeRef}
            src={previewUrl}
            onLoad={handleFrameLoad}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"
            className="absolute inset-0 w-full h-full border-none"
            style={{ background: 'var(--preview-bg)' }}
            title={t('preview.title')}
            data-testid="preview-iframe"
          />
          <div
            className={`pointer-events-none absolute inset-0 flex items-center justify-center gap-2 text-muted-foreground text-sm bg-[var(--preview-bg)]/85 transition-opacity duration-200 ${loading ? 'opacity-100' : 'opacity-0'}`}
          >
            <RefreshCw size={16} className="animate-spin text-primary/70" />
            {t('preview.loading')}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          {t('preview.noPreviewAvailable')}
        </div>
      )}
    </div>
  );
}
