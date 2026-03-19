import { AlertTriangle, X, Wrench, RefreshCw } from 'lucide-react';
import { useErrorStore, type AppError } from '../../stores/errors';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';

export { useErrorCapture } from '../../hooks/useErrorCapture';

function normalizeFilePath(filePath: string): string {
  const srcIdx = filePath.indexOf('/src/');
  if (srcIdx !== -1) {
    return filePath.slice(srcIdx);
  }
  if (!filePath.startsWith('/src/')) {
    if (!filePath.startsWith('/')) filePath = '/' + filePath;
    return '/src' + filePath;
  }
  return filePath;
}

function SingleErrorToast({ error }: { error: AppError }) {
  const dismissError = useErrorStore((s) => s.dismissError);
  const sendFixError = useChatStore((s) => s.sendFixError);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const openFile = useFilesStore((s) => s.openFile);
  const loadProjects = useSessionStore((s) => s.loadProjects);

  const handleFix = () => {
    sendFixError(error.message, error.file, error.line, error.stack);
    dismissError(error.id);
  };

  const handleRetry = async () => {
    dismissError(error.id);
    try {
      await loadProjects();
    } catch (err) {
      console.error('Retry failed:', err);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: '10px',
      padding: '12px 14px',
      background: 'var(--surface)',
      border: '1px solid #f38ba8',
      borderRadius: '8px',
      maxWidth: '420px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    }}>
      <AlertTriangle size={18} style={{ color: '#f38ba8', flexShrink: 0, marginTop: '2px' }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: '11px',
          fontWeight: 600,
          color: '#f38ba8',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          marginBottom: '4px',
        }}>
          {error.source === 'build' ? 'Build Error' : error.source === 'runtime' ? 'Runtime Error' : 'Connection Error'}
        </div>
        <div style={{
          fontSize: '13px',
          color: 'var(--text)',
          lineHeight: '1.4',
          wordBreak: 'break-word',
        }}>
          {error.message.length > 150
            ? error.message.slice(0, 150) + '...'
            : error.message}
        </div>
        {error.file && (
          <button
            onClick={() => openFile(normalizeFilePath(error.file!), error.line, error.column)}
            style={{
              display: 'block',
              fontSize: '11px',
              color: 'var(--accent)',
              marginTop: '6px',
              textDecoration: 'underline',
              cursor: 'pointer',
              textAlign: 'left',
            }}
            title="Open in editor"
          >
            {error.file}{error.line ? `:${error.line}` : ''}
          </button>
        )}
        {error.source === 'connection' ? (
          <button
            onClick={handleRetry}
            style={{
              display: 'flex',
              alignItems: 'center',
              marginLeft: 'auto',
              gap: '4px',
              marginTop: '10px',
              padding: '4px 10px',
              fontSize: '12px',
              fontWeight: 600,
              color: 'var(--accent)',
              border: '1px solid var(--accent)',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={12} />
            Retry
          </button>
        ) : (
          <button
            onClick={handleFix}
            disabled={isStreaming}
            style={{
              display: 'flex',
              alignItems: 'center',
              marginLeft: 'auto',
              gap: '4px',
              marginTop: '10px',
              padding: '4px 10px',
              fontSize: '12px',
              fontWeight: 600,
              color: isStreaming ? 'var(--text-dim)' : 'var(--accent)',
              border: `1px solid ${isStreaming ? 'var(--border)' : 'var(--accent)'}`,
              borderRadius: '4px',
              cursor: isStreaming ? 'not-allowed' : 'pointer',
              opacity: isStreaming ? 0.5 : 1,
            }}
          >
            <Wrench size={12} />
            Fix with AI
          </button>
        )}
      </div>
      <button
        onClick={() => dismissError(error.id)}
        style={{
          padding: '2px',
          color: 'var(--text-dim)',
          flexShrink: 0,
        }}
        title="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}

export function ErrorToast() {
  const errors = useErrorStore((s) => s.errors);

  if (errors.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: '16px',
      right: '16px',
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {errors.map((error) => (
        <SingleErrorToast key={error.id} error={error} />
      ))}
    </div>
  );
}
