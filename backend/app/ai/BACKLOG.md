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

Architecture refactoring is ~85% done (cards extracted, stores split, icons centralized).
Remaining work is styling consolidation:

- 295 inline `style={{}}` blocks — need CSS modules or design system
- Spinner animation hardcoded in 10 places — use CSS class from App.css
- No shared Button component (all buttons use inline styles)
- No shared Dropdown component (CaseSelector + ModelSelector duplicate logic)
- Large components: FollowUpProgress (168), PromptInput (245), CaseSelector (238)
- `/components/ui/` directory exists but is empty

## B5. FollowUp agent memory management

The ReACT loop in `followup_agent.py` appends every tool call and result to
`working_messages` without any pruning. With up to 15 iterations and tools
returning full file contents (500+ lines), the conversation can easily exceed
context limits.

**Options:**
- Summarize older tool results (replace full file content with "read file X, 200 lines")
- Sliding window: keep last N tool call/result pairs, summarize the rest
- Truncate large tool results beyond a token budget
- Track token count and compress when approaching the model's context limit

**Where:** `followup_agent.py` `_react_loop()` — between iterations, before the
next `complete_chat_with_tools` call.

## B6. FollowUp agent case support

The follow-up agent should support receiving case IDs (like the create flow does)
so users can integrate new data sources into an existing project without starting over.

**What to do:**
- Accept `case_ids` parameter in `FollowUpAgent.run()`
- Fetch and analyze case data (reuse `DesignService.fetch_and_analyze_case`)
- Include case context in the follow-up system prompt so the agent knows about
  available data endpoints when making edits

## B7. Rename "package" to "case" in backend

The backend still uses "package" terminology in several places while the frontend
and user-facing layer use "case". Align naming for consistency.

**Files to update:**
- `integrations/package_api.py` → rename to `case_api.py`, class `CaseApiClient`
- `api/package_api.py` → rename to `api/case_api.py`
- `services/design.py` — `fetch_and_analyze_case` already uses "case" but internally
  calls `PackageApiClient` and references `package_id`, `package_name`
- `prompts/templates/codegen.jinja2` — uses `ctx.package_name`, `ctx.package_id`
- `state.py` — `case_contexts` field already correct, but dict keys inside are
  `package_id`, `package_name` etc.
