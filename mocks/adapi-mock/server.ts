import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import Fastify from "fastify";
import cors from "@fastify/cors";
import type { AdGroup, AdUser } from "./types";

const PORT = Number(process.env.MOCK_PORT) || 6666;

const usersFile = fileURLToPath(
  new URL("./mock-data/users.json", import.meta.url),
);
const groupsFile = fileURLToPath(
  new URL("./mock-data/groups.json", import.meta.url),
);

async function loadJson<T>(file: string): Promise<T> {
  return JSON.parse(await readFile(file, "utf8")) as T;
}

// Loaded once at startup — the fixtures don't change while the server runs, so
// there's no need to re-read them on every request. Restart to pick up edits.
const [users, groups] = await Promise.all([
  loadJson<AdUser[]>(usersFile),
  loadJson<AdGroup[]>(groupsFile),
]);

/**
 * The backend queries with `?samAccountName=*term*&customFilter=(|(displayName=*term*)
 * (mail=*term*))`. All three carry the same wildcard-wrapped term, so we recover
 * it from `samAccountName` and match it (case-insensitively) as a substring
 * against `sAMAccountName`, `displayName` and `mail` — mirroring the OR that real
 * ADAPI applies. An empty/missing filter returns every record.
 */
function searchTerm(samAccountName?: string): string {
  // Strip the surrounding LDAP `*` wildcards the backend adds.
  return (samAccountName ?? "").replace(/^\*|\*$/g, "").toLowerCase();
}

function matchesTerm(
  record: { sAMAccountName: string; displayName: string; mail: string },
  term: string,
): boolean {
  if (!term) return true;
  return (
    record.sAMAccountName.toLowerCase().includes(term) ||
    record.displayName.toLowerCase().includes(term) ||
    record.mail.toLowerCase().includes(term)
  );
}

/**
 * Resolve the full (transitive) set of group DNs a user belongs to.
 *
 * Real AD/ADAPI computes nested membership server-side (via
 * LDAP_MATCHING_RULE_IN_CHAIN) and reports it on the user record's `memberOf`,
 * so callers never have to walk the nesting themselves. We mirror that: match
 * the user's `distinguishedName` against each group's `member` list, then expand
 * upward through each group's own `memberOf`, and return the resulting DNs.
 */
function resolveUserGroupDns(user: AdUser, groups: AdGroup[]): string[] {
  const byDn = new Map(groups.map((g) => [g.distinguishedName, g]));
  const resolved = new Set<string>();
  const queue: AdGroup[] = groups.filter((g) =>
    g.member?.includes(user.distinguishedName),
  );
  while (queue.length > 0) {
    const group = queue.shift()!;
    if (resolved.has(group.distinguishedName)) continue;
    resolved.add(group.distinguishedName);
    for (const parentDn of group.memberOf ?? []) {
      const parent = byDn.get(parentDn);
      if (parent && !resolved.has(parentDn)) queue.push(parent);
    }
  }
  return [...resolved];
}

const server = Fastify({ logger: false });
await server.register(cors);

/**
 * User search. Each returned record carries a `memberOf` array of group DNs —
 * the user's full (transitive) group membership — which is how the backend
 * resolves group-based access (`get_user_group_ids` reads it off the match).
 */
server.get<{ Querystring: { samAccountName?: string; customFilter?: string } }>(
  "/users",
  async (request) => {
    const term = searchTerm(request.query.samAccountName);
    return users
      .filter((u) => matchesTerm(u, term))
      .map((u) => ({ ...u, memberOf: resolveUserGroupDns(u, groups) }));
  },
);

server.get<{ Querystring: { samAccountName?: string; customFilter?: string } }>(
  "/groups",
  async (request) => {
    const term = searchTerm(request.query.samAccountName);
    return groups.filter((g) => matchesTerm(g, term));
  },
);

try {
  await server.listen({ port: PORT, host: "0.0.0.0" });
  console.log(`ADAPI mock listening on http://localhost:${PORT}`);
} catch (err) {
  server.log.error(err);
  process.exit(1);
}
