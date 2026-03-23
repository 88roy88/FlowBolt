/**
 * Mock WebSocket server for Playwright E2E tests.
 *
 * Intercepts WebSocket connections via Playwright's CDP and responds
 * with scripted event sequences.
 */
import { type Page } from '@playwright/test';
import { BUILD_EVENT_SEQUENCE, PROJECT_ID } from './data';

interface MockWSOptions {
  /** Events to send on the chat WebSocket after connection. */
  chatEvents?: Record<string, unknown>[];
  /** Delay (ms) between events. */
  eventDelay?: number;
}

/**
 * Set up mock WebSocket handling.
 *
 * Playwright can't directly intercept WebSockets, so we mock at the page level
 * by injecting a script that replaces WebSocket with a mock implementation.
 */
export async function setupMockWS(page: Page, options: MockWSOptions = {}) {
  const chatEvents = options.chatEvents ?? BUILD_EVENT_SEQUENCE;
  const eventDelay = options.eventDelay ?? 50;

  await page.addInitScript(({ projectId, events, delay }) => {
    const OriginalWebSocket = window.WebSocket;

    class MockWebSocket extends EventTarget {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      readyState = MockWebSocket.CONNECTING;
      url: string;
      binaryType: string = 'blob';
      protocol = '';
      extensions = '';
      bufferedAmount = 0;

      // Event handler properties
      onopen: ((ev: Event) => void) | null = null;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onclose: ((ev: CloseEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;

      constructor(url: string | URL, _protocols?: string | string[]) {
        super();
        this.url = url.toString();

        // If this is NOT a URL we want to mock, use the real WebSocket
        const isChatWs = this.url.includes(`/ws/chat/${projectId}`);
        const isTerminalWs = this.url.includes(`/ws/terminal/${projectId}`);
        const isErrorWs = this.url.includes(`/ws/errors/${projectId}`);
        const isServerLogWs = this.url.includes(`/ws/server-log/${projectId}`);

        if (!isChatWs && !isTerminalWs && !isErrorWs && !isServerLogWs) {
          // Fall through to real WebSocket for unknown URLs
          return new OriginalWebSocket(url, _protocols) as unknown as MockWebSocket;
        }

        // Auto-open after a tick
        setTimeout(() => {
          this.readyState = MockWebSocket.OPEN;
          const openEvent = new Event('open');
          this.dispatchEvent(openEvent);
          this.onopen?.(openEvent);

          // For chat WebSocket, send scripted events
          if (isChatWs) {
            this._playChatEvents(events, delay);
          }

          // For terminal, send a prompt
          if (isTerminalWs) {
            setTimeout(() => {
              this._sendMessage('⚡ project ❯ ');
            }, 100);
          }
        }, 10);
      }

      send(_data: string | ArrayBufferLike | Blob | ArrayBufferView) {
        // For chat WS: if user sends a message, replay build events
        // (already handled by _playChatEvents on connect for simplicity)
      }

      close(_code?: number, _reason?: string) {
        this.readyState = MockWebSocket.CLOSED;
        const closeEvent = new CloseEvent('close', { code: _code ?? 1000 });
        this.dispatchEvent(closeEvent);
        this.onclose?.(closeEvent);
      }

      _sendMessage(data: string) {
        if (this.readyState !== MockWebSocket.OPEN) return;
        const event = new MessageEvent('message', { data });
        this.dispatchEvent(event);
        this.onmessage?.(event);
      }

      async _playChatEvents(evts: Record<string, unknown>[], delayMs: number) {
        // Wait for the page to send a message before replaying
        // (handled via send() override in a real implementation)
        // For now, we don't auto-play — events are triggered by test actions
      }

      /**
       * Trigger sending a batch of events. Called from tests via page.evaluate().
       */
      _injectEvents(evts: Record<string, unknown>[], delayMs: number) {
        let i = 0;
        const sendNext = () => {
          if (i >= evts.length || this.readyState !== MockWebSocket.OPEN) return;
          this._sendMessage(JSON.stringify(evts[i]));
          i++;
          setTimeout(sendNext, delayMs);
        };
        sendNext();
      }
    }

    // Store references so tests can trigger events
    (window as any).__mockWebSockets = {} as Record<string, MockWebSocket>;

    const origDescriptor = Object.getOwnPropertyDescriptor(window, 'WebSocket');
    Object.defineProperty(window, 'WebSocket', {
      configurable: true,
      writable: true,
      value: new Proxy(OriginalWebSocket, {
        construct(_target, args) {
          const ws = new MockWebSocket(args[0], args[1]);
          const url = args[0].toString();
          if (url.includes('/ws/chat/')) (window as any).__mockWebSockets.chat = ws;
          if (url.includes('/ws/terminal/')) (window as any).__mockWebSockets.terminal = ws;
          if (url.includes('/ws/errors/')) (window as any).__mockWebSockets.errors = ws;
          if (url.includes('/ws/server-log/')) (window as any).__mockWebSockets.serverLog = ws;
          return ws;
        },
      }),
    });

    // Preserve static constants
    (window as any).WebSocket.CONNECTING = 0;
    (window as any).WebSocket.OPEN = 1;
    (window as any).WebSocket.CLOSING = 2;
    (window as any).WebSocket.CLOSED = 3;
  }, { projectId: PROJECT_ID, events: chatEvents, delay: eventDelay });
}

/**
 * Send events to the mock chat WebSocket from a test.
 */
export async function sendChatEvents(
  page: Page,
  events: Record<string, unknown>[],
  delay = 50,
) {
  await page.evaluate(({ events, delay }) => {
    const ws = (window as any).__mockWebSockets?.chat;
    if (ws) ws._injectEvents(events, delay);
  }, { events, delay });
}
