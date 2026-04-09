/**
 * Playwright globalSetup for e2e-v2.
 *
 * Spawns (in order):
 *   1. Mock LLM server  — Python/uvicorn, port 9999
 *   2. FLAPI mock        — Node/Express,   port 4000
 *   3. Backend           — Python/uvicorn, port 8000  (AIB_AI_BASE_URL → mock LLM)
 *   4. Frontend          — Vite dev server, port 5173
 *
 * Waits for each service to be ready, then writes PIDs to
 * /tmp/aib-e2e-v2-pids.json for globalTeardown.
 */

import { spawn, spawnSync, ChildProcess } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as http from 'http';
import { Client as MinioClient } from 'minio';

const ROOT = path.resolve(__dirname, '..');
const BACKEND_DIR = path.join(ROOT, 'backend');
const FRONTEND_DIR = path.join(ROOT, 'frontend');
const FLAPI_DIR = path.join(ROOT, 'mocks', 'flapi-mock');
const LLM_MOCK_SCRIPT = path.join(ROOT, 'mocks', 'llm-mock', 'server.py');

// Use os.tmpdir() so paths work on Linux (/tmp), macOS (/private/tmp), and Windows (%TEMP%)
const TMP = os.tmpdir();
const PIDS_FILE = path.join(TMP, 'aib-e2e-v2-pids.json');
const DB_FILE   = path.join(TMP, 'aib-e2e-v2.db');
const WORKSPACE_DIR = path.join(TMP, 'aib-e2e-v2-workspaces');
const MINIO_DATA_DIR = path.join(TMP, 'aib-e2e-v2-minio');

// MinIO settings (S3-compatible local object storage for Publish tests)
const MINIO_PORT = 9900;
const MINIO_ROOT_USER = 'minioadmin';
const MINIO_ROOT_PASSWORD = 'minioadmin';
const S3_BUCKET = 'e2e-test-bucket';

/** true when the `minio` binary is present on PATH */
function minioAvailable(): boolean {
  return spawnSync('minio', ['--version'], { stdio: 'ignore' }).status === 0;
}

// Backend env vars — point LLM calls at mock server, use temp SQLite DB
const BACKEND_ENV: NodeJS.ProcessEnv = {
  ...process.env,
  AIB_DB_SCHEME: 'sqlite',
  AIB_DB_NAME: DB_FILE,
  AIB_DB_USER: 'e2e',
  AIB_DB_PASSWORD: 'e2e',
  AIB_DB_HOST: 'localhost',
  AIB_DB_PORT: '5432',
  AIB_AI_BASE_URL: 'http://localhost:9999',
  AIB_AI_MODEL: 'openai/gpt-4o',
  AIB_AI_API_KEY: 'mock-key',
  AIB_FLAPI_BASE_URL: 'http://localhost:6001',
  // Allow CI to override sandbox mode (local | namespaced). Default: local.
  AIB_SANDBOX_MODE: process.env.AIB_SANDBOX_MODE ?? 'local',
  AIB_WORKSPACE_BASE_DIR: WORKSPACE_DIR,
  AIB_AUTH_REQUIRE_JWT: 'false',
  // Disable Langfuse tracing
  AIB_LANGFUSE_PUBLIC_KEY: '',
  AIB_LANGFUSE_SECRET_KEY: '',
  // S3 / MinIO (populated after MinIO availability check below)
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function waitForHttp(url: string, timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http
        .get(url, (res) => {
          if (res.statusCode && res.statusCode < 500) {
            resolve();
          } else if (Date.now() < deadline) {
            setTimeout(attempt, 500);
          } else {
            reject(new Error(`Service at ${url} not ready within ${timeoutMs}ms`));
          }
        })
        .on('error', () => {
          if (Date.now() < deadline) {
            setTimeout(attempt, 500);
          } else {
            reject(new Error(`Service at ${url} not ready within ${timeoutMs}ms`));
          }
        });
    };
    attempt();
  });
}

function spawnService(
  label: string,
  cmd: string,
  args: string[],
  options: { cwd: string; env?: NodeJS.ProcessEnv }
): ChildProcess {
  console.log(`[e2e-v2] Starting ${label}: ${cmd} ${args.join(' ')}`);
  const proc = spawn(cmd, args, {
    cwd: options.cwd,
    env: options.env ?? process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
    // Do NOT use detached — we want them as children so SIGTERM works
  });

  proc.stdout?.on('data', (d: Buffer) => process.stdout.write(`[${label}] ${d}`));
  proc.stderr?.on('data', (d: Buffer) => process.stderr.write(`[${label}] ${d}`));
  proc.on('exit', (code) => {
    if (code !== null && code !== 0) {
      console.error(`[e2e-v2] ${label} exited with code ${code}`);
    }
  });

  return proc;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default async function globalSetup() {
  console.log('[e2e-v2] Starting services...');

  // Kill any stale processes still holding our ports from a previous crashed run
  const E2E_PORTS = [4000, 5173, 8000, 9900, 9999];
  for (const port of E2E_PORTS) {
    try {
      const result = spawnSync(
        process.platform === 'win32'
          ? 'powershell'
          : 'bash',
        process.platform === 'win32'
          ? ['-Command', `Get-NetTCPConnection -LocalPort ${port} -State Listen -EA SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }`]
          : ['-c', `lsof -ti :${port} 2>/dev/null | xargs -r kill -9 2>/dev/null || true`],
        { stdio: 'ignore' }
      );
    } catch { /* port was free */ }
  }
  // Brief pause to let OS release port bindings before we re-bind
  await new Promise(r => setTimeout(r, 500));

  // Clean up stale state
  if (fs.existsSync(DB_FILE)) fs.unlinkSync(DB_FILE);
  if (fs.existsSync(PIDS_FILE)) fs.unlinkSync(PIDS_FILE);
  if (fs.existsSync(WORKSPACE_DIR)) {
    fs.rmSync(WORKSPACE_DIR, { recursive: true, force: true });
  }
  fs.mkdirSync(WORKSPACE_DIR, { recursive: true });

  // Run alembic migrations so the DB schema exists before the backend starts
  console.log('[e2e-v2] Running alembic migrations...');
  const migrate = spawnSync(
    'uv',
    ['run', '--no-sync', 'alembic', 'upgrade', 'head'],
    { cwd: BACKEND_DIR, env: BACKEND_ENV, stdio: 'inherit' }
  );
  if (migrate.status !== 0) {
    throw new Error(`alembic upgrade head failed (exit ${migrate.status})`);
  }
  console.log('[e2e-v2] ✓ Migrations applied');

  const procs: ChildProcess[] = [];

  function killAll() {
    for (const proc of procs) {
      try { proc.kill('SIGTERM'); } catch { /* already dead */ }
    }
  }

  // Register a process and track it for cleanup on failure
  function track(proc: ChildProcess): ChildProcess {
    procs.push(proc);
    return proc;
  }

  try {
    // 0. MinIO (optional S3-compatible storage for Publish tests)
    //    If the `minio` binary is not on PATH we skip S3 tests gracefully — the test
    //    will detect MINIO_AVAILABLE=false and skip the Publish assertions.
    let minioProc: ChildProcess | null = null;
    const hasMinio = minioAvailable();
    if (hasMinio) {
      fs.mkdirSync(MINIO_DATA_DIR, { recursive: true });
      minioProc = track(spawnService('minio', 'minio', ['server', `--address=:${MINIO_PORT}`, '--console-address=:9901', MINIO_DATA_DIR], {
        cwd: ROOT,
        env: { ...process.env, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD },
      }));
      // Inject S3 env into backend
      Object.assign(BACKEND_ENV, {
        AIB_S3_ENDPOINT_URL: `http://localhost:${MINIO_PORT}`,
        AIB_S3_ACCESS_KEY: MINIO_ROOT_USER,
        AIB_S3_SECRET_KEY: MINIO_ROOT_PASSWORD,
        AIB_S3_BUCKET_NAME: S3_BUCKET,
        AIB_S3_STORAGE_CLASS: 'STANDARD',  // MinIO doesn't support STANDARD_IA
      });
    } else {
      console.log('[e2e-v2] ℹ minio not found — S3/Publish tests will be skipped');
    }

    // 1. Mock LLM server — slow down responses in headed mode so phases are watchable
    const llmEnv = process.env.HEADED === '1'
      ? { ...process.env, RESPONSE_DELAY_MS: '1500' }
      : process.env;
    const llmProc = track(spawnService('llm-mock', 'uv', ['run', LLM_MOCK_SCRIPT, '--port', '9999'], {
      cwd: ROOT,
      env: llmEnv,
    }));

    // 2. FLAPI mock
    const flapiProc = track(spawnService('flapi-mock', 'pnpm', ['start'], {
      cwd: FLAPI_DIR,
    }));

    // 3. Backend
    const backendProc = track(spawnService(
      'backend',
      'uv',
      [
        'run',
        '--no-sync',
        'python',
        '-m',
        'uvicorn',
        '--app-dir',
        'src',
        'flow44.main:app',
        '--host',
        '0.0.0.0',
        '--port',
        '8000',
        '--log-level',
        'info',
      ],
      { cwd: BACKEND_DIR, env: BACKEND_ENV }
    ));

    // 4. Frontend (Vite dev server)
    // Inject auth provider URL so the e2e test can exercise the sign-in flow.
    // /sso?autoLogin=true auto-submits the mock SSO form after 500 ms.
    const frontendProc = track(spawnService('frontend', 'pnpm', ['dev'], {
      cwd: FRONTEND_DIR,
      env: {
        ...process.env,
        VITE_AUTH_PROVIDER_URL: 'http://localhost:6001/sso?autoLogin=true',
        VITE_AUTH_USE_IFRAME: 'true',
        VITE_AUTH_STORAGE_KEY: 'Auth',
      },
    }));

    // Wait for all services to be ready
    console.log('[e2e-v2] Waiting for services to be ready...');
    const readyChecks: Promise<void>[] = [
      waitForHttp('http://localhost:9999/health', 30_000).then(() =>
        console.log('[e2e-v2] ✓ Mock LLM server ready')
      ),
      waitForHttp('http://localhost:6001', 30_000).then(() =>
        console.log('[e2e-v2] ✓ FLAPI mock ready')
      ),
      waitForHttp('http://localhost:8000/health', 90_000).then(() =>
        console.log('[e2e-v2] ✓ Backend ready')
      ),
      waitForHttp('http://localhost:5173', 60_000).then(() =>
        console.log('[e2e-v2] ✓ Frontend ready')
      ),
    ];
    if (hasMinio) {
      readyChecks.push(
        waitForHttp(`http://localhost:${MINIO_PORT}/minio/health/live`, 30_000).then(async () => {
          // Create the test bucket once MinIO is up
          const mc = new MinioClient({
            endPoint: 'localhost', port: MINIO_PORT, useSSL: false,
            accessKey: MINIO_ROOT_USER, secretKey: MINIO_ROOT_PASSWORD,
          });
          const exists = await mc.bucketExists(S3_BUCKET);
          if (!exists) await mc.makeBucket(S3_BUCKET, '');
          console.log(`[e2e-v2] ✓ MinIO ready (bucket: ${S3_BUCKET})`);
        })
      );
    }
    await Promise.all(readyChecks);

    // Persist PIDs for teardown (globalTeardown will kill them after tests)
    const pids: Record<string, number> = {
      llm: llmProc.pid!,
      flapi: flapiProc.pid!,
      backend: backendProc.pid!,
      frontend: frontendProc.pid!,
    };
    if (hasMinio && minioProc) pids.minio = minioProc.pid!;
    fs.writeFileSync(PIDS_FILE, JSON.stringify({ ...pids, minioAvailable: hasMinio }, null, 2));
    // Expose MinIO availability as a process env so tests can skip S3 assertions
    process.env.E2E_MINIO_AVAILABLE = hasMinio ? '1' : '0';
    console.log('[e2e-v2] All services ready. PIDs:', pids);
  } catch (err) {
    console.error('[e2e-v2] Setup failed — killing all spawned processes');
    killAll();
    throw err;
  }
}
