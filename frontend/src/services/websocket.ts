import type { WSMessage } from '../types';

interface ChatSocket {
  send(message: WSMessage): void;
  onMessage(handler: (msg: WSMessage) => void): void;
  offMessage(handler: (msg: WSMessage) => void): void;
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
): { sendOrQueue: (data: string) => void; close: () => void } {
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

// Singleton chat sockets — one per session, reused across messages
const chatSockets = new Map<string, ChatSocket>();

export function getChatSocket(sessionId: string): ChatSocket {
  const existing = chatSockets.get(sessionId);
  if (existing) return existing;

  const handlers = new Set<(msg: WSMessage) => void>();

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
    () => {
      // on close — don't remove from map, reconnect will handle it
    },
  );

  const socket: ChatSocket = {
    send(message: WSMessage) {
      sendOrQueue(JSON.stringify(message));
    },
    onMessage(handler: (msg: WSMessage) => void) {
      handlers.add(handler);
    },
    offMessage(handler: (msg: WSMessage) => void) {
      handlers.delete(handler);
    },
    offMessage(handler: (msg: WSMessage) => void) {
      const idx = handlers.indexOf(handler);
      if (idx !== -1) handlers.splice(idx, 1);
    },
    close,
    close() {
      chatSockets.delete(sessionId);
      close();
    },
  };

  chatSockets.set(sessionId, socket);
  return socket;
}

/** Close and remove the chat socket for a session (e.g. on project delete). */
export function closeChatSocket(sessionId: string): void {
  const socket = chatSockets.get(sessionId);
  if (socket) socket.close();
}

// Keep createChatSocket as alias for backwards compat during transition
export const createChatSocket = getChatSocket;

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

const chatSockets = new Map<string, ChatSocket>();

export function getChatSocket(sessionId: string): ChatSocket {
  const existing = chatSockets.get(sessionId);
  if (existing) return existing;
  const sock = createChatSocket(sessionId);
  chatSockets.set(sessionId, sock);
  return sock;
}
