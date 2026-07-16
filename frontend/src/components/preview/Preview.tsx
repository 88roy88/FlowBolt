import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { useConsoleStore } from '../../stores/console';
import { usePublishStore } from '../../stores/publish';
import { PUBLISH_ROLES } from '../../types';
import { RefreshCw, ExternalLink, Globe } from 'lucide-react';
import { Button } from '../ui/button';
import { credentialsStore } from '../../auth';
import { useDebouncedCallback } from '../../hooks/useDebounce';

export function Preview() {
  const { t } = useTranslation();
  const projectId = useSessionStore((s) => s.projectId);
  const currentProject = useSessionStore((s) => s.currentProject);
  const saveVersion = useFilesStore((s) => s.saveVersion);
  
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
    credentialsStore.ensureCookie();
    setPreviewUrl(`/api/preview/${projectId}/proxy/`);
  }, [projectId]);

  const clearConsole = useConsoleStore((s) => s.clear);

  const reloadPreview = useCallback((reason: string) => {
    const frame = iframeRef.current?.contentWindow;
    if (!frame) return;
    console.debug(`[Preview] refresh — reason: ${reason}`);
    clearConsole();
    setLoading(true);
    frame.location.reload();
  }, [clearConsole]);

  const saveVersionRef = useRef(saveVersion);
  const debouncedRefresh = useDebouncedCallback(() => {
    reloadPreview('files saved');
  }, 2000, { maxWait: 8000 });
  useEffect(() => {
    if (saveVersion === saveVersionRef.current) return;
    saveVersionRef.current = saveVersion;
    debouncedRefresh();
  }, [saveVersion, debouncedRefresh]);

  const handleRefresh = () => reloadPreview('manual');

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
      <div className="flex items-center gap-2 px-3 py-1.5 bg-surface border-b border-border shrink-0">
        <Button variant="outline" size="sm" onClick={handleRefresh} title={t('preview.refreshPreview')}>
          <RefreshCw size={14} className="text-primary/70" />
          {t('preview.refresh')}
        </Button>
        {previewUrl && (
          <Button variant="outline" size="sm" onClick={() => { credentialsStore.ensureCookie(); window.open(previewUrl, '_blank'); }} title={t('preview.openInNewTab')}>
            <ExternalLink size={14} className="text-primary/70" />
            {t('preview.open')}
          </Button>
        )}
        <span className="text-xs text-muted-foreground truncate flex-1">
          {previewUrl ?? t('preview.loading')}
        </span>

        {/* Publish Actions */}
        <div className="flex items-center gap-1.5">
          {isPublished && liveUrl ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => { credentialsStore.ensureCookie(); window.open(liveUrl, '_blank'); }}
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
            onLoad={() => setLoading(false)}
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
