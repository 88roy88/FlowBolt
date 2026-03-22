import { useEffect } from 'react';
import { useErrorStore } from '../stores/errors';
import { useConsoleStore } from '../stores/console';
import { useSessionStore } from '../stores/session';
import { createErrorSocket } from '../services/websocket';

export function useErrorCapture() {
  const projectId = useSessionStore((s) => s.projectId);
  const pushError = useErrorStore((s) => s.pushError);
  const clearErrors = useErrorStore((s) => s.clearErrors);

  // Build errors via WebSocket
  useEffect(() => {
    if (!projectId) return;
    clearErrors();

    const socket = createErrorSocket(projectId, (data: unknown) => {
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
  }, [projectId, pushError, clearErrors]);

  // Runtime errors + console logs from preview iframe via postMessage
  const pushConsole = useConsoleStore((s) => s.push);
  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (!event.data) return;
      if (event.data.type === 'runtime-error') {
        const d = event.data;
        pushError({
          source: 'runtime',
          message: d.message ?? 'Unknown runtime error',
          file: d.file || undefined,
          line: d.line || undefined,
          column: d.column || undefined,
          stack: d.stack || undefined,
        });
      } else if (event.data.type === 'console') {
        pushConsole(event.data.level, event.data.args ?? [], event.data.file, event.data.line, event.data.column);
      }
    }

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [pushError, pushConsole]);
}
