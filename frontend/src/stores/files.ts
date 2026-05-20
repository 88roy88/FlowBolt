import { create } from 'zustand';
import type { FileEntry } from '../types';
import * as api from '../services/api';
import { useSessionStore } from './session';
import { queryClient } from '../lib/queryClient';

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
  createFile: (path: string, content?: string) => Promise<void>;
  uploadFiles: (basePath: string, files: File[]) => Promise<void>;
  renamePath: (oldPath: string, newPath: string) => Promise<void>;
  deletePath: (path: string) => Promise<void>;
  /** Incremented on every file save — used to trigger preview refresh. */
  saveVersion: number;
  refreshOpenFiles: () => Promise<void>;
  clearPendingReveal: () => void;
  reset: () => void;
}

function storageKey(projectId: string) { return `editor-tabs:${projectId}`; }

function normalizePath(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/\/$/, '');
  return normalized.startsWith('/') ? normalized : `/${normalized}`;
}

function joinPath(basePath: string, childPath: string): string {
  const base = normalizePath(basePath);
  const trimmed = childPath.trim().replace(/\\/g, '/').replace(/^\/+/, '').replace(/\/+$/, '');
  if (!trimmed) return base;
  return base === '/' ? `/${trimmed}` : `${base}/${trimmed}`;
}

function collectFilePaths(tree: FileEntry[]): Set<string> {
  const out = new Set<string>();
  const stack = [...tree];
  while (stack.length > 0) {
    const current = stack.pop();
    if (!current) continue;
    if (current.is_directory) {
      if (current.children?.length) stack.push(...current.children);
      continue;
    }
    out.add(normalizePath(current.path));
  }
  return out;
}

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
    const normalizedPath = normalizePath(path);
    const state = get();
    if (state.openFiles.has(normalizedPath)) {
      set((s) => ({
        activeFilePath: normalizedPath,
        pendingRevealLine: line ?? null,
        pendingRevealColumn: column ?? null,
        revealVersion: s.revealVersion + 1,
      }));
      return;
    }
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    try {
      const content = await queryClient.fetchQuery({
        queryKey: ['file', projectId, normalizedPath],
        queryFn: () => api.fetchFileContent(projectId, normalizedPath),
      });
      set((s) => {
        const next = new Map(s.openFiles);
        next.set(normalizedPath, content);
        return {
          openFiles: next,
          activeFilePath: normalizedPath,
          pendingRevealLine: line ?? null,
          pendingRevealColumn: column ?? null,
          revealVersion: s.revealVersion + 1,
        };
      });
      const paths = [...get().openFiles.keys()];
      const existing = collectFilePaths(get().fileTree);
      const persistable = paths.filter((p) => existing.has(normalizePath(p)));
      saveEditorTabs(persistable, normalizedPath);
    } catch (err) {
      console.error('Failed to open file:', normalizedPath, err);
    }
  },

  closeFile(path: string) {
    const normalizedPath = normalizePath(path);
    set((state) => {
      const next = new Map(state.openFiles);
      next.delete(normalizedPath);
      let activePath = state.activeFilePath;
      if (activePath === normalizedPath) {
        const keys = Array.from(next.keys());
        activePath = keys.length > 0 ? keys[keys.length - 1] : null;
      }
      return { openFiles: next, activeFilePath: activePath };
    });
    const paths = [...get().openFiles.keys()];
    const existing = collectFilePaths(get().fileTree);
    const persistable = paths.filter((p) => existing.has(normalizePath(p)));
    const active = get().activeFilePath;
    saveEditorTabs(persistable, active && existing.has(normalizePath(active)) ? normalizePath(active) : null);
  },

  setActiveFile(path: string) {
    const normalizedPath = normalizePath(path);
    set({ activeFilePath: normalizedPath });
    const paths = [...get().openFiles.keys()];
    const existing = collectFilePaths(get().fileTree);
    const persistable = paths.filter((p) => existing.has(normalizePath(p)));
    saveEditorTabs(persistable, existing.has(normalizedPath) ? normalizedPath : null);
  },

  updateFileContent(path: string, content: string) {
    const normalizedPath = normalizePath(path);
    set((state) => {
      const next = new Map(state.openFiles);
      next.set(normalizedPath, content);
      return { openFiles: next };
    });
    const projectId = useSessionStore.getState().projectId;
    if (projectId) {
      queryClient.setQueryData(['file', projectId, normalizedPath], content);
    }
  },

  async refreshOpenFiles() {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    // Mark all project files stale without triggering background refetches;
    // each open file is re-fetched directly below.
    void queryClient.invalidateQueries({ queryKey: ['file', projectId], refetchType: 'none' });
    const openFiles = get().openFiles;
    for (const path of openFiles.keys()) {
      try {
        const content = await api.fetchFileContent(projectId, path);
        get().updateFileContent(path, content);
      } catch {}
    }
  },

  async saveFile(path: string) {
    const normalizedPath = normalizePath(path);
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const content = get().openFiles.get(normalizedPath);
    if (content !== undefined) {
      await api.saveFileContent(projectId, normalizedPath, content);
      set((s) => ({ saveVersion: s.saveVersion + 1 }));
    }
  },

  async createFile(path: string, content = '') {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const normalizedPath = normalizePath(path);
    await api.createFileEntry(projectId, normalizedPath, content);
    await get().loadFileTree();
    await get().openFile(normalizedPath);
  },

  async uploadFiles(basePath: string, files: File[]) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId || files.length === 0) return;
    const normalizedBasePath = normalizePath(basePath);
    for (const file of files) {
      const relativePath = file.webkitRelativePath && file.webkitRelativePath.trim().length > 0
        ? file.webkitRelativePath
        : file.name;
      const uploadPath = joinPath(normalizedBasePath, relativePath);
      await api.uploadFileEntry(projectId, uploadPath, file);
    }
    await get().loadFileTree();
  },

  async renamePath(oldPath: string, newPath: string) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const normalizedOldPath = normalizePath(oldPath);
    const normalizedNewPath = normalizePath(newPath);
    await api.renameFileEntry(projectId, normalizedOldPath, normalizedNewPath);

    set((state) => {
      const nextOpenFiles = new Map<string, string>();
      for (const [path, content] of state.openFiles.entries()) {
        const normalizedExistingPath = normalizePath(path);
        if (normalizedExistingPath === normalizedOldPath || normalizedExistingPath.startsWith(`${normalizedOldPath}/`)) {
          const suffix = normalizedExistingPath.slice(normalizedOldPath.length);
          nextOpenFiles.set(`${normalizedNewPath}${suffix}`, content);
        } else {
          nextOpenFiles.set(normalizedExistingPath, content);
        }
      }
      let nextActivePath = state.activeFilePath;
      if (nextActivePath) {
        const normalizedActive = normalizePath(nextActivePath);
        if (normalizedActive === normalizedOldPath || normalizedActive.startsWith(`${normalizedOldPath}/`)) {
          const suffix = normalizedActive.slice(normalizedOldPath.length);
          nextActivePath = `${normalizedNewPath}${suffix}`;
        } else {
          nextActivePath = normalizedActive;
        }
      }
      return { openFiles: nextOpenFiles, activeFilePath: nextActivePath };
    });

    await get().loadFileTree();
    const paths = [...get().openFiles.keys()];
    const existing = collectFilePaths(get().fileTree);
    const persistable = paths.filter((p) => existing.has(normalizePath(p)));
    const active = get().activeFilePath;
    saveEditorTabs(persistable, active && existing.has(normalizePath(active)) ? normalizePath(active) : null);
  },

  async deletePath(path: string) {
    const projectId = useSessionStore.getState().projectId;
    if (!projectId) return;
    const normalizedPath = normalizePath(path);
    await api.deleteFileEntry(projectId, normalizedPath);

    set((state) => {
      const nextOpenFiles = new Map<string, string>();
      for (const [openPath, content] of state.openFiles.entries()) {
        const normalizedOpenPath = normalizePath(openPath);
        if (normalizedOpenPath === normalizedPath || normalizedOpenPath.startsWith(`${normalizedPath}/`)) {
          // Keep deleted entries open in tabs; UI marks them as deleted.
          nextOpenFiles.set(normalizedOpenPath, content);
          continue;
        }
        nextOpenFiles.set(normalizedOpenPath, content);
      }

      const activePath = state.activeFilePath ? normalizePath(state.activeFilePath) : null;
      return { openFiles: nextOpenFiles, activeFilePath: activePath };
    });

    await get().loadFileTree();
    const paths = [...get().openFiles.keys()];
    const existing = collectFilePaths(get().fileTree);
    const persistable = paths.filter((p) => existing.has(normalizePath(p)));
    const active = get().activeFilePath;
    saveEditorTabs(persistable, active && existing.has(normalizePath(active)) ? normalizePath(active) : null);
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
