import type { WSMessage } from '../../types';
import type { ChatSocket } from './types';
import { readDataSourceAuthorization } from '../dataSourceAuth';
import { notifyChatConnectionLost } from '../../stores/chatConnection';
import { createReconnectingSocket, getWsBase } from './reconnecting';

const chatSockets = new Map<string, ChatSocket>();

export function getChatSocket(projectId: string): ChatSocket {
  const existing = chatSockets.get(projectId);
  if (existing) return existing;

  const handlers = new Set<(msg: WSMessage) => void>();
  let stopReconnect: (() => void) | null = null;

  const sendAuthMessage = (send: (message: WSMessage) => void) => {
    const rawToken = readDataSourceAuthorization();
    const dataSourceAuthorization = rawToken?.trim() || undefined;
    send({
      type: 'auth',
      ...(dataSourceAuthorization && { dataSourceAuthorization }),
    });
  };

  // createReconnectingSocket calls this on every WebSocket `close`, including
  // before an automatic reconnect. That is intentional: a backend reload or
  // crash drops the socket while the in-memory agent task is gone, so we clear
  // stale "thinking" UI via notifyChatConnectionLost → chat store reset.

  const { sendOrQueue, close } = createReconnectingSocket(
    `${getWsBase()}/ws/chat/${projectId}`,
    () => {
      sendAuthMessage((message) => {
        sendOrQueue(JSON.stringify(message));
      });
    },
    (data) => {
      try {
        const msg = JSON.parse(data) as WSMessage;
        if (msg.type === 'error' && msg.message === 'Unknown session') {
          stopReconnect?.();
          chatSockets.delete(projectId);
          return;
        }
        handlers.forEach((h) => h(msg));
      } catch {}
    },
    notifyChatConnectionLost,
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
  stopReconnect = close;

  const socket: ChatSocket = {
    send(message: WSMessage) {
      // Re-send auth before outbound messages so backend has latest token value.
      if (message.type !== 'auth') {
        sendAuthMessage((authMessage) => {
          sendOrQueue(JSON.stringify(authMessage));
        });
      }
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
