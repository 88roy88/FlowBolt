"""Monkey-patches for benchmark mode. No production code is modified."""

import asyncio
import contextvars
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

from flow44.ai.agents._base import BaseAgent
from flow44.ai.agents.build import BuildAgent

logger = logging.getLogger("benchmarks")

# Map project_id to a human-readable run label for logging
_run_labels: dict[str, str] = {}

# Context var to track which project the current coroutine belongs to
_current_project_id: contextvars.ContextVar[str] = contextvars.ContextVar("_current_project_id", default="")


# ---------------------------------------------------------------------------
# Per-run metrics collector
# ---------------------------------------------------------------------------


@dataclass
class LLMCall:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_s: float = 0.0


@dataclass
class RunMetrics:
    model: str = ""
    llm_calls: list[LLMCall] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    auto_fix_triggered: bool = False

    @property
    def total_prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.llm_calls)

    @property
    def total_completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.llm_calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.llm_calls)

    @property
    def total_cost(self) -> float:
        total = sum(c.cost_usd for c in self.llm_calls)
        if total > 0:
            # Some calls have cost (non-streaming), some don't (streaming).
            # Extrapolate: cost_per_token from known calls, apply to all tokens.
            tokens_with_cost = sum(c.total_tokens for c in self.llm_calls if c.cost_usd > 0)
            if tokens_with_cost > 0 and self.total_tokens > tokens_with_cost:
                cost_per_token = total / tokens_with_cost
                return cost_per_token * self.total_tokens
            return total
        # Fallback: compute from total tokens via litellm pricing
        if self.model and self.total_tokens > 0:
            try:
                return _calc_cost(self.model, self.total_prompt_tokens, self.total_completion_tokens)
            except Exception:
                pass
        return 0.0


# Global state for active benchmark runs
_metrics: dict[str, RunMetrics] = {}
_workspace_dirs: dict[str, Path] = {}


def get_metrics(project_id: str) -> RunMetrics:
    return _metrics.get(project_id, RunMetrics())


def register_run(project_id: str, workspace: Path, label: str = "", model: str = "") -> None:
    _metrics[project_id] = RunMetrics(model=model)
    _workspace_dirs[project_id] = workspace
    _run_labels[project_id] = label or project_id[:8]


def cleanup_run(project_id: str) -> None:
    _metrics.pop(project_id, None)
    _workspace_dirs.pop(project_id, None)
    _run_labels.pop(project_id, None)


# ---------------------------------------------------------------------------
# Patch 1 — Auto-approve plan
# ---------------------------------------------------------------------------

_original_emit: Any = None


async def _patched_emit(self: BaseAgent, event: dict[str, Any]) -> None:
    project_id = self.project_id
    _current_project_id.set(project_id)
    label = _run_labels.get(project_id, project_id[:8])

    if project_id in _metrics:
        _metrics[project_id].events.append({**event, "_ts": time.time()})

    # Log meaningful events
    etype = event.get("type", "")
    if etype == "phase":
        phase = event.get("phase")
        logger.info("[%s] phase → %s", label, phase)
        if phase == "fixing" and project_id in _metrics:
            _metrics[project_id].auto_fix_triggered = True
    elif etype == "task_update":
        logger.info("[%s] task %s → %s", label, event.get("taskId"), event.get("status"))
    elif etype == "file":
        logger.info("[%s] wrote %s", label, event.get("path"))
    elif etype == "data_sources_fetched":
        count = len(event.get("data_sources", []))
        logger.info("[%s] fetched %d data source(s)", label, count)
    elif etype == "task_list":
        count = len(event.get("tasks", []))
        logger.info("[%s] plan: %d tasks", label, count)
    elif etype == "plan_overview":
        logger.info("[%s] plan ready — auto-approving", label)
    elif etype == "error":
        logger.error("[%s] error: %s", label, event.get("message"))

    # Auto-approve when plan is presented (schedule on next event loop tick)
    if etype == "plan_overview" and isinstance(self, BuildAgent):
        import asyncio  # noqa: PLC0415

        asyncio.get_event_loop().call_soon(self.signal_plan_response, "accept")


# ---------------------------------------------------------------------------
# Patch 2 — Replace emit_event (skip DB)
# ---------------------------------------------------------------------------


async def _patched_emit_event(project_id: str, event: dict[str, Any], *, notify: bool = True) -> None:
    if project_id in _metrics:
        _metrics[project_id].events.append({**event, "_ts": time.time()})


# ---------------------------------------------------------------------------
# Patch 3 — Redirect write_file
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Patch 4 — Skip typecheck and build
# ---------------------------------------------------------------------------


async def _patched_typecheck(self: BuildAgent) -> str:
    workspace = _workspace_dirs.get(self.project_id)
    if workspace is None:
        return ""
    # Need pnpm install first for tsc to work
    await _ensure_installed(workspace)
    proc = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        f"cd {workspace} && npx tsc --noEmit 2>&1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode(errors="replace").strip() if stdout else ""


async def _patched_build(self: BuildAgent) -> str:
    workspace = _workspace_dirs.get(self.project_id)
    if workspace is None:
        return ""
    await _ensure_installed(workspace)
    proc = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        f"cd {workspace} && pnpm build 2>&1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace").strip() if stdout else ""
    return output if output and ("error" in output.lower() or "failed" in output.lower()) else ""


# Track which workspaces have had pnpm install run
_installed: set[str] = set()


async def _ensure_installed(workspace: Path) -> None:
    key = str(workspace)
    if key in _installed:
        return
    # Remove .npmrc (Docker-only pnpm store path)
    (workspace / ".npmrc").unlink(missing_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "bash",
        "-c",
        f"cd {workspace} && pnpm install 2>&1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await proc.communicate()
    _installed.add(key)


# ---------------------------------------------------------------------------
# Patch 5 — Capture LLM metrics
# ---------------------------------------------------------------------------


def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Compute cost using litellm's pricing table."""
    try:
        from litellm import ModelResponse  # noqa: PLC0415
        from litellm.utils import Usage  # noqa: PLC0415

        resp = ModelResponse()
        resp.usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return litellm.completion_cost(completion_response=resp, model=model)
    except Exception:
        return 0.0


_original_acompletion: Any = None


async def _patched_acompletion(*args: Any, **kwargs: Any) -> Any:
    # Inject stream_options to get usage on streaming responses
    if kwargs.get("stream"):
        stream_opts = kwargs.get("stream_options") or {}
        stream_opts["include_usage"] = True
        kwargs["stream_options"] = stream_opts

    start = time.monotonic()
    response = await _original_acompletion(*args, **kwargs)
    elapsed = time.monotonic() - start

    # Figure out which project this belongs to
    project_id = _current_project_id.get("")

    # For streaming, we need to wrap the iterator to capture final usage
    if kwargs.get("stream"):
        model = kwargs.get("model", "") or (args[0] if args else "")
        return _StreamWrapper(response, project_id, model, elapsed)

    # Non-streaming: extract usage directly
    call = LLMCall(duration_s=elapsed)
    if hasattr(response, "usage") and response.usage:
        call.prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
        call.completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
        call.total_tokens = getattr(response.usage, "total_tokens", 0) or 0
    # Use cost from usage if provider includes it (e.g. OpenRouter)
    usage_cost = getattr(response.usage, "cost", None) if hasattr(response, "usage") and response.usage else None
    if usage_cost is not None and float(usage_cost) > 0:
        call.cost_usd = float(usage_cost)
    else:
        try:
            call.cost_usd = litellm.completion_cost(completion_response=response)
        except Exception:
            call.cost_usd = _calc_cost(
                kwargs.get("model", "") or (args[0] if args else ""),
                call.prompt_tokens,
                call.completion_tokens,
            )

    if project_id in _metrics:
        _metrics[project_id].llm_calls.append(call)

    return response


class _StreamWrapper:
    """Wraps a litellm streaming response to capture usage from the final chunk."""

    def __init__(self, stream: Any, project_id: str, model: str, initial_elapsed: float) -> None:
        self._stream = stream
        self._project_id = project_id
        self._model = model
        self._start = time.monotonic() - initial_elapsed
        self._usage: Any = None

    def __aiter__(self) -> "_StreamWrapper":
        return self

    async def __anext__(self) -> Any:
        try:
            chunk = await self._stream.__anext__()
            # Capture usage from chunks that have it
            if hasattr(chunk, "usage") and chunk.usage:
                self._usage = chunk.usage
            return chunk
        except StopAsyncIteration:
            self._record_metrics()
            raise

    def _record_metrics(self) -> None:
        elapsed = time.monotonic() - self._start
        call = LLMCall(duration_s=elapsed)
        if self._usage:
            call.prompt_tokens = getattr(self._usage, "prompt_tokens", 0) or 0
            call.completion_tokens = getattr(self._usage, "completion_tokens", 0) or 0
            call.total_tokens = getattr(self._usage, "total_tokens", 0) or 0
        # Use cost from usage if provider includes it (e.g. OpenRouter), else compute
        usage_cost = getattr(self._usage, "cost", None) if self._usage else None
        if usage_cost is not None and float(usage_cost) > 0:
            call.cost_usd = float(usage_cost)
        else:
            call.cost_usd = _calc_cost(self._model, call.prompt_tokens, call.completion_tokens)
        if self._project_id in _metrics:
            _metrics[self._project_id].llm_calls.append(call)


# ---------------------------------------------------------------------------
# Apply / revert all patches
# ---------------------------------------------------------------------------

_applied = False


def apply() -> None:
    global _applied, _original_emit, _original_acompletion
    if _applied:
        return
    _applied = True

    # Patch 1 — Auto-approve via emit
    _original_emit = BaseAgent.emit
    BaseAgent.emit = _patched_emit  # type: ignore[assignment]

    # Patch 2 — Skip DB event writes
    import flow44.db.events as events_mod  # noqa: PLC0415

    events_mod.emit_event = _patched_emit_event  # type: ignore[assignment]

    # Patch 4 — Skip typecheck/build
    BuildAgent._typecheck = _patched_typecheck  # type: ignore[assignment]
    BuildAgent._build = _patched_build  # type: ignore[assignment]

    # Patch 5 — Stub out direct DB calls in BuildAgent
    # Must patch in build.py's namespace since it uses `from ... import`
    import flow44.ai.agents.build as build_mod  # noqa: PLC0415
    import flow44.db.project as project_mod  # noqa: PLC0415

    async def _noop_update(*_args: Any, **_kwargs: Any) -> None:
        pass

    build_mod.update_project_summary = _noop_update  # type: ignore[assignment]
    project_mod.update_project_summary = _noop_update  # type: ignore[assignment]
    project_mod.update_project_data_sources = _noop_update  # type: ignore[assignment]

    # Patch 6 — Capture LLM metrics
    _original_acompletion = litellm.acompletion
    litellm.acompletion = _patched_acompletion  # type: ignore[assignment]


def revert() -> None:
    global _applied, _original_emit, _original_acompletion
    if not _applied:
        return
    _applied = False

    BaseAgent.emit = _original_emit  # type: ignore[assignment]
    litellm.acompletion = _original_acompletion  # type: ignore[assignment]
    _metrics.clear()
    _workspace_dirs.clear()
