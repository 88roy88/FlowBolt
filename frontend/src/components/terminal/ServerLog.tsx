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

export function ServerLog() {
  const containerRef = useRef<HTMLDivElement>(null);
  const sessionId = useSessionStore((s) => s.sessionId);

  useEffect(() => {
    if (!containerRef.current || !sessionId) return;

    const term = new XTerm({
      theme: {
        background: '#1e1e2e',
        foreground: '#cdd6f4',
        cursor: '#1e1e2e',
        cursorAccent: '#1e1e2e',
        selectionBackground: 'rgba(137, 180, 250, 0.25)',
        selectionForeground: '#cdd6f4',
        black: '#45475a',
        brightBlack: '#585b70',
        red: '#f38ba8',
        brightRed: '#f38ba8',
        green: '#a6e3a1',
        brightGreen: '#a6e3a1',
        yellow: '#f9e2af',
        brightYellow: '#f9e2af',
        blue: '#89b4fa',
        brightBlue: '#89b4fa',
        magenta: '#cba6f7',
        brightMagenta: '#cba6f7',
        cyan: '#94e2d5',
        brightCyan: '#94e2d5',
        white: '#bac2de',
        brightWhite: '#cdd6f4',
      },
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

    return () => {
      closed = true;
      resizeObserver.disconnect();
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
