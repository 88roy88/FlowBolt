import { useState, useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/session';
import { RefreshCw, ExternalLink } from 'lucide-react';

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

    // Use the reverse proxy — it rewrites Vite's absolute paths so assets
    // like /@vite/client and /src/main.tsx route back through the proxy.
    const url = `/api/preview/${sessionId}/proxy/`;
    setPreviewUrl(url);
    setLoading(false);
  }, [sessionId, refreshKey]);

  const handleRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  if (!sessionId) {
    return (
      <div style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-dim)',
        fontSize: '14px',
      }}>
        No preview available
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 12px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <button
          onClick={handleRefresh}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 8px',
            borderRadius: '4px',
            fontSize: '12px',
            color: 'var(--text-dim)',
            border: '1px solid var(--border)',
          }}
          title="Refresh preview"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
        {previewUrl && (
          <button
            onClick={() => window.open(previewUrl, '_blank')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              color: 'var(--text-dim)',
              border: '1px solid var(--border)',
            }}
            title="Open in new tab"
          >
            <ExternalLink size={14} />
            Open
          </button>
        )}
        <span style={{
          fontSize: '12px',
          color: 'var(--text-dim)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {previewUrl ?? 'Loading...'}
        </span>
      </div>

      {/* iframe */}
      {previewUrl ? (
        <iframe
          ref={iframeRef}
          key={refreshKey}
          src={previewUrl}
          style={{
            flex: 1,
            width: '100%',
            border: 'none',
            background: 'var(--preview-bg)',
          }}
          title="App Preview"
        />
      ) : (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-dim)',
          fontSize: '14px',
        }}>
          {loading ? 'Loading preview...' : 'No preview available'}
        </div>
      )}
    </div>
  );
}
