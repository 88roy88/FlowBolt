import { create } from 'zustand';
import type { FileEntry } from '../types';
import * as api from '../services/api';
import { useSessionStore } from './session';

interface FilesState {
  fileTree: FileEntry[];
  openFiles: Map<string, string>;
  activeFilePath: string | null;
  loadFileTree: () => Promise<void>;
  openFile: (path: string) => Promise<void>;
  closeFile: (path: string) => void;
  setActiveFile: (path: string) => void;
  updateFileContent: (path: string, content: string) => void;
  saveFile: (path: string) => Promise<void>;
}

export const useFilesStore = create<FilesState>((set, get) => ({
  fileTree: [],
  openFiles: new Map(),
  activeFilePath: null,

  async loadFileTree() {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    const tree = await api.fetchFileTree(sessionId);
    set({ fileTree: tree });
  },

  async openFile(path: string) {
    const state = get();
    if (state.openFiles.has(path)) {
      set({ activeFilePath: path });
      return;
    }
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    const content = await api.fetchFileContent(sessionId, path);
    set((s) => {
      const next = new Map(s.openFiles);
      next.set(path, content);
      return { openFiles: next, activeFilePath: path };
    });
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
  },

  setActiveFile(path: string) {
    set({ activeFilePath: path });
  },

  updateFileContent(path: string, content: string) {
    set((state) => {
      const next = new Map(state.openFiles);
      next.set(path, content);
      return { openFiles: next };
    });
  },

  async saveFile(path: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;
    const content = get().openFiles.get(path);
    if (content !== undefined) {
      await api.saveFileContent(sessionId, path, content);
    }
  },
}));
