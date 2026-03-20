import type { ReadOnlySocket } from './types';
import { getWsBase } from './reconnecting';

export function createServerLogSocket(sessionId: string): ReadOnlySocket {
  const handlers: Array<(data: string) => void> = [];

  let socket: WebSocket | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    socket = new WebSocket(`${getWsBase()}/ws/server-log/${sessionId}`);
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
