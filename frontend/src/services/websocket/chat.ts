import type { WSMessage } from '../../types';
import type { ChatSocket } from './types';
import { readPackageApiAuthorization } from '../packageApiAuth';
import { createReconnectingSocket, getWsBase } from './reconnecting';

const chatSockets = new Map<string, ChatSocket>();

export function getChatSocket(sessionId: string): ChatSocket {
  const existing = chatSockets.get(sessionId);
  if (existing) return existing;

  const handlers = new Set<(msg: WSMessage) => void>();

  const sendAuthMessage = (send: (message: WSMessage) => void) => {
    const rawToken = readPackageApiAuthorization();
    const packageApiAuthorization = rawToken?.trim() || undefined;
    send({
      type: 'auth',
      ...(packageApiAuthorization && { packageApiAuthorization }),
    });
  };

  const { sendOrQueue, close } = createReconnectingSocket(
    `${getWsBase()}/ws/chat/${sessionId}`,
    () => {
      sendAuthMessage((message) => {
        sendOrQueue(JSON.stringify(message));
      });
    },
    (data) => {
      try {
        const msg = JSON.parse(data) as WSMessage;
        handlers.forEach((h) => h(msg));
      } catch {}
    },
    undefined,
    () => {
      if (typeof window !== 'undefined') {
        import('../../stores/errors').then(({ useErrorStore }) => {
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

export function closeChatSocket(sessionId: string): void {
  const socket = chatSockets.get(sessionId);
  if (socket) socket.close();
}

export const createChatSocket = getChatSocket;
