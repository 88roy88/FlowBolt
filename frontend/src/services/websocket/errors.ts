import { createReconnectingSocket, getWsBase } from './reconnecting';
import { credentialsStore } from '../../auth';

export function createErrorSocket(
  projectId: string,
  onError: (data: unknown) => void,
): { close(): void } {
  const { close } = createReconnectingSocket(
    () => {
      const token = credentialsStore.getValidToken();
      return `${getWsBase()}/ws/errors/${projectId}${token ? `?token=${encodeURIComponent(token)}` : ''}`;
    },
    undefined,
    (data) => {
      try {
        onError(JSON.parse(data));
      } catch {}
    },
  );

  return { close };
}
