# Optional packages

A curated whitelist of npm packages the **build** agent may add to a generated app when the app
actually needs them. Selection happens once, during planning (`PlanAgent._step_decide_packages`);
selected packages are installed at execute start and their rule fragments are injected into the
build prompts.

The follow-up and fix-error agents run long after planning, when `BuildState.selected_packages` is
gone. They recover the list from the sandbox `package.json` via `ChatAgent._installed_optional_package_names()`,
which maps installed npm deps back to registry names with `installed_packages()`. That keeps their
prompts honest about what the app actually has.

**Rulesets key to tasks, not agents.** `FIX_ERRORS` has two consumers — execute's inner validate→fix
loop and `FixErrorAgent` — because both do the same job. Add a new ruleset only for a genuinely
different task, not for a new caller.

## Add a package

Drop a folder — it is autodiscovered by `registry.py`, no central list to edit.

```
optional_packages/
  <python_safe_name>/          # e.g. date_fns  (folder name may not contain dashes)
    __init__.py                # declares `PACKAGE = OptionalPackage(...)`
    templates/
      codegen_rules.md         # rules injected into the codegen + fix prompts
      merge_rules.md           # rules injected into the task-planning (merge) prompt
      fix_errors_rules.md      # rules injected into the validate->fix loop
      followup_rules.md        # rules injected into the follow-up (edit-an-existing-app) prompt
```

`__init__.py`:

```python
from pathlib import Path

from flow44.ai.agents.optional_packages.base import OptionalPackage

PACKAGE = OptionalPackage(
    name="date-fns",                                    # exact npm name (installed via `pnpm add`)
    capability="date_formatting",                       # short slug used in the selection prompt
    packages=("date-fns",),                             # npm names to install (usually just `name`)
    templates_dir=Path(__file__).parent / "templates",  # anchors the rule-fragment lookup
    use_when="...",                                     # one line: when the model SHOULD pick this
    avoid_when="...",                                   # one line: when native APIs already suffice
)
```

Only ship the `templates/*.md` a package needs — missing files are skipped.

## Rule-fragment style (example-first)

Every fragment opens with the same `### <npm-name> — <label>` heading, so concatenated blocks from
several packages stay attributable to the package they came from.

Each `codegen_rules.md` is ~≤15 lines:
1. one line: "Use `<pkg>` for <capability>:"
2. ONE canonical `tsx` example — correct import + idiomatic usage.
3. 2-3 `Why:` notes — the reasoning that prevents the top failure.
4. at most one positive "Use only <pkg> for this" line (no `Forbidden:` lists).

`merge_rules.md` (≤4 lines): what to plan + any data transform + one scope line.
`fix_errors_rules.md` (≤4 lines): the top 1-2 symptom→cause fixes, phrased positively.
`followup_rules.md` (≤4 bullets, **no code fence**): how to extend usage that already exists — reuse
the file's import and its established pattern. Deliberately example-free: the follow-up agent reads
the app's real code with `read_file`, so a sample would tempt it to copy the sample's shape instead.

Prefer showing the right thing over forbidding the wrong thing. Start lean; grow a fragment only
when the build model is observed getting it wrong.
