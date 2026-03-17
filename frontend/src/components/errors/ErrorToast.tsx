import { useEffect, useRef } from 'react';
import { AlertTriangle, X, Wrench } from 'lucide-react';
import { useErrorStore, type AppError } from '../../stores/errors';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';

function getWsBase(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

/** Connect to the build-error WebSocket and listen for runtime errors from the preview iframe. */
export function useErrorCapture() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const pushError = useErrorStore((s) => s.pushError);
  const clearErrors = useErrorStore((s) => s.clearErrors);
  const wsRef = useRef<WebSocket | null>(null);

  // Build errors via WebSocket
  useEffect(() => {
    if (!sessionId) return;
    clearErrors();

    let closed = false;
    let retryDelay = 2000;

    function connect() {
      if (closed) return;
      const ws = new WebSocket(`${getWsBase()}/ws/errors/${sessionId}`);
      wsRef.current = ws;

      ws.addEventListener('message', (event) => {
        try {
          const data = JSON.parse(event.data as string);
          pushError({
            source: 'build',
            message: data.message ?? '',
            file: data.file,
            line: data.line,
            column: data.column,
            stack: data.stack,
          });
        } catch { /* ignore */ }
      });

      ws.addEventListener('close', () => {
        wsRef.current = null;
        if (!closed) {
          setTimeout(() => {
            retryDelay = Math.min(retryDelay * 2, 30000);
            connect();
          }, retryDelay);
        }
      });

      ws.addEventListener('open', () => {
        retryDelay = 2000;
      });

      ws.addEventListener('error', () => {
        ws.close();
      });
    }

    connect();

    return () => {
      closed = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId, pushError, clearErrors]);

  // Runtime errors from preview iframe via postMessage
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (!event.data || event.data.type !== 'runtime-error') return;
      const d = event.data;
      pushError({
        source: 'runtime',
        message: d.message ?? 'Unknown runtime error',
        file: d.file || undefined,
        line: d.line || undefined,
        column: d.column || undefined,
        stack: d.stack || undefined,
      });
    }

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [pushError]);
}

function SingleErrorToast({ error }: { error: AppError }) {
  const dismissError = useErrorStore((s) => s.dismissError);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const openFile = useFilesStore((s) => s.openFile);

  const handleFix = () => {
    const parts: string[] = [
      `Fix this ${error.source} error:`,
      '',
      `**Error:** ${error.message}`,
    ];
    if (error.file) {
      parts.push(`**File:** ${error.file}${error.line ? `:${error.line}` : ''}`);
    }
    if (error.stack) {
      parts.push('', '```', error.stack.slice(0, 500), '```');
    }
    sendMessage(parts.join('\n'));
    dismissError(error.id);
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
          {error.source === 'build' ? 'Build Error' : 'Runtime Error'}
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
            onClick={() => {
              // Normalize path to match editor's workspace-relative format
              let filePath = error.file!;
              // Strip absolute workspace prefix if present
              const srcIdx = filePath.indexOf('/src/');
              if (srcIdx !== -1) {
                filePath = filePath.slice(srcIdx);
              } else if (!filePath.startsWith('/src/')) {
                // Vite reports paths relative to project root (e.g. /components/Foo.tsx)
                // but the actual file lives under /src/
                if (!filePath.startsWith('/')) filePath = '/' + filePath;
                filePath = '/src' + filePath;
              }
              openFile(filePath, error.line, error.column);
            }}
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
