# Architecture

How BuildApp works, end to end, as merged on `develop`. Every behavior cites the code that implements it. Backend paths are relative to `backend/src/flow44/`, frontend paths to `frontend/src/`.

Visual walkthrough: [`architecture.html`](architecture.html), which shows §1–3 and §5–7 as diagrams. Open it in a browser. A hosted copy is at [BuildApp Architecture](https://claude.ai/artifact/UF8J7hSu14NGk4rdGnCJBB).

## 1. System map

| Part | What it is | Entry point |
| --- | --- | --- |
| Browser IDE | React 19 + Zustand stores (client state) + React Query (new data fetching), Monaco editor, xterm terminal, preview iframe | `App.tsx`, `stores/`, `services/websocket/` |
| Backend | One FastAPI process: REST under `/api`, WebSockets under `/ws`, published apps under `/shared` | `main.py` |
| Postgres | Projects, members, chat messages, agent events, paused turns, run heartbeats; also advisory locks and `LISTEN/NOTIFY` | `db/` |
| Sandbox | One workspace dir + one Vite dev server per project, run by the backend process | `sandbox/` |
| S3 / MinIO | Published app builds under `published/{project_id}/` | `integrations/s3.py` |
| LLM | Every call goes through `ai/core/provider.py` (LiteLLM) | `complete_chat` `ai/core/provider.py:52`, `complete_chat_with_tools` `:82`, `stream_chat` `:111` |
| FLAPI | External data sources the generated app can query | `integrations/flapi/client.py:30` |
| Directory | Users and groups for sharing and platform access | `integrations/directory/` |
| Opik | Optional LLM tracing | `ai/core/opik_utils.py` |

**Startup** (`lifespan`, `main.py:53`): init the DB → `reconcile_workspaces` kills orphan dev servers and deletes workspaces of deleted projects (`main.py:65`, `sandbox/manager.py:121`) → start the idle reaper, heartbeat reaper and abort listener → set up the S3 bucket. Shutdown suspends every sandbox.

**Routes** (`main.py:115-143`): `auth_routes` require a valid token; `public_routes` (models, `/shared`) don't; `ws_auth_routes` (chat, terminal, server log, errors) validate the token on the handshake.

**One process.** Prod runs a single backend pod. Two kinds of state live only in that process's memory: live event subscriptions (`_channels`, `db/events.py:17`) and running sandboxes with their ports (`SandboxManager._sandboxes`, `sandbox/manager.py:21`). Everything else is in Postgres, the workspace disk or S3.

## 2. Lifecycle of a chat turn

A turn is one agent run started by a chat WebSocket message. At most one turn runs per project.

1. **Connect.** `/ws/chat/{project_id}` (`api/chat.py:234`) requires `write` permission. It wakes the sandbox (`api/chat.py:246`), subscribes to the project's live events, and forwards each one to the socket.
2. **Dispatch.** Incoming `type` decides the run (`api/chat.py:280-423`):

   | WS message | Starts |
   | --- | --- |
   | `message` | `AgentRouter.handle_message` (see §3) |
   | `plan_response` `accept` | `ExecuteAgent.run` |
   | `plan_response` `modify` | `PlanAgent.rebuild_with_feedback` |
   | `interview_response` `submit`/`skip` | `AgentRouter.resume_interview` |
   | `fix_error` | `FixErrorAgent.run` |
   | `abort` | `run_abort.request_abort` (no new run) |
   | anything else | `versioning.handle_action` (see §6) |

3. **Claim.** `_start_turn` (`api/chat.py:192`) → `_claim_run` → `versioning.begin_turn` (`services/versioning/service.py:152`). Under the project's workspace lock it refuses when a run is active, the workspace is previewing an old version, or there are unsaved user edits. Then `try_claim_run` (`db/heartbeat.py:49`) upserts the `agent_run_heartbeat` row only if the existing one is stale. The lock is released after the claim; for the rest of the run, the fresh heartbeat row is what marks the project busy (`is_run_active`, `db/heartbeat.py:78`). A refused check sends a `version_error`, such as "Can't edit while the AI is working" (`services/versioning/service.py:26`). Losing the claim race to a concurrent turn sends "An agent is already running for this project" (`api/chat.py:46`).
4. **Prepare.** Only after a successful claim: save the user message, or clear the paused turn being resumed (`api/chat.py:308`).
5. **Run.** `_run_agent_safe` (`api/chat.py:139`) runs the agent as a background task, held in `_RUNNING` so it isn't garbage-collected (`api/chat.py:44`). `_heartbeat_until_done` (`api/chat.py:87`) touches the heartbeat every `AGENT_RUN_STALE_TIMEOUT / 4` (15 s by default) and enforces `AGENT_RUN_TIMEOUT` (1800 s) (`config.py:34-35`).
6. **End.** Exactly one of:
   - **Finished or failed:** `commit_turn` (`services/versioning/service.py:238`) commits whatever the agent wrote. A failure (timeout, context window exceeded, exception) first emits `phase: idle` plus an `error` event.
   - **Aborted:** rollback. `discard_agent_response` (`services/versioning/service.py:212`) resets the workspace to the last commit and deletes the turn's events and messages. For Execute and resumed interviews, `on_abort` re-pauses the plan or interview so the user can try again (`api/chat.py:347`, `:378`).

   Then the heartbeat row is cleared and a transient `run_released` or `turn_aborted` event is sent.

**Abort** (`services/run_abort.py:41`) sends `pg_notify('run_abort', project_id)`. The abort listener holds a `LISTEN` connection and wakes the watcher in `_heartbeat_until_done`, which cancels the run. If the listener is down, the abort is delivered in-process.

**Crashed runs.** The heartbeat reaper sweeps every `AGENT_RUN_STALE_TIMEOUT / 2` and deletes stale heartbeats, emitting `phase: idle` and "Agent run was interrupted" for each (`db/heartbeat.py:83`).

## 3. Agents

```
message ──► AgentRouter ─┬─ new project + interview mode ─► Interview ─┬─ questions ─► pause awaiting_interview
                         │                                             └─ none ──────► Plan
                         ├─ new project ──────────────────────────────────────────────► Plan ─► pause awaiting_approval
                         └─ existing project ─────────────────────────────────────────► FollowUp

plan_response accept ─► Execute        fix_error ─► FixError
```

**Routing** (`ai/agents/routing.py`). A project is new until it has an `action_complete` event (`ai/agents/routing.py:9`), which Execute, FollowUp and FixError emit at the end of a run. So a project whose first plan was never approved is still new. New projects go to `PlanAgent`, others to `FollowUpAgent` (`ai/agents/routing.py:40`). Interview runs only for a new project whose message was sent with `mode: "interview"` (`api/chat.py:287`, `ai/agents/routing.py:26`). On an existing project the mode is ignored.

**`Flow`** (`ai/core/flow.py`) is the step engine that Plan, Execute and FixError are built on. Each step is an async function `state → state`, and `next_step` is a step name or a function of the state. `run` (`ai/core/flow.py:73`) stops when `next_step` is `None`, and raises `MaxStepsExceededError` once it has run 50 steps (`:87`).

**Paused turns** (`db/paused_turn.py`). Interview and Plan end their run by storing their state in `paused_turns` with phase `awaiting_interview` or `awaiting_approval` (`db/paused_turn.py:8`). The user's reply arrives as a new turn, which loads that state. This is how Execute resumes the plan after approval.

### Interview (`ai/agents/interview/agent.py`)
`ask` (`:65`) fetches data sources if any, then asks the LLM for clarifying questions. With no questions it hands off straight to Plan in the same run. Otherwise it pauses `awaiting_interview` (`:90`) and emits `interview_questions`. `apply_answers` (`:96`) folds the answers into the prompt, and the router continues with Plan or FollowUp.

### Plan (`ai/agents/plan/agent.py`)
Flow (`:48`): `fetch_data_sources` → `design` → `build_overview` → `persist`. It starts at `design` when there are no data sources (`:84`).
- `design` runs the architecture and UX designs in parallel (`:149`). A failed design degrades to an empty model and does not fail the run.
- `build_overview` produces the user-facing plan (`UserPlanOverview`).
- `persist` pauses `awaiting_approval` with the whole `BuildState` (`ai/state.py:12`) and emits `plan_overview` (`:166`).
- **Modify:** `rebuild_with_feedback` (`:175`) regenerates only the overview with the feedback and pauses again (`:200`).

### Execute (`ai/agents/execute/agent.py`)
Flow (`:54`): `build_plan` → `execute_tasks` → `validate` → (`fix_errors` → `validate`)* → `summarize`.
- `build_plan` asks the LLM for a `WorkPlan` of tasks, each with its files and `depends_on`. Dependencies on unknown task ids are dropped.
- `execute_tasks` runs the tasks layer by layer, with each layer in parallel (`:162-163`). `execution_layers` (`ai/agents/execute/models.py:33`) groups tasks whose dependencies are done; a cycle puts all remaining tasks in one final layer (`:43`). Each task streams code (`stream_chat`), parsed by `ActionParser` (`ai/parser.py:49`) and screened by `screen_generated_files` (`ai/file_safety.py:88`). Files outside the task's declared list are rejected (`:393`).
- `validate` runs `npx tsc --noEmit` and `pnpm build` in parallel (`:178`). `run_build_command` (`sandbox/pnpm_mixin.py:67`) reports errors when the output contains "error" or "failed", case-insensitive (`:83`); it doesn't read exit codes.
- `fix_errors` is Execute's own fix loop: one LLM pass that rewrites whole files from the errors. It runs at most `MAX_FIX_ATTEMPTS = 10` times (`:36`, routing at `:65`), then `summarize` runs anyway.
- `summarize` stores the project summary and emits `project_summary`, then `phase: complete` and `action_complete`.

### FollowUp (`ai/agents/followup/agent.py`)
Not a step `Flow`. It's a ReAct tool loop: `ReActFlow.react_loop` (`ai/core/react_flow.py:46`, called at `:202`) calls the LLM with tools, runs the tool calls, and repeats until the model answers in plain text or `MAX_ITERATIONS = 15` is reached (`:25`). Its tools (`_build_tool_executor`, `:63`) are `grep`, `glob`, `read_file`, `write_file` and `edit_file`. It gets the chat history, project summary and file tree as context. A tool call leaked into plain text gets a correction message and another iteration (`ai/core/react_flow.py:94`).

### FixError (`ai/agents/fix_error/agent.py`)
Runs only on a `fix_error` WS message: the user clicks fix on an error toast (`components/errors/ErrorToast.tsx:32`). The error comes from the dev-server log (errors WS, §5) or from runtime and console errors in the preview (`hooks/useErrorCapture.ts`). Flow (`:49`): `discover` (files related to the error) → `generate` (whole files or search/replace edits) → `write` → `validate` (`pnpm build`) → `retry` → `validate` … → `complete`. It retries at most `MAX_RETRY_ATTEMPTS = 3` times (`:28`).

**There are two fix loops:** Execute's internal ×10 rewrite loop after generation, and FixErrorAgent's ×3 loop for errors the user reports.

## 4. Event stream

Agents talk to the browser only through events.

- `emit_event` (`db/events.py:68`) stores the event in `agent_events`, then pushes it to live subscribers.
- `emit_transient` (`db/events.py:81`) only pushes it live and never stores it: streamed file contents, `run_released`, version previews.
- **Reload and replay.** On opening a project the frontend fetches `GET /api/chat/{id}/events` (`api/chat.py:228`) and replays every stored event through the same handler it uses live (`stores/chat.ts:401-437`). Stored events are therefore the source of truth for chat history; the chat messages table is the LLM's conversation memory.
- **Frontend handlers.** `createSendMessageHandler` (`stores/chatHandlers.ts:220`) handles build and follow-up turns; `createFixErrorHandler` (`stores/chatHandlers.ts:160`) handles fix turns.

| Event | Emitted by | UI effect |
| --- | --- | --- |
| `user_message` | chat WS | user bubble (with data sources, selected elements or the fix request) |
| `phase` | all agents, run wrapper | status line: `interviewing`, `designing`, `planning`, `awaiting_approval`, `executing`, `fixing`, `exploring`, `complete`, `idle` … |
| `interview_questions`, `interview_answered` | Interview | question card, then the answers |
| `design_progress` | Plan | architecture/UX progress |
| `plan_overview` | Plan | plan card with accept/modify |
| `plan_accepted`, `task_list`, `task_update` | Execute | task list with live status |
| `followup_step` | FollowUp | tool-call steps |
| `fix_step` | FixError | fix progress card |
| `file` (transient) | Execute, FollowUp, FixError | open editor tabs update live |
| `file_diffs` | FollowUp, FixError | diff summary |
| `text` | FollowUp, FixError | assistant message |
| `project_summary` | Execute | project summary |
| `data_sources_fetched` | Plan | data-source card |
| `version_committed` | versioning | version list entry |
| `error` | anyone | error message |
| `action_complete` | Execute, FollowUp, FixError | ends the turn in the UI |

## 5. Sandbox

**Class.** `PnpmSandbox` (`sandbox/main.py:20`) combines file system, search and pnpm behavior with a platform base. `_get_sandbox_class` (`sandbox/manager.py:47`) picks `PnpmSandboxNamespace` (nsjail) when `SANDBOX_MODE=namespaced`, `PnpmSandboxWindows` on Windows, otherwise `PnpmSandboxUnix`. Prod runs `SANDBOX_MODE=local` on Linux, so it uses `PnpmSandboxUnix`. `local` is the default (`config.py:33`); the repo's `backend/Dockerfile:77` sets `namespaced`, but prod overrides it.

**Lifecycle** (`sandbox/manager.py`):
- **Create** (`:81`): on project creation (`api/projects.py:142`) the template `backend/pnpm-project-template` is copied in, `vite.config.ts` is stamped with the project id and auth settings, `pnpm install` runs (`sandbox/pnpm_mixin.py:35`), and the dev server starts. Then `versioning.ensure_repo` makes the "Version 0" commit (`api/projects.py:151`).
- **Get / wake** (`:57`): first use takes a free port from `SANDBOX_PORT_RANGE_START`–`END` (3501–4501, `config.py:22`) and creates the sandbox object. Wake also starts `pnpm dev --port <port> --strictPort` (`sandbox/pnpm_mixin.py:108`). Every get resets the idle timer (`:72`).
- **Suspend** (`:88`): kills its processes and frees the port, keeping the workspace on disk. The idle reaper suspends sandboxes untouched for `SANDBOX_IDLE_TTL_SECONDS` (300 s) (`sandbox/idle_reaper.py:35`).
- **Destroy**: on project delete, the workspace is deleted after the published files and DB rows (`api/projects.py:184`).

**Preview** (`api/preview.py`). `/api/preview/{id}/proxy/{path}` (`:71`) wakes the sandbox and proxies to `127.0.0.1:<port>`. It serves a self-reloading "Preparing…" or "Waking up…" page while the dev server comes up. HTML responses get the preview toolbar script for users with `write` (`:139`). Vite HMR goes through the WebSocket proxy (`:156`), which holds the workspace lock per message so a version checkout can't send half-written files (`:185`).

**Other per-project sockets**: `/ws/terminal` (PTY; in `local` mode it's limited to system admins, `api/deps.py:213-218`), `/ws/server-log`, and `/ws/errors` (`api/errors.py:21`), which watches `.dev-server.log` for build errors.

## 6. Versioning

Each workspace is its own git repo on branch `main` (`services/versioning/`). Every operation runs under `_locked_workspace` (`services/versioning/service.py:89`): a Postgres advisory lock per project (`db/locks.py:47`). It clears an `index.lock` left by a killed git (`:93`) and creates the repo with "Version 0 — blank scaffold" if it's missing (`:71`).

| Action | What happens | Refused when |
| --- | --- | --- |
| end of turn | `commit_turn` commits everything → `version_committed` (`:238`) | previewing |
| `save_version` | commits the user's own edits as "Your edits" and adds a chat note (`:161`) | run active, previewing |
| `discard_edits` | `reset --hard` + `clean -fd` (`:173`) | run active, previewing |
| `preview_version` | detached checkout of an old commit; the newest one returns to `main` (`:180`) | run active, unsaved edits |
| `exit_preview` | back to `main` | — |
| `restore_version` | moves `main` to that commit and deletes later events and messages (`:200`) | run active, unsaved edits |

Only shas recorded in `version_committed` events are accepted, so raw client input never reaches git.

## 7. Publish

`POST /api/export/{id}/publish` (`api/publish.py:40`, needs `publish`) → `publish_project` (`logic/publish.py:25`):
1. `build_dist` runs `pnpm build` in the sandbox with a relative base and collects `dist/` (`sandbox/operations.py:142`).
2. `deploy_dist` uploads every file to `published/{project_id}/` as public-read (`integrations/s3.py:111`). Files from the previous publish that are no longer present get a deletion tag; a bucket lifecycle rule expires them later (`:144`).
3. The handle is the optional slug (`SLUG_RE`, `logic/publish.py:8`) or the project id, stored on the project.

Serving: `/shared/{handle}/{path}` (`api/shared.py:50`) needs no sign-in. It maps the handle to a project, reads from S3, and falls back to `index.html` for extension-less paths so client-side routes work (`services/shared_service.py:11`). Hashed `assets/` are cached for a year, HTML is `no-cache`, and page loads are counted as page views.

## 8. Data sources

Picking a data source in chat sends its ids with the message.
1. `fetch_and_analyze_data_source` (`ai/agents/analyze_data_source.py:30`) gets the name, usage (sample, queries, params) and summary from FLAPI, then asks the LLM which fields matter. A failed analysis degrades to a basic description and doesn't fail the run.
2. `generate_data_source_files` (`:110`) writes a deterministic, typed TS module `src/dataSources/<Name>.ts` (`ai/codegen/data_source_module.py:40`) plus a `.docs.md`, with no LLM involved. The generated app calls the module; the LLM is told how to use it.
3. The contexts are saved on the project, so FollowUp knows which sources already exist.

## 9. Auth and access

- **Tokens.** An RS256 JWT, verified with `AUTH_JWT_PUBLIC_KEY` (`api/deps.py:85`); the user id is its `…/UniqueID` claim, casefolded. The token is read from the `Authorization` header or the auth cookie (`api/deps.py:72`). WebSockets resolve the user from the cookie (`api/deps.py:299`) and reject the handshake when it's invalid.
- **Project access.** `ProjectDep` (`get_project`, `api/deps.py:221`) loads the project and returns 404 when the user has no permission on it, so private projects don't leak their existence. `WsProjectDep` (`api/deps.py:312`) rejects the handshake with code 1008 instead.
- **Roles** (`auth/permissions.py:40`): viewer `read`; editor `read, write`; publisher `read, publish`; maintainer `read, write, publish, manage_members`. Owners also get `delete`. Roles can be granted to users or directory groups.
- **Admins** are ids in `SYSTEM_ADMIN_IDS` (`api/deps.py:140`). They get the `*_all` permissions, which satisfy the plain ones (`has_permission`, `auth/permissions.py:82`).
- **Platform access** (needed to create projects): admin, an explicit platform user, or a member of a platform group (`api/deps.py:273`).

## 10. Where to start

Reading order:
1. `api/chat.py`: the turn lifecycle; everything else hangs off it.
2. `ai/agents/routing.py`, then `ai/agents/plan/agent.py` and `ai/agents/execute/agent.py`: the build path.
3. `ai/core/flow.py` and `ai/core/react_flow.py`: the two agent engines.
4. `db/events.py` and `frontend/src/stores/chatHandlers.ts`: how the UI hears about it.
5. `services/versioning/service.py` and `sandbox/manager.py`.

Glossary:
- **Turn**: one agent run, claimed by a heartbeat row and committed or rolled back at the end.
- **Paused turn**: Interview or Plan state saved while waiting for the user.
- **Layer**: a set of Execute tasks whose dependencies are all done; they run in parallel.
- **Transient event**: pushed live, never stored, never replayed.
- **Handle**: the slug or project id a published app is served under.
