let connectionLostHandler: (() => void) | null = null;

export function registerChatConnectionLostHandler(handler: () => void): void {
  connectionLostHandler = handler;
}

export function notifyChatConnectionLost(): void {
  connectionLostHandler?.();
}
