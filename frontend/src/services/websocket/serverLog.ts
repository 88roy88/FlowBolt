import type { ReadOnlySocket } from './types';
import { getWsBase } from './reconnecting';

export function createServerLogSocket(projectId: string): ReadOnlySocket {
  const handlers: Array<(data: string) => void> = [];

  let socket: WebSocket | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    const ws = new WebSocket(`${getWsBase()}/ws/server-log/${projectId}`);
    ws.binaryType = 'arraybuffer';
    socket = ws;

    ws.addEventListener('message', (event) => {
      const text = event.data instanceof ArrayBuffer
        ? new TextDecoder().decode(event.data)
        : event.data as string;
      handlers.forEach((h) => h(text));
    });

    ws.addEventListener('close', () => {
      socket = null;
      if (!closed) setTimeout(connect, 2000);
    });

    ws.addEventListener('error', () => {
      ws.close();
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
