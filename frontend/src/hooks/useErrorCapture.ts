import { useEffect } from 'react';
import { useErrorStore } from '../stores/errors';
import { useConsoleStore } from '../stores/console';
import { useSessionStore } from '../stores/session';
import { createErrorSocket } from '../services/websocket';
import { fetchFileContent } from '../services/api';

/** Parse file:line:col from a stack trace, preferring /src/ frames over node_modules. */
function parseStack(stack: string | undefined): { file: string; line: number; column?: number } | undefined {
  if (!stack) return undefined;
  for (const frame of stack.split('\n')) {
    if (frame.includes('node_modules')) continue;
    if (frame.includes('__ERROR_REPORTER__')) continue;
    // Match: at Foo (path/src/App.tsx:39:9) or path/src/App.tsx:39:9
    const m = frame.match(/\/src\/(.+?)(?:\?[^:]*)?:(\d+):(\d+)/);
    if (m) return { file: 'src/' + m[1], line: parseInt(m[2], 10), column: parseInt(m[3], 10) };
  }
  return undefined;
}

/** Extract "src/..." from a URL, absolute path, or pass through relative paths. */
function extractSourceFile(raw: string | undefined): string | undefined {
  if (!raw) return undefined;
  if (raw.includes('node_modules')) return undefined;
  // URL like https://host/api/preview/.../proxy/src/App.tsx?t=123
  const proxyIdx = raw.indexOf('/proxy/src/');
  if (proxyIdx !== -1) {
    const path = raw.slice(proxyIdx + 7); // skip "/proxy/"
    return path.split('?')[0]; // strip query string
  }
  // Absolute like /home/project/src/App.tsx
  const srcIdx = raw.indexOf('/src/');
  if (srcIdx !== -1) return raw.slice(srcIdx + 1);
  // Already relative
  if (raw.startsWith('src/')) return raw;
  return undefined;
}

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
        const msg = d.message ?? '';
        if (msg.includes('[vite] failed to connect to websocket')) return;
        const fromStack = parseStack(d.stack);
        const file = fromStack?.file ?? extractSourceFile(d.file);
        if (d.file && !file) return; // node_modules — skip
        // Stack trace line numbers are from transformed code — resolve real line from source
        if (file) {
          const pid = useSessionStore.getState().projectId;
          if (pid) {
            fetchFileContent(pid, file).then((content) => {
              const searchStr = (d.message ?? '').replace(/^Uncaught \w+:\s*/, '');
              let line: number | undefined;
              if (searchStr) {
                const idx = content.split('\n').findIndex((l: string) => l.includes(searchStr));
                if (idx >= 0) line = idx + 1;
              }
              pushError({ source: 'runtime', message: d.message ?? 'Unknown runtime error', file, line, stack: d.stack || undefined });
            }).catch(() => {
              pushError({ source: 'runtime', message: d.message ?? 'Unknown runtime error', file, stack: d.stack || undefined });
            });
            return;
          }
        }
        pushError({ source: 'runtime', message: d.message ?? 'Unknown runtime error', file, stack: d.stack || undefined });
      } else if (event.data.type === 'console') {
        pushConsole(event.data.level, event.data.args ?? [], event.data.file, event.data.line, event.data.column);
        if (event.data.level === 'error') {
          const errorMsg = (event.data.args ?? []).join(' ') || 'Console error';
          if (errorMsg.includes('[vite] failed to connect to websocket')) return;
          // React error boundaries repeat the actual error — skip them
          if (errorMsg.includes('The above error occurred in')) return;
          const file = event.data.file || undefined;
          // Resolve the real source line by searching the file content
          // (parseCaller stack traces give transformed line numbers)
          if (file) {
            const pid = useSessionStore.getState().projectId;
            if (pid) {
              fetchFileContent(pid, file).then((content) => {
                const searchStr = (event.data.args ?? [])[0];
                let line: number | undefined;
                if (searchStr) {
                  const idx = content.split('\n').findIndex((l: string) => l.includes(searchStr));
                  if (idx >= 0) line = idx + 1;
                }
                pushError({ source: 'console', message: errorMsg, file, line });
              }).catch(() => {
                pushError({ source: 'console', message: errorMsg, file });
              });
              return;
            }
          }
          pushError({ source: 'console', message: errorMsg, file });
        }
      }
    }

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [pushError, pushConsole]);
}
