/**
 * Playwright globalTeardown for e2e-v2.
 * Kills all processes spawned by globalSetup.
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

const TMP = os.tmpdir();
const PIDS_FILE = path.join(TMP, 'aib-e2e-v2-pids.json');
const MINIO_DATA_DIR = path.join(TMP, 'aib-e2e-v2-minio');

function killPid(pid: number, label: string) {
  try {
    process.kill(pid, 'SIGTERM');
    console.log(`[e2e-v2] Stopped ${label} (PID ${pid})`);
  } catch {
    // Already dead or permission denied — ignore
  }
}

export default async function globalTeardown() {
  if (!fs.existsSync(PIDS_FILE)) {
    console.warn('[e2e-v2] No PIDs file found, skipping teardown');
    return;
  }

  const data = JSON.parse(fs.readFileSync(PIDS_FILE, 'utf8'));

  for (const [label, value] of Object.entries(data)) {
    if (typeof value === 'number') killPid(value, label);
  }

  fs.unlinkSync(PIDS_FILE);

  // Clean up MinIO data dir (it can be large due to uploaded HTML bundles)
  if (fs.existsSync(MINIO_DATA_DIR)) {
    fs.rmSync(MINIO_DATA_DIR, { recursive: true, force: true });
  }

  console.log('[e2e-v2] Teardown complete');
}
