import { create } from 'zustand';
import type { FileEntry } from '../types';
import * as api from '../services/api';
import { useSessionStore } from './session';

interface FilesState {
  loadedProjectId: string | null;
  fileTree: FileEntry[];
  openFiles: Map<string, string>;
  activeFilePath: string | null;
  pendingRevealLine: number | null;
  pendingRevealColumn: number | null;
  revealVersion: number;
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

function storageKey(projectId: string) { return `editor-tabs:${projectId}`; }

function saveEditorTabs(openPaths: string[], activePath: string | null) {
  const projectId = useSessionStore.getState().projectId;
  if (!projectId) return;
  try {
    localStorage.setItem(storageKey(projectId), JSON.stringify({ openPaths, activePath }));
  } catch {}
}

function loadEditorTabs(projectId: string): { openPaths: string[]; activePath: string | null } | null {
  try {
    const raw = localStorage.getItem(storageKey(projectId));
    if (raw) {
      const { openPaths, activePath } = JSON.parse(raw);
      if (Array.isArray(openPaths)) return { openPaths, activePath };
    }
  } catch {}
  return null;
}

/** Bumps on every loadFileTree call so in-flight responses from older requests are ignored. */
let _fileTreeRequestSerial = 0;

export const useFilesStore = create<FilesState>((set, get) => ({
  loadedProjectId: null,
  fileTree: [],
  openFiles: new Map(),
  activeFilePath: null,
  pendingRevealLine: null,
  pendingRevealColumn: null,
  revealVersion: 0,
  saveVersion: 0,

  async loadFileTree() {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const state = get();
    if (state.loadedProjectId !== projectId) {
      // Hard project boundary: never keep tabs/models between different projects.
      set({
        loadedProjectId: projectId,
        fileTree: [],
        openFiles: new Map(),
        activeFilePath: null,
        pendingRevealLine: null,
        pendingRevealColumn: null,
      });
    }

    const requestId = ++_fileTreeRequestSerial;
    const tree = await api.fetchFileTree(projectId);
    // Drop stale responses (newer loadFileTree started, or project switched).
    if (requestId !== _fileTreeRequestSerial) return;
    if (useSessionStore.getState().projectId !== projectId) return;
    set((s) => ({ fileTree: tree, saveVersion: s.saveVersion + 1 }));

    if (requestId !== _fileTreeRequestSerial) return;
    if (useSessionStore.getState().projectId !== projectId) return;

    // Restore previously open tabs if none are open yet
    if (get().openFiles.size === 0) {
      const saved = loadEditorTabs(projectId);
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
      set((s) => ({ activeFilePath: path, pendingRevealLine: line ?? null, pendingRevealColumn: column ?? null, revealVersion: s.revealVersion + 1 }));
      return;
    }
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    try {
      const content = await api.fetchFileContent(projectId, path);
      set((s) => {
        const next = new Map(s.openFiles);
        next.set(path, content);
        return { openFiles: next, activeFilePath: path, pendingRevealLine: line ?? null, pendingRevealColumn: column ?? null, revealVersion: s.revealVersion + 1 };
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
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const openFiles = get().openFiles;
    for (const path of openFiles.keys()) {
      try {
        const content = await api.fetchFileContent(projectId, path);
        get().updateFileContent(path, content);
      } catch {}
    }
  },

  async saveFile(path: string) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const content = get().openFiles.get(path);
    if (content !== undefined) {
      await api.saveFileContent(projectId, path, content);
      set((s) => ({ saveVersion: s.saveVersion + 1 }));
    }
  },

  clearPendingReveal() {
    set({ pendingRevealLine: null, pendingRevealColumn: null });
  },

  reset() {
    set({
      loadedProjectId: null,
      fileTree: [],
      openFiles: new Map(),
      activeFilePath: null,
      pendingRevealLine: null,
      pendingRevealColumn: null,
      revealVersion: 0,
    });
  },
}));
