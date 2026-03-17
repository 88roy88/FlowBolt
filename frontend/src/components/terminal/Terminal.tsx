import { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useSessionStore } from '../../stores/session';
import { createTerminalSocket } from '../../services/websocket';
import '@xterm/xterm/css/xterm.css';

function getTerminalTheme(): XTerm['options']['theme'] {
  if (typeof window === 'undefined') return undefined;
  const isLight = document.documentElement.dataset.theme === 'light';
  const styles = getComputedStyle(document.documentElement);
  const bg = styles.getPropertyValue('--bg').trim() || '#1e1e2e';
  const fg = styles.getPropertyValue('--text').trim() || '#cdd6f4';
  const accent = styles.getPropertyValue('--accent').trim() || '#89b4fa';

  return {
    background: bg,
    foreground: fg,
    cursor: accent,
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
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', Menlo, monospace",
      cursorBlink: true,
      cursorStyle: 'bar',
      convertEol: true,
      lineHeight: 1.2,
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
