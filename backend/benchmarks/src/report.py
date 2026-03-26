import json
from pathlib import Path
from typing import Any


def write_metadata(run_dir: Path, metadata: dict[str, Any]) -> None:
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))


def generate_report(results_dir: Path, model: str) -> str:
    """Read all metadata.json files and produce a markdown report."""
    runs: list[dict[str, Any]] = []
    for meta_path in sorted(results_dir.glob("*/metadata.json")):
        runs.append(json.loads(meta_path.read_text()))

    if not runs:
        return "# Benchmark Report\n\nNo runs completed.\n"

    total_runs = len(runs)
    successes = sum(1 for r in runs if r.get("success"))
    total_tokens = sum(r.get("tokens", {}).get("total", 0) for r in runs)
    total_cost = sum(r.get("cost_usd", 0) for r in runs)
    avg_duration = sum(r.get("duration_s", 0) for r in runs) / total_runs

    lines = [
        "# Benchmark Report",
        "",
        f"**Model:** `{model}` | **Runs:** {total_runs}",
        "",
        "| Prompt | Run | Agent | Build | Auto-fix | Duration | Tokens | Cost | Files | Preview |",
        "|--------|-----|-------|-------|---------|----------|--------|------|-------|---------|",
    ]

    for r in runs:
        agent_ok = "✅" if r.get("success") else "❌"
        build_ok = "✅" if r.get("build_success") else ("❌" if r.get("build_success") is False else "—")
        auto_fix = "🔧" if r.get("auto_fix") else "—"
        tokens_k = f"{r.get('tokens', {}).get('total', 0) / 1000:.1f}k"
        cost = f"${r.get('cost_usd', 0):.3f}"
        duration = f"{r.get('duration_s', 0):.0f}s"
        files = str(len(r.get("files_generated", [])))
        slug = r["prompt_name"].lower().replace(" ", "-").replace("/", "-")
        preview = f"[open]({slug}--{r['run']}/preview.html)" if r.get("preview") else "—"
        lines.append(
            f"| {r['prompt_name']} | {r['run']} | {agent_ok} | {build_ok} | {auto_fix} | {duration} | {tokens_k} | {cost} | {files} | {preview} |"
        )

    lines += [
        "",
        "## Summary",
        "",
        f"- **Agent success:** {successes}/{total_runs} ({successes * 100 // total_runs}%)",
        f"- **Build success:** {sum(1 for r in runs if r.get('build_success'))}/{total_runs}",
        f"- **Avg duration:** {avg_duration:.0f}s",
        f"- **Total tokens:** {total_tokens / 1000:.1f}k",
        f"- **Total cost:** ${total_cost:.3f}",
    ]

    # Screenshots gallery
    screenshots = [r for r in runs if r.get("screenshot")]
    if screenshots:
        lines += ["", "## Screenshots", ""]
        for r in screenshots:
            slug = r["prompt_name"].lower().replace(" ", "-").replace("/", "-")
            lines.append(f"### {r['prompt_name']} (run {r['run']})")
            lines.append(f"![{r['prompt_name']}]({slug}--{r['run']}/screenshot.png)")
            lines.append("")

    return "\n".join(lines) + "\n"
