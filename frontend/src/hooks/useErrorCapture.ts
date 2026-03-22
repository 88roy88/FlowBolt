import { useEffect } from 'react';
import { useErrorStore } from '../stores/errors';
import { useSessionStore } from '../stores/session';
import { createErrorSocket } from '../services/websocket';

export function useErrorCapture() {
  const sessionId = useSessionStore((s) => s.sessionId);
  const pushError = useErrorStore((s) => s.pushError);
  const clearErrors = useErrorStore((s) => s.clearErrors);

  // Build errors via WebSocket
  useEffect(() => {
    if (!sessionId) return;
    clearErrors();

    const socket = createErrorSocket(sessionId, (data: unknown) => {
      const d = data as { message?: string; file?: string; line?: number; column?: number; stack?: string };
      pushError({
        source: 'build',
        message: d.message ?? '',
        file: d.file,
        line: d.line,
        column: d.column,
        stack: d.stack,
      });
    });

    return () => {
      socket.close();
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
