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
 * Resolve the full (transitive) set of groups a user belongs to.
 *
 * Real AD/ADAPI computes nested membership server-side (via
 * LDAP_MATCHING_RULE_IN_CHAIN); we mirror that here so callers never have to
 * deal with DNs or `memberOf` nesting themselves. Membership is matched by the
 * user's `distinguishedName` against each group's `member` list, then expanded
 * upward through `memberOf`.
 */
function resolveUserGroups(user: AdUser, groups: AdGroup[]): AdGroup[] {
  const byDn = new Map(groups.map((g) => [g.distinguishedName, g]));
  const resolved = new Map<string, AdGroup>();
  const queue: AdGroup[] = groups.filter((g) =>
    g.member?.includes(user.distinguishedName),
  );
  while (queue.length > 0) {
    const group = queue.shift()!;
    if (resolved.has(group.distinguishedName)) continue;
    resolved.set(group.distinguishedName, group);
    for (const parentDn of group.memberOf ?? []) {
      const parent = byDn.get(parentDn);
      if (parent && !resolved.has(parentDn)) queue.push(parent);
    }
  }
  return [...resolved.values()];
}

const server = Fastify({ logger: false });
await server.register(cors);

server.get<{ Querystring: { samAccountName?: string; customFilter?: string } }>(
  "/api/users",
  async (request) => {
    const users = await loadJson<AdUser[]>(usersFile);
    const term = searchTerm(request.query.samAccountName);
    return users.filter((u) => matchesTerm(u, term));
  },
);

server.get<{ Querystring: { samAccountName?: string; customFilter?: string } }>(
  "/api/groups",
  async (request) => {
    const groups = await loadJson<AdGroup[]>(groupsFile);
    const term = searchTerm(request.query.samAccountName);
    return groups.filter((g) => matchesTerm(g, term));
  },
);

/**
 * Return every group the given user is a member of, transitively (nested groups
 * included). Lookup is by `sAMAccountName` — the identifier carried in the auth
 * token's UniqueID claim. Returns 404 if no such user exists.
 */
server.get<{ Params: { sAMAccountName: string } }>(
  "/api/users/:sAMAccountName/groups",
  async (request, reply) => {
    const [users, groups] = await Promise.all([
      loadJson<AdUser[]>(usersFile),
      loadJson<AdGroup[]>(groupsFile),
    ]);
    const target = request.params.sAMAccountName.toLowerCase();
    const user = users.find(
      (u) => u.sAMAccountName.toLowerCase() === target,
    );
    if (!user) {
      return reply.status(404).send({ error: "user not found" });
    }
    return resolveUserGroups(user, groups);
  },
);

try {
  await server.listen({ port: PORT, host: "0.0.0.0" });
  console.log(`ADAPI mock listening on http://localhost:${PORT}`);
} catch (err) {
  server.log.error(err);
  process.exit(1);
}
