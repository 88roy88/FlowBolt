import { createReconnectingSocket, getWsBase } from './reconnecting';

export function createErrorSocket(
  projectId: string,
  onError: (data: unknown) => void,
): { close(): void } {
  const { close } = createReconnectingSocket(
    `${getWsBase()}/ws/errors/${projectId}`,
    undefined,
    (data) => {
      try {
        onError(JSON.parse(data));
      } catch {}
    },
  );

  return { close };
}
