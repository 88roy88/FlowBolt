import { useState, useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { useConsoleStore } from '../../stores/console';
import { RefreshCw, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';

export function Preview() {
  const projectId = useSessionStore((s) => s.projectId);
  const saveVersion = useFilesStore((s) => s.saveVersion);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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

  if (!projectId) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        No preview available
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-surface border-b border-border shrink-0">
        <Button variant="outline" size="sm" onClick={handleRefresh} title="Refresh preview">
          <RefreshCw size={14} />
          Refresh
        </Button>
        {previewUrl && (
          <Button variant="outline" size="sm" onClick={() => window.open(previewUrl, '_blank')} title="Open in new tab">
            <ExternalLink size={14} />
            Open
          </Button>
        )}
        <span className="text-xs text-muted-foreground truncate">
          {previewUrl ?? 'Loading...'}
        </span>
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
          title="App Preview"
          data-testid="preview-iframe"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          {loading ? 'Loading preview...' : 'No preview available'}
        </div>
      )}
    </div>
  );
}
