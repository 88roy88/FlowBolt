# ADAPI Mock

A local TypeScript + Fastify mock of the ADAPI service, serving two search
endpoints backed by static JSON fixtures. Run with `tsx` (same stack as
`flapi-mock`).

## Endpoints

| Method | Path                    | Description                                  |
| ------ | ----------------------- | -------------------------------------------- |
| GET    | `/api/users?samAccountName=*<value>*&customFilter=(\|(displayName=*<value>*) (mail=*<value>*))` | Search users, matching `<value>` (case-insensitive substring) against `sAMAccountName`, `displayName` or `mail`. |
| GET    | `/api/groups?samAccountName=*<value>*&customFilter=(\|(displayName=*<value>*) (mail=*<value>*))` | Search groups, matching `<value>` against `sAMAccountName`, `displayName` or `mail`. |
| GET    | `/api/users/<sAMAccountName>/groups` | Every group the user belongs to, transitively (nested groups included). `404` if the user does not exist. |

The search is optional — omitting the query returns every record. The mock
recovers the term from the `*`-wrapped `samAccountName` param and ORs it across
`sAMAccountName`, `displayName` and `mail`, mimicking the real LDAP filter.

The user-groups endpoint resolves nested membership server-side (mirroring AD's
`LDAP_MATCHING_RULE_IN_CHAIN`): it matches the user's `distinguishedName`
against each group's `member` list, then walks up `memberOf`. Callers get the
full group set without ever handling DNs. Lookup is by `sAMAccountName` — the
identifier carried in the auth token's UniqueID claim.

## Data

- `mock-data/users.json` — user records (Active Directory user shape).
- `mock-data/groups.json` — group records. Each group **references users** from
  `mock-data/users.json` via:
  - `managedBy` — DN of the managing user.
  - `member` — DNs of member users.
  - `memberOf` — DNs of parent groups (references other groups).

Edit these files and the changes are picked up on the next request (no restart
needed).

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
curl "http://localhost:6666/api/users?samAccountName=*dje*&customFilter=(|(displayName=*dje*)%20(mail=*dje*))"
curl "http://localhost:6666/api/groups?samAccountName=*le*&customFilter=(|(displayName=*le*)%20(mail=*le*))"
```
