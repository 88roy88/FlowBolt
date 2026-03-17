import { create } from 'zustand';

export interface AppError {
  id: string;
  source: 'build' | 'runtime';
  message: string;
  file?: string;
  line?: number;
  column?: number;
  stack?: string;
  timestamp: number;
}

interface ErrorState {
  errors: AppError[];
  pushError: (error: Omit<AppError, 'id' | 'timestamp'>) => void;
  dismissError: (id: string) => void;
  clearErrors: () => void;
}

export const useErrorStore = create<ErrorState>((set, get) => ({
  errors: [],

  pushError(partial) {
    const existing = get().errors;
    // Deduplicate by file + line (stable across re-renders with different timestamps)
    const isDupe = existing.some((e) => {
      if (e.file && partial.file && e.file === partial.file && e.line && partial.line && e.line === partial.line) return true;
      if (e.message === partial.message && e.file === partial.file) return true;
      return false;
    });
    if (isDupe) return;

    const error: AppError = {
      ...partial,
      id: crypto.randomUUID(),
      timestamp: Date.now(),
    };

    // Keep at most 5 errors
    set((s) => ({
      errors: [...s.errors.slice(-4), error],
    }));
  },

  dismissError(id) {
    set((s) => ({ errors: s.errors.filter((e) => e.id !== id) }));
  },

  clearErrors() {
    set({ errors: [] });
  },
}));
