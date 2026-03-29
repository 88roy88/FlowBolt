# Workflows: Explicit Orchestration with pydantic-graph

This directory contains **pydantic-graph workflows** that provide explicit, type-safe orchestration for multi-step processes.

## Terminology Clarity

⚠️ **Important distinction:**

- **Agent** = Autonomous system with tools and ReAct capability (e.g., `FollowUpAgent`)
- **Workflow** = Orchestrated multi-step process (e.g., `BuildWorkflow`)
- **LLM call** = Single structured call for typed output (e.g., `_generate_architecture()`)

**We use pydantic-ai's `Agent` API for convenience,** but most aren't true "agents":

```python
# NOT an agent - just a typed LLM call
_architecture_model: Agent[None, ArchitectureDesign] = Agent(output_type=ArchitectureDesign)

# REAL agent - has tools and ReAct loop
followup_agent: Agent[FollowUpDeps, str] = Agent(deps_type=FollowUpDeps)

@followup_agent.tool
async def read_file(...): ...  # ← Tools make it a real agent
```

## Architecture

```
Workflows (orchestration):
  └─ BuildWorkflow (pydantic-graph)
       ├─ Makes LLM calls for structured output
       │   └─ _generate_architecture() → ArchitectureDesign
       │   └─ _generate_ux_design() → UXDesign
       │   └─ _generate_plan_overview() → UserPlanOverview
       └─ Uses streaming for code generation

Agents (autonomous with tools):
  └─ FollowUpAgent (pydantic-ai with tools)
       ├─ Tools: grep, glob, read, edit, write
       └─ ReAct loop: explores and modifies code
```

## Why workflows?

**Before (implicit):**
```python
# Hidden ReAct loop, unclear flow
result = await agent.run(...)  # What's happening inside?
```

**After (explicit):**
```python
# Clear DAG with visible steps
DesignNode → PlanNode → [AWAIT APPROVAL]
                            ↓
        ExecuteNode → ValidateNode ⟲ FixErrorsNode
                            ↓
                       SummarizeNode → End
```

## Benefits

✅ **Explicit flow** - Graph structure visible in code
✅ **Type-safe edges** - Return types define next steps
✅ **Stateful** - `BuildState` flows through all nodes
✅ **Conditional branching** - `ValidateNode → FixErrorsNode | End`
✅ **Observable** - Each node is a clear, traceable step
✅ **Testable** - Individual nodes can be tested in isolation
✅ **Resumable** - State is persisted, workflow can resume after approval

## Example: Build Workflow

**API Entry Point:**
```python
# chat.py
workflow = BuildWorkflow(
    project_id=project_id,
    sandbox=sandbox,
    emit=lambda event: emit_event(project_id, event),
    model=selected_model,
)

# Run design + plan phases (pauses for approval)
await workflow.run_design_and_plan(user_content, data_source_ids)

# After user approval, resume execution
await workflow.run_execution(state)
```

**Graph Definition:**
```python
# build_workflow.py
self._graph = Graph(
    nodes=[
        DesignNode,      # Step 1: Design architecture + UX (parallel LLM calls)
        PlanNode,        # Step 2: Build plan overview → PAUSE
        ExecuteNode,     # Step 3: Generate code (after approval)
        ValidateNode,    # Step 4: Typecheck + build
        FixErrorsNode,   # Step 5: Fix errors (conditional)
        SummarizeNode,   # Step 6: Generate summary
    ]
)
```

**Node Example:**
```python
@dataclass
class DesignNode(BaseNode[BuildState, BuildDeps, None]):
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> PlanNode:
        # Make LLM calls for structured output
        ctx.state.architecture = await _generate_architecture(...)
        ctx.state.ux_design = await _generate_ux_design(...)

        # Return next node
        return PlanNode()
```

**Helper Functions (not "agents"):**
```python
async def _generate_architecture(...) -> ArchitectureDesign:
    """Generate architecture design via LLM."""
    prompt = render_architecture(...)
    result = await _architecture_model.run(user_request, instructions=prompt, model=model)
    return result.output
```

## State Management

**BuildState** flows through the entire graph:

```python
@dataclass
class BuildState(BaseModel):
    # Input
    project_id: str
    user_content: str
    data_source_ids: list[str]

    # Design phase outputs
    architecture: ArchitectureDesign
    ux_design: UXDesign
    user_overview: UserPlanOverview

    # Execute phase outputs
    work_plan: WorkPlan
    completed_files: dict[str, str]
    task_files: dict[str, list[str]]

    # Validation & fix tracking
    validation_errors: str
    fix_attempts: int

    # Current phase
    phase: Literal["idle", "designing", "planning", ...]
```

State is **persisted to DB** at approval boundaries, allowing the workflow to resume across server restarts.

## Conditional Branching

**ValidateNode** demonstrates conditional flow:

```python
@dataclass
class ValidateNode(BaseNode[BuildState, BuildDeps, str]):
    async def run(
        self, ctx: GraphRunContext[BuildState, BuildDeps]
    ) -> SummarizeNode | FixErrorsNode | End[str]:

        if not errors:
            return SummarizeNode()  # Success!

        if ctx.state.fix_attempts >= 3:
            return End("build_failed")  # Give up

        return FixErrorsNode()  # Try to fix
```

**FixErrorsNode** loops back to validation:

```python
@dataclass
class FixErrorsNode(BaseNode[BuildState, BuildDeps, None]):
    async def run(self, ctx: GraphRunContext[BuildState, BuildDeps]) -> ValidateNode:
        # Fix errors
        ctx.state.fix_attempts += 1
        # ... use LLM to fix ...

        # Loop back to validation
        return ValidateNode()
```

## Observability

Each node execution:
- Emits SSE events (`{"type": "phase", "phase": "executing"}`)
- Is traced with Langfuse (`@observe` decorator)
- Updates shared state visible to all subsequent nodes

## Adding New Workflows

1. Create a new file in `workflows/`
2. Define your nodes as `@dataclass` classes inheriting from `BaseNode`
3. Each node's `run()` method returns the next node or `End`
4. Create a `Graph` with your nodes
5. Expose a high-level class with `run()` methods for API integration

See `build_workflow.py` for a complete example.

## Real Agents

**FollowUpAgent** (in `agents/followup/`) is a true agent:
- Has tools (`grep`, `glob`, `read`, `edit`, `write`)
- Uses pydantic-ai's implicit ReAct loop
- Autonomous exploration and modification

```python
followup_agent: Agent[FollowUpDeps, str] = Agent(deps_type=FollowUpDeps)

@followup_agent.tool
async def read_file(ctx: RunContext[FollowUpDeps], path: str) -> str:
    """Read a file"""
    return await read_file_with_lines(ctx.deps.sandbox, path)

# Agent autonomously decides which tools to call
result = await followup_agent.run(content, deps=deps)
```
