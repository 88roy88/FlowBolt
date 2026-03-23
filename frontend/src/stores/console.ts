import { create } from 'zustand';

export type ConsoleLevel = 'log' | 'warn' | 'error' | 'info';

export interface ConsoleEntry {
  id: string;
  level: ConsoleLevel;
  args: string[];
  file?: string;
  line?: number;
  column?: number;
  timestamp: number;
}

interface ConsoleState {
  entries: ConsoleEntry[];
  push: (level: ConsoleLevel, args: string[], file?: string, line?: number, column?: number) => void;
  clear: () => void;
}

const MAX_ENTRIES = 200;

export const useConsoleStore = create<ConsoleState>((set) => ({
  entries: [],

  push(level, args, file?, line?, column?) {
    set((state) => {
      const entries = [
        ...state.entries,
        { id: crypto.randomUUID(), level, args, file, line, column, timestamp: Date.now() },
      ];
      return { entries: entries.length > MAX_ENTRIES ? entries.slice(-MAX_ENTRIES) : entries };
    });
  },

  clear() {
    set({ entries: [] });
  },
}));
