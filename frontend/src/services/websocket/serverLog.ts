import type { ReadOnlySocket } from './types';
import { getWsBase } from './reconnecting';
import { credentialsStore } from '../../auth';

export function createServerLogSocket(projectId: string): ReadOnlySocket {
  const handlers: Array<(data: string) => void> = [];

  let socket: WebSocket | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    const token = credentialsStore.getValidToken();
    socket = new WebSocket(`${getWsBase()}/ws/server-log/${projectId}${token ? `?token=${encodeURIComponent(token)}` : ''}`);
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

  return {
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
