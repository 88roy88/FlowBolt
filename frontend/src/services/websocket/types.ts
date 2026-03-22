import type { WSMessage } from '../../types';

export interface ChatSocket {
  send(message: WSMessage): void;
  onMessage(handler: (msg: WSMessage) => void): void;
  offMessage(handler: (msg: WSMessage) => void): void;
  close(): void;
}

export interface TerminalSocket {
  send(data: string): void;
  onData(handler: (data: string) => void): void;
  close(): void;
}

export interface ReadOnlySocket {
  onData(handler: (data: string) => void): void;
  close(): void;
}
