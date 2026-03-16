import type { WSMessage } from '../types';

interface ChatSocket {
  send(message: WSMessage): void;
  onMessage(handler: (msg: WSMessage) => void): void;
  close(): void;
}

interface TerminalSocket {
  send(data: string): void;
  onData(handler: (data: string) => void): void;
  close(): void;
}

function getWsBase(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
}

function createReconnectingSocket(
  url: string,
  onOpen?: () => void,
  onMessage?: (data: string) => void,
  onClose?: () => void,
): { getSocket: () => WebSocket | null; sendOrQueue: (data: string) => void; close: () => void } {
  let socket: WebSocket | null = null;
  let closed = false;
  let retryDelay = 1000;
  const maxRetryDelay = 30000;
  const pendingQueue: string[] = [];

  function flushQueue() {
    while (pendingQueue.length > 0 && socket?.readyState === WebSocket.OPEN) {
      socket.send(pendingQueue.shift()!);
    }
  }

  function connect() {
    if (closed) return;
    socket = new WebSocket(url);

    socket.addEventListener('open', () => {
      retryDelay = 1000;
      flushQueue();
      onOpen?.();
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

    socket.addEventListener('error', () => {
      socket?.close();
    });
  }

  connect();

  return {
    getSocket: () => socket,
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

export function createChatSocket(sessionId: string): ChatSocket {
  const handlers: Array<(msg: WSMessage) => void> = [];

  const { sendOrQueue, close } = createReconnectingSocket(
    `${getWsBase()}/ws/chat/${sessionId}`,
    undefined,
    (data) => {
      try {
        const msg = JSON.parse(data) as WSMessage;
        handlers.forEach((h) => h(msg));
      } catch {
        // ignore malformed messages
      }
    },
  );

  return {
    send(message: WSMessage) {
      sendOrQueue(JSON.stringify(message));
    },
    onMessage(handler: (msg: WSMessage) => void) {
      handlers.push(handler);
    },
    close,
  };
}

export function createTerminalSocket(sessionId: string): TerminalSocket {
  const handlers: Array<(data: string) => void> = [];

  const { sendOrQueue, close } = createReconnectingSocket(
    `${getWsBase()}/ws/terminal/${sessionId}`,
    undefined,
    (data) => {
      handlers.forEach((h) => h(data));
    },
  );

  return {
    send(data: string) {
      sendOrQueue(data);
    },
    onData(handler: (data: string) => void) {
      handlers.push(handler);
    },
    close,
  };
}
