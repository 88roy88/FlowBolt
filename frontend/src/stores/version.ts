import { create } from 'zustand';
import type { Message, OnDirty, WSMessage } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { useChatStore } from './chat';
import { useFilesStore } from './files';
import { useErrorStore } from './errors';
import { isReplaying } from './chatHandlers';

type PendingDirtyOp = { op: 'preview' | 'restore'; commit_sha: string };

interface VersionState {
  versions: string[];
  previewingVersion: string | null;
  pendingDirtyOp: PendingDirtyOp | null;
  previewVersion: (commit_sha: string, on_dirty?: OnDirty) => void;
  exitPreview: () => void;
  restoreVersion: (commit_sha: string, on_dirty?: OnDirty) => Promise<boolean>;
  saveVersion: () => void;
  resolveDirtyOp: (on_dirty: OnDirty) => void;
  dismissDirtyOp: () => void;
  reset: () => void;
}

export function formatVersionLabel(versions: string[], commit_sha: string): string {
  const idx = versions.indexOf(commit_sha);
  return idx >= 0 ? `v${idx}` : commit_sha.slice(0, 7);
}

let pendingRestore: ((ok: boolean) => void) | null = null;

let lastAttempt: PendingDirtyOp | null = null;

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

function refreshEditorFiles() {
  void useFilesStore.getState().loadFileTree();
  void useFilesStore.getState().refreshOpenFiles();
}

export const useVersionStore = create<VersionState>((set, get) => ({
  versions: [],
  previewingVersion: null,
  pendingDirtyOp: null,

  previewVersion(commit_sha: string, on_dirty?: OnDirty) {
    lastAttempt = { op: 'preview', commit_sha };
    if (!sendVersionAction({ type: 'preview_version', commit_sha, on_dirty })) return;
    useErrorStore.getState().suppressPreviewErrors(true);
  },

  exitPreview() {
    sendVersionAction({ type: 'exit_preview' });
  },

  restoreVersion(commit_sha: string, on_dirty?: OnDirty) {
    settlePendingRestore(false);
    lastAttempt = { op: 'restore', commit_sha };
    if (!sendVersionAction({ type: 'restore_version', commit_sha, on_dirty })) return Promise.resolve(false);
    return new Promise<boolean>((resolve) => {
      pendingRestore = resolve;
    });
  },

  saveVersion() {
    if (!sendVersionAction({ type: 'save_version' })) return;
    useFilesStore.setState({ hasUnsavedEdits: false }); // a clean tree commits nothing, so nothing would clear it
  },

  resolveDirtyOp(on_dirty: OnDirty) {
    const pending = get().pendingDirtyOp;
    set({ pendingDirtyOp: null });
    if (!pending) return;
    if (pending.op === 'preview') get().previewVersion(pending.commit_sha, on_dirty);
    else void get().restoreVersion(pending.commit_sha, on_dirty);
  },

  dismissDirtyOp() {
    set({ pendingDirtyOp: null });
    settlePendingRestore(false);
  },

  reset() {
    set({ versions: [], previewingVersion: null, pendingDirtyOp: null });
    useErrorStore.getState().suppressPreviewErrors(false);
  },
}));

function userEditMessage(sha: string, files: string[]): Message {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    agentCard: { type: 'user_edit', files },
    version: sha,
  };
}

function handleVersionCommitted(msg: { commit_sha: string; author?: string; files?: string[] }) {
  const sha = msg.commit_sha;
  useVersionStore.setState((s) => ({
    versions: s.versions.includes(sha) ? s.versions : [...s.versions, sha],
  }));
  useFilesStore.setState({ hasUnsavedEdits: false });

  if (msg.author === 'user') {
    useChatStore.setState((s) => ({ messages: [...s.messages, userEditMessage(sha, msg.files ?? [])] }));
    return;
  }

  const lastAssistantIdx = useChatStore.getState().messages.findLastIndex((m) => m.role === 'assistant');
  if (lastAssistantIdx < 0) return; // v0 scaffold — no message yet
  useChatStore.setState((s) => ({
    messages: s.messages.map((m, i) => (i === lastAssistantIdx ? { ...m, version: sha } : m)),
  }));
}

function handleVersionPreviewActive(msg: { commit_sha: string; is_latest: boolean }) {
  const previewingVersion = msg.is_latest ? null : msg.commit_sha;
  useVersionStore.setState({ previewingVersion });
  useErrorStore.getState().suppressPreviewErrors(previewingVersion !== null);
  if (!isReplaying()) refreshEditorFiles();
}

function handleVersionRestored(msg: { commit_sha: string }) {
  const versions = useVersionStore.getState().versions;
  const shaIdx = versions.indexOf(msg.commit_sha);
  const keep = new Set(versions.slice(0, shaIdx + 1));
  useChatStore.setState((s) => {
    const last = s.messages.findLastIndex((m) => m.version && keep.has(m.version));
    return { messages: s.messages.slice(0, last + 1) };
  });
  useVersionStore.setState({
    previewingVersion: null,
    versions: shaIdx >= 0 ? versions.slice(0, shaIdx + 1) : versions,
  });
  useErrorStore.getState().suppressPreviewErrors(false);
  refreshEditorFiles();
  settlePendingRestore(true);
}

function handleVersionError(msg: { message: string; code: string }) {
  settlePendingRestore(false);
  if (msg.code === 'dirty_workspace') {
    useVersionStore.setState({ pendingDirtyOp: lastAttempt });
    useFilesStore.setState({ hasUnsavedEdits: true }); // the tree may be dirty from the terminal, which we never see
    useErrorStore.getState().suppressPreviewErrors(false);
    return;
  }
  useFilesStore.setState({ hasUnsavedEdits: true });
  const previewing = useVersionStore.getState().previewingVersion !== null;
  useErrorStore.getState().suppressPreviewErrors(previewing);
  useErrorStore.getState().pushError({ source: 'connection', message: msg.message });
}

const versionRoutes: { [M in WSMessage as M['type']]?: (msg: M) => void } = {
  version_committed: handleVersionCommitted,
  version_preview_active: handleVersionPreviewActive,
  version_restored: handleVersionRestored,
  version_error: handleVersionError,
  error: () => settlePendingRestore(false),
};

export function handleVersionMessage(msg: WSMessage) {
  (versionRoutes[msg.type] as ((m: WSMessage) => void) | undefined)?.(msg);
}
