"""CLI entry point for the AI benchmark runner.

Usage:
    cd backend
    uv run python -m benchmarks.runner [OPTIONS]
"""

import asyncio
import logging
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer
import yaml

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from flow44.ai.agents.build import BuildAgent  # noqa: E402
from flow44.config import settings  # noqa: E402

from . import patches  # noqa: E402
from .patches import RunMetrics, get_metrics, register_run  # noqa: E402
from .report import generate_report, write_metadata  # noqa: E402

BENCHMARKS_DIR = Path(__file__).resolve().parent.parent  # benchmarks/
DEFAULT_CONFIG = BENCHMARKS_DIR / "config.yaml"
RESULTS_DIR = BENCHMARKS_DIR / "results"

logger = logging.getLogger("benchmarks")

app = typer.Typer(help="AI Benchmark Runner — test prompts at scale, collect metrics.")


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("/", "-")


async def _run_single(
    prompt_name: str,
    prompt_content: str,
    model: str,
    run_number: int,
    data_source_ids: list[str] | None,
    results_dir: Path,
) -> dict[str, Any]:
    """Execute a single benchmark run. Returns metadata dict."""
    project_id = str(uuid.uuid4())
    slug = _slugify(prompt_name)
    run_dir = results_dir / f"{slug}--{run_number}"

    # Set up workspace: code/ subfolder gets the template + generated files
    code_dir = run_dir / "code"
    shutil.copytree(settings.TEMPLATE_DIR, code_dir, dirs_exist_ok=True)
    label = f"{slug}/{run_number}"
    register_run(project_id, code_dir, label=label, model=model)

    typer.echo(f"  ▶ {prompt_name} (run {run_number}) — {project_id[:8]}...")

    success = True
    error_msg: str | None = None
    start = time.monotonic()

    try:
        patches._current_project_id.set(project_id)
        agent = BuildAgent(project_id=project_id, model=model, data_source_authorization="admin")
        await agent.run(prompt_content, data_source_ids=data_source_ids)
    except Exception as exc:
        success = False
        error_msg = str(exc)
        typer.echo(f"  ✗ {prompt_name} (run {run_number}) — FAILED: {error_msg[:100]}")

    duration = time.monotonic() - start
    metrics: RunMetrics = get_metrics(project_id)

    # Files actually written by the agent (deduplicated, not template files)
    generated_files = list(dict.fromkeys(metrics.files_written))

    # Build the project and generate single HTML preview
    # Build the project and generate single HTML preview
    build_success: bool | None = None
    build_error: str | None = None
    preview_html: str | None = None
    if success:
        typer.echo(f"  🔨 {prompt_name} (run {run_number}) — building...")
        build_success, build_output = await _build_project(code_dir)
        if build_success:
            preview_html = _generate_single_html(code_dir)
            if preview_html:
                preview_path = run_dir / "preview.html"
                preview_path.write_text(preview_html, encoding="utf-8")
                typer.echo(f"  📄 {prompt_name} (run {run_number}) — preview.html generated")
                await _take_screenshot(preview_path, run_dir / "screenshot.png")
                typer.echo(f"  📸 {prompt_name} (run {run_number}) — screenshot captured")
        else:
            build_error = build_output[:500]
            typer.echo(f"  ⚠ {prompt_name} (run {run_number}) — build failed")

        # Clean up heavy dirs — keep only source code + preview
        for cleanup_dir in ("node_modules", "dist", ".env.production.local"):
            p = code_dir / cleanup_dir
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                p.unlink(missing_ok=True)

    # Compute phase durations from event timestamps
    phase_events = [e for e in metrics.events if e.get("type") == "phase"]
    phases = []
    for i, pe in enumerate(phase_events):
        if i + 1 < len(phase_events):
            dur = phase_events[i + 1]["_ts"] - pe["_ts"]
        else:
            dur = 0.0  # last phase ("complete") has no meaningful duration
        phases.append({
            "phase": pe.get("phase"),
            "duration_s": round(dur, 1),
        })

    metadata: dict[str, Any] = {
        "prompt_name": prompt_name,
        "prompt_content": prompt_content,
        "model": model,
        "data_source_ids": data_source_ids or [],
        "run": run_number,
        "project_id": project_id,
        "success": success,
        "error": error_msg,
        "duration_s": round(duration, 1),
        "tokens": {
            "prompt": metrics.total_prompt_tokens,
            "completion": metrics.total_completion_tokens,
            "total": metrics.total_tokens,
        },
        "cost_usd": round(metrics.total_cost, 4),
        "llm_calls": len(metrics.llm_calls),
        "files_generated": sorted(generated_files),
        "build_success": build_success,
        "build_error": build_error,
        "auto_fix": metrics.auto_fix_triggered,
        "preview": "preview.html" if preview_html else None,
        "screenshot": "screenshot.png" if preview_html and (run_dir / "screenshot.png").exists() else None,
        "phases": phases,
    }

    write_metadata(run_dir, metadata)

    status = "✓" if success else "✗"
    tokens_k = f"{metrics.total_tokens / 1000:.1f}k" if metrics.total_tokens else "?"
    cost = f"${metrics.total_cost:.3f}" if metrics.total_cost else "?"
    typer.echo(f"  {status} {prompt_name} (run {run_number}) — {duration:.0f}s, {tokens_k} tokens, {cost}")

    return metadata


async def _build_project(workspace: Path) -> tuple[bool, str]:
    """Run pnpm install + build. Returns (success, output)."""
    # Remove .npmrc (points to Docker-only /pnpm-store)
    npmrc = workspace / ".npmrc"
    npmrc.unlink(missing_ok=True)

    # Write .env.production.local so vite uses root-relative paths
    # and API calls point to the local backend
    env_file = workspace / ".env.production.local"
    env_file.write_text("VITE_BASE=/\nVITE_API_BASE=http://localhost:8000\n", encoding="utf-8")

    proc = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        f"cd {workspace} && pnpm install 2>&1 && pnpm build 2>&1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout_bytes, _ = await proc.communicate()
    output = stdout_bytes.decode(errors="replace") if stdout_bytes else ""

    env_file.unlink(missing_ok=True)
    return proc.returncode == 0, output


def _generate_single_html(workspace: Path) -> str | None:
    """Inline CSS/JS from dist/ into a single HTML file."""
    dist_dir = workspace / "dist"
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        return None

    html = index_path.read_text(encoding="utf-8", errors="replace")

    # Inline CSS
    def _inline_css(match: re.Match[str]) -> str:
        href = match.group(1).lstrip("/")
        css_path = dist_dir / href
        if css_path.is_file():
            return f"<style>{css_path.read_text(encoding='utf-8', errors='replace')}</style>"
        return match.group(0)

    html = re.sub(r'<link\s[^>]*?href=["\']([^"\']+)["\'][^>]*?rel=["\']stylesheet["\'][^>]*/?>',
                  _inline_css, html, flags=re.IGNORECASE)
    html = re.sub(r'<link\s[^>]*?rel=["\']stylesheet["\'][^>]*?href=["\']([^"\']+)["\'][^>]*/?>',
                  _inline_css, html, flags=re.IGNORECASE)

    # Inline JS
    def _inline_js(match: re.Match[str]) -> str:
        src = match.group(1).lstrip("/")
        js_path = dist_dir / src
        if js_path.is_file():
            js = js_path.read_text(encoding="utf-8", errors="replace")
            type_m = re.search(r'type=["\']([^"\']+)["\']', match.group(0))
            type_attr = f' type="{type_m.group(1)}"' if type_m else ""
            return f"<script{type_attr}>{js}</script>"
        return match.group(0)

    html = re.sub(r'<script\s[^>]*?src=["\']([^"\']+)["\'][^>]*?>\s*</script>',
                  _inline_js, html, flags=re.IGNORECASE)

    # Strip error reporter script
    html = re.sub(r'<script\s+id=["\']__ERROR_REPORTER__["\']>.*?</script>\s*',
                  "", html, flags=re.DOTALL | re.IGNORECASE)

    return html


async def _take_screenshot(html_path: Path, output_path: Path) -> None:
    """Open the HTML in headless Chromium and take a screenshot."""
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 720})
            await page.goto(f"file://{html_path.resolve()}")
            await page.evaluate("window.localStorage.setItem('flowbolt.dataSourceApiToken', 'admin')")
            await page.reload()
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=str(output_path))
            await browser.close()
    except Exception as e:
        logger.warning("Screenshot failed: %s", e)


def _init_env() -> None:
    """Initialize Langfuse + litellm callbacks (same as main.py lifespan)."""
    import os  # noqa: PLC0415

    import litellm as _litellm  # noqa: PLC0415

    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

        from langfuse import Langfuse  # noqa: PLC0415

        Langfuse()
        _litellm.success_callback = ["langfuse"]
        _litellm.failure_callback = ["langfuse"]
        typer.echo(f"Langfuse: enabled ({settings.LANGFUSE_HOST})")
    else:
        typer.echo("Langfuse: disabled")


async def _run_all(config: dict[str, Any]) -> None:
    model = config.get("model", settings.AI_MODEL)
    runs_per_prompt = config.get("runs_per_prompt", 1)
    prompts = config.get("prompts", [])

    # Create timestamped results directory
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    results_dir = RESULTS_DIR / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

    total = len(prompts) * runs_per_prompt
    typer.echo(f"Model: {model}")
    typer.echo(f"Prompts: {len(prompts)} × {runs_per_prompt} runs = {total} total")
    typer.echo(f"Results: {results_dir}")
    typer.echo()

    # Apply patches
    patches.apply()

    # Build task list
    tasks = []
    for prompt_cfg in prompts:
        for run_num in range(1, runs_per_prompt + 1):
            tasks.append(
                _run_single(
                    prompt_name=prompt_cfg["name"],
                    prompt_content=prompt_cfg["content"],
                    model=model,
                    run_number=run_num,
                    data_source_ids=prompt_cfg.get("data_source_ids"),
                    results_dir=results_dir,
                )
            )

    # Run all in parallel
    typer.echo(f"Launching {len(tasks)} runs in parallel...\n")
    all_metadata = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    for m in all_metadata:
        if isinstance(m, Exception):
            typer.echo(f"  ✗ Run failed with exception: {m}")

    # Generate report
    report_md = generate_report(results_dir, model)
    (results_dir / "report.md").write_text(report_md)

    typer.echo(f"\n{'═' * 50}")
    typer.echo(report_md)
    typer.echo(f"Full results: {results_dir}")

    patches.revert()


@app.command()
def run(
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", "-c", help="Config YAML path"),
) -> None:
    """Run AI benchmarks from a config file."""
    if not config.exists():
        typer.echo(f"Config not found: {config}", err=True)
        raise typer.Exit(1)

    cfg = yaml.safe_load(config.read_text())
    prompts = cfg.get("prompts", [])
    if not prompts:
        typer.echo("No prompts defined in config.", err=True)
        raise typer.Exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    typer.echo("═══ AI Benchmark Runner ═══\n")
    _init_env()
    asyncio.run(_run_all(cfg))


def main() -> None:
    app()
