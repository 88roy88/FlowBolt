import { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useSessionStore } from '../../stores/session';
import { createTerminalSocket } from '../../services/websocket';
import '@xterm/xterm/css/xterm.css';

function getTerminalTheme(): XTerm['options']['theme'] {
  if (typeof window === 'undefined') {
    return undefined;
  }
  const root = document.documentElement;
  const styles = getComputedStyle(root);
  const bg = styles.getPropertyValue('--bg').trim() || '#1e1e2e';
  const fg = styles.getPropertyValue('--text').trim() || '#cdd6f4';
  const accent = styles.getPropertyValue('--accent').trim() || '#89b4fa';
  const border = styles.getPropertyValue('--border').trim() || '#45475a';

  return {
    background: bg,
    foreground: fg,
    cursor: accent,
    cursorAccent: bg,
    selectionBackground: border,
  };
}

export function Terminal() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const socketRef = useRef<ReturnType<typeof createTerminalSocket> | null>(null);
  const sessionId = useSessionStore((s) => s.sessionId);

  useEffect(() => {
    if (!containerRef.current || !sessionId) return;

    const term = new XTerm({
      theme: getTerminalTheme(),
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

    // React to theme changes (light/dark)
    const mutationObserver = new MutationObserver(() => {
      const theme = getTerminalTheme();
      if (theme) {
        term.options.theme = theme;
      }
    });
    mutationObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });

    return () => {
      resizeObserver.disconnect();
      mutationObserver.disconnect();
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
