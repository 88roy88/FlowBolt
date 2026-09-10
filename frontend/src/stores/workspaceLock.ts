import { WRITE_ROLES } from '../types';
import { useSessionStore } from './session';
import { useChatStore } from './chat';
import { useVersionStore } from './version';
import { isAgentAlive } from './chatAgentState';

export type LockCode = 'read_only' | 'run_active' | 'previewing' | null;

export const LOCK_MESSAGES = {
  read_only: 'chat.placeholder.readOnly',
  run_active: 'version.busyTooltip',
  previewing: 'version.previewReadOnly',
} as const;

export function lockCode(canWrite: boolean, agentBusy: boolean, previewing: boolean): LockCode {
  if (!canWrite) return 'read_only';
  if (agentBusy) return 'run_active';
  if (previewing) return 'previewing';
  return null;
}

export function useWorkspaceLock() {
  const role = useSessionStore((s) => s.currentProject?.role);
  const agentBusy = useChatStore(isAgentAlive);
  const previewing = useVersionStore((s) => s.previewingVersion !== null);
  const canWrite = !role || WRITE_ROLES.has(role);
  return { code: lockCode(canWrite, agentBusy, previewing), agentBusy, canWrite };
}

export function workspaceLocked(): LockCode {
  const role = useSessionStore.getState().currentProject?.role;
  const previewing = useVersionStore.getState().previewingVersion !== null;
  return lockCode(!role || WRITE_ROLES.has(role), isAgentAlive(useChatStore.getState()), previewing);
}
