import type { TerminalSocket } from './types';
import { credentialsStore } from '../../auth';
import { getWsBase } from './reconnecting';

const terminalSockets = new Map<string, TerminalSocket>();

export function getTerminalSocket(projectId: string): TerminalSocket {
  const existing = terminalSockets.get(projectId);
  if (existing) return existing;

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
    credentialsStore.ensureCookie();
    const ws = new WebSocket(`${getWsBase()}/ws/terminal/${projectId}`);
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

  const instance: TerminalSocket = {
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
      terminalSockets.delete(projectId);
    },
  };

  terminalSockets.set(projectId, instance);
  return instance;
}

export function closeTerminalSocket(projectId: string): void {
  const existing = terminalSockets.get(projectId);
  if (existing) existing.close();
}

export function createTerminalSocket(projectId: string): TerminalSocket {
  return getTerminalSocket(projectId);
}
