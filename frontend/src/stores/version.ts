import { create } from 'zustand';
import type { Message, WSMessage } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { useChatStore } from './chat';
import { useFilesStore } from './files';
import { useErrorStore } from './errors';
import { getTimestamp, isReplaying } from './chatHandlers';

type Attempt =
  | { op: 'preview'; commit_sha: string }
  | { op: 'restore'; commit_sha: string }
  | { op: 'send'; run: () => void };

export type PendingDirtyOp = Attempt & { files?: string[] };
type DirtyResolution = 'save' | 'discard';

interface VersionState {
  versions: string[];
  previewingVersion: string | null;
  pendingDirtyOp: PendingDirtyOp | null;
  dirtyFiles: string[];
  previewVersion: (commit_sha: string) => void;
  exitPreview: () => void;
  restoreVersion: (commit_sha: string) => void;
  saveVersion: () => void;
  discardEdits: () => void;
  resolveDirtyOp: (resolution: DirtyResolution) => void;
  dismissDirtyOp: () => void;
  reset: () => void;
}

export function formatVersionLabel(versions: string[], commit_sha: string): string {
  const idx = versions.indexOf(commit_sha);
  return idx >= 0 ? `v${idx}` : commit_sha.slice(0, 7);
}

let pending: (Attempt & { undo?: () => void }) | null = null;

function settle(ok: boolean) {
  const attempt = pending;
  pending = null;
  if (!ok) attempt?.undo?.();
}

function send(message: WSMessage): boolean {
  const projectId = useSessionStore.getState().projectId;
  if (!projectId) return false;
  getChatSocket(projectId).send(message);
  return true;
}

function issue(attempt: Attempt & { undo?: () => void }, message: WSMessage) {
  settle(false);
  pending = attempt;
  if (!send(message)) settle(false);
}

export function armTurn(run: () => void, undo: () => void) {
  settle(false);
  pending = { op: 'send', run, undo };
}

function refreshEditorFiles() {
  void useFilesStore.getState().loadFileTree();
  void useFilesStore.getState().refreshOpenFiles();
}

export const useVersionStore = create<VersionState>((set, get) => ({
  versions: [],
  previewingVersion: null,
  pendingDirtyOp: null,
  dirtyFiles: [],

  previewVersion(commit_sha: string) {
    issue({ op: 'preview', commit_sha }, { type: 'preview_version', commit_sha });
  },

  exitPreview() {
    send({ type: 'exit_preview' });
  },

  restoreVersion(commit_sha: string) {
    issue({ op: 'restore', commit_sha }, { type: 'restore_version', commit_sha });
  },

  saveVersion() {
    send({ type: 'save_version' });
  },

  discardEdits() {
    send({ type: 'discard_edits' });
  },

  resolveDirtyOp(resolution: DirtyResolution) {
    const refused = get().pendingDirtyOp;
    set({ pendingDirtyOp: null });
    if (!refused) return;
    // Same socket, so the server settles the tree before it reads the retried op.
    if (!send({ type: resolution === 'save' ? 'save_version' : 'discard_edits' })) return;
    if (refused.op === 'send') refused.run();
    else if (refused.op === 'preview') get().previewVersion(refused.commit_sha);
    else get().restoreVersion(refused.commit_sha);
  },

  dismissDirtyOp() {
    set({ pendingDirtyOp: null });
  },

  reset() {
    pending = null;
    set({ versions: [], previewingVersion: null, pendingDirtyOp: null, dirtyFiles: [] });
  },
}));

function userEditMessage(sha: string, files: string[]): Message {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    timestamp: getTimestamp(),
    agentCard: { type: 'user_edit', files },
    version: sha,
  };
}

function handleVersionCommitted(msg: { commit_sha: string; author?: string; files?: string[] }) {
  const sha = msg.commit_sha;
  useVersionStore.setState((s) => ({
    versions: s.versions.includes(sha) ? s.versions : [...s.versions, sha],
  }));

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
  const entering = previewingVersion !== null && useVersionStore.getState().previewingVersion === null;
  useVersionStore.setState({ previewingVersion });
  if (entering) useErrorStore.getState().clearErrors();
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
  useErrorStore.getState().clearErrors();
  refreshEditorFiles();
  settle(true);
}

function handleVersionError(msg: { message: string; code: string; files?: string[] }) {
  const refused = pending;
  settle(false);
  if (msg.code === 'dirty_workspace' && refused) {
    useVersionStore.setState({ pendingDirtyOp: { ...refused, files: msg.files } });
    return;
  }
  useErrorStore.getState().pushError({ source: 'connection', message: msg.message });
}

const versionRoutes: { [M in WSMessage as M['type']]?: (msg: M) => void } = {
  version_committed: handleVersionCommitted,
  version_preview_active: handleVersionPreviewActive,
  version_restored: handleVersionRestored,
  version_error: handleVersionError,
  workspace_dirty: (msg) => useVersionStore.setState({ dirtyFiles: msg.files }),
  error: () => settle(false),
  phase: () => { if (pending?.op === 'send') settle(true); },
};

export function handleVersionMessage(msg: WSMessage) {
  (versionRoutes[msg.type] as ((m: WSMessage) => void) | undefined)?.(msg);
}
