# AI Module Backlog

## B1. Parallel per-file codegen

Change `ExecutionService._execute_task` to fire one LLM call per file in parallel
instead of one call per task that generates all files via bolt XML.

**Current flow:**
- Task has 3-5 files → one LLM call → streams all files via boltArtifact XML
- `ActionParser` extracts files from the XML stream

**Proposed flow:**
- Task has 3-5 files → 3-5 parallel LLM calls → each returns raw file content
- No XML parsing needed, each call is a simple request/response

**What it enables:**
- ~5x faster wall-clock time for multi-file tasks
- Delete `ActionParser` (177 lines) — no more streaming XML state machine
- Simpler per-file prompts ("write this one file" vs "write these 5 files in XML")
- Better error isolation — one file fails, others succeed, retry just that file
- Simpler codegen Jinja template (no boltArtifact output format section)

**Risk:**
- Coherence between files in the same task (e.g. a component importing from a sibling).
  Mitigated by: architecture context provides the interfaces, dependency system ensures
  types are available, typecheck/fix cycle catches mismatches.

**Changes needed:**
- `services/execution.py` — replace `stream_chat` + `ActionParser` with parallel `complete_chat`
- `prompts/templates/codegen.jinja2` — remove boltArtifact output format, simplify to "return the file content"
- `parser.py` — delete entirely (only used by codegen and fix_errors, both would switch)
- `prompts/templates/fix_errors.jinja2` — also switch from XML to direct file content

## ~~B2. Wire up `ai/core/` framework to agents~~ DONE

- FollowUpAgent uses `ToolExecutor` + `FunctionTool` (auto-generated schemas from docstrings)
- All LLM calls use `Message` objects via provider (backward-compat with raw dicts)
- Deleted manual `FOLLOWUP_TOOLS` dict (142 lines) and `followup.py`
- Remaining: Wire `Flow` to orchestrator (low priority — current direct service calls work fine)

## B3. Remaining code quality fixes

- `api/errors.py` — bound the dedup set with TTL or max size (memory leak)
- `ai/provider.py` — add retry with exponential backoff for transient LLM failures
- `models/project.py` — replace 6 repetitive ALTER TABLE migration blocks
- `sandbox/filesystem.py` — use `run_in_executor` for async file I/O

## B4. Frontend refactor

- Split `ChatMessage.tsx` (967 lines) into separate card components
- Split `chat.ts` store (766 lines) into focused stores (messages, agent-phase, follow-up, models)
- Extract duplicated icon mappings, spinner animations, dropdown components
- Build shared base components (Card, Button, Dropdown, Spinner)
