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

### Ruff noqa cleanup (74 suppressed warnings to resolve properly)

These are currently suppressed with `# noqa` but should be fixed:

- **ASYNC230/240/220 (29)** — blocking file I/O in async functions. Use `aiofiles` or
  `asyncio.run_in_executor`. Affects: filesystem.py, sandbox/base.py, sandbox/local.py,
  export.py, errors.py, server_log.py, tools/glob.py, tools/grep.py
- **PLC0415 (13)** — imports inside functions. Review which are for circular import
  avoidance (keep) vs lazy habit (move to top)
- **C901/PLR0912/PLR0915 (19)** — complex functions. Candidates for extraction:
  chat_ws, errors_ws, export_html, _discover_files, _kill_stale_dev_servers
- **PLW0603 (1)** — global DB path in models/project.py. Use proper singleton or DI
- **PLR0913 (1)** — too many args in render_codegen. Consider a params dataclass

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

Zero tests across the entire codebase. Need both backend (Python) and frontend (TypeScript) tests.

### Backend (pytest)

**Setup:**
- Add `pytest`, `pytest-asyncio`, `pytest-cov` to dev dependencies
- Create `backend/tests/` directory
- Add `Makefile` target: `make test-backend`

**Priority 1 — Unit tests (no external deps):**
- `ActionParser` — test streaming XML parsing, edge cases (truncated, malformed, nested)
- `core/tools.py` — FunctionTool schema generation, ToolExecutor dispatch, error handling
- `core/flow.py` — step execution, routing, max-step guard
- `core/messages.py` — Message creation, to_dict conversion
- `helpers.py` — parse_json_response with markdown fences, malformed JSON
- `prompts/` — Jinja template rendering with various inputs
- `task_tree.py` — WorkPlan.execution_layers dependency resolution
- `sandbox/filesystem.py` — path traversal prevention (_safe_path)
- `sandbox/pty.py` — PtyHandle.read/write/kill (mock fd)
- `state.py` — BuildState serialization

**Priority 2 — Integration tests (mock LLM, real DB):**
- `agents/build.py` — full pipeline with mocked LLM responses
- `agents/followup.py` — ReACT loop with mocked tool results
- `agents/fix_error.py` — discover → generate → validate flow
- `models/events.py` — emit, get, clear, subscribe/notify
- `models/project.py` — CRUD, migrations, cascade delete
- `models/chat.py` — save/get messages
- `api/chat.py` — WebSocket handler with mocked agents

**Priority 3 — Sandbox tests (need filesystem):**
- `sandbox/manager.py` — create/destroy lifecycle, port allocation
- `sandbox/local.py` — exec, dev server start/stop
- Template scaffolding (copytree + stamp_vite_config)

### Frontend (vitest)

**Setup:**
- Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`
- Add `vitest.config.ts`
- Add `Makefile` target: `make test-frontend`

**Priority 1 — Store tests:**
- `stores/chat.ts` — sendMessage, loadHistory, event replay
- `stores/chatHandlers.ts` — each event type handler
- `stores/session.ts` — project CRUD, model persistence
- `stores/files.ts` — file tree loading

**Priority 2 — Component tests:**
- `ChatMessage` — renders different card types correctly
- `WorkPlanView` — accept/modify/reject actions
- `TaskProgress` — progress bar, status icons
- `ChatPanel` — phase indicator visibility logic
- `ModelSelector` — dropdown open/close, selection

**Priority 3 — Integration tests:**
- WebSocket mock — test event flow from connect to UI update
- Full flow — send message → see progress → see result

### CI integration
- Run tests in GitHub Actions (I6)
- Require passing tests for PR merge
- Coverage reporting (target: 60% backend, 40% frontend initially)

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

## A6. Structured output for JSON prompts (PARTIALLY DONE)

Pydantic schemas created in `schemas.py` (ArchitectureDesign, UXDesign,
UserPlanOverview, ProjectSummary, PackageAnalysis, ClassificationResult).
BuildState and BuildAgent now validate LLM responses into these models.

Remaining: use LiteLLM `response_format` or tool-based extraction to enforce
structured output at the LLM level (not just post-parse validation).

### Original description:

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

## ~~I6. CI/CD pipeline~~ DONE

GitHub Actions at repo root: ci.yaml → backend.yaml (ruff + mypy + pytest).
Reusable workflow pattern. uv-setup shared action.

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

---

## B17. Improve grep tool discoverability for FollowUp agent

**Problem:** The FollowUp agent uses `glob` + `read_file` to search for text instead
of using `grep`, which is much faster. The LLM doesn't understand that `grep` searches
the entire codebase.

**Root cause:**
- Tool name is just `grep` — doesn't signal "codebase-wide search"
- Tool description is a single line, no examples or usage guidance
- The `path` parameter is confusing — LLM may think it means "file path" not "directory"
- The followup system prompt (`followup.jinja2`) barely mentions grep

**Changes needed:**
- Rename tool to `grep_codebase` (or at minimum improve description)
- Add rich docstring with examples: `"useState"`, `"import.*axios"`, `"className="`
- Explain when to use grep vs glob vs read_file
- Remove the `path` parameter (always search from root) or rename to `directory`
- Update `followup.jinja2` prompt to guide tool selection:
  - `grep` for searching text/patterns across the codebase
  - `glob` only for discovering files by name/path
  - `read_file` for reading specific files found via grep/glob

**Reference:** See `primesrc/code-validation-service` `base_subagent.py` for a
well-prompted `grep_codebase` tool with examples and clear Args documentation.

---

## A7. Multi-model strategy per phase

Different agent phases have different requirements. Use the best model for each job
instead of one model for everything.

| Phase | Needs | Tier |
|-------|-------|------|
| Classify, Summary | Simple | Cheap/fast (Haiku) |
| Architecture, UX, Planning | Strong reasoning | Smart (Opus/Sonnet) |
| Codegen (per task) | Correct code, focused | Fast + good at code (Sonnet) |
| Error fixing | Debugging reasoning | Smart (Sonnet/Opus) |
| Follow-up (ReACT) | Balanced | Sonnet |

**Implementation:**
- Add `ModelConfig` with per-phase model overrides in settings
- `BuildAgent` selects model per phase instead of using `self.model` everywhere
- Default: use the user's selected model for everything (backward compat)
- Advanced: settings UI to configure per-phase models
- Cost savings: Haiku for classify/summary is ~10x cheaper than Opus

---

## F14. Browser notification on build complete

When the user switches to another tab during a build, send a browser notification
when the agent finishes.

**Implementation:**
- Request `Notification.permission` on first build start
- On `action_complete` event: if `document.hidden`, fire `new Notification(...)`
- Show project name + "Build complete" or "Error occurred"
- Click notification → focus the tab
- Respect user preference (add toggle in settings)

---

## F15. Console output capture from preview

Capture `console.log`, `console.error`, `console.warn` from the preview iframe
and display in a "Console" tab next to Terminal / Server Log.

**How it works:**
- We already inject an `__ERROR_REPORTER__` script into `index.html` (in the template)
- Extend it to also intercept `console.log/warn/error/info` via monkey-patching
- `postMessage` each log entry to the parent window (same as runtime errors)
- Frontend listens for these messages and displays in a console panel

**Injected script addition:**
```js
['log','warn','error','info'].forEach(level => {
  const orig = console[level];
  console[level] = function(...args) {
    orig.apply(console, args);
    window.parent.postMessage({
      type: 'console',
      level,
      args: args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)),
    }, '*');
  };
});
```

**Frontend:**
- New "Console" tab in the bottom drawer (alongside Terminal / Server Log)
- Color-coded by level: log=default, warn=yellow, error=red, info=blue
- Timestamp + level + message
- Clear button
- Filter by level
- Useful for debugging case API calls, state issues, render problems

---

## F16. User authentication & project ownership

Currently no auth — anyone with the URL can access any project.

**Phase 1 — Basic auth:**
- User registration + login (email/password or OAuth with GitHub/Google)
- JWT or session-based auth
- Projects belong to a user (add `user_id` column to projects table)
- API endpoints check ownership before allowing access
- WebSocket connections authenticated via token

**Phase 2 — Project sharing:**
- Share a project with another user (read-only or read-write)
- Share via link (public preview URL, no login needed to view)
- Project permissions: owner, editor, viewer
- Shared projects appear in the sidebar with a badge

**Phase 3 — Teams:**
- Create teams/organizations
- Team-level project visibility
- Role-based access (admin, member)

**Dependencies:** I7 (Postgres) makes user tables + relations cleaner.

---

## F17. Auto-save with status indicator

**Problem:** Editor changes are saved via debounced timer. No visual feedback.
If save fails, user doesn't know. Related to B10.

**What to add:**
- Save indicator in editor tab or status bar: "Saved" / "Saving..." / "Unsaved"
- Save on Cmd+S (explicit save, not just debounce)
- Save on tab switch / window blur
- Save before agent runs (ensure AI sees latest edits)
- Show error toast if save fails
- Debounce reduced from 1000ms to 500ms for faster feedback

---

## F18. Deploy to S3 with proxied preview URL

Export and deploy the built project to S3 for persistent hosting.

**Phase 1 — S3 upload:**
- Build the project (`VITE_BASE=/ pnpm build` — already works in export endpoint)
- ZIP the `dist/` directory or produce a single minified HTML (already have both in `api/export.py`)
- Upload to S3 bucket under a unique path: `s3://deployments/{project_id}/{timestamp}/`
- Store deployment URL in the project record

**Phase 2 — Proxied preview URL:**
- Each deployment gets a nice URL: `https://preview.flow44.com/{project-slug}`
- CloudFront or similar CDN proxies to the S3 path
- Custom subdomains per project: `{project-slug}.flow44.app`
- Deploy history — list past deployments, rollback to previous

**Phase 3 — Custom domains:**
- Users bring their own domain
- CNAME setup instructions + SSL via ACM/Let's Encrypt

**Backend:**
- `POST /api/projects/{id}/deploy` — build + upload to S3 + return URL
- `GET /api/projects/{id}/deployments` — list past deployments
- Add `boto3` for S3 upload (already in dependencies for Bedrock)
- Store deployment records in DB (url, timestamp, status)

**Frontend:**
- "Deploy" button in the sidebar or toolbar
- Show deployment URL with copy button
- Deployment history in project settings

---

## F19. Image upload + screenshot-to-code

**Image upload (Phase 1):**
- Users can upload images, icons, logos to the project
- Drop zone in the editor panel or file tree
- Files saved to `public/` in the sandbox
- Backend: `POST /api/files/{session_id}/upload` — multipart form data

**Screenshot of preview (Phase 2):**
- "Screenshot" button on the preview pane
- Capture the iframe content via `html2canvas` or `iframe.contentWindow` capture
- Send screenshot to the AI as context: "Here's what the app looks like now, change X"
- Attach as an image in the chat message

**Screenshot/image to code (Phase 3):**
- Paste or upload a design screenshot
- Send to a vision model (Claude with vision, GPT-4V)
- AI generates matching UI code from the image
- "Make it look like this" workflow

**Requirements:**
- Vision-capable model (Claude Sonnet/Opus support images)
- LiteLLM supports image content blocks in messages
- Frontend: file input + drag-and-drop + clipboard paste handler

---

## F20. Screenshot preview and send to LLM

"Screenshot" button on the preview pane that captures the current state of the
preview and sends it to the AI as visual context.

**How it works:**
- Button in preview toolbar captures the iframe content
- Use `html2canvas` on `iframe.contentDocument` or the native `iframe.contentWindow` screenshot API
- Attach the image to the next chat message as visual context
- User types "Make the header bigger" + the AI sees the screenshot → better results

**Implementation:**
- Frontend: capture iframe → convert to base64 PNG → store in chat store
- When sending next message, include the image as a content block
- LiteLLM supports image content blocks for vision-capable models (Claude Sonnet/Opus)
- Show thumbnail of attached screenshot in the chat input area
- "Remove screenshot" button to detach before sending

**Also useful for:**
- Bug reports: "See this screenshot, the layout is broken"
- Design feedback: "Make it look more like this" (paste external screenshot)

---

## ~~F21. Template gallery~~ PARTIALLY DONE

Template system exists (pnpm-project-template). Gallery UI for selecting
templates on project creation is partially implemented.

---

## ~~F22. Mobile layout — chat + preview only~~ DONE

The builder UI only works on desktop. Add a simple mobile layout for
chatting with the AI and viewing the preview. No code editor on mobile.

**Scope:**
- New `MobileLayout.tsx` — single pane, bottom tab bar: Chat / Preview
- Chat is the default view
- Preview as second tab
- Sidebar as a slide-out drawer (hamburger button)
- No Monaco editor, no file tree, no terminal on mobile
- PromptInput adapts to mobile keyboard

**Detection:**
- `useMediaQuery('(max-width: 768px)')` or Tailwind `md:` breakpoint
- AppShell renders `MobileLayout` below breakpoint, desktop layouts above

**Effort:** ~half day. All components already work standalone.

---

## B18. Validate boltArtifact XML completeness

The ActionParser accepts streaming XML and fires `on_file_action` when a
`</boltAction>` close tag is found. But if the LLM response is truncated
(hits max_tokens, network error, etc.), some `<boltAction>` tags may never
close — resulting in silently dropped files.

**What to validate:**
- Every `<boltAction type="file">` that was opened must have a matching `</boltAction>`
- If the response ends with unclosed actions, either:
  - Retry the LLM call for the missing files
  - Emit an error event so the user knows files were incomplete
  - Write partial content with a warning comment at the top

**Where:** `ActionParser.flush()` should check for unclosed state and report it.
Currently `flush()` just emits remaining text buffer — it doesn't check if we're
mid-action.

**Also applies to:** `_fix_errors` and `FixErrorAgent` which both use ActionParser.

---

## F13. VS Code-like editor features

The editor uses Monaco (same engine as VS Code). Many features are built-in and
just need to be enabled or wired up. Others need a small backend endpoint.

### High value, easy (Monaco built-in)

**Find and replace in file (Cmd+H / Cmd+F):**
- Monaco has this built-in. Just needs `editor.getAction('actions.find')` or
  it may already work. Verify and ensure keyboard shortcuts aren't captured
  by the browser/app shell.

**Go to line (Ctrl+G):**
- Built-in: `editor.getAction('editor.action.gotoLine')`

**Multiple cursors (Cmd+D, Alt+Click):**
- Built-in, enabled by default in Monaco.

**Minimap:**
- Built-in: `minimap: { enabled: true }` in editor options.
- Currently might be disabled. Toggle in settings or enable by default.

**Bracket matching, auto-close, auto-indent:**
- Built-in. Verify our Monaco config enables these.

### Medium effort

**Quick file open (Cmd+P):**
- Frontend-only. Fuzzy search over the file tree (already loaded in files store).
- Build a command palette modal: input → fuzzy filter file list → arrow keys → Enter to open.
- No backend needed.

**Search across files (Cmd+Shift+F):**
- Need a backend endpoint: `GET /api/files/{session_id}/search?q=...&regex=true&glob=*.tsx`
- Use ripgrep in the sandbox (already have the `grep` tool in `ai/tools/grep.py`).
- Frontend: search panel with results grouped by file, click-to-open-at-line.
- Could reuse the `grep` tool function directly from a REST handler.

**Breadcrumb navigation:**
- Show `src / components / Header.tsx` above the editor, clickable segments.
- Parse the file path from the active tab. Frontend-only.

**Tab management:**
- Close tab (X button, middle-click) — may already work in FileTabs component.
- Reorder tabs by drag.
- Right-click context menu: "Close", "Close others", "Close all".

### Larger effort

**Split editor / side-by-side:**
- Monaco supports `DiffEditor` and multiple editor instances.
- Need layout changes to host two editors in the code pane.
- Useful for comparing files or viewing AI diffs.

**File operations from file tree:**
- New file / New folder — needs backend endpoint + file tree UI.
- Rename (F2) — backend endpoint to rename + update file tree.
- Delete — backend endpoint + confirm dialog.
- Drag to move — backend rename + file tree drag support.

**Diff view for AI changes:**
- Monaco has `monaco.editor.createDiffEditor()` built-in.
- Show before/after when AI modifies a file.
- Ties into F2 (diff view backlog item).

### Click-to-file from errors

**Server log / terminal:**
- Vite/TypeScript errors show file paths like `src/components/Header.tsx:42:15`
- Parse these in the xterm output (regex for `src/...:\d+:\d+` patterns)
- Render as clickable links in the terminal (xterm supports link handlers via `WebLinksAddon` or custom `registerLinkProvider`)
- On click: open the file in the editor at that line/column

**Preview iframe runtime errors:**
- Runtime errors captured by the `__ERROR_REPORTER__` script include `file`, `line`, `column`
- The error toast already shows these — make the file path clickable
- On click: open file in editor at that line
- Stack trace lines with file references should also be clickable

**Implementation:**
- Add a shared `openFileAtLine(path, line, column?)` function that:
  1. Opens the file in EditorPanel (add to files store or via event)
  2. Calls `editor.revealLineInCenter(line)` + `editor.setPosition({lineNumber, column})`
- Terminal: use xterm's `registerLinkProvider` to detect file paths in output
- Error toast: wrap file path in a clickable element
- Server log: same link provider as terminal

### Implementation notes
- Most Monaco features are enabled via editor options or `editor.addAction()`.
- Keyboard shortcuts need careful handling — Cmd+P and Cmd+Shift+F are browser
  shortcuts that need `e.preventDefault()` to intercept.
- The file tree is already in the Zustand `files` store — quick open just needs
  a fuzzy filter (use `fzf-for-js` or simple substring match).

---

## I8. Workspace lifecycle — evict idle projects to save disk

**Problem:** Each workspace keeps `node_modules` (~80MB) permanently. With many
projects this adds up fast (13 projects = ~1GB just in node_modules).

**Insight:** pnpm install with a shared content-addressable store takes <1s
(`reused 132, downloaded 0`). Reinstalling is cheap. Keeping node_modules for
idle projects is wasteful.

**Design:**
- Track last-active timestamp per sandbox (WebSocket connect, chat message, terminal use)
- Keep only N sandboxes "hot" (dev server running, node_modules present). Default N=5.
- When a sandbox goes idle beyond a threshold (e.g. 30 min with no connections):
  1. Stop dev server
  2. Delete `node_modules/` and `dist/`
  3. Keep source files, package.json, pnpm-lock.yaml
- When user switches back to an evicted project:
  1. `pnpm install` (~1s from shared store)
  2. Start dev server
  3. Resume normally

**Disk savings:** ~80MB per evicted project. With 50 projects and 5 hot, saves ~3.6GB.

**Config:**
- `AIB_MAX_HOT_SANDBOXES=5`
- `AIB_SANDBOX_IDLE_TIMEOUT=1800` (seconds)

**Files:**
- `sandbox/manager.py` — LRU eviction logic, idle tracking
- `sandbox/base.py` — `evict()` method (stop dev server, rm node_modules/dist)
- `sandbox/base.py` — `rehydrate()` method (pnpm install, start dev server)
- `api/chat.py` / `api/terminal.py` — touch last-active on connect
