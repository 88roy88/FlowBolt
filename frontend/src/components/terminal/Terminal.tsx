import { useEffect, useRef } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { useSessionStore } from '../../stores/session';
import { getTerminalSocket } from '../../services/websocket/terminal';
import { getTerminalTheme } from '../../utils/terminalTheme';
import '@xterm/xterm/css/xterm.css';

export function Terminal() {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const projectId = useSessionStore((s) => s.projectId);

  useEffect(() => {
    if (!containerRef.current || !projectId) return;

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

    const socket = getTerminalSocket(projectId);
    termRef.current = term;

    // Replayed history can contain terminal queries (e.g. device attributes) that were
    // already answered; xterm's automatic replies to them must not reach the shell as input.
    let pendingReplays = 0;
    term.onData((data) => {
      if (pendingReplays === 0) socket.send(data);
    });

    // The PTY must match xterm's size, or the shell's cursor positioning lands in the wrong place.
    socket.resize(term.cols, term.rows);
    term.onResize(({ cols, rows }) => {
      socket.resize(cols, rows);
    });

    const handler = (data: string, replay: boolean) => {
      if (!replay) {
        term.write(data);
        return;
      }
      pendingReplays++;
      term.write(data, () => {
        pendingReplays--;
      });
    };
    const unsubscribe = socket.onData(handler);

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch {
        // container may not be visible
      }
    });
    resizeObserver.observe(containerRef.current);

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
      unsubscribe();
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      term.dispose();
      termRef.current = null;
    };
  }, [projectId]);

  if (!projectId) {
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
