import type { TerminalSocket } from './types';
import { credentialsStore } from '../../auth';
import { getWsBase } from './reconnecting';

const MAX_HISTORY_CHARS = 256 * 1024;
const terminalSockets = new Map<string, TerminalSocket>();

export function getTerminalSocket(projectId: string): TerminalSocket {
  const existing = terminalSockets.get(projectId);
  if (existing) return existing;

  const handlers: Array<(data: string, replay: boolean) => void> = [];
  let history = '';
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();

  let socket: WebSocket | null = null;
  let closed = false;
  let retryDelay = 1000;
  const pendingQueue: ArrayBuffer[] = [];
  let size: { cols: number; rows: number } | null = null;

  function flushQueue() {
    while (pendingQueue.length > 0 && socket?.readyState === WebSocket.OPEN) {
      socket.send(pendingQueue.shift()!);
    }
  }

  function sendSize() {
    if (size && socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'resize', ...size }));
    }
  }

  function connect() {
    if (closed) return;
    credentialsStore.ensureCookie();
    const ws = new WebSocket(`${getWsBase()}/ws/projects/${projectId}/terminal`);
    ws.binaryType = 'arraybuffer';
    socket = ws;
    history = '';

    ws.addEventListener('open', () => {
      retryDelay = 1000;
      sendSize();
      flushQueue();
    });

    ws.addEventListener('message', (event) => {
      let text: string;
      let replay = false;
      if (event.data instanceof ArrayBuffer) {
        text = decoder.decode(event.data);
      } else {
        const scrollback = parseScrollback(event.data as string);
        replay = scrollback !== null;
        text = scrollback ?? event.data as string;
      }
      history = (history + text).slice(-MAX_HISTORY_CHARS);
      handlers.forEach((h) => h(text, replay));
    });

    ws.addEventListener('close', () => {
      socket = null;
      if (!closed) {
        setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, 30000);
          connect();
        }, retryDelay);
      }
    });

    ws.addEventListener('error', () => {
      ws.close();
    });
  }

  connect();

  const instance: TerminalSocket = {
    send(data: string) {
      const buf = encoder.encode(data);
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(buf);
      } else {
        pendingQueue.push(buf.buffer);
      }
    },
    resize(cols: number, rows: number) {
      size = { cols, rows };
      sendSize();
    },
    onData(handler: (data: string, replay: boolean) => void) {
      if (history) handler(history, true);
      handlers.push(handler);
      return () => {
        const idx = handlers.indexOf(handler);
        if (idx !== -1) handlers.splice(idx, 1);
      };
    },
    close() {
      closed = true;
      socket?.close();
      socket = null;
      terminalSockets.delete(projectId);
    },
  };

  terminalSockets.set(projectId, instance);
  return instance;
}

function parseScrollback(text: string): string | null {
  try {
    const msg = JSON.parse(text);
    return msg?.type === 'scrollback' && typeof msg.data === 'string' ? msg.data : null;
  } catch {
    return null;
  }
}

export function closeTerminalSocket(projectId: string): void {
  const existing = terminalSockets.get(projectId);
  if (existing) existing.close();
}

export function createTerminalSocket(projectId: string): TerminalSocket {
  return getTerminalSocket(projectId);
}
