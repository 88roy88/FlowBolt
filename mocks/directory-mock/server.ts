import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import Fastify from "fastify";
import cors from "@fastify/cors";
import type { AdGroup, AdUser } from "./types";

const PORT = Number(process.env.MOCK_PORT) || 6002;

// Artificial latency so local dev exercises the UI's loading states — the real directory service
// is noticeably slow. Override with MOCK_DELAY_MS=0 to disable.
const DELAY_MS = process.env.MOCK_DELAY_MS !== undefined ? Number(process.env.MOCK_DELAY_MS) : 2000;
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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
 * User search queries with `?aNR=term` — AD's Ambiguous Name Resolution, which
 * prefix-matches the term (case-insensitively) against the naming attributes, and
 * also matches a "first last" term against givenName + sn in either order.
 * An empty/missing term returns every user.
 */
function matchesAnr(user: AdUser, anr: string): boolean {
  const term = anr.trim().toLowerCase();
  if (!term) return true;
  const startsWith = (value: string | undefined, prefix: string) =>
    (value ?? "").toLowerCase().startsWith(prefix);
  if (
    [user.sAMAccountName, user.displayName, user.givenName, user.sn, user.mail].some((v) =>
      startsWith(v, term),
    )
  ) {
    return true;
  }
  const [first, ...rest] = term.split(/\s+/);
  const last = rest.join(" ");
  return (
    last !== "" &&
    ((startsWith(user.givenName, first) && startsWith(user.sn, last)) ||
      (startsWith(user.sn, first) && startsWith(user.givenName, last)))
  );
}

/**
 * Group search queries with `?customFilter=(&(|(displayName=*term*)(samAccountName=*term*))
 * (groupType<=0))`. Recover the term from the displayName clause (undoing the RFC 4515
 * `\xx` escapes the backend applies) and whether only security groups — whose groupType
 * has the sign bit set — were asked for. A missing filter returns every group.
 */
function parseGroupFilter(customFilter?: string): { term: string; securityOnly: boolean } {
  const raw = customFilter?.match(/displayName=\*((?:[^*()\\]|\\[0-9a-f]{2})*)\*/i)?.[1] ?? "";
  const term = raw.replace(/\\([0-9a-f]{2})/gi, (_, hex: string) =>
    String.fromCharCode(parseInt(hex, 16)),
  );
  return { term: term.toLowerCase(), securityOnly: /\(groupType<=0\)/i.test(customFilter ?? "") };
}

/**
 * The auth path resolves a single user's groups with an exact `?customFilter=(sAMAccountName=id)`
 * lookup (no `aNR` param). Pull the value of an `attr=value` clause out of a
 * customFilter, case-folded, or undefined if absent.
 */
function filterValue(customFilter: string | undefined, attr: string): string | undefined {
  const match = customFilter?.match(new RegExp(`${attr}=([^()*]+)`, "i"));
  return match ? match[1].toLowerCase() : undefined;
}

/**
 * Resolve the full (transitive) set of group DNs a user belongs to.
 *
 * The real AD directory service computes nested membership server-side (via
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
server.get<{ Querystring: { aNR?: string; customFilter?: string } }>(
  "/users",
  async (request) => {
    await delay(DELAY_MS);
    const { aNR, customFilter } = request.query;
    // Auth path: an exact `(sAMAccountName=…)` lookup with no `aNR` param — mirror how
    // the backend resolves a single user's groups. Otherwise it's the share/admin
    // free-text search.
    const account = aNR === undefined ? filterValue(customFilter, "sAMAccountName") : undefined;
    const filtered =
      account !== undefined
        ? users.filter((u) => u.sAMAccountName.toLowerCase() === account)
        : users.filter((u) => matchesAnr(u, aNR ?? ""));
    return filtered.map((u) => ({ ...u, memberOf: resolveUserGroupDns(u, groups) }));
  },
);

server.get<{ Querystring: { customFilter?: string } }>(
  "/groups",
  async (request) => {
    await delay(DELAY_MS);
    const { term, securityOnly } = parseGroupFilter(request.query.customFilter);
    return groups.filter(
      (g) =>
        (!securityOnly || Number(g.groupType) <= 0) &&
        (!term ||
          g.displayName.toLowerCase().includes(term) ||
          g.sAMAccountName.toLowerCase().includes(term)),
    );
  },
);

try {
  await server.listen({ port: PORT, host: "0.0.0.0" });
  console.log(`Directory mock listening on http://localhost:${PORT}`);
} catch (err) {
  server.log.error(err);
  process.exit(1);
}
