# Brief: follow-up agent context overflow

You are collecting data, not fixing code. Use the `opik` skill (`SKILL.md` in this folder) against **prod**. Deliver
exactly the report described under "Output". Don't recommend fixes or edit any repo file.

## The problem

Prod users of the follow-up agent hit this error (model: DeepSeek, 600,000-token window, every user on it):

```
litellm.BadRequestError: OpenAIException - ... error code: 400 - {'error': {'message': "This model's maximum context
length is 600000 tokens. However, you requested 0 output tokens and your prompt contains at least 600001 input tokens ...
```

We must decide which part of the prompt to shrink. The answer depends on which of these is true:

- **HISTORY**: the chat history loaded at the start of a run is already too large. `get_messages` loads the whole
  project chat on every run with no limit. Such a project is stuck for good, because each new message adds history.
- **IN-TURN**: tool results build up inside one run of up to 15 agent iterations. `read_file` returns up to 1000 lines
  with no character cap. `grep` has no line-length cap, and its `max_results=50` is passed as rg `--max-count`, which
  is per file, not a total. `write_file` arguments carry whole files. Tool results are saved to history as ≤200-char
  previews and tool args as ≤500 chars, so the next run starts small again.
- **SYSTEM**: the system prompt (file tree, data-source schemas, project summary) is too large on its own.

## How the data is shaped

- Run trace: `name = "followup-agent-run"`, `thread_id` = FlowBolt project id, `output = {"answer", "steps"}`.
- One LLM span per agent iteration, children of the run. Order them by `start_time`; position 0 is the first call.
- **Successful** LLM span: `usage.prompt_tokens` (or `output.usage.prompt_tokens`; use `llm_result()`). Full
  `input` messages.
- **Failed** LLM span: named `<model>_failure`, `error_info.message` holds the 400 text, `input = {"messages": [...]}`
  with the **full** prompt that was sent, and **no usage**.
- `input` may be a dict with `messages`, a bare list, or a Python-repr string (parse with `ast.literal_eval`).
  Handle all three.
- Message shapes: `system` (the rendered `followup.jinja2`), `user`, `assistant` (may have `tool_calls[].function`
  with `name` + JSON `arguments`), `tool` (`tool_call_id`, `content`). Tools: `grep`, `glob`, `read_file`,
  `write_file`, `edit_file`.
- **Prior turns** = every message before the last `user` message. **Current turn** = from the last `user` message on.
- System prompt sections: split the system content on lines starting with `## `. Expected sections: `New Data Sources`,
  `Existing Data Sources`, `Current Project`, `File Tree`, `How to Work`, `Rules for editing`, plus file-safety rules.

## Steps

1. Credentials: `backend/.env.prod.local` must exist with the `AIB_OPIK_*` prod values. If it's missing, stop and ask.
2. Pull the last 30 days of follow-up runs into a fresh temp dir outside the repo:
   ```
   PYTHONIOENCODING=utf-8 uv run --directory backend --no-sync python ../.claude/skills/opik/opik_pull.py pull --env prod --name followup-agent-run --since <today-30d> --out <tmp>/followup
   ```
3. Run `errors --data <tmp>/followup --top 5` and `context --data <tmp>/followup --top 20`. Keep their output for the
   appendix.
4. Write a throwaway script in a separate temp dir (not inside `<tmp>/followup`). It imports `iter_traces`,
   `spans_by_id`, `owning_step` and `llm_result` from `opik_pull.py`, streams one trace at a time, and produces every
   number below. Run it with `uv run --directory backend --no-sync python -I <script> <tmp>/followup`.
5. Write the report.

## Rules

- Never `Read` or `json.load` the whole export. Stream it with `iter_traces`.
- **Privacy:** the report holds sizes, counts, roles, tool names, file paths and grep patterns only. Never include
  message content, code, user text or answers.
- **Overflow call:** an LLM span whose `error_info.message` contains `maximum context length`.
- **Token estimate for failed spans:** calibrate `ratio = Σ prompt_tokens / Σ chars` over every successful follow-up
  LLM span, where chars = the summed length of every message `content` plus every tool-call `arguments` string. Report
  the ratio and n. Estimated tokens = chars × ratio. Never use chars/4.
- Cite trace ids (first 13 chars) and `start_time` for every example. State n on every table.
- If a number can't be computed, write `n/a` and the reason. Don't guess.

## Output

One file, `<tmp>/context-report.md`, with exactly these sections in this order.

### 1. Scope

| metric | value |
|---|---|
| window (since → until) | |
| follow-up runs | |
| runs with ≥1 overflow call | |
| distinct projects (thread_id) with ≥1 overflow | |
| overflow runs per day | `{date: n}` |
| other error types on follow-up LLM spans | type: n |
| models seen on overflow spans | |
| limit stated in error messages | e.g. 600000 |
| token calibration ratio (tokens/char, n spans) | |

### 2. Where it overflows (one row per overflow call)

| trace | start | project | iteration index | class | est. total tokens | system | prior turns | current turn |
|---|---|---|---|---|---|---|---|---|

- `class` = `HISTORY` if the iteration index is 0, `IN-TURN` otherwise. Below the table, give the counts per class.
- The last three columns hold estimated tokens and % of total, e.g. `412k (68%)`.

### 3. Are projects stuck?

For each project with an overflow: the follow-up runs in the window after its first overflow, how many of them also
overflowed, and whether any later run succeeded.

| project | first overflow | later runs | later overflows | recovered (y/n) |
|---|---|---|---|---|

### 4. What fills the failed prompt (summed across all overflow calls)

**4a. By bucket**: rows `system`, `prior turns`, `current turn`. Columns: est. tokens total, % of all overflow
tokens, p50 and max per call.

**4b. System prompt sections**: one row per `## ` section, with est. tokens p50 / max. Also give the `File Tree`
line count p50 / max.

**4c. Prior turns**:

| metric | p50 | p95 | max |
|---|---|---|---|
| user messages (turn count) | | | |
| messages total | | | |
| est. tokens: user content | | | |
| est. tokens: assistant content | | | |
| est. tokens: assistant tool-call args | | | |
| est. tokens: tool results | | | |
| largest single tool result (chars) — expected ≤ ~203 | | | |
| largest single tool-call args (chars) — expected ≤ ~600 | | | |
| largest single user message (chars) | | | |

Flag every call where a prior-turn tool result is over 300 chars or a tool-call arg is over 600 chars. That means
the persistence truncation was bypassed: list the trace and message index.

**4d. Current turn, by tool**:

| tool | calls | result est. tokens (sum) | result p50 / max (chars) | args est. tokens (sum) | args max (chars) |
|---|---|---|---|---|---|

**4e. Top 10 largest single messages in overflow prompts**: trace, bucket, role, tool, key argument (`path` /
`pattern` / `file_pattern`), chars, est. tokens. For `read_file` results also give the line count and chars per line,
which detects minified or one-line files.

**4f. Duplicate reads in the current turn**: per call, the number of `read_file` calls on a path already read in the
same turn, and the est. tokens they repeat. Totals across all calls.

### 5. Normal traffic (all follow-up runs, successful calls only)

| metric | n | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| prompt tokens, first call of a run (≈ system + history) | | | | | |
| prompt tokens, any call | | | | | |
| growth per iteration (prompt_tokens[i] − [i−1]) | | | | | |
| iterations per run | | | | | |
| tool calls per iteration | | | | | |
| tool result size, chars, per tool (one row each) | | | | | |

Then:

- Runs that hit 15 iterations: count.
- Near misses: calls with prompt_tokens over 300k, 450k and 550k (counts, plus the 5 largest with trace ids).
- History growth: for the 10 projects with the most follow-up runs, list the first-call prompt tokens per run in
  time order as `run#: tokens`, and the average tokens added per user turn.

### 6. Verdict (facts only, max 6 lines)

- Share of overflow calls that are HISTORY / IN-TURN / SYSTEM-dominated (system over 50% of the prompt).
- The single largest contributor across all overflow tokens: bucket, then tool, with %.
- Whether stuck projects exist, and how many.
- Whether one tool result alone exceeded 100k tokens in any call: yes/no, with count.
- Whether any persistence-truncation violation was found (4c).
- Sample-size caveat: n overflow calls, n runs, window.

### Appendix

The raw output of `errors` and `context`, and the full analysis script.
