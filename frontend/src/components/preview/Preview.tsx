import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { useConsoleStore } from '../../stores/console';
import { RefreshCw, ExternalLink, Globe, Download, ChevronDown, FileCode, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { downloadZip, downloadSingleHtml, publishToS3 } from '../../services/api';
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
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  const isPublished = !!currentProject?.published_url;

  useEffect(() => {
    if (!projectId) {
      setPreviewUrl(null);
      return;
    }
    setLoading(true);
    const url = `/api/preview/${projectId}/proxy/`;
    setPreviewUrl(url);
    setLoading(false);
  }, [projectId, refreshKey]);

  // Auto-refresh preview when files are saved (by user or AI).
  // Debounce to avoid rapid refreshes during bulk writes.
  const saveVersionRef = useRef(saveVersion);
  useEffect(() => {
    if (saveVersion === saveVersionRef.current) return;
    saveVersionRef.current = saveVersion;
    const timer = setTimeout(() => { clearConsole(); setRefreshKey((k) => k + 1); }, 800);
    return () => clearTimeout(timer);
  }, [saveVersion]);

  const clearConsole = useConsoleStore((s) => s.clear);
  const handleRefresh = () => {
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

  const handleExportZip = () => {
    if (projectId) {
      downloadZip(projectId);
      setExportMenuOpen(false);
    }
  };

  const handleExportHtml = () => {
    if (projectId) {
      downloadSingleHtml(projectId);
      setExportMenuOpen(false);
    }
  };

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false);
      }
    };
    if (exportMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [exportMenuOpen]);

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

        {/* Export/Publish Actions */}
        <div className="flex items-center gap-1.5">
          {/* Export Dropdown */}
          <div className="relative" ref={exportMenuRef}>
            <Button
              variant="outline"
              size="sm"
              disabled={!projectId}
              onClick={() => setExportMenuOpen(!exportMenuOpen)}
              title={t('editor.exportZip')}
            >
              <Download size={14} />
              <ChevronDown size={12} className={`transition-transform ${exportMenuOpen ? 'rotate-180' : ''}`} />
            </Button>
            {exportMenuOpen && (
              <div className="absolute right-0 top-full mt-1 z-50 min-w-[180px] rounded-md border border-border bg-popover shadow-lg">
                <div className="p-1">
                  <button
                    onClick={handleExportZip}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent transition-colors text-left"
                  >
                    <Download size={14} className="text-muted-foreground" />
                    <span>{t('editor.exportZip')}</span>
                  </button>
                  <button
                    onClick={handleExportHtml}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent transition-colors text-left"
                  >
                    <FileCode size={14} className="text-muted-foreground" />
                    <span>{t('editor.exportHtml')}</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Publish Button - Primary Action */}
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
