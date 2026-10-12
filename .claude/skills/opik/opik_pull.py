from __future__ import annotations

import argparse
import heapq
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import opik
from opik.cli.exports.project import export_project_traces

from flow44.config import OpikSettings

BACKEND_ROOT = Path(__file__).resolve().parents[3] / "backend"
FILE_PATH_RE = re.compile(r'filePath="([^"]+)"')
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

Spans = list[dict[str, Any]]


def settings(env: str | None) -> OpikSettings:
    env_file = BACKEND_ROOT / (f".env.{env}.local" if env else ".env")
    if not env_file.exists():
        raise SystemExit(f"Missing {env_file} — create it with AIB_OPIK_API_KEY / AIB_OPIK_WORKSPACE")
    config = OpikSettings(_env_file=env_file)
    if not config.OPIK_API_KEY and not config.OPIK_URL_OVERRIDE:
        raise SystemExit(f"No Opik credentials. Set AIB_OPIK_API_KEY (and AIB_OPIK_WORKSPACE) in {env_file}")
    if config.OPIK_URL_OVERRIDE:
        # OpikSettings only exports the URL when a key is set, and the exporter reads the host from env
        os.environ["OPIK_URL_OVERRIDE"] = config.OPIK_URL_OVERRIDE
    return config


def utc(value: str) -> str:
    moment = datetime.fromisoformat(value)
    return moment.replace(tzinfo=moment.tzinfo or UTC).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def window_filter(args: argparse.Namespace) -> str | None:
    clauses = [f'start_time >= "{utc(args.since)}"'] if args.since else []
    clauses += [f'start_time < "{utc(args.until)}"'] if args.until else []
    clauses += [f'name = "{args.name}"'] if args.name else []
    clauses += [f'thread_id = "{args.thread}"'] if args.thread else []
    return " AND ".join(clauses) or None


def read_trace(path: Path) -> tuple[dict[str, Any], Spans]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["trace"], sorted(payload["spans"], key=lambda s: s.get("start_time") or "")


def iter_traces(data_dir: Path) -> Iterator[tuple[dict[str, Any], Spans]]:
    paths = sorted(data_dir.rglob("trace_*.json"))
    if not paths:
        raise SystemExit(f"No traces in {data_dir}. Run: opik_pull.py pull --out {data_dir}")
    return map(read_trace, paths)


def runs_of(data: str, trace_name: str) -> Iterator[tuple[dict[str, Any], Spans]]:
    return ((trace, spans) for trace, spans in iter_traces(Path(data)) if trace.get("name") == trace_name)


def spans_by_id(trace_spans: Spans) -> dict[str, dict]:
    return {s["id"]: s for s in trace_spans if s.get("id")}


def owning_step(span: dict[str, Any], by_id: dict[str, dict]) -> str:
    parent_id = span.get("parent_span_id")
    while parent_id and parent_id in by_id:
        parent = by_id[parent_id]
        if parent.get("type") != "llm":
            return str(parent.get("name") or "")
        parent_id = parent.get("parent_span_id")
    return ""


def llm_result(span: dict[str, Any]) -> tuple[str | None, str, dict[str, Any]]:
    output = span.get("output") or {}
    choice = (output.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    return choice.get("finish_reason"), content, output.get("usage") or span.get("usage") or {}


def contract_gaps(trace_spans: Spans) -> list[tuple[str, list[str], bool]]:
    gaps = []
    for span in trace_spans:
        name = str(span.get("name") or "")
        if not name.startswith("execute-task"):
            continue
        expected = set((span.get("input") or {}).get("expected_files") or [])
        written = set((span.get("output") or {}).get("files_written") or [])
        missing = sorted(expected - written)
        if missing or (span.get("error_info") and not written):
            gaps.append((name, missing, bool((span.get("metadata") or {}).get("retry"))))
    return gaps


MAX_FIX_ATTEMPTS = 10
TAINT_TRANSPORT = ("APIConnectionError", "ReadTimeout", "Cannot connect to host", "getaddrinfo", "Timeout on reading")
TAINT_TOOLCHAIN = ("Failed to load PostCSS config", "Cannot find module 'tailwindcss'")
TAXONOMY = (
    ("import:unresolved", re.compile(r'(?:failed to resolve import|Could not resolve) "([^"]+)"')),
    ("import:wrong-export", re.compile(r'"([^"]+)" is not exported by')),
    ("jsx-in-ts", re.compile(r"[\w./-]+\.ts:\d+:\d+: ERROR: Expected")),
    ("syntax", re.compile(r"Transform failed with")),
    ("tailwind-class", re.compile(r"The `([\w-]+)` class does not exist")),
    ("ts-type", re.compile(r"error TS(?!2307)\d+:")),
    ("toolchain", re.compile(r"Failed to load PostCSS config")),
)


def children(span_id: str, trace_spans: Spans) -> Spans:
    return [s for s in trace_spans if s.get("parent_span_id") == span_id]


def errors_text(span: dict[str, Any]) -> str:
    return ANSI_RE.sub("", str((span.get("input") or {}).get("errors") or ""))


def taint(trace_spans: Spans) -> str | None:
    for span in trace_spans:
        blob = str((span.get("error_info") or {}).get("message") or "") + str(
            (span.get("error_info") or {}).get("exception_type") or ""
        )
        if any(marker in blob for marker in TAINT_TRANSPORT):
            return "transport"
    for span in trace_spans:
        if span.get("name") == "fix-errors" and any(m in errors_text(span) for m in TAINT_TOOLCHAIN):
            return "toolchain"
    return None


def gap_cause(span: dict[str, Any], trace_spans: Spans) -> str:
    info = span.get("error_info") or {}
    if info:
        blob = str(info.get("message") or "") + str(info.get("exception_type") or "")
        return "network" if any(m in blob for m in TAINT_TRANSPORT) else "abort"
    for child in children(str(span.get("id") or ""), trace_spans):
        if child.get("type") == "llm" and llm_result(child)[0] == "length":
            return "truncation"
    return "skipped"


def verdict(trace: dict[str, Any]) -> str:
    output = trace.get("output") or {}
    if output.get("verdict"):
        return str(output["verdict"])
    attempts = output.get("fix_attempts")
    if attempts is None:
        return "unknown"
    if attempts >= MAX_FIX_ATTEMPTS:
        return "shipped_red"
    return "green_first_validate" if attempts == 0 else f"green_after_{attempts}_fixes"


def task_gap_cause(span: dict[str, Any], trace_spans: Spans) -> str | None:
    if not str(span.get("name") or "").startswith("execute-task") or (span.get("metadata") or {}).get("retry"):
        return None
    expected = set((span.get("input") or {}).get("expected_files") or [])
    if not expected - set((span.get("output") or {}).get("files_written") or []):
        return None
    return gap_cause(span, trace_spans)


def token_bucket(span: dict[str, Any], by_id: dict[str, dict]) -> str:
    step = owning_step(span, by_id)
    return step if step in ("fix-errors", "build-technical-plan") else "codegen"


def new_stats() -> dict[str, Any]:
    counters: dict[str, Any] = {k: Counter() for k in ("outcomes", "causes", "tokens", "passes")}
    return {**counters, "class_runs": defaultdict(set), "fixed_runs": 0, "rejection_only": 0}


def tally(stats: dict[str, Any], trace: dict[str, Any], trace_spans: Spans) -> None:
    by_id = spans_by_id(trace_spans)
    stats["outcomes"][verdict(trace)] += 1
    fixes = [s for s in trace_spans if s.get("name") == "fix-errors"]
    stats["fixed_runs"] += bool(fixes)

    for span in trace_spans:
        if span.get("type") == "llm":
            usage = llm_result(span)[2] or {}
            bucket = token_bucket(span, by_id)
            stats["tokens"][f"{bucket}:prompt"] += usage.get("prompt_tokens") or 0
            stats["tokens"][f"{bucket}:completion"] += usage.get("completion_tokens") or 0
            continue
        cause = task_gap_cause(span, trace_spans)
        if cause:
            stats["causes"][cause] += 1

    for span in fixes:
        text = errors_text(span)
        if not text.strip():
            for child in children(str(span.get("id") or ""), trace_spans):
                stats["rejection_only"] += (llm_result(child)[2] or {}).get("completion_tokens") or 0
            continue
        for label, pattern in TAXONOMY:
            if pattern.search(text):
                stats["class_runs"][label].add(trace["id"])
                stats["passes"][label] += 1


def print_tokens(tokens: Counter[str], runs_n: int) -> None:
    total_in = sum(v for k, v in tokens.items() if k.endswith(":prompt"))
    total_out = sum(v for k, v in tokens.items() if k.endswith(":completion"))
    total = total_in + total_out
    print(f"\ntokens: {total} total ({total_in} in / {total_out} out)")
    print(f"        {total // max(runs_n, 1)} per run over {runs_n} runs")
    for bucket in sorted({k.split(":")[0] for k in tokens}):
        prompt, completion = tokens[f"{bucket}:prompt"], tokens[f"{bucket}:completion"]
        share = 100 * (prompt + completion) / max(total, 1)
        print(f"        {bucket:22} in={prompt:<9} out={completion:<8} {share:4.1f}%")


def cmd_score(args: argparse.Namespace) -> None:
    stats = new_stats()
    kept = 0
    dropped = []
    for trace, trace_spans in runs_of(args.data, args.trace_name):
        reason = taint(trace_spans)
        if reason and not args.include_tainted:
            dropped.append((trace, reason))
            continue
        kept += 1
        tally(stats, trace, trace_spans)

    print(f"{kept + len(dropped)} {args.trace_name} traces -> {kept} usable, {len(dropped)} environment-tainted")
    for trace, reason in dropped:
        print(f"  excluded {trace['id'][:13]} {(trace.get('start_time') or '')[:19]}  {reason}")

    print(f"\nruns needing at least one fix pass : {stats['fixed_runs']} of {kept}")
    print(f"outcomes                           : {dict(stats['outcomes'].most_common())}")
    print(f"contract-gap cause                 : {dict(stats['causes'].most_common())}")
    print(f"rejection-only fix-pass tokens     : {stats['rejection_only']}")
    print_tokens(stats["tokens"], kept)

    class_runs, passes = stats["class_runs"], stats["passes"]
    print("\nbuild-error class by run-spread")
    for label in sorted(class_runs, key=lambda k: (-len(class_runs[k]), k)):
        print(f"  {label:22} runs={len(class_runs[label]):<3} passes={passes[label]}")


def cmd_projects(args: argparse.Namespace) -> None:
    config = settings(args.env)
    client = opik.Opik(api_key=config.OPIK_API_KEY, workspace=config.OPIK_WORKSPACE, host=config.OPIK_URL_OVERRIDE)
    projects = []
    page = 1
    while batch := client.rest_client.projects.find_projects(page=page, size=100).content:
        projects.extend(batch)
        page += 1
    for project in sorted(projects, key=lambda p: str(p.last_updated_at or ""), reverse=True):
        print(f"{str(project.last_updated_at or '')[:19]:20} {project.name:40} {project.id}")


def cmd_pull(args: argparse.Namespace) -> None:
    config = settings(args.env)
    export_project_traces(
        project_name=args.project or config.OPIK_PROJECT_NAME,
        workspace=config.OPIK_WORKSPACE or "default",
        output_path=args.out,
        filter_string=window_filter(args),
        max_results=args.max,
        force=args.force,
        debug=False,
        format="json",
        api_key=config.OPIK_API_KEY,
        include_attachments=False,
        page_size=args.page_size,
    )
    if not next(Path(args.out).rglob("trace_*.json"), None):
        raise SystemExit(f"No traces matched {window_filter(args)!r}")

    days: Counter[str] = Counter()
    names: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    span_count = 0
    for trace, trace_spans in iter_traces(Path(args.out)):
        days[str(trace.get("start_time") or "")[:10]] += 1
        names[trace.get("name")] += 1
        span_count += len(trace_spans)
        errors.update((s["error_info"] or {}).get("exception_type") for s in trace_spans if s.get("error_info"))
    print(f"\n{args.out}")
    print(f"  traces {days.total()}   spans {span_count}")
    print(f"  days   {dict(sorted(days.items()))}")
    print(f"  names  {names.most_common(12)}")
    if errors:
        print(f"  errors {errors.most_common()}")


def cmd_runs(args: argparse.Namespace) -> None:
    count = 0
    for trace, trace_spans in runs_of(args.data, args.trace_name):
        count += 1
        output = trace.get("output") or {}
        gaps = contract_gaps(trace_spans)
        marks = [f"{key}={output[key]}" for key in ("fix_attempts", "retry_count") if key in output]
        if output.get("files_written"):
            marks.append(f"files={len(output['files_written'])}")
        if gaps:
            marks.append(f"GAPS={sum(len(missing) for _, missing, _ in gaps)}")
        if any(s.get("error_info") for s in trace_spans):
            marks.append("ERRORS")
        print(f"{(trace.get('start_time') or '')[:19]}  {trace['id']}  {'  '.join(marks)}")
        for name, missing, retried in gaps:
            print(f"     {name}: missing={missing} retry={retried}")
    print(f"\n{count} {args.trace_name} traces")


def cmd_trace(args: argparse.Namespace) -> None:
    path = next(Path(args.data).rglob(f"trace_{args.trace_id}*.json"), None)
    if not path:
        raise SystemExit(f"No trace starting with {args.trace_id}")
    trace, trace_spans = read_trace(path)
    by_id = spans_by_id(trace_spans)
    print(f"TRACE {trace['id']}  {trace.get('name')}  {(trace.get('start_time') or '')[:19]}")
    print(f"OUTPUT {json.dumps(trace.get('output'), default=str)[:600]}\n")
    for span in trace_spans:
        head = f"  [{(span.get('start_time') or '')[:19]}] {span.get('name') or '?'}"
        if span.get("type") == "llm":
            finish, content, usage = llm_result(span)
            print(f"{head}  finish={finish} tokens={usage.get('completion_tokens')} step={owning_step(span, by_id)}")
            paths = FILE_PATH_RE.findall(content)
            if paths:
                print(f"        files: {paths}")
        else:
            body = json.dumps(span.get("output"), default=str)[:400] if span.get("output") else ""
            print(f"{head}  {body}")
        if span.get("error_info"):
            info = span.get("error_info") or {}
            message = ANSI_RE.sub("", str(info.get("message") or ""))[:300]
            print(f"        ERROR {info.get('exception_type')}: {message}")


def mean(values: list[int]) -> str:
    return f"{sum(values) / len(values):.2f} (n={len(values)})" if values else "-"


def cmd_packages(args: argparse.Namespace) -> None:
    decides = failed_decides = empty = plans = 0
    off_list: Counter[str] = Counter()
    runs = []
    for trace, trace_spans in iter_traces(Path(args.data)):
        decide_spans = [s for s in trace_spans if s.get("name") == "decide-packages"]
        decides += len(decide_spans)
        failed_decides += sum(1 for s in decide_spans if s.get("error_info"))
        empty += sum(1 for s in decide_spans if not (s.get("output") or {}).get("output"))
        output = trace.get("output") or {}
        if "selected_packages" not in output:
            continue
        if trace.get("name") == "execute-agent-run":
            runs.append(output)
        if trace.get("name") != "plan-agent-run":
            continue
        plans += 1
        proposed = ((decide_spans[0] if decide_spans else {}).get("output") or {}).get("output") or []
        off_list.update(set(proposed) - set(output["selected_packages"]))

    print(f"decide-packages spans {decides}  failed={failed_decides}  empty-selection={empty}")
    print(f"plan runs {plans}  off-list proposals {dict(off_list.most_common())}")
    no_package = sum(1 for r in runs if not r["selected_packages"])
    print(f"\nexecute runs with package data: {len(runs)}  (no package: {no_package})")
    names = sorted({n for r in runs for n in r["selected_packages"]})
    print(f"{'package':18} {'selected':>8} {'failed':>7} {'used':>5}  fix_attempts with / without")
    for name in names:
        with_pkg = [r for r in runs if name in r["selected_packages"]]
        without = [r["fix_attempts"] for r in runs if name not in r["selected_packages"]]
        failed = sum(1 for r in with_pkg if name in r["failed_packages"])
        used = sum(1 for r in with_pkg if name in r["used_packages"])
        print(
            f"{name:18} {len(with_pkg):>8} {failed:>7} {used:>5}  "
            f"{mean([r['fix_attempts'] for r in with_pkg])} / {mean(without)}"
        )


def step_of(span: dict[str, Any], by_id: dict[str, dict]) -> str:
    return owning_step(span, by_id) if span.get("type") == "llm" else str(span.get("name") or "")


def cmd_errors(args: argparse.Namespace) -> None:
    groups: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for trace, trace_spans in iter_traces(Path(args.data)):
        by_id = spans_by_id(trace_spans)
        for span in trace_spans:
            info = span.get("error_info")
            if not info:
                continue
            message = ANSI_RE.sub("", str(info.get("message") or "")).strip().partition("\n")[0][:120]
            key = (str(info.get("exception_type")), step_of(span, by_id), message)
            groups[key].append((str(span.get("start_time") or "")[:19], trace["id"]))

    for (kind, step, message), hits in sorted(groups.items(), key=lambda group: -len(group[1])):
        print(f"{len(hits):>5}  {kind}  [{step}]  {message}")
        for started, trace_id in hits[-args.top :]:
            print(f"         {started}  {trace_id}")


def percentile(values: list[int], pct: int) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, len(ordered) * pct // 100)]


def cmd_context(args: argparse.Namespace) -> None:
    calls = []
    for trace, trace_spans in iter_traces(Path(args.data)):
        by_id = spans_by_id(trace_spans)
        for span in trace_spans:
            tokens = (llm_result(span)[2] or {}).get("prompt_tokens") if span.get("type") == "llm" else None
            if tokens:
                started, model = str(span.get("start_time") or "")[:19], span.get("model") or span["name"]
                calls.append((tokens, started, trace["id"], owning_step(span, by_id), model))

    by_step: dict[str, list[int]] = defaultdict(list)
    for tokens, _, _, step, _ in calls:
        by_step[step or "?"].append(tokens)
    print(f"{len(calls)} LLM calls with prompt_tokens\n")
    print(f"{'step':30} {'n':>5} {'p50':>8} {'p95':>8} {'max':>8}")
    for step, values in sorted(by_step.items(), key=lambda item: -max(item[1])):
        print(f"{step:30} {len(values):>5} {percentile(values, 50):>8} {percentile(values, 95):>8} {max(values):>8}")

    print(f"\nlargest {args.top} prompts")
    for tokens, started, trace_id, step, model in heapq.nlargest(args.top, calls):
        print(f"  {tokens:>8}  {started}  {trace_id}  {step}  {model}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="opik_pull.py", description="Pull and inspect Opik traces")
    sub = parser.add_subparsers(dest="command", required=True)

    env_help = "Read backend/.env.<ENV>.local instead of backend/.env, e.g. prod"
    projects = sub.add_parser("projects", help="List Opik projects in the workspace")
    projects.add_argument("--env", help=env_help)
    projects.set_defaults(func=cmd_projects)

    pull = sub.add_parser("pull", help="Export traces (one file each) via the Opik SDK and print an overview")
    pull.add_argument("--out", required=True)
    pull.add_argument("--env", help=env_help)
    pull.add_argument("--thread", help="Only traces of this FlowBolt project id (Opik thread_id)")
    pull.add_argument("--project")
    pull.add_argument("--since", help="ISO date/datetime lower bound (UTC if no offset), e.g. 2026-08-16")
    pull.add_argument("--until", help="ISO date/datetime exclusive upper bound")
    pull.add_argument("--name", help="Only traces with this name, e.g. execute-agent-run")
    pull.add_argument("--max", type=int, help="Max traces to fetch (default: no cap)")
    pull.add_argument("--page-size", type=int, default=50, help="Traces held in memory per chunk")
    pull.add_argument("--force", action="store_true", help="Re-download traces already in --out")
    pull.set_defaults(func=cmd_pull)

    runs = sub.add_parser("runs", help="Summarise agent runs and contract gaps from a dump")
    runs.add_argument("--data", required=True)
    runs.add_argument("--trace-name", default="execute-agent-run")
    runs.set_defaults(func=cmd_runs)

    trace = sub.add_parser("trace", help="Print one trace's spans, LLM calls and errors")
    trace.add_argument("trace_id")
    trace.add_argument("--data", required=True)
    trace.set_defaults(func=cmd_trace)

    score = sub.add_parser("score", help="Outcome rates, contract-gap causes and error taxonomy over a dump")
    score.add_argument("--data", required=True)
    score.add_argument("--trace-name", default="execute-agent-run")
    score.add_argument("--include-tainted", action="store_true", help="Keep runs whose environment failed")
    score.set_defaults(func=cmd_score)

    packages = sub.add_parser("packages", help="Optional-package selection, install, usage and fix-attempt rates")
    packages.add_argument("--data", required=True)
    packages.set_defaults(func=cmd_packages)

    errors = sub.add_parser("errors", help="Span errors grouped by type, step and message, with example traces")
    errors.add_argument("--data", required=True)
    errors.add_argument("--top", type=int, default=3, help="Example traces per group (most recent)")
    errors.set_defaults(func=cmd_errors)

    context = sub.add_parser("context", help="Prompt tokens per LLM call: per-step p50/p95/max and largest calls")
    context.add_argument("--data", required=True)
    context.add_argument("--top", type=int, default=10)
    context.set_defaults(func=cmd_context)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
