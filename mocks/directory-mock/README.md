# Directory Mock

A local TypeScript + Fastify mock of the directory service, serving two search
endpoints backed by static JSON fixtures. Run with `tsx` (same stack as
`flapi-mock`).

## Endpoints

| Method | Path                    | Description                                  |
| ------ | ----------------------- | -------------------------------------------- |
| GET    | `/users?aNR=<value>` | Search users by Ambiguous Name Resolution: `<value>` is prefix-matched (case-insensitive) against `sAMAccountName`, `displayName`, `givenName`, `sn` and `mail`, and a `first last` value also matches `givenName` + `sn` in either order. Each record carries a `memberOf` array of the user's (transitive) group DNs. |
| GET    | `/users?customFilter=(sAMAccountName=<account>)` | Exact account lookup, used by the backend to resolve a user's groups. |
| GET    | `/groups?customFilter=(&(\|(displayName=*<value>*)(samAccountName=*<value>*))(groupType<=0))` | Search security groups, matching `<value>` (case-insensitive substring) against `displayName` or `sAMAccountName`. |

The search is optional — omitting the query returns every record. For groups,
the mock recovers the term from the `displayName` clause (undoing RFC 4515 `\xx`
escapes) and, when `(groupType<=0)` is present, keeps only security groups
(negative `groupType`), mimicking the real LDAP filter.

Group membership rides on the user record's `memberOf`: the mock resolves nested
membership server-side (mirroring AD's `LDAP_MATCHING_RULE_IN_CHAIN`) by matching
the user's `distinguishedName` against each group's `member` list and walking up
`memberOf`, then returns the resulting group DNs. The backend
(`get_user_group_ids`) reads that array off the matching user, so group grants
are keyed on the DN — no separate membership endpoint.

## Data

- `mock-data/users.json` — user records (Active Directory user shape).
- `mock-data/groups.json` — group records. Each group **references users** from
  `mock-data/users.json` via:
  - `managedBy` — DN of the managing user.
  - `member` — DNs of member users.
  - `memberOf` — DNs of parent groups (references other groups).

The fixtures are loaded once at startup, so restart the server to pick up edits.

## Running

```sh
pnpm install
pnpm dev          # serves on http://localhost:6002
```

Override the port with `MOCK_PORT`:

```sh
MOCK_PORT=7000 pnpm dev
```

### Examples

```sh
curl "http://localhost:6002/users?aNR=dje"
curl "http://localhost:6002/groups?customFilter=(%26(|(displayName=*le*)(samAccountName=*le*))(groupType<=0))"
```
