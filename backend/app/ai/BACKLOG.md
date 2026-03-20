# AI Builder Backlog

## ~~B0. Decouple agents from WebSocket — DB as source of truth~~ DONE

**Problem:** Agents take `ws_send` and call it directly. Browser refresh kills the
build. State lives only in memory.

**Goal:** DB is the source of truth. Agents write to DB. WebSocket watches DB.
Browser can disconnect/reconnect freely. Multiple tabs work.

### Architecture

```
┌──────────┐      ┌────────────┐  subscribe   ┌──────────────┐
│ Browser  │◄────►│ WebSocket  │◄────────────►│ Notify       │
│(can drop)│      │ (thin)     │              │ Channel      │
└──────────┘      └─────┬──────┘              │(asyncio.Queue)│
                        │ on connect:          └──────▲───────┘
                        │ read state from DB          │ notify
                        ▼                       ┌─────┴───────┐
                  ┌──────────┐  write    ┌──────┴──────┐
                  │    DB    │◄──────────│   Agent     │
                  │(sqlite)  │           │ (background │
                  └──────────┘           │  task)      │
                                         └─────────────┘
```

### DB schema: agent_events table

```sql
CREATE TABLE agent_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_events_session ON agent_events(session_id, id);
```

Plus add to projects table:
- `agent_phase TEXT` — current phase (idle, designing, executing, etc.)
- `agent_state TEXT` — serialized BuildState JSON (for resume after server restart)

### How it works

**Agent side:**
- `BaseAgent.emit(event)` → INSERT into agent_events + notify channel
- Agent doesn't know about WebSocket
- Agent writes BuildState to DB at phase transitions
- Agent runs as `asyncio.create_task`, not inline in WS handler

**WebSocket side:**
- On connect: `SELECT * FROM agent_events WHERE session_id = ? ORDER BY id` → send all
- Subscribe to in-process notify channel for live updates
- On disconnect: nothing happens (agent keeps running)
- On reconnect: same as connect — read from DB, subscribe to channel

**Plan approval flow:**
- BuildAgent writes `plan_overview` event to DB, sets phase to `awaiting_approval`
- Agent awaits on an `asyncio.Event`
- User clicks accept → WS handler sets flag
- Agent resumes execution

### Migration path
1. Create `agent_events` table + `emit()` helper
2. Create notify channel (dict of queues)
3. Update `BaseAgent`: replace `ws_send` with `emit`
4. Update all agents: `self.ws_send(...)` → `self.emit(...)`
5. Update `chat.py`: start agents as background tasks, WS reads from DB + subscribes
6. Add BuildState persistence to DB for resume
7. Frontend: handle reconnect (re-fetch state on WS open)

---

## B1. Parallel per-file codegen

One LLM call per file in parallel instead of one call per task via bolt XML.

- ~5x faster wall-clock time
- Delete `ActionParser` (177 lines)
- Simpler per-file prompts, better error isolation
- Risk: coherence between sibling files (mitigated by typecheck/fix cycle)

---

## ~~B2. Wire up core framework~~ DONE

---

## B3. Backend code quality fixes

- `api/errors.py` — bound dedup set (memory leak), use async file I/O
- `ai/provider.py` — add retry with exponential backoff
- `models/project.py` — replace 6 repetitive ALTER TABLE blocks with migration helper
- `sandbox/filesystem.py` — use `run_in_executor` for async file I/O

---

## ~~B4. Frontend refactor~~ DONE

---

## B5. FollowUp agent memory management

ReACT loop appends every tool call/result to messages without pruning. Will blow
context limits on longer sessions.

Options: summarize older results, sliding window, truncate large results, token budget.

---

## B6. FollowUp agent case support

Accept `case_ids` in follow-up agent so users can integrate new data sources into
existing projects without starting over.

---

## B7. Rename "package" to "case" in backend

Align backend naming with frontend: `PackageApiClient` → `CaseApiClient`,
`package_id` → `case_id`, etc.

---

## B8. DB connection pooling

Every query opens a fresh `aiosqlite.connect()`. Under concurrent load this is
wasteful and could exhaust resources. Introduce a shared connection or pool.

---

## B9. Preview iframe security

No `sandbox` attribute on the preview iframe — AI-generated code runs with full
browser privileges. Add `sandbox="allow-scripts allow-same-origin"` + CSP headers.

---

## B10. Editor save reliability

- Save debounce can lose edits if component unmounts mid-timer
- No UI feedback when save fails
- Add save status indicator (saved / saving / error)

---

## B11. Health & readiness endpoints

No `/health` or `/ready` endpoint. Backend going down after startup is invisible
to the frontend. Add endpoints for load balancers and k8s probes.

---

## B12. Test coverage

Zero tests. Priority targets:
- Agent flows (build / followup / fix error)
- ActionParser unit tests
- Sandbox filesystem security (path traversal)
- Tool executor
- Prompt template rendering

---

## F1. Version history / undo

No way to revert AI changes. Auto-snapshot files before each agent run.
Allow "revert to before last change." Could use git commits in the workspace.

---

## F2. Diff view for AI changes

FollowUpAgent produces diffs but BuildAgent doesn't show what changed.
Show before/after diff when AI modifies existing files.

---

## F3. Project duplication / cloning

"Duplicate project" — copy workspace + DB records to new session.
Useful for branching experiments.

---

## F4. Custom npm package support

Currently locked to pre-installed packages. Allow users to add packages
(agent runs `pnpm add`). Risk: sandbox security, build time increase.

---

## F5. Multi-framework support

Currently React-only. Add Vue, Svelte, or vanilla templates.
Template selection on project creation.

---

## F6. Deploy to hosting

"Deploy" button that builds and pushes to Vercel/Netlify/Cloudflare Pages.
Or generates a shareable preview URL.

---

## F7. Image / asset upload

Users can't add images, fonts, or static assets. Add file upload to
editor panel, write to `public/`.

---

## F8. Project import

Import existing project (ZIP upload or git clone). Bootstrap sandbox
from user's code instead of blank template.

---

## F9. Collaborative editing

Multiple users on the same project. Partially supported (multiple tabs
see same sandbox). Missing: cursor awareness, conflict resolution.

---

## F10. AI code review

Before applying changes, show a review step: "Here's what I'm about to change."
User can accept/reject individual file changes. Like plan approval but at file level.

---

## A1. Prompt versioning & A/B testing

Jinja templates enable this — swap templates per experiment. Track which prompt
version produced which quality outcome.

---

## A2. Cost tracking per project

LiteLLM returns token usage — aggregate per project. Show users estimated cost.

---

## A3. Streaming feedback during planning

User sees "Planning..." with no feedback for 10-20 seconds. Stream the overview
as it's generated.

---

## A4. Smarter error recovery

If fix_errors fails twice, try a different approach (rewrite from scratch vs patch).
Escalate to a more capable model on retry.

---

## A5. Code quality validation

After build succeeds, run ESLint on generated code. Flag issues to user or auto-fix.

---

## I1. CORS lockdown for production

Currently `allow_origins=["*"]`. Should be configurable via env var for production.

---

## I2. Graceful shutdown timeout

`destroy_all()` has no timeout — hanging sandbox blocks server shutdown.
Add timeout, force-kill after N seconds.

---

## I3. Sandbox disk quotas

No limit on workspace disk usage. AI-generated code could fill the disk.
Add per-workspace size limit.

---

## I4. Structured logging

Currently uses string format logging. Switch to JSON structured logs for production
(easier to search, aggregate, alert on).

---

## I5. Standardized tracing decorators

Port `@observe_flow`, `@observe_step`, `@observe_tool`, `@observe_llm_call` from
primesrc's `core/tracing.py`. Currently agents use ad-hoc `@observe(name=...)` and
manual `langfuse_client.span()` / `.end()` calls (especially in BuildAgent's
`_accept_plan` with 3 manual spans).

What to port:
- `@observe_flow` — wraps Flow.run with trace-level observation
- `@observe_step` — wraps step functions with span tracking (input/output state)
- `@observe_tool` — wraps tool execution with tool-type observation
- `@observe_llm_call` — wraps LLM calls with token/cost tracking

Adapt from primesrc's Bedrock-specific implementation to our LiteLLM usage.
Replace manual span management in BuildAgent with decorators.

---

## A6. Structured output for JSON prompts

Several prompts ask the LLM to respond with "ONLY a JSON object" and then we parse
it with `_parse_json_response` which strips markdown fences and does fallback
extraction. This is fragile — the LLM sometimes wraps JSON in text or returns
malformed JSON.

Use structured output (tool calling / response_format) instead:
- Define Pydantic models for each expected response (ArchitectureDesign, UXDesign,
  UserPlanOverview, TechnicalPlan, ProjectSummary, PackageAnalysis)
- Use LiteLLM's `response_format` parameter or tool-based extraction (like
  primesrc's `chat_structured`)
- Eliminates JSON parsing failures, markdown fence stripping, and fallback logic
- `_parse_json_response` helper can be deleted

**Candidate prompts:**
- `architecture.jinja2` → `ArchitectureDesign` model
- `ux_design.jinja2` → `UXDesign` model
- `user_plan.jinja2` → `UserPlanOverview` model
- `merge.jinja2` → `TechnicalPlan` model
- `summary.jinja2` → `ProjectSummary` model
- `classify.jinja2` → `ClassificationResult` model
- Package analysis in BuildAgent → `PackageAnalysis` model

**NOT candidates** (free-form output):
- `codegen.jinja2` — outputs XML/code, not JSON
- `fix_errors.jinja2` — outputs XML/code
- `followup.jinja2` — outputs text + tool calls

---

## I6. CI/CD pipeline

No CI/CD exists. Set up:

**CI (on every PR):**
- Python linting (ruff)
- TypeScript type checking (tsc --noEmit)
- Frontend build (vite build)
- Python tests (once B12 test coverage exists)
- Frontend tests (once added)

**CD (on merge to main):**
- Build Docker images (backend + frontend)
- Push to container registry
- Deploy to staging environment
- Optional: deploy to production with manual approval

**Tooling:** GitHub Actions (already using GitHub for PRs).

**Files to create:**
- `.github/workflows/ci.yml` — lint, type-check, build, test
- `.github/workflows/deploy.yml` — build + push + deploy
- `Makefile` targets for `lint`, `typecheck`, `test` (some already exist)

---

## I7. Migrate to Postgres + SQLModel + Alembic

**Current state:** Raw `aiosqlite` with hand-written SQL, no ORM, fragile ALTER TABLE
migrations that swallow errors. SQLite is single-writer and can't scale to multiple
server instances.

**Target:**
- **Postgres** as the database (jsonb for BuildState, proper concurrency, scales horizontally)
- **SQLModel** as the ORM (Pydantic models that double as DB tables — we already use
  Pydantic for BuildState, Message, etc.)
- **Alembic** for schema migrations (replaces the 6 fragile ALTER TABLE blocks in
  `models/project.py` and manual CREATE TABLE in `init_db`)

**Migration path:**
1. Add `sqlmodel`, `alembic`, `asyncpg` (or `psycopg`) to dependencies
2. Define SQLModel table classes for Project, ChatMessage, AgentEvent
3. Set up Alembic with `alembic init` and auto-migration generation
4. Replace raw SQL in `models/project.py`, `models/chat.py`, `models/events.py`
   with SQLModel queries
5. Replace `aiosqlite.connect()` with async SQLModel session
6. Add `DATABASE_URL` config supporting both `sqlite:///` and `postgresql://`
7. Generate initial Alembic migration from existing schema
8. Test with both SQLite (dev) and Postgres (staging/prod)

**Why Postgres over alternatives:**
- Data is relational (projects → messages → events, FK cascades)
- `jsonb` for BuildState snapshots and agent event payloads
- Proper connection pooling, concurrent writes, indexed queries
- Industry standard, well-supported by SQLModel/SQLAlchemy

**Why not Redis:** No need for in-memory cache or pub/sub at this stage.
The in-process asyncio.Queue handles real-time notifications. If we go
multi-process, Redis pub/sub could supplement Postgres — not replace it.

**Why not MongoDB:** Data is relational. Would lose cascade deletes,
transactions, and typed schemas.

---

## B13. Agent state persistence to DB

Part of B0 that wasn't completed. Persist BuildState to DB at phase transitions
so agents can survive server restarts (not just browser refreshes).

**What to add:**
- `agent_phase` and `agent_state` columns on projects table
- `update_agent_phase(session_id, phase)` / `get_agent_state(session_id)`
- BuildAgent writes state after: design complete, plan overview, technical plan, execution
- On server restart: check for sessions with non-idle phase, resume or mark as failed

**Depends on:** I7 (cleaner with Alembic migrations) or can be done with raw ALTER TABLE

---

## F11. React Query for frontend data fetching

Replace manual fetch/loading/caching logic with TanStack Query (react-query).

**What it gives us:**
- Loading/pending states (fixes empty state flash on refresh)
- Stale-while-revalidate (instant project switching)
- Automatic refetch on window focus, reconnect, interval
- Cache invalidation (`queryClient.invalidateQueries`)
- Deduplication, retry with backoff, error boundaries

**What it replaces:**
- Manual `loadProjects()`, `loadHistory()`, `loadFileTree()`, `loadModels()` calls
- `isCreating` state in session store
- `pollFileTree` utility
- Manual loading state tracking

**What stays in Zustand:**
- Agent UI state (phase, planOverview, tasks, streaming) — driven by WS events, not REST

---

## F12. Auto-generated API client (orval)

Use **orval** to auto-generate a fully typed react-query client from the FastAPI
OpenAPI spec. One command produces typed hooks for every endpoint.

**Setup:**
- FastAPI already serves `/openapi.json`
- `npx orval` reads the spec → generates hooks + types
- Add `orval.config.ts` with react-query output mode
- Run as a build step or `pnpm generate-api`

**What it generates:**
- `useProjects()`, `useCreateProject()`, `useDeleteProject()` — react-query hooks
- Request/response TypeScript types from backend Pydantic models
- Automatic cache invalidation on mutations

**What gets deleted:**
- `frontend/src/services/api.ts` (manual fetch functions)
- Most of `frontend/src/types/index.ts` (API types auto-generated)
- Manual type duplication between backend and frontend

**Backend prerequisites:**
- Add Pydantic response models to all endpoints (some return raw dicts)
- Consistent endpoint tagging for grouping
- Proper request body models (some already have them)

**Why orval:** Generates react-query hooks directly (not just a fetch client).
Alternatives: `@hey-api/openapi-ts` (generates client, pair with react-query manually),
`openapi-typescript` (types only).

---

## B14. Frontend reconnect handling

Part of B0 that needs verification. Backend replays events on WS connect, but
frontend may not handle receiving a batch of historical events correctly.

**What to verify/fix:**
- Frontend processes replayed events the same as live events
- No duplicate UI state from replaying events that were already processed
- Phase indicator shows correct state on reconnect
- Task progress, file tree, and chat history are consistent after reconnect

---

## B15. Fix "Fix with AI" error detection and resolution

The error capture and fix flow has several issues:

**Error detection problems:**
- `api/errors.py` watches `.dev-server.log` by appending — old errors from previous
  builds persist in the log, so stale errors keep showing up as "new"
- The dedup set helps but resets periodically, causing old errors to resurface
- Should truncate/rotate the log on each dev server restart, or track a read offset

**File detection problems:**
- `FixErrorAgent._normalize_path` has fragile heuristics for extracting the file path
  from error messages (rfind /src/, session_id stripping, etc.)
- Runtime errors from the iframe often have wrong file paths (bundled paths, not source)
- Stack traces from Vite point to transformed paths, not original source files
- Sometimes the wrong file is read, so the AI tries to fix the wrong code

**Fixes needed:**
- Truncate `.dev-server.log` when dev server restarts (in `sandbox/base.py` `start_dev_server`)
- Use source maps to map bundled paths back to source files
- Improve path normalization — use the file tree to fuzzy-match error paths
- Read all source files as context when the specific file can't be identified (already
  has fallback logic, but it's buried in nested try/except)
- Consider running `tsc --noEmit` for type errors instead of parsing build log output

---

## B16. Smarter FixErrorAgent — ReACT loop with tools

Currently FixErrorAgent is a single-shot flow: discover files → generate fix → write →
validate → maybe retry once. It doesn't explore the codebase, can't read related files,
and guesses at the fix from limited context.

**Make it a ReACT agent like FollowUpAgent:**
- Give it the same tools: grep, glob, read_file, write_file, edit_file
- Let it explore the codebase to understand the error context before fixing
- It can read imports, check related files, understand the data flow
- Use edit_file for targeted fixes instead of rewriting entire files
- Run typecheck/build as a tool to validate fixes in the loop
- Retry with more context if the first fix fails (read more files, try different approach)

**New tools specific to fixing:**
- `run_typecheck()` — run `tsc --noEmit`, return errors
- `run_build()` — run `pnpm build`, return errors
- Agent can iterate: fix → check → fix again until clean

**Reuse from FollowUpAgent:**
- Same ToolExecutor + FunctionTool setup
- Same ReACT loop structure (_react_loop with max iterations)
- Same WS step reporting (followup_step events)
- Different system prompt focused on debugging/fixing

**Expected improvement:**
- Fixes multi-file issues (reads the importing file + the broken file)
- Understands project structure before guessing at a fix
- Can fix cascading errors (fix one → check → fix the next)
- Higher fix success rate from better context
