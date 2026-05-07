import { createReconnectingSocket, getWsBase, sendWsAuth } from './reconnecting';

export function createErrorSocket(
  projectId: string,
  onError: (data: unknown) => void,
): { close(): void } {
  const { sendOrQueue, close } = createReconnectingSocket(
    `${getWsBase()}/ws/errors/${projectId}`,
    () => {
      sendWsAuth(sendOrQueue);
    },
    (data) => {
      try {
        onError(JSON.parse(data));
      } catch {}
    },
  );

  return { close };
}
