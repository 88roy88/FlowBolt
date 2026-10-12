---
name: opik
description: Pull and inspect Opik traces for FlowBolt agent runs (local or prod). Use whenever a question is about what the agents actually did — a failed run, recent errors, retries, build-error rates, token/context size, package selection — instead of reasoning from the code alone.
argument-hint: "[projects | pull | runs | trace <id> | errors | score | context | packages]"
---

Credentials come only from `AIB_OPIK_*` settings (`AIB_OPIK_API_KEY`, `AIB_OPIK_WORKSPACE`, `AIB_OPIK_PROJECT_NAME`,
`AIB_OPIK_URL_OVERRIDE`) via `OpikSettings`. Never pass keys on the command line.
- Local: `backend/.env` (default).
- Other environments: `--env prod` reads `backend/.env.prod.local` (gitignored). Create it with the prod
  `AIB_OPIK_*` values if it's missing.

Run from the repo root (on Windows prefix with `PYTHONIOENCODING=utf-8`):
```
uv run --directory backend --no-sync python ../.claude/skills/opik/opik_pull.py <command> ...
```

## Get the data

- `projects [--env prod]` — list projects in the workspace.
- `pull --out <dir> [--env prod] [--project <name>] [--since 2026-10-01] [--until 2026-10-08] [--name execute-agent-run] [--thread <flowbolt-project-id>]`

`pull` delegates to the Opik SDK exporter: filters run server-side, traces are fetched in chunks of `--page-size`
(default 50), rate limits are retried, and each trace is written with all its spans to
`<dir>/<workspace>/projects/<project-id>/trace_<id>.json`. `--thread` selects every agent run of one FlowBolt project
(traces carry `thread_id = project id`). Use a temp dir outside the repo, one `--out` per project/env.

## Reports (all take `--data <dir>`, the same dir as `--out`)

| Command | Answers |
|---|---|
| `trace <id-prefix>` | What happened in one run: spans in order, step outputs, LLM `finish_reason`/tokens, emitted files, errors. |
| `errors [--top 3]` | What is failing: errors grouped by exception type, step and message, with the most recent example traces. |
| `runs [--trace-name ...]` | One line per agent run: `fix_attempts`, files, contract gaps, errors. Default `execute-agent-run`. |
| `score [--include-tainted]` | Batch quality: outcomes, contract-gap causes, rejection-only fix tokens, token cost per step, build-error taxonomy. Drops environment-tainted runs. |
| `context [--top 10]` | Context size: prompt tokens per LLM call by owning step (n / p50 / p95 / max) and the largest calls. |
| `packages` | Package selection: decide-packages failures, off-list proposals, fix attempts with vs without each package. |

For a question none of these answer, write a throwaway script that imports `iter_traces` (streams one trace at a
time) and the helpers `owning_step`, `llm_result`, `contract_gaps` from `opik_pull.py`.

## Gotchas that will mislead you

- **Never `Read` or `json.load` the whole export.** Trace files hold full prompts and generated code; prod exports
  are far larger than memory or context. Narrow with `--since` / `--name` / `--thread`, and go through `iter_traces`.
- **`pull` is incremental per `--out`.** A manifest records what was exported; re-runs only fetch newer traces.
  Widening the window into the past needs `--force` or a fresh `--out`.
- **Step results live on spans, not the trace.** The trace output only carries `files_written`, `fix_attempts`,
  `rejected_files`. `failed_tasks` and `unfulfilled_files` are on the `execute-plan` span.
- **LLM spans are children of step spans** and are named after the model, not the step. Attribute them with
  `owning_step` — it walks `parent_span_id` past intermediate LLM spans.
- **`*_failure` spans record the exception but an empty output**, so partial generated content is not recoverable.
  An error usually appears twice in `errors`: on the LLM span and on its step span.
- **`finish_reason="length"` is a silent truncation** — the tail file of a multi-file task is dropped with no
  exception. Check finish reasons before blaming the parser or the prompt.
- **Test traces landed in the local project until 2026-10-04** (e.g. `execute-task-t1`, fake
  `execute-agent-run`/`decide-packages`). Filter older data by `--since` or `--name` before computing a rate.
- **Timestamps print as `2026-10-04 12:48:22`** (space, not `T`) — the exporter serialises datetimes with `str()`.

When reporting findings, cite trace ids and timestamps, and state the sample size — distributions over tens of runs
are directional, not settled.
