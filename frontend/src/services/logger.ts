import { sendLogs } from "./api";
import { useSessionStore } from "../stores/session";

export interface LogEvent {
  event: string;
  event_version?: number;
  project_id?: string;
  project_name?: string;
  level?: "debug" | "info" | "warning" | "error";
  properties?: Record<string, unknown>;
}

let eventQueue: LogEvent[] = [];
let flushTimeout: ReturnType<typeof setTimeout> | null = null;

async function flush(keepalive = false): Promise<void> {
  if (eventQueue.length === 0) return;

  const eventsToSend = [...eventQueue];
  eventQueue = [];

  try {
    await sendLogs(eventsToSend, { keepalive });
  } catch (error) {
    console.warn("Log flush error:", error);
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
  options: {
    level?: "debug" | "info" | "warning" | "error";
    eventVersion?: number;
  } = {},
): void {
  const state = useSessionStore.getState();
  eventQueue.push({
    event,
    event_version: options.eventVersion ?? 1,
    level: options.level || "info",
    project_id: state.projectId ?? undefined,
    project_name: state.currentProject?.name ?? undefined,
    properties,
  });
  scheduleFlush();
}

export const logger = {
  debug: (
    event: string,
    properties?: Record<string, unknown>,
    eventVersion?: number,
  ) => log(event, properties, { level: "debug", eventVersion }),
  info: (
    event: string,
    properties?: Record<string, unknown>,
    eventVersion?: number,
  ) => log(event, properties, { level: "info", eventVersion }),
  warn: (
    event: string,
    properties?: Record<string, unknown>,
    eventVersion?: number,
  ) => log(event, properties, { level: "warning", eventVersion }),
  error: (
    event: string,
    properties?: Record<string, unknown>,
    eventVersion?: number,
  ) => log(event, properties, { level: "error", eventVersion }),
};

export async function flush_logs(): Promise<void> {
  if (flushTimeout) clearTimeout(flushTimeout);
  await flush();
}

// Flush logs on window hide
if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      if (flushTimeout) clearTimeout(flushTimeout);
      flush(true);
    }
  });
}
