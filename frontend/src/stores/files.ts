import { create } from 'zustand';
import type { FileEntry } from '../types';
import * as api from '../services/api';
import { useSessionStore } from './session';

interface FilesState {
  fileTree: FileEntry[];
  openFiles: Map<string, string>;
  activeFilePath: string | null;
  pendingRevealLine: number | null;
  pendingRevealColumn: number | null;
  loadFileTree: () => Promise<void>;
  openFile: (path: string, line?: number, column?: number) => Promise<void>;
  closeFile: (path: string) => void;
  setActiveFile: (path: string) => void;
  updateFileContent: (path: string, content: string) => void;
  saveFile: (path: string) => Promise<void>;
  /** Incremented on every file save — used to trigger preview refresh. */
  saveVersion: number;
  refreshOpenFiles: () => Promise<void>;
  clearPendingReveal: () => void;
  reset: () => void;
}

function storageKey(sessionId: string) { return `editor-tabs:${sessionId}`; }

function saveEditorTabs(openPaths: string[], activePath: string | null) {
  const sessionId = useSessionStore.getState().sessionId;
  if (!sessionId) return;
  try {
    localStorage.setItem(storageKey(sessionId), JSON.stringify({ openPaths, activePath }));
  } catch {}
}

function loadEditorTabs(sessionId: string): { openPaths: string[]; activePath: string | null } | null {
  try {
    const raw = localStorage.getItem(storageKey(sessionId));
    if (raw) {
      const { openPaths, activePath } = JSON.parse(raw);
      if (Array.isArray(openPaths)) return { openPaths, activePath };
    }
  } catch {}
  return null;
}

export const useFilesStore = create<FilesState>((set, get) => ({
  fileTree: [],
  openFiles: new Map(),
  activeFilePath: null,
  pendingRevealLine: null,
  pendingRevealColumn: null,
  saveVersion: 0,

  async loadFileTree() {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    const tree = await api.fetchFileTree(sessionId);
    set((s) => ({ fileTree: tree, saveVersion: s.saveVersion + 1 }));

    // Restore previously open tabs if none are open yet
    if (get().openFiles.size === 0) {
      const saved = loadEditorTabs(sessionId);
      if (saved) {
        for (const path of saved.openPaths) {
          await get().openFile(path);
        }
        if (saved.activePath && get().openFiles.has(saved.activePath)) {
          set({ activeFilePath: saved.activePath });
        }
      }
    }
  },

  async openFile(path: string, line?: number, column?: number) {
    const state = get();
    if (state.openFiles.has(path)) {
      set({ activeFilePath: path, pendingRevealLine: line ?? null, pendingRevealColumn: column ?? null });
      return;
    }
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    try {
      const content = await api.fetchFileContent(sessionId, path);
      set((s) => {
        const next = new Map(s.openFiles);
        next.set(path, content);
        return { openFiles: next, activeFilePath: path, pendingRevealLine: line ?? null, pendingRevealColumn: column ?? null };
      });
      saveEditorTabs([...get().openFiles.keys()], path);
    } catch (err) {
      console.error('Failed to open file:', path, err);
    }
  },

  closeFile(path: string) {
    set((state) => {
      const next = new Map(state.openFiles);
      next.delete(path);
      let activePath = state.activeFilePath;
      if (activePath === path) {
        const keys = Array.from(next.keys());
        activePath = keys.length > 0 ? keys[keys.length - 1] : null;
      }
      return { openFiles: next, activeFilePath: activePath };
    });
    saveEditorTabs([...get().openFiles.keys()], get().activeFilePath);
  },

  setActiveFile(path: string) {
    set({ activeFilePath: path });
    saveEditorTabs([...get().openFiles.keys()], path);
  },

  updateFileContent(path: string, content: string) {
    set((state) => {
      const next = new Map(state.openFiles);
      next.set(path, content);
      return { openFiles: next };
    });
  },

  async refreshOpenFiles() {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    const openFiles = get().openFiles;
    for (const path of openFiles.keys()) {
      try {
        const content = await api.fetchFileContent(sessionId, path);
        get().updateFileContent(path, content);
      } catch {}
    }
  },

  async saveFile(path: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    const content = get().openFiles.get(path);
    if (content !== undefined) {
      await api.saveFileContent(sessionId, path, content);
      set((s) => ({ saveVersion: s.saveVersion + 1 }));
    }
  },

  clearPendingReveal() {
    set({ pendingRevealLine: null, pendingRevealColumn: null });
  },

  reset() {
    set({ fileTree: [], openFiles: new Map(), activeFilePath: null, pendingRevealLine: null, pendingRevealColumn: null });
  },
}));
