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
    socket = new WebSocket(url);

    socket.addEventListener('open', () => {
      hasConnectedOnce = true;
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

    socket.addEventListener('error', (event) => {
      // Only report initial connection errors (not reconnection attempts)
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
    () => {
      // on error — notify user of connection issues
      if (typeof window !== 'undefined') {
        import('../stores/errors').then(({ useErrorStore }) => {
          useErrorStore.getState().pushError({
            source: 'connection',
            message: 'Failed to establish WebSocket connection to backend. Chat may not work properly.',
          });
        });
      }
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

interface ReadOnlySocket {
  onData(handler: (data: string) => void): void;
  close(): void;
}

export function createServerLogSocket(sessionId: string): ReadOnlySocket {
  const handlers: Array<(data: string) => void> = [];

  let socket: WebSocket | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    socket = new WebSocket(`${getWsBase()}/ws/server-log/${sessionId}`);
    socket.binaryType = 'arraybuffer';

    socket.addEventListener('message', (event) => {
      let text: string;
      if (event.data instanceof ArrayBuffer) {
        text = new TextDecoder().decode(event.data);
      } else {
        text = event.data as string;
      }
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

export function createErrorSocket(
  sessionId: string,
  onError: (data: unknown) => void,
): { close(): void } {
  const { close } = createReconnectingSocket(
    `${getWsBase()}/ws/errors/${sessionId}`,
    undefined,
    (data) => {
      try {
        onError(JSON.parse(data));
      } catch { /* ignore malformed */ }
    },
  );

  return { close };
}

export function createTerminalSocket(sessionId: string): TerminalSocket {
  const handlers: Array<(data: string) => void> = [];
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();

  let socket: WebSocket | null = null;
  let closed = false;
  let retryDelay = 1000;
  const pendingQueue: ArrayBuffer[] = [];
  let hasConnectedOnce = false;

  function flushQueue() {
    while (pendingQueue.length > 0 && socket?.readyState === WebSocket.OPEN) {
      socket.send(pendingQueue.shift()!);
    }
  }

  function connect() {
    if (closed) return;
    const ws = new WebSocket(`${getWsBase()}/ws/terminal/${sessionId}`);
    // Receive binary frames as ArrayBuffer (not Blob)
    ws.binaryType = 'arraybuffer';
    socket = ws;

    ws.addEventListener('open', () => {
      hasConnectedOnce = true;
      retryDelay = 1000;
      flushQueue();
    });

    ws.addEventListener('message', (event) => {
      let text: string;
      if (event.data instanceof ArrayBuffer) {
        text = decoder.decode(event.data);
      } else {
        text = event.data as string;
      }
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
      // Send as binary to match backend's receive_bytes()
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
