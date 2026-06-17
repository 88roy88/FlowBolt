# Optional Package Modules

Optional npm packages are whitelisted in `flow44.ai.agents.optional_packages`.
Each optional package owns its Python declaration and prompt fragments in one package folder.

Package selection itself is shared agent behavior:

- `agents/templates/package_decision.jinja2` is the shared selection prompt.
- `flow44.ai.agents.optional_package_decision.decide_optional_packages` renders that prompt, validates model output, and merges deterministic high-confidence signals.
- `PlanAgent` runs the decision before the user-facing plan is persisted. The selected packages are stored on `BuildState.optional_package_decision` and later consumed by `ExecuteAgent`.
- `FollowUpAgent` can run the same decision for each follow-up, then merges new selections with packages already present in `package.json`.
- `FixErrorAgent` does not choose new packages; it reuses packages already declared in `package.json`.

Feature flags:

```env
AIB_PLAN_OPTIONAL_PACKAGE_AI_DECISION_ENABLED=true
AIB_FOLLOWUP_OPTIONAL_PACKAGE_AI_DECISION_ENABLED=true
```

When a flag is false, the corresponding agent skips the AI decision prompt and only uses deterministic high-confidence package signals.

## Directory Layout

Use one Python package folder per optional package:

```text
optional_packages/<python-safe-package-name>/
  __init__.py
  templates/
    codegen_context.jinja2
    codegen_rules.jinja2
    codegen_unselected_rules.jinja2
    merge_rules.jinja2
    merge_unselected_rules.jinja2
    fix_errors_rules.jinja2
    fix_errors_unselected_rules.jinja2
```

Only create the template files a package needs. Missing files are ignored.

Use Python-safe folder names, such as `lucide_react`, even when the npm package name contains dashes.

## Add A Package

1. Create `optional_packages/<python_safe_name>/__init__.py`.
2. Define a subclass of `OptionalPackage`.
3. Export a `PACKAGE` instance from the module.
4. Add prompt fragments under `optional_packages/<python_safe_name>/templates/`.
5. Import `PACKAGE` in `optional_packages/registry.py` and include it in `OPTIONAL_PACKAGE_DECLARATIONS`.

Example:

```python
class LucideReactPackage(OptionalPackage):
    name = "lucide-react"
    capability = "iconography"
    packages = ("lucide-react",)
    use_when = "Use when the user asks for icons or visual symbols."
    avoid_when = "Avoid when text alone is clearer."


PACKAGE = LucideReactPackage()
```
