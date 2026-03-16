import { useState, useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/session';
import { fetchPreviewPort } from '../../services/api';
import { RefreshCw, ExternalLink } from 'lucide-react';

export function Preview() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setPreviewUrl(null);
      return;
    }
    setError(null);
    fetchPreviewPort(sessionId)
      .then((port) => {
        // In dev, connect directly to the sandbox dev server port
        setPreviewUrl(`http://localhost:${port}/`);
      })
      .catch(() => {
        setError('Could not load preview port');
      });
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
      {error ? (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-dim)',
          fontSize: '14px',
        }}>
          {error}
        </div>
      ) : previewUrl ? (
        <iframe
          ref={iframeRef}
          key={refreshKey}
          src={previewUrl}
          style={{
            flex: 1,
            width: '100%',
            border: 'none',
            background: '#ffffff',
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
          Loading preview...
        </div>
      )}
    </div>
  );
}
