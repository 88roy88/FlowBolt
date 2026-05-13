import { authSession } from '../../auth';

export function getWsBase(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

export async function sendWsAuth(send: (data: string) => void): Promise<void> {
  const token = await authSession.ensureFreshToken();
  send(JSON.stringify({ type: 'auth', userAuthorization: token ?? '' }));
}

export function createReconnectingSocket(
  url: string | (() => string),
  onOpen?: () => void | Promise<void>,
  onMessage?: (data: string) => void,
  onClose?: () => void,
  onError?: (error: Event) => void,
): { sendOrQueue: (data: string) => void; close: () => void } {
  let socket: WebSocket | null = null;
  let closed = false;
  let retryDelay = 1000;
  const maxRetryDelay = 30000;
  const pendingQueue: string[] = [];
  let hasConnectedOnce = false;

  function flushQueue() {
    while (pendingQueue.length > 0 && socket?.readyState === WebSocket.OPEN) {
      socket.send(pendingQueue.shift()!);
    }
  }

  function connect() {
    if (closed) return;
    socket = new WebSocket(typeof url === 'function' ? url() : url);

    socket.addEventListener('open', async () => {
      hasConnectedOnce = true;
      retryDelay = 1000;
      await onOpen?.();
      flushQueue();
    });

    socket.addEventListener('message', (event) => {
      onMessage?.(event.data as string);
    });

    socket.addEventListener('close', () => {
      socket = null;
      onClose?.();
      if (!closed) {
        setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, maxRetryDelay);
          connect();
        }, retryDelay);
      }
    });

    socket.addEventListener('error', (event) => {
      if (!hasConnectedOnce) {
        onError?.(event);
      }
      socket?.close();
    });
  }

  connect();

  return {
    sendOrQueue: (data: string) => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(data);
      } else {
        pendingQueue.push(data);
      }
    },
    close: () => {
      closed = true;
      socket?.close();
      socket = null;
    },
  };
}
