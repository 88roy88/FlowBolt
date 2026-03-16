import { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useSessionStore } from '../../stores/session';
import { createTerminalSocket } from '../../services/websocket';
import '@xterm/xterm/css/xterm.css';

export function Terminal() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const socketRef = useRef<ReturnType<typeof createTerminalSocket> | null>(null);
  const sessionId = useSessionStore((s) => s.sessionId);

  useEffect(() => {
    if (!containerRef.current || !sessionId) return;

    const term = new XTerm({
      theme: {
        background: '#1e1e2e',
        foreground: '#cdd6f4',
        cursor: '#89b4fa',
        cursorAccent: '#1e1e2e',
        selectionBackground: '#45475a',
        black: '#45475a',
        red: '#f38ba8',
        green: '#a6e3a1',
        yellow: '#f9e2af',
        blue: '#89b4fa',
        magenta: '#cba6f7',
        cyan: '#94e2d5',
        white: '#cdd6f4',
      },
      fontSize: 13,
      fontFamily: 'var(--font-mono)',
      cursorBlink: true,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);

    term.open(containerRef.current);
    fitAddon.fit();

    const socket = createTerminalSocket(sessionId);
    socketRef.current = socket;
    termRef.current = term;

    term.onData((data) => {
      socket.send(data);
    });

    socket.onData((data) => {
      term.write(data);
    });

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch {
        // container may not be visible
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      socket.close();
      term.dispose();
      termRef.current = null;
      socketRef.current = null;
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
