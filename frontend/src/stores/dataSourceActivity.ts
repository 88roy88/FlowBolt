import { create } from 'zustand';

export type CallResult = 'ok' | 'error' | 'aborted';

export interface DataSourceCall {
  id: string;
  startedAt: number;
  /** The request body as sent, possibly shortened. Null when the call had none. */
  params: string | null;
  result: CallResult | 'running';
}

/** What one data source has done since the preview loaded. Kept in memory only. */
export interface DataSourceActivity {
  count: number;
  running: string[];
  lastResult: 'ok' | 'error' | null;
  /** Newest first. */
  recent: DataSourceCall[];
}

interface DataSourceActivityState {
  byId: Record<string, DataSourceActivity>;
  startCall: (dataSourceId: string, callId: string, params: string | null) => void;
  endCall: (dataSourceId: string, callId: string, result: CallResult) => void;
  /** The preview is gone, so calls in flight will never report back. */
  clearRunning: () => void;
  reset: () => void;
}

export const MAX_RECENT_CALLS = 5;

const IDLE: DataSourceActivity = { count: 0, running: [], lastResult: null, recent: [] };

export const useDataSourceActivityStore = create<DataSourceActivityState>((set) => ({
  byId: {},

  startCall(dataSourceId, callId, params) {
    set((state) => {
      const activity = state.byId[dataSourceId] ?? IDLE;
      const call: DataSourceCall = { id: callId, startedAt: Date.now(), params, result: 'running' };
      return {
        byId: {
          ...state.byId,
          [dataSourceId]: {
            ...activity,
            count: activity.count + 1,
            running: [...activity.running, callId],
            recent: [call, ...activity.recent].slice(0, MAX_RECENT_CALLS),
          },
        },
      };
    });
  },

  endCall(dataSourceId, callId, result) {
    set((state) => {
      const activity = state.byId[dataSourceId];
      if (!activity?.running.includes(callId)) return state;
      return {
        byId: {
          ...state.byId,
          [dataSourceId]: {
            ...activity,
            running: activity.running.filter((id) => id !== callId),
            // A cancelled call says nothing about whether the data source works.
            lastResult: result === 'aborted' ? activity.lastResult : result,
            recent: activity.recent.map((call) => (call.id === callId ? { ...call, result } : call)),
          },
        },
      };
    });
  },

  clearRunning() {
    set((state) => ({
      byId: Object.fromEntries(
        Object.entries(state.byId).map(([id, activity]) => [
          id,
          {
            ...activity,
            running: [],
            recent: activity.recent.map((call): DataSourceCall =>
              call.result === 'running' ? { ...call, result: 'aborted' } : call,
            ),
          },
        ]),
      ),
    }));
  },

  reset() {
    set({ byId: {} });
  },
}));

const RESULTS: ReadonlySet<unknown> = new Set<CallResult>(['ok', 'error', 'aborted']);

/** Applies a data source message from `static/preview_toolbar.js`. Returns whether it was one. */
export function handleDataSourceMessage(data: Record<string, unknown>): boolean {
  const store = useDataSourceActivityStore.getState();
  if (data.type === 'data-source-reset') {
    store.reset();
    return true;
  }
  if (data.type !== 'data-source-call') return false;
  const { dataSourceId, callId, phase, params, result } = data;
  if (typeof dataSourceId !== 'string' || typeof callId !== 'string') return true;
  if (phase === 'start') {
    store.startCall(dataSourceId, callId, typeof params === 'string' ? params : null);
  } else if (phase === 'end' && RESULTS.has(result)) {
    store.endCall(dataSourceId, callId, result as CallResult);
  }
  return true;
}
