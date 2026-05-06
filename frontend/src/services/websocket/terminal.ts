import type { TerminalSocket } from './types';
import { getWsBase } from './reconnecting';
import { credentialsStore } from '../../auth';

export function createTerminalSocket(projectId: string): TerminalSocket {
  const handlers: Array<(data: string) => void> = [];
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();

  let socket: WebSocket | null = null;
  let closed = false;
  let retryDelay = 1000;
  const pendingQueue: ArrayBuffer[] = [];
  function flushQueue() {
    while (pendingQueue.length > 0 && socket?.readyState === WebSocket.OPEN) {
      socket.send(pendingQueue.shift()!);
    }
  }

  function connect() {
    if (closed) return;
    const token = credentialsStore.getValidToken();
    const ws = new WebSocket(`${getWsBase()}/ws/terminal/${projectId}${token ? `?token=${encodeURIComponent(token)}` : ''}`);
    ws.binaryType = 'arraybuffer';
    socket = ws;

    ws.addEventListener('open', () => {
      retryDelay = 1000;
      flushQueue();
    });

    ws.addEventListener('message', (event) => {
      const text = event.data instanceof ArrayBuffer
        ? decoder.decode(event.data)
        : event.data as string;
      handlers.forEach((h) => h(text));
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

  return {
    send(data: string) {
      const buf = encoder.encode(data);
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(buf);
      } else {
        pendingQueue.push(buf.buffer);
      }
    },
    onData(handler: (data: string) => void) {
      handlers.push(handler);
    },
    close() {
      closed = true;
      socket?.close();
      socket = null;
    },
  };
}
