# Optional Package Prompt Templates

Optional npm packages are whitelisted in `flow44.ai.agents.optional_packages`.
Each package can own prompt fragments under this folder.
Prompt fragments are loaded by `OptionalPackagePrompt` in `optional_packages.py`, so each filename maps to one prompt scenario.

## Directory Layout

Use one folder per optional package:

```text
templates/optional_packages/<package-name>/
  codegen_context.jinja2      # Implementation context rendered before codegen Rules
  codegen_rules.jinja2        # Implementation rules rendered inside codegen Rules
  merge_rules.jinja2          # Planning guidance rendered only in merge prompts
  fix_errors_rules.jinja2     # Repair guidance rendered only in fix-error prompts
```

Only create the files a package needs. Missing files are ignored.

## Add A Package

1. Add one entry to `OPTIONAL_PACKAGES` in `optional_packages.py`.
2. Set `name` to the npm package key used by package decisions.
3. Set `packages` to the npm packages that should be installed.
4. Set `capability`, `use_when`, and `avoid_when` for the package decision prompt.
5. Add package prompt fragments in `templates/optional_packages/<name>/` only for the prompt scenarios that need package-specific guidance.

Example:

```python
"mui": OptionalPackage(
    name="mui",
    capability="material_ui_components",
    packages=("@mui/material", "@emotion/react", "@emotion/styled"),
    use_when="Use when the user explicitly asks for Material UI or MUI.",
    avoid_when="Do not use when Tailwind and basic React components are sufficient.",
),
```

If the prompt folder name cannot match the npm package name, set `template_dir`.
