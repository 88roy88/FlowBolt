import { create } from 'zustand';

export type CallResult = 'ok' | 'error' | 'aborted';

export interface DataSourceCall {
  id: string;
  startedAt: number;
  params: string | null;
  paramsCut: boolean;
  result: CallResult | 'running';
}

export interface DataSourceActivity {
  count: number;
  running: string[];
  lastResult: 'ok' | 'error' | null;
  /** Newest first. */
  recent: DataSourceCall[];
}

interface DataSourceActivityState {
  byId: Record<string, DataSourceActivity>;
  startCall: (dataSourceId: string, callId: string, params: string | null, paramsCut?: boolean) => void;
  endCall: (dataSourceId: string, callId: string, result: CallResult) => void;
  clearRunning: () => void;
  reset: () => void;
}

export const MAX_RECENT_CALLS = 20;

const IDLE: DataSourceActivity = { count: 0, running: [], lastResult: null, recent: [] };

export const useDataSourceActivityStore = create<DataSourceActivityState>((set) => ({
  byId: {},

  startCall(dataSourceId, callId, params, paramsCut = false) {
    set((state) => {
      const activity = state.byId[dataSourceId] ?? IDLE;
      const call: DataSourceCall = { id: callId, startedAt: Date.now(), params, paramsCut, result: 'running' };
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

export function handleDataSourceMessage(data: Record<string, unknown>): boolean {
  const store = useDataSourceActivityStore.getState();
  if (data.type === 'data-source-reset') {
    store.reset();
    return true;
  }
  if (data.type !== 'data-source-call') return false;
  const { dataSourceId, callId, phase, params, paramsCut, result } = data;
  if (typeof dataSourceId !== 'string' || typeof callId !== 'string') return true;
  if (phase === 'start') {
    store.startCall(dataSourceId, callId, typeof params === 'string' ? params : null, paramsCut === true);
  } else if (phase === 'end' && RESULTS.has(result)) {
    store.endCall(dataSourceId, callId, result as CallResult);
  }
  return true;
}
