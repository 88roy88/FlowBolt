# Optional packages

A curated whitelist of npm packages the **build** agent may add to a generated app when the app
actually needs them. Selection happens once, during planning (`PlanAgent._step_decide_packages`);
selected packages are installed at execute start and their rule fragments are injected into the
build prompts. Follow-up / fix-error agents do not use this system.

## Add a package

Drop a folder — it is autodiscovered by `registry.py`, no central list to edit.

```
optional_packages/
  <python_safe_name>/          # e.g. date_fns  (folder name may not contain dashes)
    __init__.py                # declares the package + `PACKAGE = <Class>()`
    templates/
      codegen_rules.md         # rules injected into the codegen + fix prompts
      merge_rules.md           # rules injected into the task-planning (merge) prompt
      fix_errors_rules.md      # rules injected into the validate->fix loop
```

`__init__.py`:

```python
from flow44.ai.agents.optional_packages.base import OptionalPackage


class DateFnsPackage(OptionalPackage):
    name = "date-fns"              # exact npm name (installed via `pnpm add`)
    capability = "date_formatting" # short slug used in the selection prompt
    packages = ("date-fns",)       # npm names to install (usually just `name`)
    use_when = "..."               # one line: when the model SHOULD pick this
    avoid_when = "..."             # one line: when native APIs already suffice


PACKAGE = DateFnsPackage()
```

Only ship the `templates/*.md` a package needs — missing files are skipped.

## Rule-fragment style (example-first)

Each `codegen_rules.md` is ~≤15 lines:
1. one line: "Use `<pkg>` for <capability>:"
2. ONE canonical `tsx` example — correct import + idiomatic usage.
3. 2-3 `Why:` notes — the reasoning that prevents the top failure.
4. at most one positive "Use only <pkg> for this" line (no `Forbidden:` lists).

`merge_rules.md` (≤4 lines): what to plan + any data transform + one scope line.
`fix_errors_rules.md` (≤4 lines): the top 1-2 symptom→cause fixes, phrased positively.

Prefer showing the right thing over forbidding the wrong thing. Start lean; grow a fragment only
when the build model is observed getting it wrong.
