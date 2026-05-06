import { useState, useRef, useEffect, useCallback } from 'react';
import { credentialsStore } from '../../auth';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { useConsoleStore } from '../../stores/console';
import { RefreshCw, ExternalLink, Globe, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { publishToS3 } from '../../services/api';
import { PublishModal } from '../ui/PublishModal';

export function Preview() {
  const { t } = useTranslation();
  const projectId = useSessionStore((s) => s.projectId);
  const currentProject = useSessionStore((s) => s.currentProject);
  const saveVersion = useFilesStore((s) => s.saveVersion);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishModalState, setPublishModalState] = useState<{ open: boolean; url?: string; error?: string }>({ open: false });

  const isPublished = !!currentProject?.published_url;

  useEffect(() => {
    if (!projectId) {
      setPreviewUrl(null);
      return;
    }
    setLoading(true);
    const token = useSessionStore.getState().projectId ? credentialsStore.getValidToken() : null;
    const url = `/api/preview/${projectId}/proxy/${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    setPreviewUrl(url);
    setLoading(false);
    console.debug('[Preview] refresh — reason: project changed', { projectId, refreshKey });
  }, [projectId, refreshKey]);

  // Auto-refresh preview when files are saved (by user or AI).
  // Debounce to avoid rapid refreshes during bulk writes.
  const saveVersionRef = useRef(saveVersion);
  useEffect(() => {
    if (saveVersion === saveVersionRef.current) return;
    saveVersionRef.current = saveVersion;
    const timer = setTimeout(() => {
      console.debug('[Preview] refresh — reason: files saved', { saveVersion });
      clearConsole();
      setRefreshKey((k) => k + 1);
    }, 2000);
    return () => clearTimeout(timer);
  }, [saveVersion]);

  const clearConsole = useConsoleStore((s) => s.clear);
  const handleRefresh = () => {
    console.debug('[Preview] refresh — reason: manual');
    clearConsole();
    setRefreshKey((k) => k + 1);
  };

  const handlePublish = useCallback(async () => {
    if (!projectId || isPublishing) return;
    setIsPublishing(true);
    try {
      const result = await publishToS3(projectId);
      const current = useSessionStore.getState().currentProject;
      if (current) {
        useSessionStore.getState().setProjectPublishedUrl(current.id, result.url);
      }
      setPublishModalState({ open: true, url: result.url });
    } catch (err) {
      setPublishModalState({ open: true, error: err instanceof Error ? err.message : String(err) });
    } finally {
      setIsPublishing(false);
    }
  }, [projectId, isPublishing]);

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
          <RefreshCw size={14} />
          {t('preview.refresh')}
        </Button>
        {previewUrl && (
          <Button variant="outline" size="sm" onClick={() => window.open(previewUrl, '_blank')} title={t('preview.openInNewTab')}>
            <ExternalLink size={14} />
            {t('preview.open')}
          </Button>
        )}
        <span className="text-xs text-muted-foreground truncate flex-1">
          {previewUrl ?? t('preview.loading')}
        </span>

        {/* Publish Actions */}
        <div className="flex items-center gap-1.5">
          {isPublished && projectId ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(`/api/export/${projectId}/published`, '_blank')}
              title={t('preview.viewPublishedApp')}
            >
              <ExternalLink size={14} />
              {t('preview.viewLive')}
            </Button>
          ) : null}
          <Button
            variant="default"
            size="sm"
            disabled={!projectId || isPublishing}
            onClick={handlePublish}
            title={isPublished ? t('preview.republish') : t('preview.publish')}
          >
            {isPublishing ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Globe size={14} />
            )}
            {isPublished ? t('preview.republish') : t('preview.publish')}
          </Button>
        </div>
      </div>

      {/* iframe */}
      {previewUrl ? (
        <iframe
          ref={iframeRef}
          key={refreshKey}
          src={previewUrl}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          className="flex-1 w-full border-none"
          style={{ background: 'var(--preview-bg)' }}
          title={t('preview.title')}
          data-testid="preview-iframe"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          {loading ? t('preview.loading') : t('preview.noPreviewAvailable')}
        </div>
      )}

      <PublishModal
        open={publishModalState.open}
        onOpenChange={(open) => setPublishModalState(s => ({ ...s, open }))}
        url={publishModalState.url}
        errorMessage={publishModalState.error}
      />
    </div>
  );
}
