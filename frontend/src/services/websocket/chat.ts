import type { WSMessage } from '../../types';
import type { ChatSocket } from './types';
import { createReconnectingSocket, getWsBase } from './reconnecting';

const chatSockets = new Map<string, ChatSocket>();

export function getChatSocket(projectId: string): ChatSocket {
  const existing = chatSockets.get(projectId);
  if (existing) return existing;

  const handlers = new Set<(msg: WSMessage) => void>();

  const { sendOrQueue, close } = createReconnectingSocket(
    `${getWsBase()}/ws/chat/${projectId}`,
    undefined,
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
      chatSockets.delete(projectId);
      close();
    },
  };

  chatSockets.set(projectId, socket);
  return socket;
}

export function closeChatSocket(projectId: string): void {
  const socket = chatSockets.get(projectId);
  if (socket) socket.close();
}

export const createChatSocket = getChatSocket;
