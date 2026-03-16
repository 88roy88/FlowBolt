import { useState, useRef } from 'react';
import { useSessionStore } from '../../stores/session';
import { RefreshCw } from 'lucide-react';

export function Preview() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [refreshKey, setRefreshKey] = useState(0);

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
        <span style={{
          fontSize: '12px',
          color: 'var(--text-dim)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          /preview/{sessionId}/
        </span>
      </div>

      {/* iframe */}
      <iframe
        ref={iframeRef}
        key={refreshKey}
        src={`/preview/${sessionId}/`}
        style={{
          flex: 1,
          width: '100%',
          border: 'none',
          background: '#ffffff',
        }}
        title="App Preview"
        sandbox="allow-scripts allow-forms allow-same-origin allow-popups"
      />
    </div>
  );
}
