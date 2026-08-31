import { describe, it, expect } from 'vitest';
import { lockCode } from '../workspaceLock';

describe('lockCode', () => {
  it('reports read_only before anything else', () => {
    expect(lockCode(false, true, true)).toEqual('read_only');
  });

  it('reports run_active before previewing', () => {
    expect(lockCode(true, true, true)).toEqual('run_active');
  });

  it('reports previewing when only previewing', () => {
    expect(lockCode(true, false, true)).toEqual('previewing');
  });

  it('is null when the workspace is writable and idle', () => {
    expect(lockCode(true, false, false)).toBeNull();
  });
});
