import { sendLogs } from './api';
import { useSessionStore } from '../stores/session';

export interface LogEvent {
  event: string;
  event_version?: number;
  project_id?: string;
  project_name?: string;
  level?: 'debug' | 'info' | 'warning' | 'error';
  properties?: Record<string, unknown>;
}

let eventQueue: LogEvent[] = [];
let flushTimeout: ReturnType<typeof setTimeout> | null = null;

async function flush(): Promise<void> {
  if (eventQueue.length === 0) return;

  const eventsToSend = [...eventQueue];
  eventQueue = [];

  try {
    await sendLogs(eventsToSend);
  } catch (error) {
    console.warn('Log flush error:', error);
    eventQueue.unshift(...eventsToSend);
  }
}

function scheduleFlush(): void {
  if (flushTimeout) clearTimeout(flushTimeout);
  flushTimeout = setTimeout(() => {
    flush();
  }, 1000);
}

function log(
  event: string,
  properties?: Record<string, unknown>,
  options: { level?: 'debug' | 'info' | 'warning' | 'error' } = {}
): void {
  const state = useSessionStore.getState();
  eventQueue.push({
    event,
    event_version: 1,
    level: options.level || 'info',
    project_id: state.projectId ?? undefined,
    project_name: state.currentProject?.name ?? undefined,
    properties,
  });
  scheduleFlush();
}

export const logger = {
  debug: (event: string, properties?: Record<string, unknown>) =>
    log(event, properties, { level: 'debug' }),
  info: (event: string, properties?: Record<string, unknown>) =>
    log(event, properties, { level: 'info' }),
  warn: (event: string, properties?: Record<string, unknown>) =>
    log(event, properties, { level: 'warning' }),
  error: (event: string, properties?: Record<string, unknown>) =>
    log(event, properties, { level: 'error' }),
};

export async function flush_logs(): Promise<void> {
  if (flushTimeout) clearTimeout(flushTimeout);
  await flush();
}
