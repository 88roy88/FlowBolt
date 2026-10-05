import { describe, it, expect } from 'vitest';
import { lockCode } from '../workspaceLock';

describe('lockCode', () => {
  it('applies read-only, running, previewing, then writable precedence', () => {
    const cases = [
      { canWrite: false, agentBusy: true, previewing: true, expected: 'read_only' },
      { canWrite: true, agentBusy: true, previewing: true, expected: 'run_active' },
      { canWrite: true, agentBusy: false, previewing: true, expected: 'previewing' },
      { canWrite: true, agentBusy: false, previewing: false, expected: null },
    ] as const;

    for (const { canWrite, agentBusy, previewing, expected } of cases) {
      expect(lockCode(canWrite, agentBusy, previewing)).toBe(expected);
    }
  });
});
