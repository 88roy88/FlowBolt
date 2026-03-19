import { useState, useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/session';
import { RefreshCw, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button';

export function Preview() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setPreviewUrl(null);
      return;
    }
    setLoading(true);
    const url = `/api/preview/${sessionId}/proxy/`;
    setPreviewUrl(url);
    setLoading(false);
  }, [sessionId, refreshKey]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  if (!sessionId) {
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
          className="flex-1 w-full border-none"
          style={{ background: 'var(--preview-bg)' }}
          title="App Preview"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          {loading ? 'Loading preview...' : 'No preview available'}
        </div>
      )}
    </div>
  );
}
