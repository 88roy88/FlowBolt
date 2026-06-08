import type { ReadOnlySocket } from './types';
import { credentialsStore } from '../../auth';
import { getWsBase } from './reconnecting';

const serverLogSockets = new Map<string, ReadOnlySocket>();

export function getServerLogSocket(projectId: string): ReadOnlySocket {
  const existing = serverLogSockets.get(projectId);
  if (existing) return existing;

  const handlers: Array<(data: string) => void> = [];
  let socket: WebSocket | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    credentialsStore.ensureCookie();
    socket = new WebSocket(`${getWsBase()}/ws/server-log/${projectId}`);
    socket.binaryType = 'arraybuffer';

    socket.addEventListener('message', (event) => {
      const text = event.data instanceof ArrayBuffer
        ? new TextDecoder().decode(event.data)
        : event.data as string;
      handlers.forEach((h) => h(text));
    });

    socket.addEventListener('close', () => {
      socket = null;
      if (!closed) setTimeout(connect, 2000);
    });

    socket.addEventListener('error', () => {
      socket?.close();
    });
  }

  connect();

  const instance: ReadOnlySocket = {
    onData(handler: (data: string) => void) {
      handlers.push(handler);
    },
    close() {
      closed = true;
      socket?.close();
      socket = null;
      serverLogSockets.delete(projectId);
    },
  };

  serverLogSockets.set(projectId, instance);
  return instance;
}

export function closeServerLogSocket(projectId: string): void {
  const existing = serverLogSockets.get(projectId);
  if (existing) existing.close();
}

export function createServerLogSocket(projectId: string): ReadOnlySocket {
  return getServerLogSocket(projectId);
}
