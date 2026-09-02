# Directory Mock

A local TypeScript + Fastify mock of the directory service, serving two search
endpoints backed by static JSON fixtures. Run with `tsx` (same stack as
`flapi-mock`).

## Endpoints

| Method | Path                    | Description                                  |
| ------ | ----------------------- | -------------------------------------------- |
| GET    | `/users?samAccountName=*<value>*&customFilter=(\|(displayName=*<value>*) (mail=*<value>*))` | Search users, matching `<value>` (case-insensitive substring) against `sAMAccountName`, `displayName` or `mail`. Each record carries a `memberOf` array of the user's (transitive) group DNs. |
| GET    | `/groups?samAccountName=*<value>*&customFilter=(\|(displayName=*<value>*) (mail=*<value>*))` | Search groups, matching `<value>` against `sAMAccountName`, `displayName` or `mail`. |

The search is optional — omitting the query returns every record. The mock
recovers the term from the `*`-wrapped `samAccountName` param and ORs it across
`sAMAccountName`, `displayName` and `mail`, mimicking the real LDAP filter.

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
pnpm dev          # serves on http://localhost:6666
```

Override the port with `MOCK_PORT`:

```sh
MOCK_PORT=7000 pnpm dev
```

### Examples

```sh
curl "http://localhost:6666/users?samAccountName=*dje*&customFilter=(|(displayName=*dje*)%20(mail=*dje*))"
curl "http://localhost:6666/groups?samAccountName=*le*&customFilter=(|(displayName=*le*)%20(mail=*le*))"
```
