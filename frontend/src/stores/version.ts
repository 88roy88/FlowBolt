import { create } from 'zustand';
import type { WSMessage } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { useChatStore } from './chat';
import { useFilesStore } from './files';
import { isReplaying } from './chatHandlers';

interface VersionState {
  versions: string[];
  previewingVersion: string | null;
  previewVersion: (commit_sha: string) => void;
  exitPreview: () => void;
  restoreVersion: (commit_sha: string) => Promise<boolean>;
  reset: () => void;
}

export function formatVersionLabel(versions: string[], commit_sha: string): string {
  const idx = versions.indexOf(commit_sha);
  return idx >= 0 ? `v${idx}` : commit_sha.slice(0, 7);
}

let pendingRestore: ((ok: boolean) => void) | null = null;

function settlePendingRestore(ok: boolean) {
  pendingRestore?.(ok);
  pendingRestore = null;
}

function sendVersionAction(message: WSMessage): boolean {
  const projectId = useSessionStore.getState().projectId;
  if (!projectId) return false;
  getChatSocket(projectId).send(message);
  return true;
}

function reloadFilesAfterVersionChange() {
  void useFilesStore.getState().loadFileTree();
  useFilesStore.setState((s) => ({ saveVersion: s.saveVersion + 1 }));
  void useFilesStore.getState().refreshOpenFiles();
}

export const useVersionStore = create<VersionState>((set) => ({
  versions: [],
  previewingVersion: null,

  previewVersion(commit_sha: string) {
    sendVersionAction({ type: 'preview_version', commit_sha });
  },

  exitPreview() {
    sendVersionAction({ type: 'exit_preview' });
  },

  restoreVersion(commit_sha: string) {
    settlePendingRestore(false);
    if (!sendVersionAction({ type: 'restore_version', commit_sha })) return Promise.resolve(false);
    return new Promise<boolean>((resolve) => {
      pendingRestore = resolve;
    });
  },

  reset() {
    set({ versions: [], previewingVersion: null });
  },
}));

function handleVersionCommitted(msg: { commit_sha: string }) {
  const sha = msg.commit_sha;
  const lastAssistantIdx = useChatStore.getState().messages.findLastIndex((m) => m.role === 'assistant');
  useVersionStore.setState((s) => ({
    versions: s.versions.includes(sha) ? s.versions : [...s.versions, sha],
  }));
  if (lastAssistantIdx < 0) return; // v0 scaffold — no message yet
  useChatStore.setState((s) => ({
    messages: s.messages.map((m, i) => (i === lastAssistantIdx ? { ...m, version: sha } : m)),
  }));
}

function handleVersionPreviewActive(msg: { commit_sha: string; is_latest: boolean }) {
  const previewingVersion = msg.is_latest ? null : msg.commit_sha;
  useVersionStore.setState({ previewingVersion });
  if (!isReplaying()) reloadFilesAfterVersionChange();
}

function handleVersionRestored(msg: { commit_sha: string }) {
  const sha = msg.commit_sha;
  useChatStore.setState((s) => {
    const idx = s.messages.findIndex((m) => m.version === sha);
    return { messages: idx >= 0 ? s.messages.slice(0, idx + 1) : s.messages };
  });
  useVersionStore.setState((s) => {
    const shaIdx = s.versions.indexOf(sha);
    return {
      previewingVersion: null,
      versions: shaIdx >= 0 ? s.versions.slice(0, shaIdx + 1) : s.versions,
    };
  });
  reloadFilesAfterVersionChange();
  settlePendingRestore(true);
}

const versionRoutes: { [M in WSMessage as M['type']]?: (msg: M) => void } = {
  version_committed: handleVersionCommitted,
  version_preview_active: handleVersionPreviewActive,
  version_restored: handleVersionRestored,
  error: () => settlePendingRestore(false),
};

export function handleVersionMessage(msg: WSMessage) {
  (versionRoutes[msg.type] as ((m: WSMessage) => void) | undefined)?.(msg);
}
