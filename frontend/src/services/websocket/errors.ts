import { createReconnectingSocket, getWsBase } from './reconnecting';

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
      } catch {}
    },
  );

  return { close };
}
