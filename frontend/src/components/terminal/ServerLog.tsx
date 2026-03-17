import { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useSessionStore } from '../../stores/session';
import '@xterm/xterm/css/xterm.css';

function getWsBase(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

function getServerLogTheme(): XTerm['options']['theme'] {
  if (typeof window === 'undefined') return undefined;
  const isLight = document.documentElement.dataset.theme === 'light';
  const styles = getComputedStyle(document.documentElement);
  const bg = styles.getPropertyValue('--bg').trim() || '#1e1e2e';
  const fg = styles.getPropertyValue('--text').trim() || '#cdd6f4';

  return {
    background: bg,
    foreground: fg,
    cursor: bg,
    cursorAccent: bg,
    selectionBackground: isLight ? 'rgba(37, 99, 235, 0.2)' : 'rgba(137, 180, 250, 0.25)',
    selectionForeground: fg,
    black:   isLight ? '#6b7280' : '#45475a',
    brightBlack: isLight ? '#9ca3af' : '#585b70',
    red:     isLight ? '#dc2626' : '#f38ba8',
    brightRed: isLight ? '#ef4444' : '#f38ba8',
    green:   isLight ? '#16a34a' : '#a6e3a1',
    brightGreen: isLight ? '#22c55e' : '#a6e3a1',
    yellow:  isLight ? '#ca8a04' : '#f9e2af',
    brightYellow: isLight ? '#eab308' : '#f9e2af',
    blue:    isLight ? '#2563eb' : '#89b4fa',
    brightBlue: isLight ? '#3b82f6' : '#89b4fa',
    magenta: isLight ? '#9333ea' : '#cba6f7',
    brightMagenta: isLight ? '#a855f7' : '#cba6f7',
    cyan:    isLight ? '#0891b2' : '#94e2d5',
    brightCyan: isLight ? '#06b6d4' : '#94e2d5',
    white:   isLight ? '#374151' : '#bac2de',
    brightWhite: isLight ? '#111827' : '#cdd6f4',
  };
}

export function ServerLog() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sessionId = useSessionStore((s) => s.sessionId);

  useEffect(() => {
    if (!containerRef.current || !sessionId) return;

    const term = new XTerm({
      theme: getServerLogTheme(),
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', Menlo, monospace",
      cursorBlink: false,
      disableStdin: true,
      convertEol: true,
      lineHeight: 1.2,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);

    term.open(containerRef.current);
    fitAddon.fit();

    let ws: WebSocket | null = null;
    let closed = false;
    let retryDelay = 1000;

    function connect() {
      if (closed) return;
      ws = new WebSocket(`${getWsBase()}/ws/server-log/${sessionId}`);
      ws.binaryType = 'arraybuffer';

      ws.addEventListener('message', (event) => {
        if (event.data instanceof ArrayBuffer) {
          term.write(new Uint8Array(event.data));
        } else {
          term.write(event.data as string);
        }
      });

      ws.addEventListener('close', () => {
        ws = null;
        if (!closed) {
          setTimeout(() => {
            retryDelay = Math.min(retryDelay * 2, 30000);
            connect();
          }, retryDelay);
        }
      });

      ws.addEventListener('open', () => {
        retryDelay = 1000;
      });

      ws.addEventListener('error', () => {
        ws?.close();
      });
    }

    connect();

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch {
        // container may not be visible
      }
    });
    resizeObserver.observe(containerRef.current);

    const mutationObserver = new MutationObserver(() => {
      const theme = getServerLogTheme();
      if (theme) term.options.theme = theme;
    });
    mutationObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });

    return () => {
      closed = true;
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      ws?.close();
      ws = null;
      term.dispose();
    };
  }, [sessionId]);

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
        No session active
      </div>
    );
  }

  return <div ref={containerRef} style={{ height: '100%', width: '100%' }} />;
}
