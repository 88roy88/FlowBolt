# Running the backend on multiple pods

## Why routing matters

A project's live state exists only in the backend pod that started it: the Vite dev server, the terminal PTY, the dev-server log tail, the in-memory chat event queues and a running agent turn. If a project's requests reach different pods, each pod starts its own dev server for it.

So **every request for a project must reach the same pod.** Database coordination (advisory locks, the agent-run heartbeat, stored events) already works across pods; only routing needed to change.

## How it works

The frontend nginx (`frontend/nginx/default.conf.template`) picks the backend pod from the URL:

```
Route ─► nginx (any replica) ─┬─ URL has a project ID ─► hash(project_id) ─► always the same pod for that project
                              └─ no project ID ────────► hash(random key) ─► any pod
```

> **Note — the rule for new routes:** anything that touches a sandbox or workspace **must** live under `/api/projects/{project_id}/…`, `/ws/projects/{project_id}/…` or `/api/preview/{project_id}/…`, or nginx can't send it to the project's pod. Nothing else may sit directly under those prefixes.

### Workspaces are set up on first use

Creating a project (`POST /api/projects`) has no project ID in the URL yet, so it can land on any pod. It only inserts the database row. The workspace (template scaffold, `pnpm install`, git repo) is set up by the pod that serves the project, on its first request (`SandboxManager.wake_sandbox`). Until that finishes, the preview shows "Preparing…".

## Why a StatefulSet with one `server` line per pod

The hash maps each project onto nginx's list of backend servers, so that list has to stay stable. Hashing over a Deployment's pod IPs breaks whenever pods are added, removed or restarted: the IPs change and most projects jump to another pod. (A single `server <headless-service> resolve;` line, resolving to every pod's IP, is worse: open-source nginx silently falls back to round-robin.) A **StatefulSet**'s pods have stable names, each with its own DNS name through the headless Service, so nginx gets one line per pod:

```nginx
upstream backend {
    zone backend 64k;
    hash $project_key consistent;
    server base-backend-0.base-backend-headless.base.svc.cluster.local:8000 resolve;
    server base-backend-1.base-backend-headless.base.svc.cluster.local:8000 resolve;
}
```

The effect:

- A project maps to a pod **name**, so restarts and deploys don't change the mapping. `resolve` (re-checked every 5 s) picks up the pod's new IP.
- While a pod is down, its projects move to the next pod and return when it's back.
- Changing the replica count moves only ~1/N of projects, because the hashing is consistent.

### The script that generates the `server` lines: `frontend/nginx/16-backend-servers.envsh`

- **What it does:** builds the `server` lines from env vars (see [Inputs](#inputs)) and exports them as `BACKEND_SERVERS`. The template inserts them with `${BACKEND_SERVERS}`.
- **Who runs it:** the nginx image's entrypoint (`/docker-entrypoint.sh`). On every container start, before nginx starts, the entrypoint runs each file in `/docker-entrypoint.d/` in name order. The image already ships `15-local-resolvers.envsh` (fills `NGINX_LOCAL_RESOLVERS` from `/etc/resolv.conf`) and `20-envsubst-on-templates.sh` (renders `/etc/nginx/templates/*.template` into `conf.d`). The Dockerfile copies our script in between.
- **Why `16-` and `.envsh`:** it has to run before `20-envsubst…`, which needs `BACKEND_SERVERS`. `.envsh` files are *sourced* rather than executed, so the `export` reaches the later envsubst step. A `.sh` file would run in its own process and the variable would be lost.
- `frontend/nginx/.gitattributes` keeps the script at LF line endings, since a CRLF checkout on Windows would break `sh`.

## Inputs

Set **exactly one** of these two options on the frontend. Neither, both, or half of the second one makes the container exit at startup with an error saying what to set.

**One backend pod:**

| Variable | Meaning |
|---|---|
| `BACKEND_INTERNAL_URL` | The backend Service's URL, e.g. `http://base-backend.base:8000`. Becomes a single `server base-backend.base:8000;` line. |

This is the setup from before multi-pod. Projects aren't pinned to a pod, so it's only correct while the backend runs **one pod**. The line has no `resolve`: a Service's IP doesn't change, and without `resolve` nginx looks the name up once at startup through the system resolver, so short names like `base-backend.base` work.

**Several backend pods:**

| Variable | Meaning |
|---|---|
| `BACKEND_STATEFULSET` | StatefulSet name. Its pods are `<name>-0` … `<name>-(N-1)` (Kubernetes naming). |
| `BACKEND_SERVICE` | The StatefulSet's headless Service, **fully qualified**: nginx's resolver ignores `search` domains. |
| `BACKEND_REPLICAS` | Must match the StatefulSet's replica count. |
| `BACKEND_PORT` | Optional, default `8000`. |

## Deployment requirements

- **nginx ≥ 1.27.3** for `resolve` in an upstream block.
- **Backend as a StatefulSet** with `serviceName` pointing at a headless Service:

  ```yaml
  apiVersion: v1
  kind: Service
  metadata:
    name: base-backend-headless
  spec:
    clusterIP: None
    selector:
      app: base-backend
    ports:
      - port: 8000
  ---
  apiVersion: apps/v1
  kind: StatefulSet
  metadata:
    name: base-backend
  spec:
    serviceName: base-backend-headless
    replicas: 2
    # selector, pod template, workspace volume: as in the current Deployment
  ```

  Keep the existing `base-backend` Service for everything else.
- **Frontend env:** `BACKEND_STATEFULSET=base-backend`, `BACKEND_SERVICE=base-backend-headless.<namespace>.svc.cluster.local`, `BACKEND_REPLICAS=<n>`. When you scale the backend, update `BACKEND_REPLICAS` too.

## Known limitations

- **Moves leave a stale sandbox.** When a project changes pods (its pod restarted, or the replica count changed), open WebSockets stay on the old pod until the client reconnects. The old pod's dev server is reaped after `SANDBOX_IDLE_TTL_SECONDS`.
- **No live events after a move.** An agent turn running on the old pod finishes there. A client that reconnected to the new pod sees its result only in history, because chat events are delivered in-memory.
- **The first request to a down pod waits.** It takes ~3 s (the connect timeout) before nginx moves on, and again after `fail_timeout` (10 s) while the pod stays down.
- **Admin maintenance doesn't hot-reload.** Its file changes are written from a random pod, so they don't show up in a running dev server until it restarts.

## Testing locally

`docker compose up` runs one backend, with `BACKEND_INTERNAL_URL: http://backend:8000`.

To try two, run two backend services named `backend-0` and `backend-1` (for example a compose override where both use `extends: { service: backend }`). Then set `BACKEND_STATEFULSET: backend` and `BACKEND_REPLICAS: 2` on `frontend`, in place of `BACKEND_INTERNAL_URL`, and leave `BACKEND_SERVICE` unset. Check the backend logs or `GET /api/admin/debug/sandboxes` (admin only) on each container to confirm that each project's sandbox runs on exactly one of them.
