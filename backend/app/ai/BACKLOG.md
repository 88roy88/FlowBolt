# AI Builder Backlog

## B0. Decouple agents from WebSocket — DB as source of truth (NEXT)

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
