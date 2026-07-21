#!/usr/bin/env node
// Cross-platform "free these TCP ports" helper. Replaces the OS-specific
// lsof / Get-NetTCPConnection branches that used to live in the Makefile so
// the same `pnpm` scripts work on macOS, Linux and Windows.
//
// Usage: node scripts/kill-ports.mjs 8000 5173 6001
import { execSync } from "node:child_process";

const isWindows = process.platform === "win32";
const ports = process.argv.slice(2).filter((p) => /^\d+$/.test(p));

if (ports.length === 0) {
  console.error("kill-ports: no ports given");
  process.exit(0);
}

/** Return the set of PIDs listening on `port` (empty when nothing is bound). */
function listenersOn(port) {
  try {
    if (isWindows) {
      // netstat is on every Windows; parse the PID column of LISTENING rows.
      const out = execSync(`netstat -ano -p tcp`, { encoding: "utf8" });
      const pids = new Set();
      for (const line of out.split(/\r?\n/)) {
        const m = line.match(/^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$/);
        if (m && m[1] === String(port)) pids.add(m[2]);
      }
      return [...pids];
    }
    const out = execSync(`lsof -nP -iTCP:${port} -sTCP:LISTEN -t`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return [...new Set(out.split(/\s+/).filter(Boolean))];
  } catch {
    // Non-zero exit just means "nothing is listening" — treat as empty.
    return [];
  }
}

function kill(pid) {
  try {
    if (isWindows) {
      // /T kills the whole tree (uvicorn/vite spawn children), /F forces it.
      execSync(`taskkill /PID ${pid} /F /T`, { stdio: "ignore" });
    } else {
      execSync(`kill -9 ${pid}`, { stdio: "ignore" });
    }
  } catch {
    /* already gone — ignore */
  }
}

for (const port of ports) {
  const pids = listenersOn(port);
  if (pids.length > 0) {
    console.log(`Stopping listener PID(s) ${pids.join(", ")} on port ${port}`);
    pids.forEach(kill);
  }
}
